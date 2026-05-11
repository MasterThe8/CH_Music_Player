"""
Metadata Scanner - Scans music folders and extracts song metadata
Supports: MP3, FLAC, WAV, OGG, M4A, AAC
"""

import os
import hashlib
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, QThreadPool, QMutex

from utils.database import DatabaseManager, Song

SUPPORTED_FORMATS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma", ".opus"}


def format_duration(seconds: float) -> str:
    """Convert seconds to mm:ss or hh:mm:ss string."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def extract_metadata(file_path: str) -> dict:
    """
    Extract metadata from an audio file.
    Returns a dict with title, artist, album, duration, etc.
    Uses mutagen if available, otherwise falls back to filename parsing.
    """
    meta = {
        "title": os.path.splitext(os.path.basename(file_path))[0],
        "artist": "Unknown Artist",
        "album": "Unknown Album",
        "duration": 0.0,
        "genre": "",
        "year": "",
        "track_number": 0,
        "cover_art": None,
        "lyrics": None,
    }

    try:
        import mutagen
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.oggvorbis import OggVorbis
        from mutagen.id3 import ID3NoHeaderError

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".mp3":
            try:
                audio = MP3(file_path)
                meta["duration"] = audio.info.length
                tags = audio.tags
                if tags:
                    meta["title"] = str(tags.get("TIT2", meta["title"]))
                    meta["artist"] = str(tags.get("TPE1", meta["artist"]))
                    meta["album"] = str(tags.get("TALB", meta["album"]))
                    meta["genre"] = str(tags.get("TCON", ""))
                    meta["year"] = str(tags.get("TDRC", ""))
                    tn = str(tags.get("TRCK", "0")).split("/")[0]
                    meta["track_number"] = int(tn) if tn.isdigit() else 0
                    # Embedded lyrics
                    for key in tags.keys():
                        if key.startswith("USLT"):
                            meta["lyrics"] = tags[key].text
                            break
                    # Cover art
                    for key in tags.keys():
                        if key.startswith("APIC"):
                            import base64
                            meta["cover_art"] = base64.b64encode(tags[key].data).decode()
                            break
            except Exception:
                pass

        elif ext == ".flac":
            try:
                audio = FLAC(file_path)
                meta["duration"] = audio.info.length
                meta["title"] = audio.get("title", [meta["title"]])[0]
                meta["artist"] = audio.get("artist", [meta["artist"]])[0]
                meta["album"] = audio.get("album", [meta["album"]])[0]
                meta["genre"] = audio.get("genre", [""])[0]
                meta["year"] = audio.get("date", [""])[0]
                tn = audio.get("tracknumber", ["0"])[0].split("/")[0]
                meta["track_number"] = int(tn) if tn.isdigit() else 0
                meta["lyrics"] = audio.get("lyrics", [None])[0]
                if audio.pictures:
                    import base64
                    meta["cover_art"] = base64.b64encode(audio.pictures[0].data).decode()
            except Exception:
                pass

        elif ext in (".m4a", ".aac", ".mp4"):
            try:
                audio = MP4(file_path)
                meta["duration"] = audio.info.length
                tags = audio.tags or {}
                meta["title"] = str(tags.get("\xa9nam", [meta["title"]])[0])
                meta["artist"] = str(tags.get("\xa9ART", [meta["artist"]])[0])
                meta["album"] = str(tags.get("\xa9alb", [meta["album"]])[0])
                meta["genre"] = str(tags.get("\xa9gen", [""])[0])
                meta["year"] = str(tags.get("\xa9day", [""])[0])
                tn = tags.get("trkn", [(0, 0)])[0]
                meta["track_number"] = tn[0] if isinstance(tn, tuple) else 0
                if "covr" in tags:
                    import base64
                    meta["cover_art"] = base64.b64encode(bytes(tags["covr"][0])).decode()
            except Exception:
                pass

        elif ext == ".ogg":
            try:
                audio = OggVorbis(file_path)
                meta["duration"] = audio.info.length
                meta["title"] = audio.get("title", [meta["title"]])[0]
                meta["artist"] = audio.get("artist", [meta["artist"]])[0]
                meta["album"] = audio.get("album", [meta["album"]])[0]
                meta["genre"] = audio.get("genre", [""])[0]
                meta["year"] = audio.get("date", [""])[0]
            except Exception:
                pass

        else:
            # Fallback: try generic mutagen
            try:
                audio = mutagen.File(file_path)
                if audio and hasattr(audio, "info"):
                    meta["duration"] = audio.info.length
            except Exception:
                pass

    except ImportError:
        # mutagen not installed — try basic duration via wave for WAVs
        if file_path.endswith(".wav"):
            try:
                import wave
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    meta["duration"] = frames / float(rate)
            except Exception:
                pass

    return meta


# ─── Scanner Worker ───────────────────────────────────────────────────────────

class ScanWorker(QObject):
    """Runs in a QThread to scan folders without blocking the UI."""

    progress = Signal(int, int, str)     # current, total, filename
    song_found = Signal(object)          # Song
    finished = Signal(int)               # total songs added
    error = Signal(str)

    def __init__(self, folders: list[str], db: DatabaseManager):
        super().__init__()
        self._folders = folders
        self._db = db
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        all_files = []
        for folder in self._folders:
            if not os.path.isdir(folder):
                continue
            for root, _, files in os.walk(folder):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SUPPORTED_FORMATS:
                        all_files.append(os.path.join(root, fname))

        total = len(all_files)
        added = 0

        for i, file_path in enumerate(all_files):
            if self._cancelled:
                break
            self.progress.emit(i + 1, total, os.path.basename(file_path))

            try:
                if self._db.song_exists(file_path):
                    continue

                meta = extract_metadata(file_path)
                song_id = Song.generate_id(file_path)
                song = Song(
                    id=song_id,
                    file_path=file_path,
                    title=meta["title"],
                    artist=meta["artist"],
                    album=meta["album"],
                    duration=meta["duration"],
                    cover_art=meta.get("cover_art"),
                    lyrics=meta.get("lyrics"),
                    genre=meta.get("genre", ""),
                    year=str(meta.get("year", "")),
                    track_number=meta.get("track_number", 0),
                )
                self._db.add_song(song)
                self.song_found.emit(song)
                added += 1
            except Exception as e:
                self.error.emit(f"Error scanning {file_path}: {e}")

        self.finished.emit(added)


class FolderScanner(QObject):
    """
    High-level scanner that manages the scan thread lifecycle.
    """

    scan_started = Signal()
    scan_progress = Signal(int, int, str)
    song_found = Signal(object)
    scan_finished = Signal(int)
    scan_error = Signal(str)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._thread: Optional[QThread] = None
        self._worker: Optional[ScanWorker] = None

    def scan_folders(self, folders: list[str]):
        if self._thread and self._thread.isRunning():
            self.cancel()

        self._thread = QThread(self)
        self._worker = ScanWorker(folders, self._db)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.scan_progress)
        self._worker.song_found.connect(self.song_found)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self.scan_error)

        self.scan_started.emit()
        self._thread.start()

    def cancel(self):
        if self._worker:
            self._worker.cancel()
        if self._thread:
            self._thread.quit()
            self._thread.wait()

    def _on_finished(self, count: int):
        self.scan_finished.emit(count)
        if self._thread:
            self._thread.quit()
