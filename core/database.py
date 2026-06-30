import os
import sqlite3
import time
import json
from typing import List

DB_PATH = "database/library.db"


class Database:

    def __init__(self):

        # Auto-create database folder
        os.makedirs("database", exist_ok=True)

        self.conn = sqlite3.connect(DB_PATH)

        # Access row by column name
        self.conn.row_factory = sqlite3.Row

        self.cursor = self.conn.cursor()

        # Enable foreign keys
        self.cursor.execute("PRAGMA foreign_keys = ON")

        # Create schema
        self.create_tables()

    # =====================================================
    # BASIC QUERY
    # =====================================================

    def execute(self, query, params=()):

        self.cursor.execute(query, params)
        self.conn.commit()

    def executemany(self, query, params_list):

        self.cursor.executemany(query, params_list)
        self.conn.commit()

    def fetchall(self, query, params=()):

        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fetchone(self, query, params=()):

        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    # =====================================================
    # TABLE CREATION
    # =====================================================

    def create_tables(self):

        # =================================================
        # SONGS
        # =================================================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT,
            artist TEXT,
            album TEXT,
            charter TEXT,
            genre TEXT,
            year TEXT,

            folder_path TEXT UNIQUE,

            song_ini_path TEXT,
            chart_path TEXT,
            album_art_path TEXT,

            song_audio_path TEXT,
            audio_tracks TEXT,

            duration_ms INTEGER,

            lyrics TEXT,

            folder_modified INTEGER DEFAULT 0,

            play_count INTEGER DEFAULT 0,
            favorite INTEGER DEFAULT 0,

            created_at INTEGER,
            updated_at INTEGER
        )
        """)

        # =================================================
        # SCAN ROOTS
        # =================================================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_roots (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            root_path TEXT UNIQUE,

            enabled INTEGER DEFAULT 1
        )
        """)

        # =================================================
        # PLAYLISTS
        # =================================================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT,

            created_at INTEGER
        )
        """)

        # =================================================
        # PLAYLIST SONGS
        # =================================================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_songs (

            playlist_id INTEGER,
            song_id INTEGER,
            position INTEGER,

            PRIMARY KEY (playlist_id, song_id),

            FOREIGN KEY(playlist_id)
                REFERENCES playlists(id)
                ON DELETE CASCADE,

            FOREIGN KEY(song_id)
                REFERENCES songs(id)
                ON DELETE CASCADE
        )
        """)

        # =================================================
        # PLAY HISTORY
        # =================================================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS play_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            song_id INTEGER,

            played_at INTEGER,

            FOREIGN KEY(song_id)
                REFERENCES songs(id)
                ON DELETE CASCADE
        )
        """)

        # =================================================
        # INDEXES
        # =================================================

        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_song_title
        ON songs(title)
        """)

        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_song_artist
        ON songs(artist)
        """)

        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_song_album
        ON songs(album)
        """)

        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_song_folder
        ON songs(folder_path)
        """)

        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_song
        ON play_history(song_id)
        """)

        self.conn.commit()

    # =====================================================
    # SONGS
    # =====================================================

    def upsert_song(self, song):

        current_time = int(time.time())

        self.execute("""
        INSERT INTO songs (

            title,
            artist,
            album,
            charter,
            genre,
            year,

            folder_path,

            song_ini_path,
            chart_path,
            album_art_path,
            song_audio_path,
            audio_tracks,
            duration_ms,
            lyrics,
            folder_modified,

            created_at,
            updated_at

        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(folder_path)
        DO UPDATE SET

            title=excluded.title,
            artist=excluded.artist,
            album=excluded.album,
            charter=excluded.charter,
            genre=excluded.genre,
            year=excluded.year,
            lyrics=excluded.lyrics,
            song_ini_path=excluded.song_ini_path,
            chart_path=excluded.chart_path,
            album_art_path=excluded.album_art_path,
            song_audio_path=excluded.song_audio_path,
            audio_tracks=excluded.audio_tracks,
            duration_ms=excluded.duration_ms,
            folder_modified=excluded.folder_modified,

            updated_at=excluded.updated_at
        """, (

            song.name,
            song.artist,
            song.album,
            song.charter,
            song.genre,
            song.year,

            song.folder_path,

            song.song_ini,
            song.chart_file,
            song.album_art,
            song.main_audio,
            json.dumps(song.audio_tracks),
            song.duration_ms,
            song.lyrics,
            int(os.path.getmtime(song.folder_path)),

            current_time,
            current_time
        ))

        # Return song_id
        result = self.fetchone("""
        SELECT id
        FROM songs
        WHERE folder_path=?
        """, (song.folder_path,))

        return result["id"]

    # =====================================================
    # PLAY HISTORY
    # =====================================================

    def add_play_history(self, song_id):

        self.execute("""
        INSERT INTO play_history (
            song_id,
            played_at
        )
        VALUES (?, ?)
        """, (
            song_id,
            int(time.time())
        ))

        self.execute("""
        UPDATE songs
        SET play_count = play_count + 1
        WHERE id=?
        """, (song_id,))

    # =====================================================
    # FAVORITE
    # =====================================================

    def set_favorite(self, song_id, favorite=True):

        self.execute("""
        UPDATE songs
        SET favorite=?
        WHERE id=?
        """, (
            1 if favorite else 0,
            song_id
        ))

    # =====================================================
    # QUERY HELPERS
    # =====================================================

    def get_all_songs(self):

        return self.fetchall("""
        SELECT *
        FROM songs
        ORDER BY artist, title
        """)

    def search_songs(self, keyword):

        keyword = f"%{keyword}%"

        return self.fetchall("""
        SELECT *
        FROM songs
        WHERE
            title LIKE ?
            OR artist LIKE ?
            OR album LIKE ?
            OR year LIKE ?
            OR genre LIKE ?
            OR charter LIKE ?
        ORDER BY artist, title
        """, (
            keyword,
            keyword,
            keyword,
            keyword,
            keyword,
            keyword
        ))

    def get_song_by_id(self, song_id):

        return self.fetchone("""
        SELECT *
        FROM songs
        WHERE id=?
        """, (song_id,))

    def get_audio_tracks(self, song_id):

        result = self.fetchone("""
        SELECT audio_tracks
        FROM songs
        WHERE id=?
        """, (song_id,))

        if not result:
            return {}

        try:
            return json.loads(
                result["audio_tracks"] or "{}"
            )
        except:
            return {}

    def get_recently_played(self, limit=50):

        return self.fetchall("""
        SELECT
            songs.*,
            play_history.played_at
        FROM play_history

        JOIN songs
            ON songs.id = play_history.song_id

        ORDER BY play_history.played_at DESC
        LIMIT ?
        """, (limit,))

    def get_favorites(self):

        return self.fetchall("""
        SELECT *
        FROM songs
        WHERE favorite = 1
        ORDER BY artist, title
        """)

    # =====================================================
    # PLAYLISTS
    # =====================================================

    def get_all_playlists(self):

        return self.fetchall("""
        SELECT
            playlists.*,
            COUNT(playlist_songs.song_id) AS song_count
        FROM playlists
        LEFT JOIN playlist_songs
            ON playlists.id = playlist_songs.playlist_id
        GROUP BY playlists.id
        ORDER BY playlists.name
        """)

    def create_playlist(self, name):

        self.execute("""
        INSERT INTO playlists (name, created_at)
        VALUES (?, ?)
        """, (name, int(time.time())))

        return self.cursor.lastrowid

    def get_playlist_songs(self, playlist_id):

        return self.fetchall("""
        SELECT songs.*
        FROM playlist_songs
        JOIN songs ON songs.id = playlist_songs.song_id
        WHERE playlist_songs.playlist_id = ?
        ORDER BY playlist_songs.position
        """, (playlist_id,))

    def get_playlist_by_name(self, name):

        return self.fetchone("""
        SELECT *
        FROM playlists
        WHERE name=?
        """, (name,))

    def add_song_to_playlist(self, playlist_id, song_id, position=None):
        """Add a song to a playlist. Returns True if added, False if already exists."""

        existing = self.fetchone("""
        SELECT 1 FROM playlist_songs
        WHERE playlist_id=? AND song_id=?
        """, (playlist_id, song_id))

        if existing:
            if position is not None:
                self.execute("""
                UPDATE playlist_songs
                SET position=?
                WHERE playlist_id=? AND song_id=?
                """, (position, playlist_id, song_id))
            return False

        if position is None:
            # Get next position
            result = self.fetchone("""
            SELECT COALESCE(MAX(position), 0) + 1 AS next_pos
            FROM playlist_songs
            WHERE playlist_id=?
            """, (playlist_id,))

            position = result["next_pos"] if result else 1

        self.execute("""
        INSERT INTO playlist_songs (playlist_id, song_id, position)
        VALUES (?, ?, ?)
        """, (playlist_id, song_id, position))

        return True

    def remove_song_from_playlist(self, playlist_id, song_id):
        """Remove a song from a playlist."""

        self.execute("""
        DELETE FROM playlist_songs
        WHERE playlist_id=? AND song_id=?
        """, (playlist_id, song_id))

    def delete_playlist(self, playlist_id):
        """Delete a playlist and all its song associations."""

        self.execute("""
        DELETE FROM playlist_songs
        WHERE playlist_id=?
        """, (playlist_id,))

        self.execute("""
        DELETE FROM playlists
        WHERE id=?
        """, (playlist_id,))

    def rename_playlist(self, playlist_id, new_name):
        """Rename a playlist."""

        self.execute("""
        UPDATE playlists
        SET name=?
        WHERE id=?
        """, (new_name, playlist_id))

    # =====================================================
    # SCAN ROOTS
    # =====================================================

    def add_scan_root(self, root_path):

        self.execute("""
        INSERT OR IGNORE INTO scan_roots (root_path)
        VALUES (?)
        """, (root_path,))

    def get_scan_roots(self):

        return self.fetchall("""
        SELECT root_path
        FROM scan_roots
        WHERE enabled = 1
        """)

    # =====================================================
    # FAST RESCAN
    # =====================================================

    def needs_rescan(self, folder_path, import_lyrics=False):

        result = self.fetchone("""
        SELECT folder_modified, lyrics
        FROM songs
        WHERE folder_path=?
        """, (folder_path,))

        # Song not exists
        if result is None:
            return True

        current_modified = int(os.path.getmtime(folder_path))

        if current_modified != result["folder_modified"]:
            return True

        if import_lyrics and not result["lyrics"]:
            return True

        return False

    # =====================================================
    # ROW → SONG PACKAGE
    # =====================================================

    @staticmethod
    def row_to_song_package(row):
        """Convert a sqlite3.Row to a SongPackage dataclass."""
        from utils.scanner import SongPackage

        audio_tracks = {}
        try:
            audio_tracks = json.loads(row["audio_tracks"] or "{}")
        except Exception:
            pass

        return SongPackage(
            folder_path=row["folder_path"] or "",
            name=row["title"] or "Unknown Song",
            artist=row["artist"] or "Unknown Artist",
            album=row["album"] or "",
            charter=row["charter"] or "",
            genre=row["genre"] or "",
            year=row["year"] or "",
            duration_ms=row["duration_ms"] or 0,
            song_ini=row["song_ini_path"],
            chart_file=row["chart_path"],
            album_art=row["album_art_path"],
            audio_tracks=audio_tracks,
            main_audio=row["song_audio_path"],
            lyrics=row["lyrics"] or "",
            created_at=row["created_at"] or 0,
        )

    @staticmethod
    def rows_to_song_packages(rows) -> List:
        """Convert a list of sqlite3.Row to SongPackage list."""
        return [Database.row_to_song_package(r) for r in rows]

    # =====================================================
    # CLEANUP
    # =====================================================

    def close(self):

        self.conn.close()