"""
Scan Worker - Background QThread for scanning Clone Hero songs
"""

from PySide6.QtCore import QThread, Signal
from utils.scanner import CHSongScanner


class ScanWorker(QThread):
    """Runs CHSongScanner.scan() in a background thread."""

    # Signals
    progress = Signal(str)          # status message
    finished = Signal(list)         # list of SongPackage
    error = Signal(str)             # error message

    def __init__(self, root_path: str, import_lyrics: bool = True, parent=None):
        super().__init__(parent)
        self.root_path = root_path
        self.import_lyrics = import_lyrics

    def run(self):
        try:
            self.progress.emit(f"Scanning: {self.root_path}")

            scanner = CHSongScanner(self.root_path)
            songs = scanner.scan(import_lyrics=self.import_lyrics)

            self.progress.emit(f"Found {len(songs)} new songs")
            self.finished.emit(songs)

        except Exception as e:
            self.error.emit(str(e))
