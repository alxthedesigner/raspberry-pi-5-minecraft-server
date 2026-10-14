"""
FastAPI backend for Minecraft Server Manager.
Runs on the Raspberry Pi, exposes REST API + WebSocket endpoints.
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Security, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import APIKeyHeader
import io
import zipfile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import List, Optional

import psutil
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from server_manager import ServerManager
from log_streamer import log_streamer
from alert_monitor import alert_monitor
import whitelist_manager as wm
import mod_manager as mm
import config_manager as cm


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks on startup
    t1 = asyncio.create_task(log_streamer.tail_loop(), name="log_tail")
    t2 = asyncio.create_task(alert_monitor.monitor_loop(), name="alert_monitor")
    yield
    t1.cancel()
    t2.cancel()


app = FastAPI(title="Minecraft Manager API", lifespan=lifespan)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

server = ServerManager()

# ─── Authentication ───────────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(_api_key_header)):
    if not settings.api_key or key != settings.api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


_auth = [Depends(require_api_key)]


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class WhitelistEntry(BaseModel):
    name: str
    uuid: Optional[str] = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]{3,16}$', v):
            raise ValueError("Invalid Minecraft username (3-16 alphanumeric chars or underscores)")
        return v


class WhitelistRequest(BaseModel):
    minecraft_name: str
    discord_name: Optional[str] = ""
    note: Optional[str] = ""

    @field_validator("minecraft_name")
    @classmethod
    def validate_mc_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]{3,16}$', v):
            raise ValueError("Invalid Minecraft username (3-16 alphanumeric chars or underscores)")
        return v

    @field_validator("discord_name")
    @classmethod
    def cap_discord(cls, v):
        return (v or "")[:100]

    @field_validator("note")
    @classmethod
    def cap_note(cls, v):
        return (v or "")[:500]


class CommandRequest(BaseModel):
    command: str

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        v = v.strip()
        if len(v) > 256:
            raise ValueError("Command too long (max 256 characters)")
        return v


class JvmArgsRequest(BaseModel):
    args: str

    @field_validator("args")
    @classmethod
    def validate_jvm_args(cls, v):
        v = v.strip()
        if len(v) > 512:
            raise ValueError("JVM args too long (max 512 characters)")
        if re.search(r'[;&|`$<>]', v):
            raise ValueError("Invalid characters in JVM args")
        return v


class ServerPropertiesRequest(BaseModel):
    properties: dict[str, str]

    @field_validator("properties")
    @classmethod
    def validate_props(cls, v):
        for k, val in v.items():
            if len(k) > 64 or len(val) > 256:
                raise ValueError("Property key or value too long")
        return v


class NeoForgeConfigRequest(BaseModel):
    content: str


# ─── Server Control ───────────────────────────────────────────────────────────

@app.get("/api/status", dependencies=_auth)
def get_status():
    return server.get_status()


@app.post("/api/start", dependencies=_auth)
@limiter.limit("10/minute")
def start_server(request: Request):
    return server.start()


@app.post("/api/stop", dependencies=_auth)
@limiter.limit("10/minute")
def stop_server(request: Request):
    return server.stop()


@app.post("/api/restart", dependencies=_auth)
@limiter.limit("10/minute")
async def restart_server(request: Request):
    return await server.restart()


@app.post("/api/wake", dependencies=_auth)
@limiter.limit("10/minute")
def wake_server(request: Request):
    return server.wake()


@app.post("/api/command", dependencies=_auth)
@limiter.limit("10/minute")
def send_command(request: Request, req: CommandRequest):
    return server.send_command(req.command)


# ─── System Stats ─────────────────────────────────────────────────────────────

@app.get("/api/system", dependencies=_auth)
def get_system_stats():
    cpu = psutil.cpu_percent(interval=0.2)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temps = {}
    try:
        for name, entries in psutil.sensors_temperatures().items():
            if entries:
                temps[name] = round(entries[0].current, 1)
    except (AttributeError, OSError):
        pass
    return {
        "cpu_percent": cpu,
        "ram_used_mb": round(vm.used / 1024 / 1024),
        "ram_total_mb": round(vm.total / 1024 / 1024),
        "ram_percent": vm.percent,
        "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
        "disk_percent": disk.percent,
        "temperatures": temps,
    }


# ─── Players & Whitelist ──────────────────────────────────────────────────────

@app.get("/api/players", dependencies=_auth)
def get_players():
    return {"players": wm.get_online_players()}


@app.get("/api/whitelist", dependencies=_auth)
def get_whitelist():
    return {"whitelist": wm.get_whitelist()}


@app.post("/api/whitelist", dependencies=_auth)
def add_whitelist(entry: WhitelistEntry):
    return wm.add_to_whitelist(entry.name, entry.uuid)


@app.delete("/api/whitelist/{name}", dependencies=_auth)
def remove_whitelist(name: str):
    return wm.remove_from_whitelist(name)


@app.get("/api/whitelist-requests", dependencies=_auth)
def get_requests():
    return {"requests": wm.get_requests()}


@app.post("/api/whitelist-requests")
@limiter.limit("5/minute")
def submit_request(request: Request, req: WhitelistRequest):
    return wm.submit_request(req.minecraft_name, req.discord_name, req.note)


@app.post("/api/whitelist-requests/{request_id}/approve", dependencies=_auth)
def approve_request(request_id: str):
    return wm.approve_request(request_id)


@app.post("/api/whitelist-requests/{request_id}/deny", dependencies=_auth)
def deny_request(request_id: str):
    return wm.deny_request(request_id)


# ─── Alerts ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts", dependencies=_auth)
def get_alerts(since_id: int = 0):
    return {"alerts": alert_monitor.get_alerts(since_id)}


# ─── Mods ─────────────────────────────────────────────────────────────────────

@app.get("/api/mods", dependencies=_auth)
def get_mods():
    return mm.list_mods()


@app.get("/api/mods/{filename}/download", dependencies=_auth)
def download_mod(filename: str):
    from pathlib import Path
    path = Path(settings.mods_dir) / filename
    if not path.exists() or not path.name.endswith(".jar"):
        raise HTTPException(status_code=404, detail="Mod not found")
    return FileResponse(path, media_type="application/java-archive", filename=filename)


@app.get("/api/mods/download-all", dependencies=_auth)
def download_all_mods():
    from pathlib import Path
    # Stored (not re-compressed) zip spooled to disk: jars are already compressed,
    # and compressing ~80 MB in memory is slow enough on a Pi to time out.
    buf, _ = mm.zip_files(sorted(p.name for p in Path(settings.mods_dir).glob("*.jar")))
    return StreamingResponse(
        mm.iter_file(buf),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=mods.zip"},
    )


@app.post("/api/mods/upload", dependencies=_auth)
def upload_mod(file: UploadFile = File(...)):
    return mm.add_mod(file.filename, file.file)


@app.post("/api/mods/{filename}/enable", dependencies=_auth)
def enable_mod(filename: str):
    return mm.enable_mod(filename)


@app.post("/api/mods/{filename}/disable", dependencies=_auth)
def disable_mod(filename: str):
    return mm.disable_mod(filename)


# ─── Mod packages ─────────────────────────────────────────────────────────────

class PackagesPayload(BaseModel):
    packages: List[dict]
    active: str = ""


@app.get("/api/packages", dependencies=_auth)
def get_packages():
    return mm.get_packages()


@app.put("/api/packages", dependencies=_auth)
def put_packages(body: PackagesPayload):
    return mm.save_packages(body.packages, body.active)


@app.get("/api/packages/download", dependencies=_auth)
def download_packages(name: List[str] = Query(...)):
    buf, missing = mm.zip_packages(name)
    if buf is None:
        raise HTTPException(status_code=404, detail=missing)
    names = list(dict.fromkeys(name))
    filename = f"{mm.safe_name(names[0])}.zip" if len(names) == 1 else "mod-packages.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"', "X-Missing-Mods": str(len(missing))}
    return StreamingResponse(mm.iter_file(buf), media_type="application/zip", headers=headers)


# ─── Configuration ────────────────────────────────────────────────────────────

@app.get("/api/config/server-properties", dependencies=_auth)
def get_server_props():
    return {"properties": cm.read_server_properties()}


@app.put("/api/config/server-properties", dependencies=_auth)
def put_server_props(req: ServerPropertiesRequest):
    return cm.write_server_properties(req.properties)


@app.get("/api/config/jvm-args", dependencies=_auth)
def get_jvm_args():
    return {"args": cm.read_jvm_args()}


@app.put("/api/config/jvm-args", dependencies=_auth)
def put_jvm_args(req: JvmArgsRequest):
    return cm.write_jvm_args(req.args)


@app.get("/api/config/neoforge", dependencies=_auth)
def list_neoforge():
    return {"files": cm.list_neoforge_configs()}


@app.get("/api/config/neoforge/{filename:path}", dependencies=_auth)
def get_neoforge_config(filename: str):
    return cm.read_neoforge_config(filename)


@app.put("/api/config/neoforge/{filename:path}", dependencies=_auth)
def put_neoforge_config(filename: str, req: NeoForgeConfigRequest):
    return cm.write_neoforge_config(filename, req.content)


# ─── WebSocket: Log Stream ────────────────────────────────────────────────────

@app.websocket("/ws/log")
async def ws_log(ws: WebSocket):
    key = ws.headers.get("X-API-Key") or ws.query_params.get("api_key")
    if not settings.api_key or key != settings.api_key:
        await ws.close(code=4003)
        return
    await log_streamer.connect(ws)
    try:
        while True:
            # Keep connection alive; client can send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await log_streamer.disconnect(ws)


# ─── WebSocket: Alerts ────────────────────────────────────────────────────────

@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    key = ws.headers.get("X-API-Key") or ws.query_params.get("api_key")
    if not settings.api_key or key != settings.api_key:
        await ws.close(code=4003)
        return
    await ws.accept()
    await alert_monitor.add_ws_client(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await alert_monitor.remove_ws_client(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=False)
