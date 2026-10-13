"""
Pure-Python Minecraft RCON client.
Protocol: https://wiki.vg/RCON
"""
import socket
import struct
import random


SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RconError(Exception):
    pass


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        self._authenticate()

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def command(self, cmd: str) -> str:
        if not self._sock:
            raise RconError("Not connected")
        request_id = random.randint(1, 2**31 - 1)
        self._send(request_id, SERVERDATA_EXECCOMMAND, cmd)
        resp_id, resp_type, payload = self._recv()
        if resp_id != request_id:
            raise RconError(f"Response ID mismatch: {resp_id} != {request_id}")
        return payload

    def _authenticate(self):
        request_id = random.randint(1, 2**31 - 1)
        self._send(request_id, SERVERDATA_AUTH, self.password)
        resp_id, resp_type, _ = self._recv()
        if resp_id == -1:
            raise RconError("Authentication failed: wrong password")
        if resp_id != request_id:
            raise RconError(f"Auth response ID mismatch: {resp_id} != {request_id}")

    def _send(self, request_id: int, packet_type: int, payload: str):
        body = struct.pack("<ii", request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
        packet = struct.pack("<i", len(body)) + body
        self._sock.sendall(packet)

    def _recv(self) -> tuple[int, int, str]:
        # Read packet length
        raw_len = self._recvn(4)
        length = struct.unpack("<i", raw_len)[0]
        body = self._recvn(length)
        request_id = struct.unpack("<i", body[0:4])[0]
        packet_type = struct.unpack("<i", body[4:8])[0]
        payload = body[8:-2].decode("utf-8", errors="replace")
        return request_id, packet_type, payload

    def _recvn(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise RconError("Connection closed by server")
            data += chunk
        return data
