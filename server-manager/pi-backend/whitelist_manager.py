"""
Whitelist management: read/write whitelist.json and handle player requests.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional
from config import settings
from rcon_client import RconClient


def _read_json(path: str, default) -> any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _write_json(path: str, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2))


# ─── Whitelist ────────────────────────────────────────────────────────────────

def get_whitelist() -> list[dict]:
    return _read_json(settings.whitelist_file, [])


def add_to_whitelist(name: str, uuid_str: Optional[str] = None) -> dict:
    whitelist = get_whitelist()
    if any(e.get("name", "").lower() == name.lower() for e in whitelist):
        return {"success": False, "message": f"{name} is already whitelisted"}
    entry = {"uuid": uuid_str or "", "name": name}
    whitelist.append(entry)
    _write_json(settings.whitelist_file, whitelist)
    # Also run in-game command if server is up
    try:
        with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
            rcon.command(f"whitelist add {name}")
    except Exception:
        pass
    return {"success": True, "message": f"{name} added to whitelist"}


def remove_from_whitelist(name: str) -> dict:
    whitelist = get_whitelist()
    new_whitelist = [e for e in whitelist if e.get("name", "").lower() != name.lower()]
    if len(new_whitelist) == len(whitelist):
        return {"success": False, "message": f"{name} not found in whitelist"}
    _write_json(settings.whitelist_file, new_whitelist)
    try:
        with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
            rcon.command(f"whitelist remove {name}")
    except Exception:
        pass
    return {"success": True, "message": f"{name} removed from whitelist"}


# ─── Whitelist Requests ───────────────────────────────────────────────────────

def get_requests() -> list[dict]:
    return _read_json(settings.whitelist_requests_file, [])


def submit_request(minecraft_name: str, discord_name: str = "", note: str = "") -> dict:
    requests = get_requests()
    # Prevent duplicate pending requests
    if any(
        r.get("minecraft_name", "").lower() == minecraft_name.lower()
        and r.get("status") == "pending"
        for r in requests
    ):
        return {"success": False, "message": "A pending request already exists for this username"}
    request = {
        "id": str(uuid.uuid4()),
        "minecraft_name": minecraft_name,
        "discord_name": discord_name,
        "note": note,
        "status": "pending",
        "submitted_at": time.time(),
    }
    requests.append(request)
    _write_json(settings.whitelist_requests_file, requests)
    return {"success": True, "message": "Request submitted!", "id": request["id"]}


def approve_request(request_id: str) -> dict:
    requests = get_requests()
    for r in requests:
        if r["id"] == request_id:
            if r["status"] != "pending":
                return {"success": False, "message": "Request is not pending"}
            result = add_to_whitelist(r["minecraft_name"])
            if result["success"]:
                r["status"] = "approved"
                _write_json(settings.whitelist_requests_file, requests)
            return result
    return {"success": False, "message": "Request not found"}


def deny_request(request_id: str) -> dict:
    requests = get_requests()
    for r in requests:
        if r["id"] == request_id:
            r["status"] = "denied"
            _write_json(settings.whitelist_requests_file, requests)
            return {"success": True, "message": "Request denied"}
    return {"success": False, "message": "Request not found"}


# ─── Online Players ───────────────────────────────────────────────────────────

def get_online_players() -> list[str]:
    try:
        with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
            response = rcon.command("list")
        # Response: "There are X of a max of Y players online: player1, player2"
        if ":" in response:
            names_part = response.split(":", 1)[1].strip()
            if names_part:
                return [n.strip() for n in names_part.split(",") if n.strip()]
        return []
    except Exception:
        return []
