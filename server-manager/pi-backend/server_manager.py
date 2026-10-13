import asyncio
import subprocess
import shutil
import os
import time
from pathlib import Path
from typing import Optional
from config import settings


class ServerManager:
    def __init__(self):
        self.tmux_session = "minecraft"

    def _run(self, cmd: list[str]) -> tuple[str, str, int]:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode

    def is_tmux_running(self) -> bool:
        _, _, code = self._run(["tmux", "has-session", "-t", self.tmux_session])
        return code == 0

    def is_server_online(self) -> bool:
        """Check via RCON if the Minecraft server is accepting connections."""
        if not self.is_tmux_running():
            return False
        try:
            from rcon_client import RconClient
            with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
                rcon.command("list")
            return True
        except Exception:
            return False

    def get_status(self) -> dict:
        tmux_up = self.is_tmux_running()
        online = False
        if tmux_up:
            online = self.is_server_online()
        return {
            "tmux_running": tmux_up,
            "minecraft_online": online,
            "server_dir": settings.server_dir,
            "version": "26.3",
            "loader": "NeoForge 26.3.0.60-beta",
        }

    def start(self) -> dict:
        if self.is_tmux_running():
            return {"success": False, "message": "Server is already running"}

        if not (Path(settings.server_dir) / "run.sh").exists():
            return {"success": False, "message": "Could not find run.sh in server directory"}

        # Same as: tmux new-session -d -s minecraft -c <server_dir> './run.sh nogui'
        # run.sh is the NeoForge launcher, so mods and user_jvm_args.txt are used
        _, err, code = self._run([
            "tmux", "new-session", "-d", "-s", self.tmux_session,
            "-c", settings.server_dir, "./run.sh nogui",
        ])
        if code != 0:
            return {"success": False, "message": f"Failed to start tmux session: {err}"}
        return {"success": True, "message": "Server starting..."}

    def stop(self) -> dict:
        if not self.is_tmux_running():
            return {"success": False, "message": "Server is not running"}
        try:
            from rcon_client import RconClient
            with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
                rcon.command("stop")
            return {"success": True, "message": "Stop command sent via RCON"}
        except Exception:
            # Fallback: send via tmux
            self._run(["tmux", "send-keys", "-t", self.tmux_session, "stop", "Enter"])
            return {"success": True, "message": "Stop command sent via tmux"}

    async def restart(self) -> dict:
        stop_result = self.stop()
        if not stop_result["success"]:
            return stop_result
        # Wait up to 60s for tmux session to end
        for _ in range(60):
            await asyncio.sleep(1)
            if not self.is_tmux_running():
                break
        else:
            # Force kill
            self._run(["tmux", "kill-session", "-t", self.tmux_session])
        return self.start()

    def wake(self) -> dict:
        """Start server if not running (called from player portal)."""
        if self.is_server_online():
            return {"success": False, "message": "Server is already online"}
        if self.is_tmux_running():
            return {"success": False, "message": "Server process is starting, please wait"}
        return self.start()

    def send_command(self, command: str) -> dict:
        if not self.is_tmux_running():
            return {"success": False, "message": "Server is not running"}
        # Try RCON first for response
        try:
            from rcon_client import RconClient
            with RconClient(settings.rcon_host, settings.rcon_port, settings.rcon_password) as rcon:
                response = rcon.command(command)
            return {"success": True, "response": response}
        except Exception:
            # Fallback: tmux send-keys (no response)
            self._run(["tmux", "send-keys", "-t", self.tmux_session, command, "Enter"])
            return {"success": True, "response": "(sent via tmux, no response available)"}
