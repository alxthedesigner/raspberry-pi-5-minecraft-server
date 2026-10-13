"""
Mod management: toggle mods between mods/ and mods_disabled/.
"""
import os
import shutil
import zipfile
from pathlib import Path
from config import settings


def _ensure_dirs():
    Path(settings.mods_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.mods_disabled_dir).mkdir(parents=True, exist_ok=True)


def list_mods() -> dict:
    _ensure_dirs()
    enabled = []
    disabled = []

    mods_path = Path(settings.mods_dir)
    for f in sorted(mods_path.glob("*.jar")):
        enabled.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
        })

    disabled_path = Path(settings.mods_disabled_dir)
    for f in sorted(disabled_path.glob("*.jar")):
        disabled.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
        })

    return {"enabled": enabled, "disabled": disabled}


def enable_mod(filename: str) -> dict:
    _ensure_dirs()
    src = Path(settings.mods_disabled_dir) / filename
    dst = Path(settings.mods_dir) / filename
    if not src.exists():
        return {"success": False, "message": f"{filename} not found in disabled mods"}
    if dst.exists():
        return {"success": False, "message": f"{filename} is already enabled"}
    shutil.move(str(src), str(dst))
    return {"success": True, "message": f"{filename} enabled (restart required)"}


def disable_mod(filename: str) -> dict:
    _ensure_dirs()
    src = Path(settings.mods_dir) / filename
    dst = Path(settings.mods_disabled_dir) / filename
    if not src.exists():
        return {"success": False, "message": f"{filename} not found in enabled mods"}
    if dst.exists():
        return {"success": False, "message": f"{filename} already in disabled folder"}
    shutil.move(str(src), str(dst))
    return {"success": True, "message": f"{filename} disabled (restart required)"}


def add_mod(filename: str, fileobj) -> dict:
    """Save an uploaded .jar straight into mods/ (enabled)."""
    _ensure_dirs()
    name = Path(filename or "").name
    if not name.lower().endswith(".jar"):
        return {"success": False, "message": f"{name or 'File'} is not a .jar file"}
    dst = Path(settings.mods_dir) / name
    if dst.exists():
        return {"success": False, "message": f"{name} is already enabled"}
    if (Path(settings.mods_disabled_dir) / name).exists():
        return {"success": False, "message": f"{name} is in disabled mods - enable it instead"}

    # Write to a .part file first so the server never sees a half-uploaded jar
    tmp = dst.with_name(name + ".part")
    try:
        with open(tmp, "wb") as out:
            shutil.copyfileobj(fileobj, out)
        if not zipfile.is_zipfile(tmp):
            tmp.unlink()
            return {"success": False, "message": f"{name} is not a valid jar file"}
        tmp.rename(dst)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return {"success": False, "message": f"Failed to save {name}: {e}"}
    return {"success": True, "message": f"{name} added (restart required)"}
