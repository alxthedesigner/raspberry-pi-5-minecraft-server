"""
App-wide look: colour tokens, the Qt stylesheet, icons, and small widget helpers.

Widgets pick a look through dynamic properties instead of inline styles:
  QPushButton  variant = primary | danger | warning | info | ghost
  QLabel       role    = h1 | h2 | muted | caption | mono | banner-warn | banner-danger | pill
  QLabel pill  state   = ok | warn | danger | off
  QProgressBar level   = ok | warn | danger
"""
import os
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtCore import QSize


# ── Colour tokens ─────────────────────────────────────────────────────────────

BG = "#0b0f17"          # window
SIDEBAR = "#0f141d"
CARD = "#141a24"
RAISED = "#1b2230"      # buttons, menus
INPUT = "#0e131c"       # lists, inputs, logs
BORDER = "#222a37"
BORDER_STRONG = "#2f3949"
TEXT = "#e6e9ef"
MUTED = "#8b95a7"
SUBTLE = "#5d6778"

ACCENT = "#22c55e"
ACCENT_HOVER = "#34d671"
ACCENT_SOFT = "#173326"

OK = "#4ade80"
WARN = "#fbbf24"
DANGER = "#f87171"
INFO = "#7cb3ff"


# ── Icons (stroke SVGs in the style of Lucide) ────────────────────────────────

_ICON_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
                 '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "console": '<path d="M4 17l6-6-6-6"/><path d="M12 19h8"/>',
    "players": '<circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/>'
               '<path d="M16 3.13a4 4 0 0 1 0 7.75"/><path d="M21 21v-2a4 4 0 0 0-3-3.85"/>',
    "mods": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
            '<path d="M3.27 6.96L12 12.01l8.73-5.05"/><path d="M12 22.08V12"/>',
    "config": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38'
                'a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73'
                'l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25'
                'a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74'
                'l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
                '<circle cx="12" cy="12" r="3"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
}

_ICON_DIR = os.path.join(tempfile.gettempdir(), "minecraft-manager-icons")


def _icon_file(name: str, color: str, width: float = 2) -> str:
    os.makedirs(_ICON_DIR, exist_ok=True)
    path = os.path.join(_ICON_DIR, f"{name}-{color.lstrip('#')}.svg")
    if not os.path.exists(path):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
               f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
               f'{_ICON_PATHS[name]}</svg>')
        with open(path, "w") as f:
            f.write(svg)
    return path.replace("\\", "/")


def icon(name: str) -> QIcon:
    """Muted icon that turns bright when its list item is selected."""
    ic = QIcon()
    for mode, color in [(QIcon.Mode.Normal, MUTED), (QIcon.Mode.Selected, TEXT), (QIcon.Mode.Active, TEXT)]:
        ic.addFile(_icon_file(name, color), QSize(24, 24), mode)
    return ic


# ── Stylesheet ────────────────────────────────────────────────────────────────

def _variant(name: str, bg: str, border: str, fg: str, hover_bg: str, weight: int = 600) -> str:
    return f"""
    QPushButton[variant="{name}"] {{ background: {bg}; border-color: {border}; color: {fg}; font-weight: {weight}; }}
    QPushButton[variant="{name}"]:hover {{ background: {hover_bg}; }}
    QPushButton[variant="{name}"]:disabled {{ background: {CARD}; border-color: {BORDER}; color: {SUBTLE}; }}
    """


