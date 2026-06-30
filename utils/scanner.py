"""
Metadata Scanner - Clone Hero song scanner
"""

import os
import re
import configparser

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils.lyrics_scanner import LyricsScanner
from utils.mid_parser import MidiLyricsScanner
from core.database import Database

# =========================================================
# UTILITY
# =========================================================

def format_duration(seconds: float) -> str:
    """Convert seconds to mm:ss or hh:mm:ss string."""

    seconds = int(seconds)

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"

    return f"{m}:{s:02d}"


# =========================================================
# CONFIG
# =========================================================

SUPPORTED_AUDIO = (
    ".ogg",
    ".mp3",
    ".opus",
    ".wav",
    ".flac"
)

SUPPORTED_IMAGE = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp"
)

CHART_PRIORITY = [
    "notes.chart",
    "song.chart"
]

ALBUM_ART_PRIORITY = [
    "album.png",
    "album.jpg",
    "album.jpeg"
]


# =========================================================
# DATA MODEL
# =========================================================

@dataclass
class SongPackage:

    folder_path: str

    # Metadata
    name: str = "Unknown Song"
    artist: str = "Unknown Artist"
    album: str = ""
    charter: str = ""
    genre: str = ""
    year: str = ""

    duration_ms: int = 0

    # Files
    song_ini: Optional[str] = None
    chart_file: Optional[str] = None
    album_art: Optional[str] = None

    # Audio
    audio_tracks: Dict[str, str] = field(default_factory=dict)
    main_audio: Optional[str] = None

    # Lyrics
    lyrics: str = ""

    # Playlist
    playlist: str = ""
    playlist_track: Optional[int] = None

    # Timestamps
    created_at: int = 0


# =========================================================
# MAIN SCANNER
# =========================================================

