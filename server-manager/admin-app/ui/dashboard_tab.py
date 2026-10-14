"""
Dashboard tab: server status, start/stop/restart/wake controls, alert banner.
"""
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QProgressBar, QSizePolicy,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from api_client import api
from thread_manager import run_in_thread
from ui import theme


class StatusIndicator(QLabel):
    """Round status dot."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(14, 14)
        self.set_unknown()

    def _set(self, color: str):
        self.setStyleSheet(f"background: {color}; border-radius: 7px;")

    def set_online(self):
        self._set(theme.OK)

    def set_starting(self):
        self._set(theme.WARN)

    def set_offline(self):
        self._set(theme.DANGER)

    def set_unknown(self):
        self._set(theme.SUBTLE)


class StatTile(QWidget):
    """Card with a label, big value, detail line and usage bar."""
    def __init__(self, title: str):
        super().__init__()
        self.frame, body = theme.card()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.frame)
        body.setSpacing(6)
        body.addWidget(theme.label(title.upper(), "caption"))
        self.value = theme.label("—", "stat")
        body.addWidget(self.value)
        self.detail = theme.label(" ", "muted")
        body.addWidget(self.detail)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        body.addWidget(self.bar)

    def set(self, value: str, detail: str, pct: float = None, warn: float = 60, danger: float = 85):
        self.value.setText(value)
        self.detail.setText(detail)
        if pct is None:
            self.bar.hide()
            return
        self.bar.show()
        self.bar.setValue(int(pct))
        theme.set_prop(self.bar, "level", "danger" if pct >= danger else "warn" if pct >= warn else "ok")


class DashboardTab(QWidget):
    alert_received = pyqtSignal(dict)
    status_changed = pyqtSignal(str, str)   # text, pill state (ok | warn | danger | off)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_alert_id = 0
        self._server_online = False
        self._polling = False
        self._build_ui()
        # Delay first poll so window renders first
        QTimer.singleShot(500, self._start_polling)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Alert Banner (hidden by default) ──────────────────────────────────
        self.alert_banner = theme.label("", "banner-danger", wrap=True)
        self.alert_banner.hide()
        root.addWidget(self.alert_banner)

        # ── Status + controls ─────────────────────────────────────────────────
        status_card, sb = theme.card()
        row = QHBoxLayout()
        row.setSpacing(14)
        self.indicator = StatusIndicator()
        row.addWidget(self.indicator, 0, Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.status_label = theme.label("Connecting…", "h1")
        self.version_label = theme.label("Minecraft · NeoForge", "muted")
        info_col.addWidget(self.status_label)
        info_col.addWidget(self.version_label)
        row.addLayout(info_col, 1)

        self.btn_start   = self._make_btn("▶  Start",   "primary", self._start)
        self.btn_stop    = self._make_btn("■  Stop",    "danger",  self._stop)
        self.btn_restart = self._make_btn("↻  Restart", "warning", self._restart)
        self.btn_wake    = self._make_btn("⚡  Wake",    "info",    self._wake)
        for btn in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_wake):
            row.addWidget(btn)
        self.btn_backup = self._make_btn("⬇  Backup World", None, self._backup_world)
        self.btn_backup.setToolTip("Download a zip of the whole world to this computer")
        row.addWidget(self.btn_backup)
        sb.addLayout(row)

        self.backup_bar = QProgressBar()
        self.backup_bar.setTextVisible(False)
        self.backup_bar.setFixedHeight(6)
        self.backup_bar.hide()
        sb.addWidget(self.backup_bar)

        self.message_label = theme.label(" ", "caption")
        sb.addWidget(self.message_label)
        root.addWidget(status_card)

        # ── Player portal on/off ──────────────────────────────────────────────
        portal_card, pb = theme.card()
        prow = QHBoxLayout()
        prow.setSpacing(12)
        pcol = QVBoxLayout()
        pcol.setSpacing(2)
        ptitle = QHBoxLayout()
        ptitle.setSpacing(8)
        ptitle.addWidget(theme.label("Player Portal", "h2"))
        self.portal_pill = theme.label("● Checking", "pill")
        ptitle.addWidget(self.portal_pill)
        ptitle.addStretch()
        pcol.addLayout(ptitle)
        pcol.addWidget(theme.label(
            "The website where friends see server status and download mod packages. "
            "It's always off after the Pi restarts. Minecraft itself works either way.", "caption", wrap=True))
        prow.addLayout(pcol, 1)
        self.btn_portal = self._make_btn("Turn On", None, self._toggle_portal)
        self.btn_portal.setEnabled(False)
        prow.addWidget(self.btn_portal, 0, Qt.AlignmentFlag.AlignVCenter)
        pb.addLayout(prow)
        self._portal_running = None
        self._portal_busy = False

        # ── Pi system stats ───────────────────────────────────────────────────
        stats = QGridLayout()
        stats.setSpacing(14)
        self._cpu_tile = StatTile("CPU")
        self._ram_tile = StatTile("Memory")
        self._swap_tile = StatTile("Swap")
        self._disk_tile = StatTile("Disk")
        self._temp_tile = StatTile("Temperature")
        for i, tile in enumerate((self._cpu_tile, self._ram_tile, self._swap_tile, self._disk_tile, self._temp_tile)):
            stats.addWidget(tile, 0, i)
            stats.setColumnStretch(i, 1)
        root.addLayout(stats)

        # ── Connection info ───────────────────────────────────────────────────
        info_card, ib = theme.card("Connection")
        self._info_grid = QGridLayout()
        self._info_grid.setHorizontalSpacing(24)
        self._info_grid.setVerticalSpacing(8)
        self._info_grid.setColumnStretch(1, 1)
        self._info_values = {}
        for r, key in enumerate(["Host", "API Port", "Server Dir", "Version", "Loader"]):
            self._info_grid.addWidget(theme.label(key, "muted"), r, 0)
            val = theme.label("—", "mono")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._info_grid.addWidget(val, r, 1)
            self._info_values[key] = val
        ib.addLayout(self._info_grid)
        root.addWidget(info_card)
        root.addWidget(portal_card)

        # Cards keep their natural height; spare space goes below them
        for w in (status_card, portal_card, info_card, *(t.frame for t in (self._cpu_tile, self._ram_tile, self._swap_tile, self._disk_tile, self._temp_tile))):
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        root.addStretch(1)

    def _make_btn(self, text: str, variant: str, slot):
        btn = theme.button(text, variant, slot)
        btn.setMinimumHeight(38)
        btn.setMinimumWidth(104)
        return btn

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_polling(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._dispatch_poll)
        self._timer.start(5000)
        self._dispatch_poll()

    def _dispatch_poll(self):
        if self._polling:
            return
        self._polling = True
        last_id = self._last_alert_id
        def fetch():
            return (api.get_status(), api.get_system_stats(), api.get_alerts(last_id), api.get_portal())
        run_in_thread(fetch, lambda r: self._on_poll_result(*r))

    def _on_poll_result(self, status, sys_stats, alerts_data, portal=None):
        self._polling = False
        self._apply_status(status)
        self._apply_system_stats(sys_stats)
        self._apply_alerts(alerts_data)
        self._apply_portal(portal)

    def _apply_portal(self, data):
        if self._portal_busy:
            return
        if not data or "error" in data:
            self._portal_running = None
            self.portal_pill.setText("● Unknown")
            theme.set_prop(self.portal_pill, "state", "off")
            self.btn_portal.setEnabled(False)
            return
        self._portal_running = bool(data.get("running"))
        self.portal_pill.setText("● On" if self._portal_running else "● Off")
        theme.set_prop(self.portal_pill, "state", "ok" if self._portal_running else "off")
        self.btn_portal.setText("Turn Off" if self._portal_running else "Turn On")
        theme.set_prop(self.btn_portal, "variant", "danger" if self._portal_running else "primary")
        self.btn_portal.setEnabled(True)

    def _toggle_portal(self):
        if self._portal_running is None or self._portal_busy:
            return
        turning_on = not self._portal_running
        self._portal_busy = True
        self.btn_portal.setEnabled(False)
        self.portal_pill.setText("● Turning on…" if turning_on else "● Turning off…")
        theme.set_prop(self.portal_pill, "state", "warn")

        def on_done(result):
            self._portal_busy = False
            if not result or not result.get("success"):
                msg = "could not connect to the Pi" if result is None else (result.get("message") or result.get("error", "unknown error"))
                self.message_label.setText(f"Player portal: {msg}")
            else:
                self.message_label.setText(result.get("message", ""))
            self._apply_portal(result if result and "running" in result else None)
            if result is None or "running" not in result:
                run_in_thread(api.get_portal, self._apply_portal)

        run_in_thread(api.start_portal if turning_on else api.stop_portal, on_done)

    # ── Apply results (runs on main thread via signal) ────────────────────────

    def _apply_status(self, status):
        if status is None:
            self.indicator.set_unknown()
            self.status_label.setText("Cannot reach server")
            self.status_changed.emit("Unreachable", "off")
            self._set_buttons_enabled(False, False)
            self.btn_start.setEnabled(False)
            self.btn_wake.setEnabled(False)
            self._update_info(None)
            return

        online = status.get("minecraft_online", False)
        tmux   = status.get("tmux_running", False)
        self._server_online = online

        if online:
            self.indicator.set_online()
            self.status_label.setText("Online")
            self.status_changed.emit("Online", "ok")
            self._set_buttons_enabled(running=True, online=True)
        elif tmux:
            self.indicator.set_starting()
            self.status_label.setText("Starting…")
            self.status_changed.emit("Starting", "warn")
            self._set_buttons_enabled(running=True, online=False)
        else:
            self.indicator.set_offline()
            self.status_label.setText("Offline")
            self.status_changed.emit("Offline", "danger")
            self._set_buttons_enabled(running=False, online=False)

        self._update_info(status)

    def _set_buttons_enabled(self, running: bool, online: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_restart.setEnabled(running)
        self.btn_wake.setEnabled(not running)

    def _update_info(self, status):
        from config import config
        values = {
            "Host": config.pi_host or "(not configured)",
            "API Port": str(config.api_port),
            "Server Dir": config.server_dir,
        }
        if status:
            values["Version"] = status.get("version", "?")
            values["Loader"] = status.get("loader", "?")
            self.version_label.setText(f"Minecraft {values['Version']} · {values['Loader']}")
        for key, lbl in self._info_values.items():
            if key in values:
                lbl.setText(values[key])

    def _apply_system_stats(self, data):
        if not data or "error" in data:
            for tile in (self._cpu_tile, self._ram_tile, self._swap_tile, self._disk_tile, self._temp_tile):
                tile.set("—", "Not reported by the Pi")
            return
        cpu =data.get("cpu_percent", 0)
        self._cpu_tile.set(f"{cpu:.0f}%", "Processor load", cpu)

        ram_used  = data.get("ram_used_mb", 0)
        ram_total = data.get("ram_total_mb", 1)
        ram_pct   = data.get("ram_percent", 0)
        # Memory normally sits at 80-90% on a 2 GB Pi running Minecraft, so only go red at 90%
        self._ram_tile.set(f"{ram_pct:.0f}%", f"{ram_used} / {ram_total} MB", ram_pct, danger=90)

        if "swap_total_mb" in data:
            swap_used = data.get("swap_used_mb", 0)
            swap_total = data.get("swap_total_mb", 0)
            swap_pct = data.get("swap_percent", 0)
            if swap_total:
                # Swap is normally near empty; a lot in use means RAM is under pressure
                self._swap_tile.set(f"{swap_pct:.0f}%", f"{swap_used} / {swap_total} MB", swap_pct, warn=30, danger=65)
            else:
                self._swap_tile.set("Off", "No swap configured")
        else:
            self._swap_tile.set("—", "Not reported by the Pi")

        disk_used  = data.get("disk_used_gb", 0)
        disk_total = data.get("disk_total_gb", 1)
        disk_pct   = data.get("disk_percent", 0)
        self._disk_tile.set(f"{disk_pct:.0f}%", f"{disk_used} / {disk_total} GB", disk_pct)

        temps = data.get("temperatures", {})
        if temps:
            hottest = max(temps.values())
            def f(c): return c * 9 / 5 + 32
            self._temp_tile.set(f"{hottest}°C · {f(hottest):.0f}°F",
                                "  ·  ".join(f"{k}: {v}°C / {f(v):.1f}°F" for k, v in temps.items()),
                                min(hottest, 100))
        else:
            self._temp_tile.set("N/A", "No sensor data")

    def _apply_alerts(self, data):
        if not data:
            return
        alerts = data.get("alerts", [])
        if alerts:
            newest = alerts[-1]
            self._last_alert_id = newest["id"]
            msg = f"⚠️  Non-whitelisted player tried to join: {newest['player']}"
            self.alert_banner.setText(msg)
            self.alert_banner.show()
            self.alert_received.emit(newest)

    # ── Actions (run API call in thread, then re-poll) ────────────────────────

    def _run_action(self, action_fn, label: str):
        self.message_label.setText(f"{label}…")
        def on_done(result):
            msg = result.get("message", "Done") if result else "No response"
            self.message_label.setText(msg)
            self._dispatch_poll()
        run_in_thread(action_fn, on_done)

    def _backup_world(self):
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save World Backup",
            os.path.join(os.path.expanduser("~/Documents"), f"minecraft_world_backup_{stamp}.zip"),
            "Zip files (*.zip)",
        )
        if not dest:
            return
        progress = {"done": 0, "total": 0}
        self.btn_backup.setEnabled(False)
        self.backup_bar.setRange(0, 0)  # busy until the size is known
        self.backup_bar.show()
        self.message_label.setText("Backing up world… the Pi is saving and zipping it (this can take a minute)")

        def tick():
            done, total = progress["done"], progress["total"]
            if total:
                self.backup_bar.setRange(0, 1000)
                self.backup_bar.setValue(int(done * 1000 / total))
                self.message_label.setText(f"Downloading world backup… {done / 1e6:,.0f} / {total / 1e6:,.0f} MB")

        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(300)

        def on_done(result):
            timer.stop()
            self.backup_bar.hide()
            self.btn_backup.setEnabled(True)
            if result and result.get("success"):
                self.message_label.setText(f"World backup saved: {os.path.basename(dest)}")
                QMessageBox.information(
                    self, "Backup World",
                    f"Saved {result['files']} files ({result['bytes'] / 1e6:,.0f} MB) to:\n{dest}",
                )
            else:
                msg = "could not connect to the Pi" if result is None else result.get("error", "unknown error")
                self.message_label.setText(f"World backup failed: {msg}")
                QMessageBox.warning(self, "Backup World", f"Backup failed: {msg}")

        run_in_thread(lambda: api.backup_world(dest, progress), on_done)

    def _start(self):   self._run_action(api.start_server,   "Starting")
    def _stop(self):    self._run_action(api.stop_server,    "Stopping")
    def _restart(self): self._run_action(api.restart_server, "Restarting")
    def _wake(self):    self._run_action(api.wake_server,    "Waking")

    def _open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._update_info(None)
            self._dispatch_poll()
