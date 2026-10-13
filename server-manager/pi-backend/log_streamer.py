"""
Real-time log streaming via WebSocket.
Tails logs/latest.log and broadcasts to all connected clients.
"""
import asyncio
import os
from pathlib import Path
from typing import Set
from fastapi import WebSocket
from config import settings

# Lines of existing log sent to a client when it connects
HISTORY_LINES = 200


def _last_lines(path: Path, count: int) -> list:
    """Return the last `count` lines of a file without reading all of it."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = min(size, 256 * 1024)
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    lines = data.splitlines()
    if block < size:
        lines = lines[1:]  # first line is probably cut off
    return lines[-count:]


class LogStreamer:
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        # Send recent history so the console isn't empty until the next log line
        for line in _last_lines(Path(settings.log_file), HISTORY_LINES):
            await ws.send_text(line)
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, line: str):
        if not self._clients:
            return
        dead = set()
        async with self._lock:
            clients = set(self._clients)
        for ws in clients:
            try:
                await ws.send_text(line)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._clients -= dead

    async def tail_loop(self):
        """Background task: tail the log file and broadcast new lines."""
        log_path = Path(settings.log_file)
        from_start = False  # first open skips to the end; history is sent on connect
        while True:
            if not log_path.exists():
                await asyncio.sleep(2)
                from_start = True
                continue
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    if not from_start:
                        f.seek(0, 2)
                    inode = os.fstat(f.fileno()).st_ino
                    partial = ""
                    while True:
                        chunk = f.readline()
                        if chunk:
                            partial += chunk
                            if partial.endswith("\n"):
                                await self.broadcast(partial.rstrip("\n"))
                                partial = ""
                            continue
                        await asyncio.sleep(0.1)
                        # Each server start replaces latest.log with a new file;
                        # follow the new one instead of the old, rotated file.
                        try:
                            st = os.stat(log_path)
                        except FileNotFoundError:
                            break
                        if st.st_ino != inode or st.st_size < f.tell():
                            break
                from_start = True
            except Exception:
                await asyncio.sleep(1)


log_streamer = LogStreamer()
