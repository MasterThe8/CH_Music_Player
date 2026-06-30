"""
Main Window - Orchestrates all UI panels and connects to backend services
"""

import random

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStatusBar, QLabel,
    QProgressBar, QFrame, QSizePolicy,
    QInputDialog, QMessageBox, QCheckBox,
    QProgressDialog
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon

from components.playlist_panel import PlaylistPanel
from components.main_panel import MainPanel
from components.now_playing_panel import NowPlayingPanel
from components.player_bar import PlayerBar
from components.stems_mixer import StemsMixer

from core.database import Database
from utils.audio_engine import AudioEngine
from utils.vlc_audio_engine import VLCEngine
from utils.scanner import SongPackage, format_duration
from utils.scan_worker import ScanWorker
from components.database_manager import DatabaseManager

class LoadWorker(QThread):
    finished = Signal(bool, int)

    def __init__(self, engine, tracks, engine_id, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.tracks = tracks
        self.engine_id = engine_id

    def run(self):
        success = self.engine.load(self.tracks)
        self.finished.emit(success, self.engine_id)

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

    def __init__(self, db: Database, audio_engine: AudioEngine):
        super().__init__()
        self.setWindowTitle("CH Music Player")
        self.setMinimumSize(1000, 650)
        self.resize(1300, 780)

        self.setWindowIcon(QIcon("assets/icon.ico"))

        # ── Backend references ────────────────────────────────────────────────
        self.db = db
        self.audio_engine = audio_engine          # Precision Mode (Stem Mixer)
        self.vlc_engine = VLCEngine()              # Fast Mode (VLC)
        self.active_engine = self.audio_engine     # Default: Precision Mode
        self._engine_mode = 1                      # 0 = VLC, 1 = Precision

        # ── Playback state ────────────────────────────────────────────────────
        self.current_song: SongPackage = None
        self.current_index: int = -1
        self.is_shuffle: bool = False
        self.repeat_mode: int = 0  # 0=off, 1=repeat all, 2=repeat one

        # ── Scan worker reference ─────────────────────────────────────────────
        self._scan_worker: ScanWorker = None

        self._build_ui()
        self._connect_signals()
        self._load_initial_data()

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
        self.playlist_panel = PlaylistPanel()
        self.left_toggle = PanelToggleButton("‹")
        self.left_toggle.setChecked(True)
        self.left_toggle.clicked.connect(self._toggle_left_panel)

        # Center
        self.main_panel = MainPanel()
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

        # Connect lyrics toggle from right panel to main panel view switch
        self.now_playing_panel.lyrics_toggled.connect(self.main_panel._toggle_view)

        # Connect stems mixer toggle
        self.stems_mixer = StemsMixer(self.active_engine, self)
        self.now_playing_panel.stems_mixer_toggled.connect(self._toggle_stems_mixer)

        # Connect engine switch
        self.playlist_panel.engine_changed.connect(self._on_engine_changed)

        # ── Bottom player bar ──────────────────────────────────────────────
        self.player_bar = PlayerBar()
        self.player_bar.set_seek_enabled(True)  # Precision mode default — seek enabled

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

    # ── Signal Connections ────────────────────────────────────────────────────

    def _connect_signals(self):
        # ── MainPanel signals ─────────────────────────────────────────────
        self.main_panel.song_selected.connect(self._on_song_selected)
        self.main_panel.folder_added.connect(self._on_folder_added)
        self.main_panel.list_changed.connect(self._on_list_changed)
        self.main_panel.btn_play_all.clicked.connect(self._on_play_all)
        self.main_panel.search_box.textChanged.connect(self._on_search)
        self.main_panel.open_database_requested.connect(self._open_database_manager)

        # ── PlayerBar signals ─────────────────────────────────────────────
        self.player_bar.play_pause_clicked.connect(self._on_play_pause)
        self.player_bar.next_clicked.connect(self._on_next)
        self.player_bar.prev_clicked.connect(self._on_prev)
        self.player_bar.seek_requested.connect(self._on_seek)
        self.player_bar.volume_changed.connect(self._on_volume_changed)
        self.player_bar.shuffle_toggled.connect(self._on_shuffle_toggled)
        self.player_bar.repeat_toggled.connect(self._on_repeat_toggled)

        # ── AudioEngine signals ───────────────────────────────────────────
        self._connect_engine_signals(self.active_engine)

        # ── PlaylistPanel signals ─────────────────────────────────────────
        self.playlist_panel.navigate.connect(self._on_navigate)
        self.playlist_panel.playlist_selected.connect(self._on_playlist_selected)
        self.playlist_panel.new_playlist_requested.connect(self._on_new_playlist)
        self.playlist_panel.playlist_delete_requested.connect(self._on_delete_playlist)
        self.playlist_panel.playlist_rename_requested.connect(self._on_rename_playlist)

        # ── SongTable playlist signals ───────────────────────────────────
        self.main_panel.song_table.add_to_playlist.connect(self._on_add_to_playlist)
        self.main_panel.song_table.add_to_new_playlist.connect(self._on_add_to_new_playlist)

    # ── Initial Data Load ─────────────────────────────────────────────────────

    def _load_initial_data(self):
        """Load songs and playlists from database on startup."""
        # Load all songs
        rows = self.db.get_all_songs()
        songs = self.db.rows_to_song_packages(rows)
        self.main_panel.load_songs(songs)
        self.status_label.setText(f"{len(songs)} songs in library")

        # Load playlists
        self._refresh_playlists()

    # ── Song Selection & Playback ─────────────────────────────────────────────

    def _on_song_selected(self, row: int):
        """User double-clicked a song row — load and play it."""
        song = self.main_panel.song_table.get_song(row)
        self._play_song(song, row)

    def _play_song(self, song: SongPackage, row: int):
        """Load a song into the audio engine asynchronously and start playback."""
        self.current_song = song
        self.current_index = row
        
        self.active_engine.stop()

        # Load audio tracks into engine
        if not song.audio_tracks:
            self.status_label.setText(f"No audio tracks found for: {song.name}")
            return

        self.status_label.setText(f"Loading {song.name}...")
        self.player_bar.set_playing_state(False)
        self.player_bar.setEnabled(False)

        self._start_audio_load(self.active_engine, song.audio_tracks, self._engine_mode)

    def _start_audio_load(self, engine, tracks, engine_id):
        song = self.current_song
        
        if hasattr(self, '_load_dialog') and self._load_dialog:
            self._load_dialog.close()

        self._load_dialog = QProgressDialog(f"Loading {song.name} into memory...", None, 0, 0, self)
        self._load_dialog.setWindowTitle("Loading Audio")
        self._load_dialog.setWindowModality(Qt.WindowModal)
        self._load_dialog.setMinimumDuration(300) # Only show if loading takes longer than 300ms
        self._load_dialog.setCancelButton(None)
        self._load_dialog.show()

        self._load_worker = LoadWorker(engine, tracks, engine_id, self)
        self._load_worker.finished.connect(self._on_audio_loaded)
        self._load_worker.start()

    def _on_audio_loaded(self, success: bool, engine_id: int):
        if hasattr(self, '_load_dialog') and self._load_dialog:
            self._load_dialog.close()
            self._load_dialog = None

        self.player_bar.setEnabled(True)
        song = self.current_song
        row = self.current_index

        if not success:
            # Fallback to the other engine if this was the first attempt
            if engine_id == self._engine_mode:
                other_mode = 1 if self._engine_mode == 0 else 0
                
                # Update UI to reflect the new engine state
                if other_mode == 1:
                    self.playlist_panel.radio_stem.setChecked(True)
                else:
                    self.playlist_panel.radio_vlc.setChecked(True)
                    
                self._on_engine_changed(other_mode)
                
                # Try loading again with the new engine
                self.status_label.setText(f"Fallback: Loading {song.name} with other engine...")
                self._start_audio_load(self.active_engine, song.audio_tracks, other_mode)
                return
            else:
                self.status_label.setText(f"Failed to load: {song.name} (Both engines failed)")
                return

        self.active_engine.play()

        # Check for VLC warning
        if self._engine_mode == 0 and len(song.audio_tracks) > 1:
            if getattr(self, "_suppress_vlc_warning", False) is False:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("Playback Engine Warning")
                msg_box.setText(
                    "This song uses multitrack/stem audio.\n"
                    "Playback with VLC Mode may cause the stems to become unsynchronized during playback.\n\n"
                    "For accurate stem sync and mixer support, it is recommended to use:\n"
                    "Precision Mode (Stem Mixer)."
                )
                cb = QCheckBox("Don't show again until reopen")
                msg_box.setCheckBox(cb)
                msg_box.exec()
                
                if cb.isChecked():
                    self._suppress_vlc_warning = True

        # Update seek capability based on mode & song type
        is_vlc_multitrack = (self._engine_mode == 0 and len(song.audio_tracks) > 1)
        self.player_bar.set_seek_enabled(not is_vlc_multitrack)

        # Skip silence (Disabled ONLY if VLC mode + multitrack)
        if not is_vlc_multitrack and self.player_bar.chk_skip_silence.isChecked():
            skip_ms = self.player_bar.spin_skip_ms.value()
            if skip_ms > 0:
                self.active_engine.seek(skip_ms / 1000.0)

        # Update UI
        self.player_bar.update_song_info(song)
        self.now_playing_panel.update_song(song)
        self.main_panel.song_table.highlight_playing(row)

        # Update lyrics view
        self.main_panel.lyrics_view.update_lyrics(song.lyrics)

        # Record play history
        db_row = self.db.fetchone(
            "SELECT id FROM songs WHERE folder_path=?",
            (song.folder_path,)
        )
        if db_row:
            self.db.add_play_history(db_row["id"])

        self.status_label.setText(f"Playing: {song.name} — {song.artist}")

        # Update stems mixer
        stems = self.active_engine.get_loaded_stems()
        self.stems_mixer.load_stems(stems)

    def _on_play_all(self):
        """Play the first song in the current list."""
        if self.main_panel.song_table.song_count() > 0:
            self._on_song_selected(0)

    # ── Playback Controls ─────────────────────────────────────────────────────

    def _on_play_pause(self):
        """Toggle play/pause."""
        if not self.active_engine.is_loaded:
            # If nothing loaded, try playing first song
            self._on_play_all()
            return

        self.active_engine.toggle_playback()

    def _on_next(self):
        """Play next song in list."""
        total = self.main_panel.song_table.song_count()
        if total == 0:
            return

        if self.is_shuffle:
            # Random from displayed list
            next_idx = random.randint(0, total - 1)
        else:
            next_idx = (self.current_index + 1) % total

        self._on_song_selected(next_idx)

    def _on_prev(self):
        """Play previous song in list."""
        total = self.main_panel.song_table.song_count()
        if total == 0:
            return

        if self.is_shuffle:
            next_idx = random.randint(0, total - 1)
        else:
            next_idx = (self.current_index - 1) % total

        self._on_song_selected(next_idx)

    def _on_seek(self, seconds: float):
        if self.active_engine.is_loaded:
            self.active_engine.seek(seconds)

    def _on_volume_changed(self, volume: float):
        """Volume slider changed (0.0 to 1.0)."""
        self.active_engine.set_master_volume(volume * 100)

    def _on_shuffle_toggled(self, checked: bool):
        """Toggle shuffle mode."""
        self.is_shuffle = checked

    def _on_repeat_toggled(self):
        """Cycle repeat mode: off → all → one → off."""
        self.repeat_mode = (self.repeat_mode + 1) % 3
        self.player_bar.set_repeat_mode(self.repeat_mode)

    def _on_position_changed(self, position_ms: int):
        """Called every ~50ms by audio engine timer."""
        duration_ms = self.active_engine.get_duration()
        self.player_bar.update_progress(position_ms, duration_ms)

    def _on_song_finished(self):
        pos = self.active_engine.get_position()
        dur = self.active_engine.get_duration()
        
        if dur > 0 and pos < dur - 1000:
            return

        if self.active_engine._is_seeking:
            return

        if self.repeat_mode == 2:
            if self.current_song:
                self._play_song(self.current_song, self.current_index)
        elif self.repeat_mode == 1:
            self._on_next()
        else:
            total = self.main_panel.song_table.song_count()
            if self.current_index < total - 1:
                self._on_next()
            else:
                self.player_bar.set_playing_state(False)
                self.status_label.setText("Playback finished")

    # ── Folder Scanning ───────────────────────────────────────────────────────

    def _on_folder_added(self, folder_path: str, import_lyrics: bool = True):
        """User selected a folder to scan."""
        # Save scan root to database
        self.db.add_scan_root(folder_path)

        # Start background scan
        self._start_scan(folder_path, import_lyrics)

    def _start_scan(self, root_path: str, import_lyrics: bool = True):
        """Start scanning in a background thread."""
        if self._scan_worker and self._scan_worker.isRunning():
            self.status_label.setText("Scan already in progress...")
            return

        self.scan_progress.setVisible(True)
        self.scan_progress.setRange(0, 0)  # Indeterminate
        self.status_label.setText(f"Scanning: {root_path}")

        self._scan_worker = ScanWorker(root_path, import_lyrics, self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, message: str):
        """Update status bar during scan."""
        self.status_label.setText(message)

    def _on_scan_finished(self, scanned_songs: list):
        """Scan complete — reload all songs from database."""
        self.scan_progress.setVisible(False)

        # Reload from database (includes previously scanned songs)
        rows = self.db.get_all_songs()
        songs = self.db.rows_to_song_packages(rows)
        self.main_panel.load_songs(songs)

        # Refresh playlists too
        playlists = self.db.get_all_playlists()
        self.playlist_panel.load_playlists(playlists)

        self.status_label.setText(
            f"Scan complete — {len(scanned_songs)} new songs added, "
            f"{len(songs)} total in library"
        )

    def _on_scan_error(self, error_msg: str):
        """Handle scan error."""
        self.scan_progress.setVisible(False)
        self.status_label.setText(f"Scan error: {error_msg}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_navigate(self, route: str):
        """Handle left panel navigation clicks."""
        if route == "library":
            rows = self.db.get_all_songs()
            songs = self.db.rows_to_song_packages(rows)
            self.main_panel.load_songs(songs)
            self.main_panel.title_label.setText("All Songs")

        elif route == "recent":
            rows = self.db.get_recently_played()
            songs = self.db.rows_to_song_packages(rows)
            self.main_panel.load_songs(songs, apply_sort=False)
            self.main_panel.title_label.setText("Recently Played")

    def _on_playlist_selected(self, playlist_id: int):
        """Load songs from a specific playlist."""
        self._current_playlist_id = playlist_id
        rows = self.db.get_playlist_songs(playlist_id)
        songs = self.db.rows_to_song_packages(rows)
        self.main_panel.load_songs(songs)

        # Update title to playlist name
        pl = self.db.fetchone(
            "SELECT name FROM playlists WHERE id=?",
            (playlist_id,)
        )
        if pl:
            self.main_panel.title_label.setText(pl["name"])

    # ── Playlist Management ──────────────────────────────────────────────

    def _refresh_playlists(self):
        """Reload playlists from DB into sidebar and song table cache."""
        playlists = self.db.get_all_playlists()
        self.playlist_panel.load_playlists(playlists)
        self.main_panel.song_table.set_playlists(playlists)

    def _on_new_playlist(self):
        """User clicked '+' in playlist panel — prompt for name."""
        name, ok = QInputDialog.getText(
            self, "New Playlist", "Playlist name:"
        )
        if ok and name.strip():
            self.db.create_playlist(name.strip())
            self._refresh_playlists()
            self.status_label.setText(f"Playlist \"{name.strip()}\" created")

    def _on_delete_playlist(self, playlist_id: int, name: str):
        """User requested deleting a playlist."""
        reply = QMessageBox.question(
            self, "Delete Playlist",
            f"Are you sure you want to delete \"{name}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_playlist(playlist_id)
            self._refresh_playlists()
            self.status_label.setText(f"Playlist \"{name}\" deleted")

    def _on_rename_playlist(self, playlist_id: int, current_name: str):
        """User requested renaming a playlist."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Playlist", "New name:",
            text=current_name
        )
        if ok and new_name.strip():
            self.db.rename_playlist(playlist_id, new_name.strip())
            self._refresh_playlists()
            self.status_label.setText(
                f"Playlist renamed to \"{new_name.strip()}\""
            )

    def _on_add_to_playlist(self, folder_path: str, playlist_id: int):
        """Add a song to an existing playlist."""
        db_row = self.db.fetchone(
            "SELECT id FROM songs WHERE folder_path=?",
            (folder_path,)
        )
        if not db_row:
            return

        added = self.db.add_song_to_playlist(playlist_id, db_row["id"])

        # Get playlist name for status
        pl = self.db.fetchone(
            "SELECT name FROM playlists WHERE id=?",
            (playlist_id,)
        )
        pl_name = pl["name"] if pl else "playlist"

        if added:
            self._refresh_playlists()
            self.status_label.setText(f"Added to \"{pl_name}\"")
        else:
            self.status_label.setText(f"Song already in \"{pl_name}\"")

    def _on_add_to_new_playlist(self, folder_path: str):
        """Create a new playlist and add the song to it."""
        name, ok = QInputDialog.getText(
            self, "New Playlist", "Playlist name:"
        )
        if not ok or not name.strip():
            return

        playlist_id = self.db.create_playlist(name.strip())

        db_row = self.db.fetchone(
            "SELECT id FROM songs WHERE folder_path=?",
            (folder_path,)
        )
        if db_row:
            self.db.add_song_to_playlist(playlist_id, db_row["id"])

        self._refresh_playlists()
        self.status_label.setText(
            f"Created \"{name.strip()}\" and added song"
        )

    def _on_list_changed(self):
        """When the song list changes (sort/filter), update current_index and highlight."""
        if not self.current_song:
            return

        songs = self.main_panel.song_table.get_songs()
        for idx, song in enumerate(songs):
            if song.folder_path == self.current_song.folder_path:
                self.current_index = idx
                self.main_panel.song_table.highlight_playing(idx)
                return
        
        # If not found (e.g., filtered out)
        self.current_index = -1

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search(self, keyword: str):
        """Filter songs based on search keyword."""
        keyword = keyword.strip()
        if keyword:
            rows = self.db.search_songs(keyword)
        else:
            rows = self.db.get_all_songs()

        songs = self.db.rows_to_song_packages(rows)
        self.main_panel.load_songs(songs)

    # ── Panel Toggles ─────────────────────────────────────────────────────────

    def _toggle_left_panel(self):
        visible = not self.playlist_panel.isVisible()
        self.playlist_panel.setVisible(visible)
        self.left_toggle.setText("›" if not visible else "‹")

    def _toggle_right_panel(self):
        visible = not self.now_playing_panel.isVisible()
        self.now_playing_panel.setVisible(visible)
        self.right_toggle.setText("‹" if not visible else "›")

    def _toggle_stems_mixer(self):
        """Show or hide the Stems Mixer sub-window."""
        if self.stems_mixer.isVisible():
            self.stems_mixer.hide()
        else:
            self.stems_mixer.show()
            self.stems_mixer.raise_()
            self.stems_mixer.activateWindow()

    # ── Engine Switching ──────────────────────────────────────────────────────

    def _connect_engine_signals(self, engine):
        """Connect playback signals from the given engine."""
        engine.position_changed.connect(self._on_position_changed)
        engine.song_finished.connect(self._on_song_finished)
        engine.playback_started.connect(
            lambda: self.player_bar.set_playing_state(True)
        )
        engine.playback_paused.connect(
            lambda: self.player_bar.set_playing_state(False)
        )
        engine.playback_stopped.connect(
            lambda: self.player_bar.set_playing_state(False)
        )

    def _disconnect_engine_signals(self, engine):
        """Disconnect playback signals from the given engine."""
        try:
            engine.position_changed.disconnect(self._on_position_changed)
            engine.song_finished.disconnect(self._on_song_finished)
            engine.playback_started.disconnect()
            engine.playback_paused.disconnect()
            engine.playback_stopped.disconnect()
        except RuntimeError:
            pass

    def _on_engine_changed(self, engine_id: int):
        """Switch between VLC (0) and Precision (1) engine."""
        if engine_id == self._engine_mode:
            return

        # Stop current engine
        self.active_engine.stop()
        self._disconnect_engine_signals(self.active_engine)

        # Evaluate if seek should be disabled
        self._engine_mode = engine_id
        is_vlc_multitrack = False
        if self.current_song:
            is_vlc_multitrack = (engine_id == 0 and len(self.current_song.audio_tracks) > 1)

        # Switch
        if engine_id == 0:
            self.active_engine = self.vlc_engine
            self.player_bar.set_seek_enabled(not is_vlc_multitrack)
            self.status_label.setText("Engine: Fast Mode (VLC)")
        else:
            self.active_engine = self.audio_engine
            self.player_bar.set_seek_enabled(True)
            self.status_label.setText("Engine: Precision Mode (Stem Mixer)")

        # Reconnect signals
        self._connect_engine_signals(self.active_engine)

        # Re-bind stems mixer
        self.stems_mixer.set_engine(self.active_engine)

        # Apply current volume setting
        vol = self.player_bar.volume_slider.value()
        self.active_engine.set_master_volume(vol)

        # Reset player bar
        self.player_bar.reset()

    def _open_database_manager(self):
        dialog = DatabaseManager(self.db, self)
        dialog.database_changed.connect(self._reload_library_after_database_change)
        dialog.exec()

    def _reload_library_after_database_change(self):
        rows = self.db.get_all_songs()
        songs = self.db.rows_to_song_packages(rows)

        self.main_panel.load_songs(songs)
        self.status_label.setText(f"{len(songs)} songs in library")

        self._refresh_playlists()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Clean up resources on window close."""
        self.audio_engine.cleanup()
        self.vlc_engine.cleanup()
        self.db.close()
        super().closeEvent(event)
