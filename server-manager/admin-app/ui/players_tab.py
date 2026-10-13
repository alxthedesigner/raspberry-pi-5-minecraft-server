"""
Players tab: online players, whitelist management, and pending requests.
"""
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QInputDialog, QMessageBox, QSplitter, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from api_client import api
from thread_manager import run_in_thread
from ui import theme


class PlayersTab(QWidget):
    badge_update = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        QTimer.singleShot(600, self._start_polling)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        top.setSpacing(14)

        # ── Left: Online Players ───────────────────────────────────────────────
        online_card, ob = theme.card("Online now")
        self.online_list = QListWidget()
        ob.addWidget(self.online_list)
        top.addWidget(online_card, 1)

        # ── Right: Whitelist ──────────────────────────────────────────────────
        add_btn = theme.button("+ Add", "primary", self._add_whitelist)
        remove_btn = theme.button("Remove", "danger", self._remove_whitelist)
        wl_card, wb = theme.card("Whitelist", "Players allowed to join", actions=[add_btn, remove_btn])
        self.whitelist_widget = QListWidget()
        wb.addWidget(self.whitelist_widget)
        top.addWidget(wl_card, 1)

        root.addLayout(top, 3)

        # ── Bottom: Pending Requests ──────────────────────────────────────────
        approve_btn = theme.button("✓  Approve", "primary", self._approve_request)
        deny_btn = theme.button("✕  Deny", "danger", self._deny_request)
        req_card, rb = theme.card("Pending whitelist requests", "Sent from the player portal",
                                  actions=[approve_btn, deny_btn])

        self.requests_table = QTableWidget(0, 4)
        self.requests_table.setHorizontalHeaderLabels(["Minecraft Name", "Discord", "Note", "Submitted"])
        self.requests_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.requests_table.verticalHeader().hide()
        self.requests_table.setShowGrid(False)
        self.requests_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.requests_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        rb.addWidget(self.requests_table)

        root.addWidget(req_card, 2)

    def _start_polling(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(10000)
        self._refresh()

    def _refresh(self):
        run_in_thread(api.get_players, self._apply_players)
        run_in_thread(api.get_whitelist, self._apply_whitelist)
        run_in_thread(api.get_whitelist_requests, self._apply_requests)

    def _apply_players(self, data):
        self.online_list.clear()
        if data:
            for p in data.get("players", []):
                item = QListWidgetItem(f"●  {p}")
                item.setForeground(QColor(theme.OK))
                self.online_list.addItem(item)
        if self.online_list.count() == 0:
            item = QListWidgetItem("  (no players online)")
            item.setForeground(QColor(theme.SUBTLE))
            self.online_list.addItem(item)

    def _apply_whitelist(self, data):
        self.whitelist_widget.clear()
        if data:
            for entry in data.get("whitelist", []):
                self.whitelist_widget.addItem(f"  {entry.get('name', '?')}")

    def _apply_requests(self, data):
        if not data:
            return
        pending = [r for r in data.get("requests", []) if r.get("status") == "pending"]
        self.badge_update.emit(len(pending))
        self.requests_table.setRowCount(0)
        for r in pending:
            row = self.requests_table.rowCount()
            self.requests_table.insertRow(row)
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("submitted_at", 0)))
            self.requests_table.setItem(row, 0, QTableWidgetItem(r.get("minecraft_name", "")))
            self.requests_table.setItem(row, 1, QTableWidgetItem(r.get("discord_name", "")))
            self.requests_table.setItem(row, 2, QTableWidgetItem(r.get("note", "")))
            self.requests_table.setItem(row, 3, QTableWidgetItem(ts))
            self.requests_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, r["id"])

    def _add_whitelist(self):
        name, ok = QInputDialog.getText(self, "Add to Whitelist", "Minecraft username:")
        if ok and name.strip():
            def do():
                return api.add_whitelist(name.strip())
            def on_done(result):
                msg = result.get("message", "Done") if result else "API error"
                QMessageBox.information(self, "Whitelist", msg)
                run_in_thread(api.get_whitelist, self._apply_whitelist)
            run_in_thread(do, on_done)

    def _remove_whitelist(self):
        items = self.whitelist_widget.selectedItems()
        if not items:
            QMessageBox.warning(self, "Remove", "Select a player first.")
            return
        name = items[0].text().strip()
        confirm = QMessageBox.question(
            self, "Confirm", f"Remove '{name}' from whitelist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            def do():
                return api.remove_whitelist(name)
            def on_done(result):
                QMessageBox.information(self, "Whitelist", result.get("message", "Done") if result else "API error")
                run_in_thread(api.get_whitelist, self._apply_whitelist)
            run_in_thread(do, on_done)

    def _selected_request_id(self):
        rows = self.requests_table.selectedItems()
        if not rows:
            return None
        return self.requests_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _approve_request(self):
        req_id = self._selected_request_id()
        if not req_id:
            QMessageBox.warning(self, "Approve", "Select a request first.")
            return
        def do():
            return api.approve_request(req_id)
        def on_done(result):
            QMessageBox.information(self, "Approve", result.get("message", "Done") if result else "API error")
            self._refresh()
        run_in_thread(do, on_done)

    def _deny_request(self):
        req_id = self._selected_request_id()
        if not req_id:
            QMessageBox.warning(self, "Deny", "Select a request first.")
            return
        def do():
            return api.deny_request(req_id)
        def on_done(result):
            QMessageBox.information(self, "Deny", result.get("message", "Done") if result else "API error")
            self._refresh()
        run_in_thread(do, on_done)

    def notify_alert(self, alert: dict):
        player = alert.get("player", "Unknown")
        item = QListWidgetItem(f"  ⚠ {player} (not whitelisted)")
        item.setForeground(QColor(theme.DANGER))
        self.online_list.addItem(item)
