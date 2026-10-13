"""
Console tab: real-time server log viewer + command input.
Streams log via WebSocket (primary) or SSH tail (fallback).
"""
import threading
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from api_client import api
from ui import theme


# ── Log colour rules ──────────────────────────────────────────────────────────
LOG_COLORS = [
    ("ERROR", "#ef4444"),
    ("FATAL", "#ef4444"),
    ("WARN",  "#f59e0b"),
    ("INFO",  "#d1d5db"),
    ("[Server]", "#60a5fa"),
    ("joined the game", "#4ade80"),
    ("left the game",  "#f87171"),
]


def _color_for_line(line: str) -> str:
    for keyword, color in LOG_COLORS:
        if keyword in line:
            return color
    return "#9ca3af"


# ── WebSocket log receiver thread ─────────────────────────────────────────────
class WsLogThread(QThread):
    line_received = pyqtSignal(str)
    connection_status = pyqtSignal(str)

    def __init__(self, ws_url: str):
        super().__init__()
        self._url = ws_url
        self._running = True

    def run(self):
        import websocket  # websocket-client

        def on_message(ws, message):
            self.line_received.emit(message)

        def on_open(ws):
            self.connection_status.emit("connected")
            # Keep alive ping every 20s
            def ping():
                while self._running:
                    try:
                        ws.send("ping")
                    except Exception:
                        break
                    time.sleep(20)
            threading.Thread(target=ping, daemon=True).start()

        def on_close(ws, *_):
            self.connection_status.emit("disconnected")

        def on_error(ws, error):
            self.connection_status.emit(f"error: {error}")

        while self._running:
            try:
                ws = websocket.WebSocketApp(
                    self._url,
                    header=[f"{k}: {v}" for k, v in api._headers().items()],
                    on_message=on_message,
                    on_open=on_open,
                    on_close=on_close,
                    on_error=on_error,
                )
                ws.run_forever(ping_interval=0)
            except Exception:
                pass
            if self._running:
                time.sleep(3)  # Reconnect after 3s

    def stop(self):
        self._running = False
        self.quit()


# ── Console Tab ───────────────────────────────────────────────────────────────
class ConsoleTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws_thread = None  # type: WsLogThread
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.conn_label = theme.label("● Disconnected", "pill")
        theme.set_prop(self.conn_label, "state", "danger")
        toolbar.addWidget(self.conn_label)
        toolbar.addStretch()

        self.hide_rcon = QCheckBox("Hide RCON noise")
        self.hide_rcon.setChecked(True)
        self.hide_rcon.setToolTip("Hide the RCON connect/disconnect lines the app's status checks write to the log")
        toolbar.addWidget(self.hide_rcon)
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        toolbar.addWidget(self.auto_scroll)
        toolbar.addWidget(theme.button("Clear", "ghost", self._clear))
        toolbar.addWidget(theme.button("Reconnect", None, self.start_streaming))
        root.addLayout(toolbar)

        # ── Log viewer ────────────────────────────────────────────────────────
        self.log_view = QTextEdit()
        self.log_view.setObjectName("Log")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo,Consolas,monospace", 11))
        self.log_view.document().setMaximumBlockCount(5000)
        root.addWidget(self.log_view, 1)

        # ── Command input ─────────────────────────────────────────────────────
        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(8)
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("›  Type a server command and press Enter  (e.g. list, say hello, time set day)")
        self.cmd_input.setFont(QFont("Menlo,Consolas,monospace", 12))
        self.cmd_input.setMinimumHeight(36)
        self.cmd_input.returnPressed.connect(self._send_command)
        send_btn = theme.button("Send", "primary", self._send_command)
        send_btn.setMinimumHeight(36)
        send_btn.setMinimumWidth(80)
        cmd_row.addWidget(self.cmd_input)
        cmd_row.addWidget(send_btn)
        root.addLayout(cmd_row)

    def start_streaming(self):
        from config import config
        if not config.is_configured:
            self._append_line("[ERROR] Not configured — open Settings first.", "#ef4444")
            return
        # Stop existing thread
        if self._ws_thread:
            self._ws_thread.stop()
            self._ws_thread.wait(2000)

        url = f"{config.ws_base_url}/ws/log"
        self._ws_thread = WsLogThread(url)
        self._ws_thread.line_received.connect(self._on_line)
        self._ws_thread.connection_status.connect(self._on_status)
        self._ws_thread.start()

    def stop_streaming(self):
        if self._ws_thread:
            self._ws_thread.stop()
            self._ws_thread = None

    def _on_line(self, line: str):
        if self.hide_rcon.isChecked() and "net.minecraft.server.rcon.thread." in line:
            return
        self._append_line(line, _color_for_line(line))

    def _on_status(self, status: str):
        if status == "connected":
            # The Pi sends recent history on every (re)connect, so start fresh
            self.log_view.clear()
            self.conn_label.setText("● Live")
            theme.set_prop(self.conn_label, "state", "ok")
        else:
            self.conn_label.setText(f"● {status.capitalize()}")
            theme.set_prop(self.conn_label, "state", "danger")

    def _append_line(self, line: str, color: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(line + "\n")
        if self.auto_scroll.isChecked():
            self.log_view.setTextCursor(cursor)
            self.log_view.ensureCursorVisible()

    def _clear(self):
        self.log_view.clear()

    def _send_command(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.cmd_input.clear()
        # Echo in console
        self._append_line(f"> {cmd}", "#60a5fa")
        result = api.send_command(cmd)
        if result and result.get("response"):
            self._append_line(f"  {result['response']}", "#a3e635")

    def closeEvent(self, event):
        self.stop_streaming()
        super().closeEvent(event)