class CHSongScanner:

    def __init__(self, songs_root: str):

        self.songs_root = songs_root

        self._lyrics_scanner = LyricsScanner()

        self.db = Database()

    # =====================================================
    # PUBLIC
    # =====================================================

    def scan(self, import_lyrics: bool = True) -> List[SongPackage]:

        song_list = []

        for root, dirs, files in os.walk(self.songs_root):

            # -----------------------------
            # Detect song folder
            # -----------------------------
            if not self._is_song_folder(files):
                continue

            # -----------------------------
            # Fast rescan check
            # -----------------------------
            if not self.db.needs_rescan(root, import_lyrics=import_lyrics):
                continue

            try:

                song_data = self._scan_song_folder(
                    root,
                    files,
                    import_lyrics=import_lyrics
                )

                song_list.append(song_data)

            except Exception as e:

                print(f"[ERROR] Failed scanning: {root}")
                print(e)

        return song_list

    # =====================================================
    # SONG FOLDER CHECK
    # =====================================================

    def _is_song_folder(self, files: List[str]) -> bool:

        has_ini = any(
            f.lower() == "song.ini"
            for f in files
        )

        has_chart = any(
            f.lower().endswith(".chart") or
            f.lower().endswith(".mid")
            for f in files
        )

        has_audio = any(
            f.lower().endswith(SUPPORTED_AUDIO)
            for f in files
        )

        return has_ini and has_chart and has_audio

    # =====================================================
    # SCAN SINGLE SONG
    # =====================================================

    def _scan_song_folder(
        self,
        folder_path: str,
        files: List[str],
        import_lyrics: bool = True
    ) -> SongPackage:

        song = SongPackage(
            folder_path=folder_path
        )

        # -----------------------------
        # song.ini
        # -----------------------------
        song_ini = self._find_song_ini(
            folder_path,
            files
        )

        if song_ini:
            self._parse_song_ini(
                song,
                song_ini
            )

        # -----------------------------
        # chart
        # -----------------------------
        song.chart_file = self._find_chart(
            folder_path,
            files
        )

        # -----------------------------
        # lyrics
        # -----------------------------
        if import_lyrics:
            if (
                song.chart_file and
                song.chart_file.lower().endswith(".chart")
            ):

                song.lyrics = (
                    self._lyrics_scanner.extract_lyrics(
                        song.chart_file
                    )
                )

            elif (
                song.chart_file and
                song.chart_file.lower().endswith(".mid")
            ):

                song.lyrics = (
                    MidiLyricsScanner.extract_lyrics(
                        song.chart_file
                    )
                )

        # -----------------------------
        # album art
        # -----------------------------
        song.album_art = self._find_album_art(
            folder_path,
            files
        )

        # -----------------------------
        # audio tracks
        # -----------------------------
        song.audio_tracks = self._detect_audio_tracks(
            folder_path,
            files
        )

        # Main playback audio
        song.main_audio = (
            song.audio_tracks.get("song")
            or next(
                iter(song.audio_tracks.values()),
                None
            )
        )

        # -----------------------------
        # fallback name
        # -----------------------------
        if song.name == "Unknown Song":

            song.name = os.path.basename(
                folder_path
            )

        # -----------------------------
        # Save database
        # -----------------------------
        self._save_to_database(song)

        return song

    # =====================================================
    # FINDERS
    # =====================================================

    def _find_song_ini(
        self,
        folder_path,
        files
    ):

        for file in files:

            if file.lower() == "song.ini":

                return os.path.join(
                    folder_path,
                    file
                )

        return None

    def _find_chart(
        self,
        folder_path,
        files
    ):

        lower_map = {
            f.lower(): f
            for f in files
        }

        # -----------------------------
        # Priority search
        # -----------------------------
        for priority_name in CHART_PRIORITY:

            if priority_name in lower_map:

                return os.path.join(
                    folder_path,
                    lower_map[priority_name]
                )

        # -----------------------------
        # Fallback .chart
        # -----------------------------
        for file in files:

            if file.lower().endswith(".chart"):

                return os.path.join(
                    folder_path,
                    file
                )

        # -----------------------------
        # Fallback .mid
        # -----------------------------
        for file in files:

            if file.lower().endswith(".mid"):

                return os.path.join(
                    folder_path,
                    file
                )

        return None

    def _find_album_art(
        self,
        folder_path,
        files
    ):

        lower_map = {
            f.lower(): f
            for f in files
        }

        # -----------------------------
        # Priority search
        # -----------------------------
        for priority_name in ALBUM_ART_PRIORITY:

            if priority_name in lower_map:

                return os.path.join(
                    folder_path,
                    lower_map[priority_name]
                )

        # -----------------------------
        # Fallback image
        # -----------------------------
        for file in files:

            if file.lower().endswith(
                SUPPORTED_IMAGE
            ):

                return os.path.join(
                    folder_path,
                    file
                )

        return None

    # =====================================================
    # PARSE song.ini
    # =====================================================

    def _parse_song_ini(
        self,
        song: SongPackage,
        ini_path: str
    ):

        parser = configparser.ConfigParser(
            strict=False,
            interpolation=None
        )

        # -----------------------------
        # Try multiple encodings
        # -----------------------------
        for encoding in (
            "utf-8-sig",
            "utf-8",
            "latin-1"
        ):

            try:

                parser.read(
                    ini_path,
                    encoding=encoding
                )

                if parser.sections():
                    break

            except Exception:
                continue

        # -----------------------------
        # Find [Song] section
        # -----------------------------
        section = None

        for sec_name in parser.sections():

            if sec_name.lower() == "song":

                section = parser[sec_name]
                break

        if section is None:
            return

        try:

            song.song_ini = ini_path

            song.name = self._strip_tags(
                section.get(
                    "name",
                    song.name
                )
            )

            song.artist = self._strip_tags(
                section.get(
                    "artist",
                    song.artist
                )
            )

            song.album = self._strip_tags(
                section.get(
                    "album",
                    ""
                )
            )

            song.charter = self._strip_tags(
                section.get(
                    "charter",
                    ""
                )
            )

            song.genre = self._strip_tags(
                section.get(
                    "genre",
                    ""
                )
            )

            song.year = self._strip_tags(
                section.get(
                    "year",
                    ""
                )
            )

            song.playlist = self._strip_tags(
                section.get(
                    "playlist",
                    ""
                )
            )

            try:
                track_str = section.get("playlist_track", "")
                if track_str:
                    song.playlist_track = int(track_str)
            except ValueError:
                song.playlist_track = None

            # song_length in milliseconds
            try:

                song.duration_ms = int(
                    section.get(
                        "song_length",
                        "0"
                    )
                )

            except ValueError:

                song.duration_ms = 0

        except Exception as e:

            print(
                f"[WARNING] Failed parsing INI: {ini_path}"
            )

            print(e)

    # =====================================================
    # TAG STRIPPING
    # =====================================================

    _TAG_RE = re.compile(r"<[^>]+>")

    @staticmethod
    def _strip_tags(value: str) -> str:

        return CHSongScanner._TAG_RE.sub(
            "",
            value
        ).strip()

    # =====================================================
    # AUDIO DETECTOR
    # =====================================================

    def _detect_audio_tracks(
        self,
        folder_path,
        files
    ):

        tracks = {}

        # -----------------------------
        # Official/valid stem names
        # -----------------------------
        VALID_TRACKS = {
            "song",
            "guitar",
            "bass",
            "drums",
            "drums_1",
            "drums_2",
            "drums_3",
            "drums_4",
            "vocals",
            "keys",
            "rhythm",
            "crowd",
        }

        for file in files:

            lower = file.lower()

            # -----------------------------
            # Audio extension check
            # -----------------------------
            if not lower.endswith(
                SUPPORTED_AUDIO
            ):
                continue

            # filename without extension
            name = os.path.splitext(lower)[0]

            # -----------------------------
            # Filter invalid stems
            # -----------------------------
            if name not in VALID_TRACKS:
                continue

            tracks[name] = os.path.join(
                folder_path,
                file
            )

        return tracks

    # =====================================================
    # DATABASE
    # =====================================================

    def _save_to_database(
        self,
        song: SongPackage
    ):

        # Save/update song
        song_id = self.db.upsert_song(song)

        # Handle playlist assignment
        if song.playlist:
            playlist = self.db.get_playlist_by_name(song.playlist)
            if playlist:
                playlist_id = playlist["id"]
            else:
                playlist_id = self.db.create_playlist(song.playlist)

            self.db.add_song_to_playlist(
                playlist_id,
                song_id,
                position=song.playlist_track
            )

        # Future:
        # save sections here
        # self.db.replace_sections(song_id, sections_data)