"""
Monitors the Minecraft server log for non-whitelisted player join attempts.
Stores alerts and pushes them to connected WebSocket clients.
"""
import asyncio
import re
import time
from collections import deque
from pathlib import Path
from typing import Set
from fastapi import WebSocket
from config import settings


# Pattern from Minecraft log: "UUID of player Steve is not whitelisted"
# Also catches: "Player Steve is not whitelisted"
WHITELIST_PATTERN = re.compile(
    r"(?:UUID of player|Player) (\w+) (?:\([0-9a-f-]+\) )?is not whitelisted",
    re.IGNORECASE
)


class AlertMonitor:
    def __init__(self):
        self._alerts: deque = deque(maxlen=100)
        self._alert_ws_clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._seen_count = 0  # for polling "new since last check"

    def get_alerts(self, since_id: int = 0) -> list[dict]:
        return [a for a in self._alerts if a["id"] > since_id]

    async def add_ws_client(self, ws: WebSocket):
        async with self._lock:
            self._alert_ws_clients.add(ws)

    async def remove_ws_client(self, ws: WebSocket):
        async with self._lock:
            self._alert_ws_clients.discard(ws)

    async def _broadcast_alert(self, alert: dict):
        dead = set()
        async with self._lock:
            clients = set(self._alert_ws_clients)
        for ws in clients:
            try:
                import json
                await ws.send_text(json.dumps({"type": "alert", "data": alert}))
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._alert_ws_clients -= dead

    async def monitor_loop(self):
        """Background task: watch log file for non-whitelist events."""
        log_path = Path(settings.log_file)
        alert_id = 0
        while True:
            if not log_path.exists():
                await asyncio.sleep(2)
                continue
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(0, 2)  # Start at end
                    while True:
                        line = f.readline()
                        if line:
                            match = WHITELIST_PATTERN.search(line)
                            if match:
                                alert_id += 1
                                alert = {
                                    "id": alert_id,
                                    "player": match.group(1),
                                    "timestamp": time.time(),
                                    "message": line.strip(),
                                }
                                self._alerts.append(alert)
                                await self._broadcast_alert(alert)
                        else:
                            await asyncio.sleep(0.2)
            except Exception:
                await asyncio.sleep(1)


alert_monitor = AlertMonitor()
