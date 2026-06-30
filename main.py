import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtCore import Qt
from core.database import Database
from utils.audio_engine import AudioEngine
from components.main_window import MainWindow

def get_base_path():
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def main():
    # Initialize backend services
    db = Database()

    app = QApplication(sys.argv)
    
    # ── FIX: Force 'Fusion' style so CSS renders correctly on compiled exe ──
    app.setStyle("Fusion")
    
    app.setApplicationName("CH Music Player")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CH Music Player")
    
    base_path = get_base_path()
    app.setWindowIcon(QIcon(os.path.join(base_path, "assets", "icon.ico")))

    # Audio engine (needs QApplication to exist for QTimer)
    audio_engine = AudioEngine()

    # Load custom stylesheet safely
    stylesheet_path = os.path.join(base_path, "assets", "style.qss")
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"[Warning] Stylesheet not found at: {stylesheet_path}")

    # Create main window with backend dependencies
    window = MainWindow(db, audio_engine)
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
