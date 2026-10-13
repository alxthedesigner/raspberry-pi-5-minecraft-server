"""
Config tab: edit server.properties, JVM args, and NeoForge TOML configs.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QPushButton, QLabel, QComboBox,
    QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from api_client import api
from thread_manager import run_in_thread
from ui import theme


class ConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        QTimer.singleShot(800, self._load_all)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        inner_tabs = QTabWidget()
        inner_tabs.addTab(self._build_props_tab(), "server.properties")
        inner_tabs.addTab(self._build_jvm_tab(), "JVM Arguments")
        inner_tabs.addTab(self._build_neoforge_tab(), "Mod Configs")
        root.addWidget(inner_tabs)

    def _page(self, title: str, subtitle: str, actions: list):
        """Card used as the body of each inner tab."""
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 12, 0, 0)
        frame, body = theme.card(title, subtitle, actions)
        vl.addWidget(frame)
        return w, body

    # ── server.properties tab ─────────────────────────────────────────────────
    def _build_props_tab(self):
        w, body = self._page(
            "server.properties", "Double-click a value to edit it. Changes need a server restart.",
            [theme.button("↻  Reload", None, self._load_props), theme.button("Save", "primary", self._save_props)],
        )
        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.props_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.props_table.verticalHeader().hide()
        self.props_table.setShowGrid(False)
        body.addWidget(self.props_table)
        return w

    # ── JVM tab ───────────────────────────────────────────────────────────────
    def _build_jvm_tab(self):
        self.jvm_presets = QComboBox()
        self.jvm_presets.addItem("Memory presets")
        self.jvm_presets.addItem("2GB RAM")
        self.jvm_presets.addItem("4GB RAM (default)")
        self.jvm_presets.addItem("6GB RAM")
        self.jvm_presets.currentIndexChanged.connect(self._apply_jvm_preset)
        w, body = self._page(
            "JVM Arguments",
            "One flag per line, or all on one line. These are passed to Java when starting the server.",
            [self.jvm_presets, theme.button("↻  Reload", None, self._load_jvm),
             theme.button("Save", "primary", self._save_jvm)],
        )
        self.jvm_edit = QTextEdit()
        self.jvm_edit.setFont(QFont("Menlo,Consolas,monospace", 12))
        body.addWidget(self.jvm_edit)
        return w

    # ── NeoForge configs tab ──────────────────────────────────────────────────
    def _build_neoforge_tab(self):
        self.neo_combo = QComboBox()
        self.neo_combo.setMinimumWidth(320)
        self.neo_combo.currentTextChanged.connect(self._load_neo_config)
        w, body = self._page(
            "NeoForge / Mod Configs", "Pick a config file to view and edit it.",
            [self.neo_combo, theme.button("↻  List", None, self._load_neo_list),
             theme.button("Save", "primary", self._save_neo_config)],
        )
        self.neo_edit = QTextEdit()
        self.neo_edit.setFont(QFont("Menlo,Consolas,monospace", 11))
        body.addWidget(self.neo_edit)
        return w

    # ── Data loading ──────────────────────────────────────────────────────────
    def _load_all(self):
        self._load_props()
        self._load_jvm()
        self._load_neo_list()

    def _load_props(self):
        run_in_thread(api.get_server_properties, self._apply_props)

    def _apply_props(self, data):
        if not data:
            return
        props = data.get("properties", {})
        self.props_table.setRowCount(0)
        for key, value in sorted(props.items()):
            row = self.props_table.rowCount()
            self.props_table.insertRow(row)
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.props_table.setItem(row, 0, key_item)
            self.props_table.setItem(row, 1, QTableWidgetItem(value))

    def _save_props(self):
        props = {}
        for row in range(self.props_table.rowCount()):
            key = self.props_table.item(row, 0).text()
            value = self.props_table.item(row, 1).text() if self.props_table.item(row, 1) else ""
            props[key] = value
        def do():
            return api.save_server_properties(props)
        def on_done(result):
            msg = result.get("message", "Saved") if result else "API error"
            QMessageBox.information(self, "server.properties", msg)
        run_in_thread(do, on_done)

    def _load_jvm(self):
        run_in_thread(api.get_jvm_args, self._apply_jvm)

    def _apply_jvm(self, data):
        if data:
            self.jvm_edit.setPlainText(data.get("args", ""))

    def _apply_jvm_preset(self, index: int):
        presets = {
            1: "-Xmx2G -Xms1G -XX:+UseG1GC -XX:+ParallelRefProcEnabled",
            2: "-Xmx4G -Xms2G -XX:+UseG1GC -XX:+ParallelRefProcEnabled",
            3: "-Xmx6G -Xms3G -XX:+UseG1GC -XX:+ParallelRefProcEnabled",
        }
        if index in presets:
            self.jvm_edit.setPlainText(presets[index])
        self.jvm_presets.setCurrentIndex(0)

    def _save_jvm(self):
        args = self.jvm_edit.toPlainText().strip()
        def do():
            return api.save_jvm_args(args)
        def on_done(result):
            msg = result.get("message", "Saved") if result else "API error"
            QMessageBox.information(self, "JVM Args", msg)
        run_in_thread(do, on_done)

    def _load_neo_list(self):
        run_in_thread(api.list_neoforge_configs, self._apply_neo_list)

    def _apply_neo_list(self, data):
        self.neo_combo.blockSignals(True)
        self.neo_combo.clear()
        if data:
            for f in data.get("files", []):
                self.neo_combo.addItem(f)
        self.neo_combo.blockSignals(False)

    def _load_neo_config(self, filename: str):
        if not filename:
            return
        def do():
            return api.get_neoforge_config(filename)
        run_in_thread(do, self._apply_neo_config)

    def _apply_neo_config(self, data):
        if data and data.get("success"):
            self.neo_edit.setPlainText(data.get("content", ""))
        else:
            self.neo_edit.setPlainText("")

    def _save_neo_config(self):
        filename = self.neo_combo.currentText()
        if not filename:
            QMessageBox.warning(self, "Save", "No file selected.")
            return
        content = self.neo_edit.toPlainText()
        def do():
            return api.save_neoforge_config(filename, content)
        def on_done(result):
            msg = result.get("message", "Saved") if result else "API error"
            QMessageBox.information(self, "NeoForge Config", msg)
        run_in_thread(do, on_done)
