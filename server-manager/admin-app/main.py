"""
Minecraft Server Manager — Admin Desktop App
Entry point. Run: python main.py
"""
import sys
import os

# Ensure local imports work when run from any directory
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from ui import theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Minecraft Manager")
    app.setOrganizationName("MinecraftAdmin")

    theme.apply(app)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
