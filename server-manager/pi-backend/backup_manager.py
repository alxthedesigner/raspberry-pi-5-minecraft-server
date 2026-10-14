"""
World backup: pause autosaving, flush the world to disk, zip it, resume saving.
"""
import os
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from config import settings

_lock = threading.Lock()
TMP_DIR_NAME = ".world-backups-tmp"


def _rcon(command: str) -> str:
    from rcon_client import RconClient
    # save-all flush can take a while on a big world
    with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password, timeout=120) as rcon:
        return rcon.command(command)


def _resume_saving():
    try:
        _rcon("save-on")
    except Exception:
        # Never leave autosave off: fall back to typing it into the server console
        subprocess.run(["tmux", "send-keys", "-t", "minecraft", "save-on", "Enter"], capture_output=True)


def _world_dir() -> Path:
    level = "world"
    try:
        for line in Path(settings.server_properties_file).read_text().splitlines():
            if line.startswith("level-name="):
                level = line.split("=", 1)[1].strip() or "world"
    except OSError:
        pass
    return Path(settings.server_dir) / level


def _tmp_dir() -> Path:
    d = Path(settings.server_dir).parent / TMP_DIR_NAME
    d.mkdir(exist_ok=True)
    # Remove leftovers from interrupted downloads
    for old in d.glob("*.zip"):
        if time.time() - old.stat().st_mtime > 3600:
            old.unlink(missing_ok=True)
    return d


def create_backup(server_running: bool):
    """Zip the world into a temporary file. Returns (path, file_count).

    Raises RuntimeError if a backup is already running or the world is missing.
    The caller must delete the file when done with it.
    """
    if not _lock.acquire(blocking=False):
        raise RuntimeError("A backup is already running")
    try:
        world = _world_dir()
        if not world.is_dir():
            raise RuntimeError(f"World folder not found: {world.name}")
        fd, path = tempfile.mkstemp(prefix="world-", suffix=".zip", dir=_tmp_dir())
        os.close(fd)
        paused = False
        try:
            if server_running:
                _rcon("save-off")
                paused = True
                _rcon("save-all flush")
            count = 0
            # Region files are already compressed, so store them as-is
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                for f in sorted(world.rglob("*")):
                    if f.is_file() and f.name != "session.lock":
                        zf.write(f, str(Path(world.name) / f.relative_to(world)))
                        count += 1
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
        finally:
            if paused:
                _resume_saving()
        return path, count
    finally:
        _lock.release()


def stream_and_delete(path: str, chunk_size: int = 1024 * 1024):
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        Path(path).unlink(missing_ok=True)
