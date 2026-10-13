"""
SSH client using Paramiko for direct Pi access and log streaming.
"""
import threading
import paramiko
import os
from typing import Callable, Optional
from config import config


class SSHClient:
    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._lock = threading.Lock()
        self._log_thread: Optional[threading.Thread] = None
        self._stop_log = threading.Event()

    def connect(self) -> tuple[bool, str]:
        """Connect to Pi via SSH. Returns (success, error_message)."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            key_path = config.ssh_key_path
            kwargs = dict(
                hostname=config.pi_host,
                username=config.ssh_user,
                timeout=10,
            )
            if key_path and os.path.exists(key_path):
                kwargs["key_filename"] = key_path
            else:
                # Try agent or default keys
                kwargs["allow_agent"] = True
                kwargs["look_for_keys"] = True

            client.connect(**kwargs)
            with self._lock:
                if self._client:
                    try:
                        self._client.close()
                    except Exception:
                        pass
                self._client = client
            return True, ""
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.stop_log_stream()
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

    def is_connected(self) -> bool:
        with self._lock:
            if not self._client:
                return False
            try:
                transport = self._client.get_transport()
                return transport is not None and transport.is_active()
            except Exception:
                return False

    def execute(self, cmd: str) -> tuple[str, str]:
        """Run a command on the Pi. Returns (stdout, stderr)."""
        with self._lock:
            if not self._client:
                return "", "Not connected"
            try:
                _, stdout, stderr = self._client.exec_command(cmd, timeout=15)
                return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")
            except Exception as e:
                return "", str(e)

    def start_log_stream(self, callback: Callable[[str], None], log_file: str = None):
        """Stream the Minecraft log file in a background thread, calling callback per line."""
        self.stop_log_stream()
        if log_file is None:
            log_file = f"{config.server_dir}/logs/latest.log"
        self._stop_log.clear()

        def _stream():
            with self._lock:
                client = self._client
            if not client:
                return
            try:
                channel = client.invoke_shell()
                channel.send(f"tail -f '{log_file}'\n")
                buf = ""
                while not self._stop_log.is_set():
                    if channel.recv_ready():
                        data = channel.recv(4096).decode(errors="replace")
                        buf += data
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            callback(line)
                    else:
                        import time
                        time.sleep(0.05)
                channel.close()
            except Exception:
                pass

        self._log_thread = threading.Thread(target=_stream, daemon=True, name="ssh-log-stream")
        self._log_thread.start()

    def stop_log_stream(self):
        self._stop_log.set()
        if self._log_thread and self._log_thread.is_alive():
            self._log_thread.join(timeout=2)
        self._log_thread = None


ssh = SSHClient()
