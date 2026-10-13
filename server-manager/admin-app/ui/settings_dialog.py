"""
Settings dialog — configure Pi connection details.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QPushButton, QHBoxLayout, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from config import config
from ui import theme


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connection Settings")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(theme.label("Connection Settings", "h1"))
        heading.addWidget(theme.label("How this app reaches the Raspberry Pi and the server on it.", "muted"))
        layout.addLayout(heading)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.pi_host = QLineEdit()
        self.pi_host.setPlaceholderText("e.g. 100.64.0.1 or pi.tail12345.ts.net")
        self.pi_host.setToolTip("Your Pi's Tailscale IP (find it by running 'tailscale ip' on the Pi)")
        form.addRow("Pi Tailscale Host:", self.pi_host)

        self.ssh_user = QLineEdit()
        self.ssh_user.setPlaceholderText("pi")
        self.ssh_user.setToolTip("Raspberry Pi username")
        form.addRow("SSH Username:", self.ssh_user)

        key_row = QHBoxLayout()
        self.ssh_key = QLineEdit()
        self.ssh_key.setPlaceholderText(os.path.expanduser("~/.ssh/id_rsa"))
        self.ssh_key.setToolTip("~/.ssh/id_rsa (default) — only needed if you use SSH features, not required for basic API use")
        key_row.addWidget(self.ssh_key)
        browse_btn = theme.button("Browse…", None, self._browse_key)
        key_row.addWidget(browse_btn)
        form.addRow("SSH Key File:", key_row)

        self.server_dir = QLineEdit()
        self.server_dir.setPlaceholderText("/home/pi/minecraft")
        self.server_dir.setToolTip("Minecraft server directory")
        form.addRow("Server Directory:", self.server_dir)

        self.api_port = QSpinBox()
        self.api_port.setRange(1024, 65535)
        self.api_port.setValue(8080)
        self.api_port.setToolTip("Pi API port — set by API_PORT in pi-backend/minecraft-manager.service")
        form.addRow("API Port:", self.api_port)

        self.rcon_password = QLineEdit()
        self.rcon_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.rcon_password.setPlaceholderText("from server.properties rcon.password")
        self.rcon_password.setToolTip("rcon.password found in server.properties")
        form.addRow("RCON Password:", self.rcon_password)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("API_KEY set in minecraft-manager.service")
        self.api_key.setToolTip("Must match the API_KEY environment variable on the Pi backend")
        form.addRow("API Key:", self.api_key)

        layout.addLayout(form)

        # Hint
        hint = theme.label(
            "Tip: the Tailscale host is the IP or MagicDNS name of your Pi "
            "(run tailscale ip on the Pi to find it).", "caption", wrap=True
        )
        layout.addWidget(hint)

        # Buttons
        btns = QHBoxLayout()
        cancel = theme.button("Cancel", "ghost", self.reject)
        save = theme.button("Save", "primary", self._save)
        save.setDefault(True)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Key File", os.path.expanduser("~/.ssh"), "All Files (*)"
        )
        if path:
            self.ssh_key.setText(path)

    def _load(self):
        self.pi_host.setText(config.pi_host)
        self.ssh_user.setText(config.ssh_user)
        self.ssh_key.setText(config.ssh_key_path)
        self.server_dir.setText(config.server_dir)
        self.api_port.setValue(config.api_port)
        self.rcon_password.setText(config.rcon_password)
        self.api_key.setText(config.api_key)

    def _save(self):
        if not self.pi_host.text().strip():
            QMessageBox.warning(self, "Required", "Pi host/IP is required.")
            return
        config.pi_host = self.pi_host.text().strip()
        config.ssh_user = self.ssh_user.text().strip() or "pi"
        config.ssh_key_path = self.ssh_key.text().strip()
        config.server_dir = self.server_dir.text().strip() or "/home/pi/minecraft"
        config.api_port = self.api_port.value()
        config.rcon_password = self.rcon_password.text()
        config.api_key = self.api_key.text().strip()
        config.sync()
        self.accept()
