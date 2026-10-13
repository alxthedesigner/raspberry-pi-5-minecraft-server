"""
Persistent configuration for the admin app using QSettings.
"""
import json
from PyQt6.QtCore import QSettings


APP_NAME = "MinecraftManager"
ORG_NAME = "MinecraftAdmin"


class AppConfig:
    def __init__(self):
        self._s = QSettings(ORG_NAME, APP_NAME)

    # ── Connection ────────────────────────────────────────────────────────────

    @property
    def pi_host(self) -> str:
        return self._s.value("connection/pi_host", "")

    @pi_host.setter
    def pi_host(self, v: str):
        self._s.setValue("connection/pi_host", v)

    @property
    def ssh_user(self) -> str:
        return self._s.value("connection/ssh_user", "pi")

    @ssh_user.setter
    def ssh_user(self, v: str):
        self._s.setValue("connection/ssh_user", v)

    @property
    def ssh_key_path(self) -> str:
        import os
        default = os.path.expanduser("~/.ssh/id_rsa")
        return self._s.value("connection/ssh_key_path", default)

    @ssh_key_path.setter
    def ssh_key_path(self, v: str):
        self._s.setValue("connection/ssh_key_path", v)

    @property
    def api_port(self) -> int:
        return int(self._s.value("connection/api_port", 8080))

    @api_port.setter
    def api_port(self, v: int):
        self._s.setValue("connection/api_port", v)

    @property
    def rcon_password(self) -> str:
        return self._s.value("connection/rcon_password", "")

    @rcon_password.setter
    def rcon_password(self, v: str):
        self._s.setValue("connection/rcon_password", v)

    @property
    def api_key(self) -> str:
        return self._s.value("connection/api_key", "")

    @api_key.setter
    def api_key(self, v: str):
        self._s.setValue("connection/api_key", v)

    @property
    def server_dir(self) -> str:
        return self._s.value("connection/server_dir", "/home/pi/minecraft")

    @server_dir.setter
    def server_dir(self, v: str):
        self._s.setValue("connection/server_dir", v)

    # ── Mod packages ──────────────────────────────────────────────────────────

    @property
    def mod_packages(self) -> list:
        """[{"name": str, "mods": {filename: checked}}], stored as JSON."""
        try:
            return json.loads(self._s.value("mods/packages", "[]"))
        except (TypeError, ValueError):
            return []

    @mod_packages.setter
    def mod_packages(self, v: list):
        self._s.setValue("mods/packages", json.dumps(v))

    @property
    def active_package(self) -> str:
        return self._s.value("mods/active_package", "")

    @active_package.setter
    def active_package(self, v: str):
        self._s.setValue("mods/active_package", v)

    # ── Derived ───────────────────────────────────────────────────────────────

    @property
    def api_base_url(self) -> str:
        return f"http://{self.pi_host}:{self.api_port}"

    @property
    def ws_base_url(self) -> str:
        return f"ws://{self.pi_host}:{self.api_port}"

    @property
    def is_configured(self) -> bool:
        return bool(self.pi_host)

    def sync(self):
        self._s.sync()


config = AppConfig()
