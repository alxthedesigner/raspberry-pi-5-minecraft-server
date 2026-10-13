"""
Mods tab: group mods into packages and choose which package is active on the server.

Packages live in the app's settings. Activating a package uses the existing
enable/disable API to move mods between mods/ and mods_disabled/ on the Pi:
checked mods in the package are enabled, every other mod is disabled.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QFileDialog, QInputDialog,
    QMenu, QSplitter, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from api_client import api
from config import config
from thread_manager import run_in_thread
from ui import theme


def _msg(result) -> str:
    if result is None:
        return "could not connect to the Pi"
    return result.get("message") or result.get("error") or "unknown error"


def _ok(result) -> bool:
    return bool(result) and bool(result.get("success"))


class ModsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._packages = config.mod_packages   # [{"name": str, "mods": {filename: checked}}]
        self._active = config.active_package
        self._enabled = {}     # filename -> size_mb, as reported by the server
        self._disabled = {}
        self._loaded = False   # server mod list fetched at least once
        self._populating = False
        self._busy = False
        self._build_ui()
        self._show_packages()
        QTimer.singleShot(700, self._refresh)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(theme.label("⚠️  Mod changes require a server restart to take effect.", "banner-warn"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(14)

        # ── Left: packages ────────────────────────────────────────────────────
        left, ll = theme.card("Packages", "The active package is what runs on the server")
        self.package_list = QListWidget()
        self.package_list.currentRowChanged.connect(self._show_package)
        ll.addWidget(self.package_list, 1)

        pkg_btns = QHBoxLayout()
        self.new_btn = theme.button("+ New Package  ▾", "primary")
        new_menu = QMenu(self)
        new_menu.addAction("From mod files…", lambda: self._new_package("files"))
        new_menu.addAction("From a folder of mods…", lambda: self._new_package("folder"))
        new_menu.addSeparator()
        new_menu.addAction("From mods enabled on the server", lambda: self._new_package("server"))
        self.new_btn.setMenu(new_menu)
        self.rename_btn = theme.button("Rename", None, self._rename_package)
        self.delete_btn = theme.button("Delete", "danger", self._delete_package)
        pkg_btns.addWidget(self.new_btn, 1)
        pkg_btns.addWidget(self.rename_btn)
        pkg_btns.addWidget(self.delete_btn)
        ll.addLayout(pkg_btns)
        splitter.addWidget(left)

        # ── Right: mods in the selected package ───────────────────────────────
        right, rl = theme.card()

        header = QHBoxLayout()
        self.package_title = theme.label("", "h2")
        header.addWidget(self.package_title)
        header.addStretch()
        self.add_mods_btn = theme.button("+ Add Mods  ▾", "info")
        add_menu = QMenu(self)
        add_menu.addAction("From mod files…", lambda: self._add_mods("files"))
        add_menu.addAction("From a folder of mods…", lambda: self._add_mods("folder"))
        self.add_mods_btn.setMenu(add_menu)
        header.addWidget(self.add_mods_btn)
        rl.addLayout(header)

        # Row 1: filter + check/uncheck everything shown
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter mods…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMinimumWidth(180)
        self.filter_edit.textChanged.connect(self._apply_filter)
        tools.addWidget(self.filter_edit, 1)
        self._mod_btns = []
        for text, variant, slot in [
            ("Check All", None, lambda: self._set_checked(self._shown_items(), True)),
            ("Uncheck All", None, lambda: self._set_checked(self._shown_items(), False)),
        ]:
            btn = theme.button(text, variant, slot)
            tools.addWidget(btn)
            self._mod_btns.append(btn)
        rl.addLayout(tools)

        # Row 2: actions on the highlighted rows
        hl = QHBoxLayout()
        hl.setSpacing(8)
        hl.addWidget(theme.label("Highlighted:", "muted"))
        for text, variant, slot in [
            ("Check", None, lambda: self._set_checked(self._highlighted(), True)),
            ("Uncheck", None, lambda: self._set_checked(self._highlighted(), False)),
            ("Remove from Package", "danger", self._remove_highlighted),
        ]:
            btn = theme.button(text, variant, slot)
            hl.addWidget(btn)
            self._mod_btns.append(btn)
        hl.addStretch()
        rl.addLayout(hl)

        self.mod_list = QListWidget()
        self.mod_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.mod_list.itemChanged.connect(self._on_item_changed)
        rl.addWidget(self.mod_list, 1)

        hint = theme.label(
            "Tip: Shift- or ⌘-click to highlight several mods, then use the Highlighted buttons. "
            "Check All and Uncheck All only affect the mods the filter is showing.", "caption", wrap=True
        )
        rl.addWidget(hint)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 780])
        root.addWidget(splitter, 1)

        # ── Bottom: summary + activate ────────────────────────────────────────
        bottom = QHBoxLayout()
        self.summary = theme.label("", "muted", wrap=True)
        bottom.addWidget(self.summary, 1)
        refresh_btn = theme.button("↻  Refresh", "ghost", self._refresh)
        bottom.addWidget(refresh_btn)
        self.activate_btn = theme.button("Activate Package on Server", "primary", self._activate)
        self.activate_btn.setMinimumHeight(36)
        bottom.addWidget(self.activate_btn)
        root.addLayout(bottom)

    # ── Package list ──────────────────────────────────────────────────────────

    def _current(self):
        row = self.package_list.currentRow()
        return self._packages[row] if 0 <= row < len(self._packages) else None

    def _find(self, name: str):
        return next((p for p in self._packages if p["name"] == name), None)

    def _save(self):
        config.mod_packages = self._packages
        config.active_package = self._active

    def _show_packages(self, select: str = None):
        """Rebuild the package list, keeping (or moving to) the selected package."""
        if select is None:
            cur = self._current()
            select = cur["name"] if cur else self._active
        self.package_list.blockSignals(True)
        self.package_list.clear()
        row = 0
        for i, pkg in enumerate(self._packages):
            on = sum(1 for v in pkg["mods"].values() if v)
            if pkg["name"] == self._active:
                item = QListWidgetItem(f"● {pkg['name']}  (active)")
                item.setForeground(QColor(theme.OK))
            else:
                item = QListWidgetItem(f"   {pkg['name']}")
            item.setToolTip(f"{on} of {len(pkg['mods'])} mods checked")
            self.package_list.addItem(item)
            if pkg["name"] == select:
                row = i
        if self._packages:
            self.package_list.setCurrentRow(row)
        self.package_list.blockSignals(False)
        self._show_package()

    def _ask_name(self, title: str, default: str = "", current: str = None):
        while True:
            name, ok = QInputDialog.getText(self, title, "Package name:", text=default)
            name = name.strip()
            if not ok or not name:
                return None
            if name != current and self._find(name):
                QMessageBox.warning(self, title, f"A package called “{name}” already exists.")
                default = name
                continue
            return name

    def _new_package(self, source: str):
        if self._busy:
            return
        if source == "server":
            if not self._loaded:
                QMessageBox.warning(self, "New Package", "Server mods haven't loaded yet. Check the connection and press Refresh.")
                return
            if not self._enabled:
                QMessageBox.information(self, "New Package", "There are no enabled mods on the server.")
                return
            name = self._ask_name("New Package", "Current server mods")
            if not name:
                return
            self._packages.append({"name": name, "mods": {n: True for n in sorted(self._enabled)}})
            if not self._active:
                self._active = name   # it matches the server exactly
            self._save()
            self._show_packages(select=name)
            return

        name = self._ask_name("New Package")
        if not name:
            return
        paths = self._pick_jars(source)
        if not paths:
            return
        pkg = {"name": name, "mods": {}}
        self._packages.append(pkg)
        self._add_to_package(pkg, paths)

    def _rename_package(self):
        pkg = self._current()
        if not pkg or self._busy:
            return
        name = self._ask_name("Rename Package", pkg["name"], current=pkg["name"])
        if not name or name == pkg["name"]:
            return
        if self._active == pkg["name"]:
            self._active = name
        pkg["name"] = name
        self._save()
        self._show_packages(select=name)

    def _delete_package(self):
        pkg = self._current()
        if not pkg or self._busy:
            return
        answer = QMessageBox.question(
            self, "Delete Package",
            f"Delete the package “{pkg['name']}”?\n\n"
            "This only removes the package from this app. Mod files on the server are not "
            "deleted, and the server's enabled mods don't change.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._packages.remove(pkg)
        if self._active == pkg["name"]:
            self._active = ""
        self._save()
        self._show_packages(select=self._active)

    # ── Mods in the selected package ──────────────────────────────────────────

    def _show_package(self, *_):
        pkg = self._current()
        self._populating = True
        self.mod_list.clear()
        if pkg is None:
            self.package_title.setText("<b>No packages yet</b>")
            item = QListWidgetItem(
                "Click “+ New Package” → “From mods enabled on the server” to turn your current "
                "mods into a package, or upload a new set of mods."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.mod_list.addItem(item)
        else:
            self._update_title(pkg)
            for name, checked in sorted(pkg["mods"].items(), key=lambda kv: kv[0].lower()):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self._style_item(item, name)
                self.mod_list.addItem(item)
        self._populating = False

        for w in [self.rename_btn, self.delete_btn, self.add_mods_btn, self.activate_btn, *self._mod_btns]:
            w.setEnabled(pkg is not None and not self._busy)
        self.new_btn.setEnabled(not self._busy)
        self._apply_filter()
        self._update_summary()

    def _update_title(self, pkg: dict):
        on = sum(1 for v in pkg["mods"].values() if v)
        active = f"  <span style='color:{theme.OK}'>(active)</span>" if pkg["name"] == self._active else ""
        self.package_title.setText(f"<b>{pkg['name']}</b>{active} — {on} of {len(pkg['mods'])} mods checked")
        item = self.package_list.currentItem()
        if item:
            item.setToolTip(f"{on} of {len(pkg['mods'])} mods checked")

    def _after_check_change(self):
        """Save and update labels without rebuilding the list (keeps scroll and highlight)."""
        pkg = self._current()
        if pkg:
            self._save()
            self._update_title(pkg)
            self._update_summary()

    def _style_item(self, item: QListWidgetItem, name: str):
        size = self._enabled.get(name, self._disabled.get(name))
        if name in self._enabled:
            status, color = "enabled on server", theme.OK
        elif name in self._disabled:
            status, color = "disabled on server", theme.MUTED
        elif self._loaded:
            status, color = "not on server", theme.DANGER
        else:
            status, color = "", theme.TEXT
        text = f"  {name}"
        if size is not None:
            text += f"  ({size} MB)"
        if status:
            text += f"  —  {status}"
        item.setText(text)
        item.setForeground(QColor(color))

    def _shown_items(self) -> list:
        items = [self.mod_list.item(i) for i in range(self.mod_list.count())]
        return [it for it in items if not it.isHidden() and it.data(Qt.ItemDataRole.UserRole)]

    def _highlighted(self) -> list:
        return [it for it in self.mod_list.selectedItems()
                if not it.isHidden() and it.data(Qt.ItemDataRole.UserRole)]

    def _apply_filter(self, *_):
        text = self.filter_edit.text().strip().lower()
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(bool(name) and text not in name.lower())

    def _on_item_changed(self, item: QListWidgetItem):
        if self._populating:
            return
        pkg = self._current()
        name = item.data(Qt.ItemDataRole.UserRole)
        if pkg and name:
            pkg["mods"][name] = item.checkState() == Qt.CheckState.Checked
            self._after_check_change()

    def _set_checked(self, items: list, checked: bool):
        pkg = self._current()
        if not pkg or not items:
            return
        self._populating = True
        for item in items:
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            pkg["mods"][item.data(Qt.ItemDataRole.UserRole)] = checked
        self._populating = False
        self._after_check_change()

    def _remove_highlighted(self):
        pkg = self._current()
        items = self._highlighted()
        if not pkg or not items:
            QMessageBox.information(self, "Remove Mods", "Highlight the mods to remove from this package first.")
            return
        answer = QMessageBox.question(
            self, "Remove Mods",
            f"Remove {len(items)} mod(s) from “{pkg['name']}”?\n\n"
            "The files stay on the server; they're just no longer part of this package.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for item in items:
            pkg["mods"].pop(item.data(Qt.ItemDataRole.UserRole), None)
        self._save()
        self._show_packages()

    # ── Uploading ─────────────────────────────────────────────────────────────

    def _pick_jars(self, source: str) -> list:
        if source == "folder":
            folder = QFileDialog.getExistingDirectory(self, "Choose a folder of mods", os.path.expanduser("~"))
            if not folder:
                return []
            paths = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".jar"))
            if not paths:
                QMessageBox.information(self, "Add Mods", "That folder doesn't contain any .jar files.")
            return paths
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose mods (⌘-A selects all)", os.path.expanduser("~"), "Mod files (*.jar)"
        )
        return paths

    def _add_mods(self, source: str):
        pkg = self._current()
        if not pkg or self._busy:
            return
        paths = self._pick_jars(source)
        if paths:
            self._add_to_package(pkg, paths)

    def _add_to_package(self, pkg: dict, paths: list):
        for p in paths:
            pkg["mods"].setdefault(os.path.basename(p), True)
        self._save()
        self._show_packages(select=pkg["name"])

        on_server = self._enabled.keys() | self._disabled.keys()
        to_upload = [p for p in paths if os.path.basename(p) not in on_server]
        if not to_upload:
            return
        # Uploads land in mods/ (enabled). Only mods that are checked in the active
        # package stay enabled; the rest are disabled until their package is activated.
        keep = {n for n, on in pkg["mods"].items() if on} if pkg["name"] == self._active else set()

        def do():
            failed = []
            for path in to_upload:
                name = os.path.basename(path)
                result = api.upload_mod(path)
                if not _ok(result):
                    failed.append(f"{name}: {_msg(result)}")
                    continue
                if name not in keep:
                    result = api.disable_mod(name)
                    if not _ok(result):
                        failed.append(f"{name}: uploaded, but couldn't be disabled ({_msg(result)})")
            return failed

        def on_done(failed):
            self._set_busy(False)
            if failed:
                QMessageBox.warning(
                    self, "Upload Mods",
                    f"Uploaded {len(to_upload) - len(failed)} of {len(to_upload)} mods.\n\n" + "\n".join(failed),
                )
            self._refresh()

        self._set_busy(True, f"Uploading {len(to_upload)} mod(s) to the server…")
        run_in_thread(do, on_done)

    # ── Activating ────────────────────────────────────────────────────────────

    def _diff(self, pkg: dict):
        want = {n for n, on in pkg["mods"].items() if on}
        enable = sorted(want & self._disabled.keys())
        disable = sorted(self._enabled.keys() - want)
        missing = sorted(want - self._enabled.keys() - self._disabled.keys())
        return enable, disable, missing

    def _activate(self):
        pkg = self._current()
        if not pkg or self._busy:
            return
        if not self._loaded:
            QMessageBox.warning(self, "Activate Package", "Server mods haven't loaded yet. Check the connection and press Refresh.")
            return
        enable, disable, missing = self._diff(pkg)
        missing_note = (f"\n\n{len(missing)} checked mod(s) aren't on the server and will be skipped. "
                        "Use “+ Add Mods” to upload them.") if missing else ""

        if not enable and not disable:
            self._active = pkg["name"]
            self._save()
            self._show_packages(select=pkg["name"])
            QMessageBox.information(self, "Activate Package",
                                    f"The server already matches “{pkg['name']}”. It's now the active package." + missing_note)
            return

        box = QMessageBox(self)
        box.setWindowTitle("Activate Package")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Make “{pkg['name']}” the active package?")
        box.setInformativeText(
            f"This will enable {len(enable)} and disable {len(disable)} mod(s) on the server. "
            "Any mod that isn't checked in this package will be disabled." + missing_note
        )
        box.setDetailedText("\n".join(
            [f"+ enable   {n}" for n in enable]
            + [f"− disable  {n}" for n in disable]
            + [f"! missing  {n}" for n in missing]
        ))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        def do():
            failed = []
            for name in disable:
                result = api.disable_mod(name)
                if not _ok(result):
                    failed.append(f"disable {name}: {_msg(result)}")
            for name in enable:
                result = api.enable_mod(name)
                if not _ok(result):
                    failed.append(f"enable {name}: {_msg(result)}")
            return failed

        def on_done(failed):
            self._set_busy(False)
            self._active = pkg["name"]
            self._save()
            self._show_packages(select=pkg["name"])
            if failed:
                QMessageBox.warning(self, "Activate Package",
                                    f"Some mods couldn't be changed:\n\n" + "\n".join(failed))
            else:
                QMessageBox.information(
                    self, "Activate Package",
                    f"“{pkg['name']}” is now active.\n\nRestart the server (Dashboard → Restart) to load the changes.",
                )
            self._refresh()

        self._set_busy(True, f"Activating “{pkg['name']}”…")
        run_in_thread(do, on_done)

    # ── Server state ──────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, text: str = ""):
        self._busy = busy
        self._show_package()
        if busy:
            self.summary.setText(text)

    def _refresh(self):
        run_in_thread(api.get_mods, self._apply_mods)

    def _apply_mods(self, data):
        if not data or "error" in data:
            if not self._busy:
                self.summary.setText("Couldn't load mods from the server. Check the connection and press Refresh.")
            return
        self._enabled = {m["filename"]: m["size_mb"] for m in data.get("enabled", [])}
        self._disabled = {m["filename"]: m["size_mb"] for m in data.get("disabled", [])}
        self._loaded = True
        self._show_package()

    def _update_summary(self):
        if self._busy:
            return
        if not self._loaded:
            self.summary.setText("Loading mods from the server…")
            return
        parts = [f"Server: {len(self._enabled)} mods enabled",
                 f"Active package: {self._active or 'none'}"]
        pkg = self._current()
        if pkg:
            enable, disable, missing = self._diff(pkg)
            if enable or disable:
                parts.append(f"Activating “{pkg['name']}” would enable {len(enable)} and disable {len(disable)}")
            else:
                parts.append(f"Server matches “{pkg['name']}”")
            if missing:
                parts.append(f"{len(missing)} checked mod(s) not on server")
        self.summary.setText("   •   ".join(parts))
