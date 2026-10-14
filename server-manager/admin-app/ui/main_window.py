"""
Main application window — sidebar navigation with one page per section.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QStatusBar, QMenu, QApplication, QSystemTrayIcon, QStyle, QWidget,
    QHBoxLayout, QVBoxLayout, QFrame, QListWidget, QListWidgetItem, QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QAction, QShortcut, QKeySequence

from ui.dashboard_tab import DashboardTab
from ui.console_tab import ConsoleTab
from ui.players_tab import PlayersTab
from ui.mods_tab import ModsTab
from ui.config_tab import ConfigTab
from ui.instructions_tab import InstructionsTab
from ui.settings_dialog import SettingsDialog
from ui import theme
from config import config


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Server Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1240, 820)

        self._build_menu()
        self._build_pages()
        self._build_statusbar()
        self._setup_tray()
        self._connect_signals()

        # Show settings on first run
        if not config.is_configured:
            QTimer.singleShot(200, self._open_settings)
        else:
            # Auto-connect console
            QTimer.singleShot(800, self.console_tab.start_streaming)

    def _build_menu(self):
        menu = self.menuBar()

        server_menu = menu.addMenu("Server")
        self._action(server_menu, "Settings…", self._open_settings, shortcut="Ctrl+,")
        server_menu.addSeparator()
        self._action(server_menu, "Quit", QApplication.quit, shortcut="Ctrl+Q")

        view_menu = menu.addMenu("View")
        self._action(view_menu, "Refresh All", self._refresh_all, shortcut="F5")

    def _action(self, menu: QMenu, text: str, slot, shortcut: str = None) -> QAction:
        act = QAction(text, self)
        act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(shortcut)
        menu.addAction(act)
        return act

    def _build_pages(self):
        self.dashboard_tab = DashboardTab()
        self.console_tab = ConsoleTab()
        self.players_tab = PlayersTab()
        self.mods_tab = ModsTab()
        self.config_tab = ConfigTab()
        self.instructions_tab = InstructionsTab()

        pages = [
            ("dashboard", "Dashboard", "Server status, controls and Pi health", self.dashboard_tab),
            ("console",   "Console",   "Live server log and commands", self.console_tab),
            ("players",   "Players",   "Who's online, the whitelist and join requests", self.players_tab),
            ("mods",      "Mods",      "Group mods into packages and choose what runs on the server", self.mods_tab),
            ("config",    "Config",    "server.properties, JVM arguments and mod configs", self.config_tab),
            ("instructions", "Instructions", "How to install everything and join the server", self.instructions_tab),
        ]

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 18, 0, 14)
        sl.setSpacing(4)

        brand = QVBoxLayout()
        brand.setContentsMargins(20, 0, 20, 14)
        brand.setSpacing(2)
        title = theme.label("Server Manager")
        title.setObjectName("Brand")
        brand.addWidget(title)
        self.host_label = theme.label("", "caption")
        brand.addWidget(self.host_label)
        sl.addLayout(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav_names = {}
        for i, (icon, name, _, _) in enumerate(pages):
            item = QListWidgetItem(theme.icon(icon), f"  {name}")
            self.nav.addItem(item)
            self._nav_names[i] = name
        sl.addWidget(self.nav, 1)

        footer = QVBoxLayout()
        footer.setContentsMargins(16, 0, 16, 0)
        footer.setSpacing(10)
        status_row = QHBoxLayout()
        status_row.addWidget(theme.label("Server", "caption"))
        status_row.addStretch()
        self.server_pill = theme.label("● Connecting", "pill")
        status_row.addWidget(self.server_pill)
        footer.addLayout(status_row)
        settings_btn = theme.button("  Settings", "ghost", self._open_settings)
        settings_btn.setIcon(theme.icon("settings"))
        settings_btn.setIconSize(QSize(16, 16))
        settings_btn.setStyleSheet("text-align: left; padding-left: 8px;")
        footer.addWidget(settings_btn)
        sl.addLayout(footer)
        h.addWidget(sidebar)

        # ── Pages ─────────────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        for _, name, subtitle, widget in pages:
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(28, 22, 28, 18)
            pl.setSpacing(14)
            head = QVBoxLayout()
            head.setSpacing(2)
            head.addWidget(theme.label(name, "h1"))
            head.addWidget(theme.label(subtitle, "muted"))
            pl.addLayout(head)
            widget.layout().setContentsMargins(0, 0, 0, 0)
            pl.addWidget(widget, 1)
            self.stack.addWidget(page)
        h.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        for i in range(len(pages)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))

        self.setCentralWidget(central)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("Minecraft Server Manager")

        tray_menu = QMenu()
        tray_menu.addAction("Show", self.show)
        tray_menu.addAction("Quit", QApplication.quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    def _connect_signals(self):
        # Dashboard → players tab alert
        self.dashboard_tab.alert_received.connect(self.players_tab.notify_alert)
        # Dashboard → tray notification
        self.dashboard_tab.alert_received.connect(self._tray_alert)
        # Dashboard → sidebar status pill
        self.dashboard_tab.status_changed.connect(self._update_server_pill)
        # Players badge (pending requests)
        self.players_tab.badge_update.connect(self._update_players_badge)

    def _update_server_pill(self, text: str, state: str):
        self.server_pill.setText(f"● {text}")
        theme.set_prop(self.server_pill, "state", state)

    def _update_players_badge(self, count: int):
        idx = self.stack.indexOf(self.players_tab.parentWidget())
        label = "  Players"
        if count > 0:
            label = f"  Players  ({count})"
        self.nav.item(idx).setText(label)

    def _tray_alert(self, alert: dict):
        player = alert.get("player", "Unknown")
        self.tray.showMessage(
            "⚠️ Non-Whitelisted Player",
            f"'{player}' tried to join the server!",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _update_status_bar(self):
        if config.is_configured:
            self.status_bar.showMessage(f"Connected to: {config.pi_host}:{config.api_port}")
            self.host_label.setText(config.pi_host)
        else:
            self.status_bar.showMessage("Not configured — open Server > Settings")
            self.host_label.setText("Not configured")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._update_status_bar()
            self.console_tab.start_streaming()
            self._refresh_all()

    def _refresh_all(self):
        self.dashboard_tab._dispatch_poll()
        self.players_tab._refresh()
        self.mods_tab._refresh()
        self.config_tab._load_all()
        self.instructions_tab.refresh()

    def closeEvent(self, event):
        self.console_tab.stop_streaming()
        super().closeEvent(event)