def stylesheet() -> str:
    check = _icon_file("check", "#04110b", 3)
    chevron = _icon_file("chevron", MUTED)
    return f"""
    QMainWindow, QDialog, QMessageBox {{ background: {BG}; }}
    QWidget {{ color: {TEXT}; font-size: 13px; }}
    QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 6px; padding: 5px 8px; }}

    /* Sidebar */
    QFrame#Sidebar {{ background: {SIDEBAR}; border: none; border-right: 1px solid {BORDER}; }}
    QLabel#Brand {{ font-size: 15px; font-weight: 700; }}
    QListWidget#Nav {{ background: transparent; border: none; padding: 0; outline: 0; }}
    QListWidget#Nav::item {{ color: {MUTED}; padding: 9px 10px; margin: 1px 10px; border-radius: 8px; }}
    QListWidget#Nav::item:hover {{ background: {RAISED}; color: {TEXT}; }}
    QListWidget#Nav::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

    /* Cards and text */
    QFrame#Card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
    QLabel[role="h1"] {{ font-size: 22px; font-weight: 700; }}
    QLabel[role="h2"] {{ font-size: 14px; font-weight: 600; }}
    QLabel[role="muted"] {{ color: {MUTED}; }}
    QLabel[role="caption"] {{ color: {SUBTLE}; font-size: 11px; }}
    QLabel[role="mono"] {{ color: {TEXT}; font-family: Menlo, Consolas, monospace; }}
    QLabel[role="stat"] {{ font-size: 20px; font-weight: 700; }}
    QLabel[role="banner-warn"] {{ background: #251e0e; color: #fcd34d; border: 1px solid #4a3a12; border-radius: 8px; padding: 8px 12px; }}
    QLabel[role="banner-danger"] {{ background: #2a1215; color: #fca5a5; border: 1px solid #4c1d22; border-radius: 8px; padding: 10px 14px; font-weight: 600; }}
    QLabel[role="pill"] {{ border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600; background: {RAISED}; color: {MUTED}; }}
    QLabel[role="pill"][state="ok"] {{ background: #12301f; color: {OK}; }}
    QLabel[role="pill"][state="warn"] {{ background: #2e2510; color: {WARN}; }}
    QLabel[role="pill"][state="danger"] {{ background: #321519; color: {DANGER}; }}

    /* Buttons */
    QPushButton {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 8px; padding: 7px 14px; }}
    QPushButton:hover {{ background: #232b3a; border-color: #3b4658; }}
    QPushButton:pressed {{ background: #161c27; }}
    QPushButton:disabled {{ background: {CARD}; border-color: {BORDER}; color: {SUBTLE}; }}
    QPushButton::menu-indicator {{ image: none; width: 0; }}
    {_variant("primary", ACCENT, ACCENT, "#04110b", ACCENT_HOVER, 700)}
    {_variant("danger", "#2a1416", "#4a1d22", DANGER, "#371a1d")}
    {_variant("warning", "#291f0d", "#4a3812", WARN, "#342811")}
    {_variant("info", "#13213a", "#1f3a63", INFO, "#182a49")}
    QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; color: {MUTED}; }}
    QPushButton[variant="ghost"]:hover {{ background: {RAISED}; color: {TEXT}; }}

    /* Inputs */
    QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
        background: {INPUT}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
        padding: 6px 10px; selection-background-color: #1f4d36;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
    QTextEdit#Log {{ background: #090d14; border-color: {BORDER}; padding: 8px; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
    QComboBox QAbstractItemView {{ background: {RAISED}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
        selection-background-color: {ACCENT_SOFT}; outline: 0; padding: 4px; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QCheckBox {{ spacing: 8px; color: {MUTED}; }}
    QCheckBox::indicator, QListWidget::indicator {{
        width: 16px; height: 16px; border-radius: 5px; border: 1px solid #455064; background: {INPUT};
    }}
    QCheckBox::indicator:hover, QListWidget::indicator:hover {{ border-color: {ACCENT}; }}
    QCheckBox::indicator:checked, QListWidget::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url({check}); }}

    /* Lists and tables */
    QListWidget, QTableWidget {{ background: {INPUT}; border: 1px solid {BORDER}; border-radius: 10px; padding: 4px; outline: 0; }}
    QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
    QListWidget::item:hover {{ background: #151c27; }}
    QListWidget::item:selected {{ background: {ACCENT_SOFT}; }}
    QTableWidget {{ gridline-color: {BORDER}; padding: 0; }}
    QTableWidget::item {{ padding: 6px; }}
    QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
    QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
        padding: 8px; font-weight: 600; }}
    QTableCornerButton::section {{ background: {CARD}; border: none; }}

    /* Scrollbars */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: #2a3342; border-radius: 3px; }}
    QScrollBar::handle:vertical {{ min-height: 30px; }}
    QScrollBar::handle:horizontal {{ min-width: 30px; }}
    QScrollBar::handle:hover {{ background: #3a4456; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    /* Progress bars */
    QProgressBar {{ background: {INPUT}; border: none; border-radius: 3px; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QProgressBar[level="warn"]::chunk {{ background: {WARN}; }}
    QProgressBar[level="danger"]::chunk {{ background: {DANGER}; }}

    /* Inner tabs (Config) */
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 8px 14px; border: none; border-bottom: 2px solid transparent; }}
    QTabBar::tab:hover {{ color: {TEXT}; }}
    QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}

    /* Menus, status bar, splitters */
    QMenu {{ background: {RAISED}; border: 1px solid {BORDER_STRONG}; border-radius: 8px; padding: 4px; }}
    QMenu::item {{ padding: 6px 16px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
    QStatusBar {{ background: {SIDEBAR}; color: {SUBTLE}; border-top: 1px solid {BORDER}; }}
    QStatusBar::item {{ border: none; }}
    QSplitter::handle {{ background: transparent; }}
    """


def apply(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, INPUT), (QPalette.ColorRole.AlternateBase, CARD),
        (QPalette.ColorRole.Button, RAISED), (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, ACCENT_SOFT),
        (QPalette.ColorRole.HighlightedText, TEXT), (QPalette.ColorRole.ToolTipBase, RAISED),
        (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, SUBTLE),
    ]:
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet())


# ── Helpers ───────────────────────────────────────────────────────────────────

def set_prop(widget: QWidget, name: str, value):
    """Change a styling property and re-apply the stylesheet to the widget."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def button(text: str, variant: str = None, slot=None, tip: str = None) -> QPushButton:
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    if slot:
        btn.clicked.connect(slot)
    if tip:
        btn.setToolTip(tip)
    return btn


def label(text: str = "", role: str = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def card(title: str = None, subtitle: str = None, actions: list = None):
    """A rounded panel. Returns (frame, body_layout); title/actions go in a header row."""
    frame = QFrame()
    frame.setObjectName("Card")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 16)
    outer.setSpacing(12)
    if title or actions:
        header = QHBoxLayout()
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        if title:
            titles.addWidget(label(title, "h2"))
        if subtitle:
            titles.addWidget(label(subtitle, "caption", wrap=True))
        header.addLayout(titles, 1)
        for w in actions or []:
            header.addWidget(w)
        outer.addLayout(header)
    body = QVBoxLayout()
    body.setSpacing(10)
    outer.addLayout(body, 1)
    return frame, body
