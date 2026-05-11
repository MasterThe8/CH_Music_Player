"""
Main Window - Orchestrates all panels and the audio engine
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QFileDialog, QStatusBar, QLabel,
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut

from utils.database import DatabaseManager, Song
from utils.audio_engine import AudioEngine
from utils.scanner import FolderScanner

from components.playlist_panel import PlaylistPanel
from components.main_panel import MainPanel
from components.now_playing_panel import NowPlayingPanel
from components.player_bar import PlayerBar


class PanelToggleButton(QPushButton):
    """Thin vertical toggle button for showing/hiding side panels."""

    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setObjectName("panelToggleBtn")
        self.setFixedWidth(16)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lumina — Music Player")
        self.setMinimumSize(1000, 650)
        self.resize(1300, 780)

        # Core systems
        self.db = DatabaseManager()
        self.engine = AudioEngine(self.db, self)
        self.scanner = FolderScanner(self.db, self)

        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._setup_shortcuts()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Content area (panels) ──────────────────────────────────────────
        content_area = QWidget()
        content_area.setObjectName("contentArea")
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left panel
        self.playlist_panel = PlaylistPanel(self.db)
        self.left_toggle = PanelToggleButton("‹")
        self.left_toggle.setChecked(True)
        self.left_toggle.clicked.connect(self._toggle_left_panel)

        # Center
        self.main_panel = MainPanel(self.db)
        self.main_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Right panel
        self.right_toggle = PanelToggleButton("›")
        self.right_toggle.setChecked(True)
        self.right_toggle.clicked.connect(self._toggle_right_panel)
        self.now_playing_panel = NowPlayingPanel()

        content_layout.addWidget(self.playlist_panel)
        content_layout.addWidget(self.left_toggle)
        content_layout.addWidget(self.main_panel, 1)
        content_layout.addWidget(self.right_toggle)
        content_layout.addWidget(self.now_playing_panel)

        # ── Bottom player bar ──────────────────────────────────────────────
        self.player_bar = PlayerBar()

        root_layout.addWidget(content_area, 1)
        root_layout.addWidget(self.player_bar)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("statusBar")
        self.setStatusBar(self.status_bar)

        self.scan_progress = QProgressBar()
        self.scan_progress.setObjectName("scanProgress")
        self.scan_progress.setMaximumWidth(200)
        self.scan_progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.scan_progress)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    # ── Signal Wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        # Player bar → engine
        self.player_bar.play_pause_clicked.connect(self.engine.toggle_play_pause)
        self.player_bar.next_clicked.connect(self.engine.next)
        self.player_bar.prev_clicked.connect(self.engine.previous)
        self.player_bar.seek_requested.connect(self.engine.seek)
        self.player_bar.volume_changed.connect(self.engine.set_volume)
        self.player_bar.shuffle_toggled.connect(self.engine.set_shuffle)
        self.player_bar.repeat_toggled.connect(self.engine.cycle_repeat)
        self.player_bar.lyrics_view_toggled.connect(self._on_lyrics_toggle)

        # Engine → UI updates
        self.engine.song_changed.connect(self._on_song_changed)
        self.engine.playback_state_changed.connect(self.player_bar.set_playback_state)
        self.engine.position_changed.connect(self.player_bar.set_position)
        self.engine.duration_changed.connect(self.player_bar.set_duration)
        self.engine.volume_changed.connect(self.player_bar.set_volume)
        self.engine.shuffle_changed.connect(self.player_bar.set_shuffle)
        self.engine.repeat_changed.connect(self.player_bar.set_repeat)
        self.engine.queue_changed.connect(self._on_queue_changed)
        self.engine.error_occurred.connect(self._on_engine_error)

        # Main panel events
        self.main_panel.song_play_requested.connect(self._on_song_play_requested)
        self.main_panel.add_to_queue_requested.connect(self.engine.add_to_queue)
        self.main_panel.add_to_playlist_requested.connect(self._on_add_to_playlist)
        self.main_panel.btn_add_folder.clicked.connect(self._add_music_folder)

        # Playlist panel events
        self.playlist_panel.navigate.connect(self._on_navigate)
        self.playlist_panel.playlist_selected.connect(self.main_panel.load_playlist)
        self.playlist_panel.playlist_deleted.connect(self._on_playlist_deleted)

        # Scanner events
        self.scanner.scan_started.connect(self._on_scan_started)
        self.scanner.scan_progress.connect(self._on_scan_progress)
        self.scanner.song_found.connect(self.main_panel.add_songs_to_table)
        self.scanner.scan_finished.connect(self._on_scan_finished)
        self.scanner.scan_error.connect(lambda e: self.status_label.setText(f"Scan error: {e}"))

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Space"), self, self.engine.toggle_play_pause)
        QShortcut(QKeySequence("Right"), self, self.engine.next)
        QShortcut(QKeySequence("Left"), self, self.engine.previous)
        QShortcut(QKeySequence("Ctrl+L"), self, self._toggle_lyrics_shortcut)
        QShortcut(QKeySequence("Ctrl+["), self, self._toggle_left_panel)
        QShortcut(QKeySequence("Ctrl+]"), self, self._toggle_right_panel)

    # ── State Restoration ─────────────────────────────────────────────────────

    def _restore_state(self):
        settings = self.db.get_settings()

        # Panels visibility
        if not settings.show_playlist_panel:
            self._toggle_left_panel()
        if not settings.show_now_playing_panel:
            self._toggle_right_panel()

        # Volume
        self.player_bar.set_volume(settings.volume)
        self.player_bar.set_shuffle(settings.shuffle)
        self.player_bar.set_repeat(settings.repeat_mode)

        # Load library
        self.main_panel.load_library()

        # Scan known folders
        if settings.music_folders:
            QTimer.singleShot(500, lambda: self.scanner.scan_folders(settings.music_folders))

    # ── Panel Toggles ─────────────────────────────────────────────────────────

    def _toggle_left_panel(self):
        visible = not self.playlist_panel.isVisible()
        self.playlist_panel.setVisible(visible)
        self.left_toggle.setText("›" if not visible else "‹")
        self.db.update_setting("show_playlist_panel", visible)

    def _toggle_right_panel(self):
        visible = not self.now_playing_panel.isVisible()
        self.now_playing_panel.setVisible(visible)
        self.right_toggle.setText("‹" if not visible else "›")
        self.db.update_setting("show_now_playing_panel", visible)

    def _toggle_lyrics_shortcut(self):
        checked = not self.player_bar.btn_lyrics_toggle.isChecked()
        self.player_bar.btn_lyrics_toggle.setChecked(checked)
        self._on_lyrics_toggle(checked)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_navigate(self, route: str):
        if route == "library":
            self.main_panel.load_library()
        elif route == "recent":
            self.main_panel.load_recent()
        elif route == "favorites":
            self.status_label.setText("Favorites — coming soon")
        elif route == "folders":
            self._add_music_folder()

    # ── Song Playback ─────────────────────────────────────────────────────────

    def _on_song_play_requested(self, song: Song, queue: list):
        self.engine.play_song(song, queue)

    def _on_song_changed(self, song: Optional[Song]):
        self.player_bar.set_song(song)
        self.now_playing_panel.set_current_song(song)
        self.main_panel.set_current_song(song)
        if song:
            self.setWindowTitle(f"{song.title} — {song.artist}  |  Lumina")
            self.status_label.setText(f"Playing: {song.title} by {song.artist}")
        else:
            self.setWindowTitle("Lumina — Music Player")

    def _on_queue_changed(self, songs: list):
        self.now_playing_panel.update_queue(songs, self.engine.current_index)

    # ── Lyrics ────────────────────────────────────────────────────────────────

    def _on_lyrics_toggle(self, show: bool):
        if show:
            self.main_panel.show_lyrics_view()
        else:
            self.main_panel.show_list_view()

    # ── Folder / Scanner ──────────────────────────────────────────────────────

    def _add_music_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Music Folder",
            os.path.expanduser("~/Music"),
            QFileDialog.ShowDirsOnly
        )
        if folder:
            settings = self.db.get_settings()
            if folder not in settings.music_folders:
                settings.music_folders.append(folder)
                self.db.save_settings(settings)
            self.scanner.scan_folders([folder])

    def _on_scan_started(self):
        self.scan_progress.setVisible(True)
        self.scan_progress.setValue(0)
        self.status_label.setText("Scanning music folder...")

    def _on_scan_progress(self, current: int, total: int, filename: str):
        if total > 0:
            self.scan_progress.setMaximum(total)
            self.scan_progress.setValue(current)
        self.status_label.setText(f"Scanning: {filename}")

    def _on_scan_finished(self, count: int):
        self.scan_progress.setVisible(False)
        self.status_label.setText(f"Scan complete — {count} new songs added")
        self.main_panel.load_library()
        QTimer.singleShot(4000, lambda: self.status_label.setText("Ready"))

    # ── Playlist ──────────────────────────────────────────────────────────────

    def _on_add_to_playlist(self, song: Song, playlist_id: str):
        if playlist_id == "__queue__":
            self.engine.add_to_queue(song)
            self.status_label.setText(f"Added '{song.title}' to queue")
        else:
            self.db.add_song_to_playlist(playlist_id, song.id)
            pl = self.db.get_playlist(playlist_id)
            if pl:
                self.playlist_panel.refresh_playlist(playlist_id)
                self.status_label.setText(f"Added '{song.title}' to {pl.name}")

    def _on_playlist_deleted(self, playlist_id: str):
        self.main_panel.load_library()

    # ── Engine Errors ─────────────────────────────────────────────────────────

    def _on_engine_error(self, message: str):
        self.status_label.setText(message)

    # ── Window Close ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        settings = self.db.get_settings()
        settings.last_position = self.engine.position
        if self.engine.current_song:
            settings.last_song_id = self.engine.current_song.id
        self.db.save_settings(settings)
        self.engine.stop()
        self.scanner.cancel()
        event.accept()
