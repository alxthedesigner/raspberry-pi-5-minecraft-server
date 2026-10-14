"""
HTTP API client for the FastAPI backend running on the Pi.
"""
import os
import requests
from typing import Optional
from config import config


class ApiClient:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    def _base(self) -> str:
        return config.api_base_url

    def _headers(self) -> dict:
        return {"X-API-Key": config.api_key} if config.api_key else {}

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        try:
            r = requests.get(f"{self._base()}{path}", params=params, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, json: dict = None) -> Optional[dict]:
        try:
            r = requests.post(f"{self._base()}{path}", json=json or {}, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def _put(self, path: str, json: dict = None) -> Optional[dict]:
        try:
            r = requests.put(f"{self._base()}{path}", json=json or {}, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, path: str) -> Optional[dict]:
        try:
            r = requests.delete(f"{self._base()}{path}", headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    # ── Server Control ────────────────────────────────────────────────────────

    def get_status(self): return self._get("/api/status")
    def get_system_stats(self): return self._get("/api/system")
    def start_server(self): return self._post("/api/start")
    def stop_server(self): return self._post("/api/stop")
    def restart_server(self): return self._post("/api/restart")
    def wake_server(self): return self._post("/api/wake")
    def send_command(self, cmd: str): return self._post("/api/command", {"command": cmd})

    # ── Players ───────────────────────────────────────────────────────────────

    def get_players(self): return self._get("/api/players")
    def get_whitelist(self): return self._get("/api/whitelist")

    def add_whitelist(self, name: str, uuid: str = ""):
        return self._post("/api/whitelist", {"name": name, "uuid": uuid})

    def remove_whitelist(self, name: str):
        return self._delete(f"/api/whitelist/{name}")

    def get_whitelist_requests(self): return self._get("/api/whitelist-requests")
    def approve_request(self, req_id: str): return self._post(f"/api/whitelist-requests/{req_id}/approve")
    def deny_request(self, req_id: str): return self._post(f"/api/whitelist-requests/{req_id}/deny")

    # ── Alerts ────────────────────────────────────────────────────────────────

    def get_alerts(self, since_id: int = 0): return self._get("/api/alerts", {"since_id": since_id})

    # ── Mods ─────────────────────────────────────────────────────────────────

    def get_mods(self): return self._get("/api/mods")
    def enable_mod(self, filename: str): return self._post(f"/api/mods/{filename}/enable")
    def disable_mod(self, filename: str): return self._post(f"/api/mods/{filename}/disable")

    def upload_mod(self, path: str) -> Optional[dict]:
        try:
            with open(path, "rb") as f:
                files = {"file": (os.path.basename(path), f, "application/java-archive")}
                # Mods can be tens of MB, so allow much longer than the default timeout
                r = requests.post(f"{self._base()}/api/mods/upload", files=files,
                                  headers=self._headers(), timeout=300)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def save_packages(self, packages: list, active: str):
        return self._put("/api/packages", {"packages": packages, "active": active})

    def download_packages(self, names: list, dest_path: str) -> Optional[dict]:
        """Save a zip of the named packages' checked mods to dest_path."""
        try:
            with requests.get(f"{self._base()}/api/packages/download", params=[("name", n) for n in names],
                              headers=self._headers(), stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        f.write(chunk)
                return {"success": True, "missing": int(r.headers.get("X-Missing-Mods", 0))}
        except requests.ConnectionError:
            return None
        except Exception as e:
            return {"error": str(e)}

    # ── Config ────────────────────────────────────────────────────────────────

    def get_server_properties(self): return self._get("/api/config/server-properties")
    def save_server_properties(self, props: dict):
        return self._put("/api/config/server-properties", {"properties": props})

    def get_jvm_args(self): return self._get("/api/config/jvm-args")
    def save_jvm_args(self, args: str):
        return self._put("/api/config/jvm-args", {"args": args})

    def list_neoforge_configs(self): return self._get("/api/config/neoforge")

    def get_neoforge_config(self, filename: str):
        return self._get(f"/api/config/neoforge/{filename}")

    def save_neoforge_config(self, filename: str, content: str):
        return self._put(f"/api/config/neoforge/{filename}", {"content": content})


api = ApiClient()
