"""
Instructions tab: the same "How to Join" steps players see on the player portal,
as a refresher. The steps are read from the portal's template so the two never drift apart.
"""
import html
import os
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from api_client import api
from thread_manager import run_in_thread
from ui import theme

PORTAL_TEMPLATE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "player-portal", "templates", "index.html"))

_STEP_RE = re.compile(
    r'<span class="step-heading">(.*?)</span>\s*<ul class="step-list">(.*?)</ul>', re.DOTALL)
_ITEM_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)


def _render(version: str, loader: str) -> str:
    try:
        with open(PORTAL_TEMPLATE, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return (f"<p style='color:{theme.DANGER}'>Couldn't find the player portal's instructions at "
                f"{html.escape(PORTAL_TEMPLATE)}.</p>")

    def fill(text: str) -> str:
        # Same substitutions the portal makes, then drop any other template tags
        text = re.sub(r"\{\{\s*version\s*\}\}", html.escape(version), text)
        text = re.sub(r"\{\{\s*loader\s*\}\}", html.escape(loader), text)
        text = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", text)
        text = re.sub(r'\s+class="[^"]*"', "", text)
        return re.sub(r"\s+", " ", text).strip()

    parts = []
    for heading, items in _STEP_RE.findall(src):
        parts.append(f"<h3>{fill(heading)}</h3><ul>")
        parts += [f"<li>{fill(item)}</li>" for item in _ITEM_RE.findall(items)]
        parts.append("</ul>")
    if not parts:
        return f"<p style='color:{theme.DANGER}'>No join steps found in the player portal page.</p>"
    return "".join(parts)


class InstructionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._version = "the server's version"
        self._loader = "the server's NeoForge version"
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        frame, body = theme.card(
            "How to Join",
            "The same steps your friends see on the player portal, for setting up a computer to play "
            "after a long break. Versions shown are what the server is running now.",
        )
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.document().setDefaultStyleSheet(f"""
            h3 {{ color: {theme.TEXT}; font-size: 15px; font-weight: 600; margin-top: 14px; margin-bottom: 4px; }}
            li {{ color: {theme.MUTED}; margin-bottom: 6px; }}
            strong {{ color: {theme.TEXT}; }}
            code {{ font-family: Menlo, Consolas, monospace; color: {theme.TEXT}; background-color: {theme.RAISED}; }}
            a {{ color: {theme.ACCENT}; }}
        """)
        body.addWidget(self.view)
        root.addWidget(frame)
        self._show()

    def _show(self):
        self.view.setHtml(_render(self._version, self._loader))

    def refresh(self):
        def apply(status):
            if status and "error" not in status:
                self._version = status.get("version") or self._version
                self._loader = status.get("loader") or self._loader
            self._show()
        run_in_thread(api.get_status, apply)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
