"""
Main Panel - Center content area
Switches between: Song Library View ↔ Lyrics View
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QScrollArea, QSizePolicy, QAbstractItemView,
    QMenu, QStackedWidget, QComboBox
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap, QIcon

from utils.database import DatabaseManager, Song, Playlist
from utils.scanner import format_duration


# ─── Song Table ───────────────────────────────────────────────────────────────

class SongTableWidget(QTableWidget):
    """Custom table for song list with context menu."""

    song_double_clicked = Signal(int)   # row index
    add_to_playlist_requested = Signal(object, str)  # Song, playlist_id
    remove_requested = Signal(object)    # Song

    COLUMNS = ["", "Title", "Artist", "Album", "Duration", ""]
    COL_IDX = 0
    COL_TITLE = 1
    COL_ARTIST = 2
    COL_ALBUM = 3
    COL_DURATION = 4
    COL_MENU = 5

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._songs: list[Song] = []
        self._current_song_id: Optional[str] = None

        self._setup_table()

    def _setup_table(self):
        self.setObjectName("songTable")
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.doubleClicked.connect(lambda idx: self.song_double_clicked.emit(idx.row()))

        header = self.horizontalHeader()
        header.setObjectName("tableHeader")
        header.setHighlightSections(False)
        header.setSectionResizeMode(self.COL_IDX, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_TITLE, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_ARTIST, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_ALBUM, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_MENU, QHeaderView.Fixed)

        self.setColumnWidth(self.COL_IDX, 50)
        self.setColumnWidth(self.COL_DURATION, 70)
        self.setColumnWidth(self.COL_MENU, 36)
        self.verticalHeader().setDefaultSectionSize(52)

    def load_songs(self, songs: list[Song]):
        self._songs = songs
        self.setRowCount(0)
        self.setRowCount(len(songs))

        for row, song in enumerate(songs):
            self._populate_row(row, song)

        self._highlight_current()

    def _populate_row(self, row: int, song: Song):
        # Index / now-playing indicator
        idx_item = QTableWidgetItem("")
        idx_item.setTextAlignment(Qt.AlignCenter)
        idx_item.setData(Qt.UserRole, song.id)
        self.setItem(row, self.COL_IDX, idx_item)

        title_item = QTableWidgetItem(song.title)
        title_item.setData(Qt.UserRole, song.id)
        self.setItem(row, self.COL_TITLE, title_item)

        artist_item = QTableWidgetItem(song.artist)
        artist_item.setForeground(QColor("#8899bb"))
        self.setItem(row, self.COL_ARTIST, artist_item)

        album_item = QTableWidgetItem(song.album)
        album_item.setForeground(QColor("#8899bb"))
        self.setItem(row, self.COL_ALBUM, album_item)

        dur = format_duration(song.duration)
        dur_item = QTableWidgetItem(dur)
        dur_item.setTextAlignment(Qt.AlignCenter)
        dur_item.setForeground(QColor("#8899bb"))
        self.setItem(row, self.COL_DURATION, dur_item)

        # More options placeholder (handled by context menu)
        more_item = QTableWidgetItem("···")
        more_item.setTextAlignment(Qt.AlignCenter)
        more_item.setForeground(QColor("#556688"))
        self.setItem(row, self.COL_MENU, more_item)

    def set_current_song(self, song_id: Optional[str]):
        old = self._current_song_id
        self._current_song_id = song_id
        # Update old row
        if old:
            self._refresh_row_indicator(old, "")
        if song_id:
            self._refresh_row_indicator(song_id, "▶")

    def _refresh_row_indicator(self, song_id: str, indicator: str):
        for row in range(self.rowCount()):
            item = self.item(row, self.COL_IDX)
            if item and item.data(Qt.UserRole) == song_id:
                item.setText(indicator)
                # Highlight the active row
                color = QColor("#1a3a6b") if indicator else QColor("transparent")
                for col in range(self.columnCount()):
                    cell = self.item(row, col)
                    if cell:
                        cell.setBackground(color)
                break

    def _highlight_current(self):
        if self._current_song_id:
            self._refresh_row_indicator(self._current_song_id, "▶")

    def get_song_at_row(self, row: int) -> Optional[Song]:
        if 0 <= row < len(self._songs):
            return self._songs[row]
        return None

    def get_all_songs(self) -> list[Song]:
        return list(self._songs)

    def _show_context_menu(self, pos):
        row = self.rowAt(pos.y())
        if row < 0:
            return
        song = self.get_song_at_row(row)
        if not song:
            return

        menu = QMenu(self)
        menu.setObjectName("contextMenu")
        play_action = menu.addAction("▶  Play Now")
        menu.addSeparator()
        queue_action = menu.addAction("⊕  Add to Queue")

        pl_menu = menu.addMenu("⊞  Add to Playlist")
        playlists = self.db.get_all_playlists()
        pl_actions = {}
        for pl in playlists:
            action = pl_menu.addAction(pl.name)
            pl_actions[action] = pl.id

        menu.addSeparator()
        remove_action = menu.addAction("✕  Remove from List")

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == play_action:
            self.song_double_clicked.emit(row)
        elif action == queue_action:
            self.add_to_playlist_requested.emit(song, "__queue__")
        elif action in pl_actions:
            self.add_to_playlist_requested.emit(song, pl_actions[action])
        elif action == remove_action:
            self.remove_requested.emit(song)


# ─── Lyrics View ─────────────────────────────────────────────────────────────

class LyricsView(QWidget):
    lyrics_edited = Signal(str, str)   # song_id, lyrics_text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lyricsView")
        self._song: Optional[Song] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(20)

        # Header
        self.song_title = QLabel("No song playing")
        self.song_title.setObjectName("lyricsSongTitle")
        self.song_title.setAlignment(Qt.AlignCenter)

        self.song_artist = QLabel("")
        self.song_artist.setObjectName("lyricsSongArtist")
        self.song_artist.setAlignment(Qt.AlignCenter)

        # Lyrics display
        scroll = QScrollArea()
        scroll.setObjectName("lyricsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.lyrics_label = QLabel("No lyrics available.\n\nYou can add lyrics by clicking 'Edit Lyrics'.")
        self.lyrics_label.setObjectName("lyricsText")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        self.lyrics_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scroll.setWidget(self.lyrics_label)

        # Edit button
        self.btn_edit = QPushButton("✏  Edit Lyrics")
        self.btn_edit.setObjectName("editLyricsBtn")
        self.btn_edit.setFixedWidth(140)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.clicked.connect(self._edit_lyrics)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_edit)
        btn_row.addStretch()

        layout.addWidget(self.song_title)
        layout.addWidget(self.song_artist)
        layout.addWidget(scroll, 1)
        layout.addLayout(btn_row)

    def set_song(self, song: Optional[Song]):
        self._song = song
        if song:
            self.song_title.setText(song.title)
            self.song_artist.setText(song.artist)
            if song.lyrics:
                self.lyrics_label.setText(song.lyrics)
            else:
                self.lyrics_label.setText(
                    "No lyrics available.\n\nClick 'Edit Lyrics' to add lyrics manually."
                )
        else:
            self.song_title.setText("No song playing")
            self.song_artist.setText("")
            self.lyrics_label.setText("Play a song to see its lyrics here.")

    def _edit_lyrics(self):
        if not self._song:
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Lyrics — {self._song.title}")
        dlg.setMinimumSize(600, 500)
        dlg.setObjectName("lyricsDialog")
        layout = QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setObjectName("lyricsEditor")
        editor.setPlainText(self._song.lyrics or "")
        editor.setPlaceholderText("Paste or type lyrics here...")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        if dlg.exec() == QDialog.Accepted:
            lyrics = editor.toPlainText()
            self._song.lyrics = lyrics
            self.lyrics_label.setText(lyrics or "No lyrics.")
            self.lyrics_edited.emit(self._song.id, lyrics)


# ─── Main Panel ───────────────────────────────────────────────────────────────

class MainPanel(QWidget):
    """
    Center panel. Hosts a QStackedWidget with:
        Page 0 — Song list (library / playlist songs)
        Page 1 — Lyrics view
    """

    song_play_requested = Signal(object, list)   # Song, queue
    add_to_queue_requested = Signal(object)       # Song
    add_to_playlist_requested = Signal(object, str)
    lyrics_saved = Signal(str, str)               # song_id, lyrics

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("mainPanel")
        self._current_mode = "library"   # library | playlist | recent etc.
        self._current_playlist_id: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setObjectName("mainTopBar")
        top_bar.setFixedHeight(64)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(24, 0, 24, 0)
        tb_layout.setSpacing(12)

        self.title_label = QLabel("All Songs")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("mainSubtitle")

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("  🔍  Search songs...")
        self.search_box.setFixedWidth(240)
        self.search_box.textChanged.connect(self._on_search)

        # View toggle: list ↔ lyrics
        self.btn_lyrics_view = QPushButton("♩ Lyrics")
        self.btn_lyrics_view.setObjectName("viewToggleBtn")
        self.btn_lyrics_view.setCheckable(True)
        self.btn_lyrics_view.setCursor(Qt.PointingHandCursor)
        self.btn_lyrics_view.setFixedWidth(100)
        self.btn_lyrics_view.clicked.connect(self._toggle_view)

        # Sort / Add folder
        self.btn_add_folder = QPushButton("⊕ Add Folder")
        self.btn_add_folder.setObjectName("addFolderBtn")
        self.btn_add_folder.setCursor(Qt.PointingHandCursor)

        # Play all
        self.btn_play_all = QPushButton("▶ Play All")
        self.btn_play_all.setObjectName("playAllBtn")
        self.btn_play_all.setCursor(Qt.PointingHandCursor)
        self.btn_play_all.clicked.connect(self._play_all)

        tb_layout.addLayout(title_col)
        tb_layout.addStretch()
        tb_layout.addWidget(self.search_box)
        tb_layout.addWidget(self.btn_lyrics_view)
        tb_layout.addWidget(self.btn_play_all)
        tb_layout.addWidget(self.btn_add_folder)

        layout.addWidget(top_bar)

        # Thin accent line
        accent = QFrame()
        accent.setObjectName("accentLine")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        # ── Stacked pages ─────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")

        # Page 0: Song list
        self.song_table = SongTableWidget(self.db)
        self.song_table.song_double_clicked.connect(self._on_song_activated)
        self.song_table.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self.song_table.remove_requested.connect(self._on_remove_song)
        self.stack.addWidget(self.song_table)

        # Page 1: Lyrics
        self.lyrics_view = LyricsView()
        self.lyrics_view.lyrics_edited.connect(self._on_lyrics_saved)
        self.stack.addWidget(self.lyrics_view)

        layout.addWidget(self.stack, 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_library(self):
        """Show all songs from DB."""
        self._current_mode = "library"
        self._current_playlist_id = None
        songs = self.db.get_all_songs()
        self._load_songs(songs, "All Songs", f"{len(songs)} songs")
        self.btn_add_folder.show()

    def load_playlist(self, playlist):
        """Show songs from a specific playlist."""
        self._current_mode = "playlist"
        self._current_playlist_id = playlist.id
        songs = self.db.get_playlist_songs(playlist.id)
        self._load_songs(songs, playlist.name, f"{len(songs)} songs")
        self.btn_add_folder.hide()

    def load_recent(self):
        self._current_mode = "recent"
        self._current_playlist_id = None
        songs = self.db.get_history()
        self._load_songs(songs, "Recently Played", f"{len(songs)} songs")
        self.btn_add_folder.hide()

    def add_songs_to_table(self, songs: list):
        """Called when scanner finds new songs."""
        if self._current_mode == "library":
            all_songs = self.db.get_all_songs()
            self.song_table.load_songs(all_songs)
            count = len(all_songs)
            self.subtitle_label.setText(f"{count} songs")

    def set_current_song(self, song: Optional[Song]):
        self.song_table.set_current_song(song.id if song else None)
        self.lyrics_view.set_song(song)

    def show_lyrics_view(self):
        self.stack.setCurrentIndex(1)
        self.btn_lyrics_view.setChecked(True)

    def show_list_view(self):
        self.stack.setCurrentIndex(0)
        self.btn_lyrics_view.setChecked(False)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_songs(self, songs: list[Song], title: str, subtitle: str):
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.song_table.load_songs(songs)

    def _toggle_view(self):
        if self.stack.currentIndex() == 0:
            self.show_lyrics_view()
        else:
            self.show_list_view()

    def _play_all(self):
        songs = self.song_table.get_all_songs()
        if songs:
            self.song_play_requested.emit(songs[0], songs)

    def _on_song_activated(self, row: int):
        song = self.song_table.get_song_at_row(row)
        if song:
            all_songs = self.song_table.get_all_songs()
            self.song_play_requested.emit(song, all_songs)

    def _on_remove_song(self, song: Song):
        if self._current_mode == "playlist" and self._current_playlist_id:
            self.db.remove_song_from_playlist(self._current_playlist_id, song.id)
            songs = self.db.get_playlist_songs(self._current_playlist_id)
            self.song_table.load_songs(songs)

    def _on_search(self, query: str):
        if not query:
            if self._current_mode == "library":
                self.song_table.load_songs(self.db.get_all_songs())
            return
        results = self.db.search_songs(query)
        self.song_table.load_songs(results)

    def _on_lyrics_saved(self, song_id: str, lyrics: str):
        self.db.update_lyrics(song_id, lyrics)
        self.lyrics_saved.emit(song_id, lyrics)
