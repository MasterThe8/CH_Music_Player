#!/usr/bin/env python3
"""
Lumina Music Player
A modern, elegant music player built with PySide6
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase

from components.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CH Music Player")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CH Music Player")
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # Load custom stylesheet
    stylesheet_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
