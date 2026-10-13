"""
Server configuration management: server.properties, JVM args, NeoForge TOML configs.
"""
import os
from pathlib import Path
from config import settings


# ─── server.properties ────────────────────────────────────────────────────────

def read_server_properties() -> dict:
    props = {}
    p = Path(settings.server_properties_file)
    if not p.exists():
        return props
    for line in p.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        props[key.strip()] = value.strip()
    return props


def write_server_properties(props: dict) -> dict:
    lines = []
    p = Path(settings.server_properties_file)
    # Preserve comments from original file
    if p.exists():
        for line in p.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                lines.append(line)
            else:
                key = stripped.split("=", 1)[0].strip()
                if key in props:
                    lines.append(f"{key}={props.pop(key)}")
    # Append any new keys not in original
    for key, value in props.items():
        lines.append(f"{key}={value}")
    p.write_text("\n".join(lines) + "\n")
    return {"success": True, "message": "server.properties saved (restart required)"}


# ─── JVM Args ─────────────────────────────────────────────────────────────────

def read_jvm_args() -> str:
    p = Path(settings.jvm_args_file)
    if not p.exists():
        return "-Xmx4G -Xms2G -XX:+UseG1GC -XX:+ParallelRefProcEnabled"
    return p.read_text().strip()


def write_jvm_args(args: str) -> dict:
    Path(settings.jvm_args_file).write_text(args.strip() + "\n")
    return {"success": True, "message": "JVM args saved (restart required)"}


# ─── NeoForge / Mod Configs ───────────────────────────────────────────────────

def list_neoforge_configs() -> list[str]:
    config_dir = Path(settings.neoforge_config_dir)
    if not config_dir.exists():
        return []
    files = []
    for ext in ("*.toml", "*.cfg", "*.json", "*.properties"):
        for f in sorted(config_dir.rglob(ext)):
            rel = str(f.relative_to(config_dir))
            files.append(rel)
    return files


def read_neoforge_config(filename: str) -> dict:
    config_dir = Path(settings.neoforge_config_dir)
    file_path = (config_dir / filename).resolve()
    # Security: prevent path traversal
    if not str(file_path).startswith(str(config_dir.resolve())):
        return {"success": False, "content": "", "message": "Invalid path"}
    if not file_path.exists():
        return {"success": False, "content": "", "message": "File not found"}
    return {"success": True, "content": file_path.read_text(errors="replace"), "message": ""}


def write_neoforge_config(filename: str, content: str) -> dict:
    config_dir = Path(settings.neoforge_config_dir)
    file_path = (config_dir / filename).resolve()
    if not str(file_path).startswith(str(config_dir.resolve())):
        return {"success": False, "message": "Invalid path"}
    file_path.write_text(content)
    return {"success": True, "message": f"{filename} saved"}
