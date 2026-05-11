"""
Database Manager - JSON-based persistence layer for Lumina Music Player
Handles playlists, song metadata, playback state, and settings
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Song:
    id: str
    title: str
    artist: str
    album: str
    duration: float          # seconds
    file_path: str
    cover_art: Optional[str] = None   # base64 or file path
    lyrics: Optional[str] = None
    genre: str = ""
    year: str = ""
    track_number: int = 0
    play_count: int = 0
    last_played: Optional[str] = None
    date_added: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Song":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @staticmethod
    def generate_id(file_path: str) -> str:
        return hashlib.md5(file_path.encode()).hexdigest()[:12]


@dataclass
class Playlist:
    id: str
    name: str
    description: str = ""
    cover_art: Optional[str] = None
    song_ids: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Playlist":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AppSettings:
    volume: float = 0.7
    shuffle: bool = False
    repeat_mode: str = "none"          # none | one | all
    last_playlist_id: Optional[str] = None
    last_song_id: Optional[str] = None
    last_position: float = 0.0
    show_playlist_panel: bool = True
    show_now_playing_panel: bool = True
    theme: str = "dark_blue"
    equalizer_preset: str = "flat"
    music_folders: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Database Manager ─────────────────────────────────────────────────────────

class DatabaseManager:
    """
    JSON-based database manager.
    All data is stored in ~/.lumina/db.json
    """

    DEFAULT_DB_DIR = os.path.join(os.path.expanduser("~"), ".lumina")
    DB_FILE = "db.json"

    def __init__(self, db_dir: Optional[str] = None):
        self.db_dir = db_dir or self.DEFAULT_DB_DIR
        self.db_path = os.path.join(self.db_dir, self.DB_FILE)
        self._data: dict = {}
        self._ensure_dir()
        self._load()

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _ensure_dir(self):
        os.makedirs(self.db_dir, exist_ok=True)

    def _default_db(self) -> dict:
        return {
            "version": "1.0",
            "songs": {},
            "playlists": {},
            "settings": AppSettings().to_dict(),
            "queue": [],
            "history": [],
        }

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = self._default_db()
        else:
            self._data = self._default_db()
            self._save()

    def _save(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[DB] Failed to save: {e}")

    # ── Songs ─────────────────────────────────────────────────────────────────

    def add_song(self, song: Song) -> Song:
        self._data["songs"][song.id] = song.to_dict()
        self._save()
        return song

    def get_song(self, song_id: str) -> Optional[Song]:
        data = self._data["songs"].get(song_id)
        return Song.from_dict(data) if data else None

    def get_all_songs(self) -> list[Song]:
        return [Song.from_dict(d) for d in self._data["songs"].values()]

    def update_song(self, song: Song):
        if song.id in self._data["songs"]:
            self._data["songs"][song.id] = song.to_dict()
            self._save()

    def delete_song(self, song_id: str):
        self._data["songs"].pop(song_id, None)
        # Remove from all playlists
        for playlist in self._data["playlists"].values():
            if song_id in playlist.get("song_ids", []):
                playlist["song_ids"].remove(song_id)
        self._save()

    def song_exists(self, file_path: str) -> bool:
        song_id = Song.generate_id(file_path)
        return song_id in self._data["songs"]

    def increment_play_count(self, song_id: str):
        if song_id in self._data["songs"]:
            self._data["songs"][song_id]["play_count"] += 1
            self._data["songs"][song_id]["last_played"] = datetime.now().isoformat()
            self._save()

    def update_lyrics(self, song_id: str, lyrics: str):
        if song_id in self._data["songs"]:
            self._data["songs"][song_id]["lyrics"] = lyrics
            self._save()

    # ── Playlists ─────────────────────────────────────────────────────────────

    def create_playlist(self, name: str, description: str = "") -> Playlist:
        playlist_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:10]
        playlist = Playlist(id=playlist_id, name=name, description=description)
        self._data["playlists"][playlist_id] = playlist.to_dict()
        self._save()
        return playlist

    def get_playlist(self, playlist_id: str) -> Optional[Playlist]:
        data = self._data["playlists"].get(playlist_id)
        return Playlist.from_dict(data) if data else None

    def get_all_playlists(self) -> list[Playlist]:
        return [Playlist.from_dict(d) for d in self._data["playlists"].values()]

    def update_playlist(self, playlist: Playlist):
        if playlist.id in self._data["playlists"]:
            playlist.updated_at = datetime.now().isoformat()
            self._data["playlists"][playlist.id] = playlist.to_dict()
            self._save()

    def delete_playlist(self, playlist_id: str):
        self._data["playlists"].pop(playlist_id, None)
        self._save()

    def add_song_to_playlist(self, playlist_id: str, song_id: str):
        playlist_data = self._data["playlists"].get(playlist_id)
        if playlist_data and song_id not in playlist_data["song_ids"]:
            playlist_data["song_ids"].append(song_id)
            playlist_data["updated_at"] = datetime.now().isoformat()
            self._save()

    def remove_song_from_playlist(self, playlist_id: str, song_id: str):
        playlist_data = self._data["playlists"].get(playlist_id)
        if playlist_data and song_id in playlist_data["song_ids"]:
            playlist_data["song_ids"].remove(song_id)
            playlist_data["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_playlist_songs(self, playlist_id: str) -> list[Song]:
        playlist_data = self._data["playlists"].get(playlist_id)
        if not playlist_data:
            return []
        songs = []
        for song_id in playlist_data.get("song_ids", []):
            song = self.get_song(song_id)
            if song:
                songs.append(song)
        return songs

    # ── Settings ─────────────────────────────────────────────────────────────

    def get_settings(self) -> AppSettings:
        return AppSettings.from_dict(self._data.get("settings", {}))

    def save_settings(self, settings: AppSettings):
        self._data["settings"] = settings.to_dict()
        self._save()

    def update_setting(self, key: str, value):
        self._data["settings"][key] = value
        self._save()

    # ── Queue & History ───────────────────────────────────────────────────────

    def save_queue(self, song_ids: list[str]):
        self._data["queue"] = song_ids
        self._save()

    def get_queue(self) -> list[str]:
        return self._data.get("queue", [])

    def add_to_history(self, song_id: str, max_history: int = 50):
        history = self._data.get("history", [])
        if song_id in history:
            history.remove(song_id)
        history.insert(0, song_id)
        self._data["history"] = history[:max_history]
        self._save()

    def get_history(self) -> list[Song]:
        history_ids = self._data.get("history", [])
        songs = []
        for song_id in history_ids:
            song = self.get_song(song_id)
            if song:
                songs.append(song)
        return songs

    # ── Search ────────────────────────────────────────────────────────────────

    def search_songs(self, query: str) -> list[Song]:
        query = query.lower()
        results = []
        for song in self.get_all_songs():
            if (query in song.title.lower() or
                query in song.artist.lower() or
                query in song.album.lower()):
                results.append(song)
        return results
