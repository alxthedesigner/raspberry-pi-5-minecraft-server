import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    server_dir: str = os.environ.get("MC_SERVER_DIR", "/home/pi/minecraft")
    rcon_host: str = "127.0.0.1"
    rcon_port: int = int(os.environ.get("RCON_PORT", "25575"))
    rcon_password: str = os.environ.get("RCON_PASSWORD", "changeme")
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8080"))
    api_key: str = os.environ.get("API_KEY", "")
    allowed_origins: list = None
    log_file: str = field(init=False)
    mods_dir: str = field(init=False)
    mods_disabled_dir: str = field(init=False)
    whitelist_file: str = field(init=False)
    whitelist_requests_file: str = field(init=False)
    server_properties_file: str = field(init=False)
    jvm_args_file: str = field(init=False)
    neoforge_config_dir: str = field(init=False)

    def __post_init__(self):
        raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5000")
        self.allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        self.log_file = os.path.join(self.server_dir, "logs", "latest.log")
        self.mods_dir = os.path.join(self.server_dir, "mods")
        self.mods_disabled_dir = os.path.join(self.server_dir, "mods_disabled")
        self.whitelist_file = os.path.join(self.server_dir, "whitelist.json")
        self.whitelist_requests_file = os.path.join(self.server_dir, "whitelist_requests.json")
        self.server_properties_file = os.path.join(self.server_dir, "server.properties")
        self.jvm_args_file = os.path.join(self.server_dir, "jvm_args.txt")
        self.neoforge_config_dir = os.path.join(self.server_dir, "config")


settings = Settings()
