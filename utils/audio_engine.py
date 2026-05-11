"""
Audio Engine - Handles all playback logic using PySide6 multimedia
"""

import os
import random
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from utils.database import DatabaseManager, Song


class AudioEngine(QObject):
    """
    Core playback engine. Wraps QMediaPlayer and exposes clean signals/slots.
    """

    # Signals
    song_changed = Signal(object)           # Song | None
    playback_state_changed = Signal(str)    # "playing" | "paused" | "stopped"
    position_changed = Signal(float)        # seconds
    duration_changed = Signal(float)        # seconds
    volume_changed = Signal(float)          # 0.0 – 1.0
    queue_changed = Signal(list)            # list[Song]
    shuffle_changed = Signal(bool)
    repeat_changed = Signal(str)            # "none" | "one" | "all"
    error_occurred = Signal(str)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db

        # Media player
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # State
        self._queue: list[Song] = []
        self._original_queue: list[Song] = []
        self._current_index: int = -1
        self._current_song: Optional[Song] = None
        self._shuffle: bool = False
        self._repeat: str = "none"
        self._volume: float = 0.7

        # Connect player signals
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_error)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Restore settings
        settings = db.get_settings()
        self.set_volume(settings.volume)
        self.set_shuffle(settings.shuffle)
        self.set_repeat(settings.repeat_mode)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_songs(self, songs: list[Song], start_index: int = 0):
        """Load a list of songs into the queue and optionally start playing."""
        self._original_queue = list(songs)
        self._queue = list(songs)
        if self._shuffle:
            self._apply_shuffle(start_index)
        self.queue_changed.emit(self._queue)
        if songs:
            self._play_index(start_index)

    def play_song(self, song: Song, queue: Optional[list[Song]] = None):
        """Play a specific song. Optionally update the queue."""
        if queue is not None:
            self._original_queue = list(queue)
            self._queue = list(queue)
            if self._shuffle:
                self._apply_shuffle(queue.index(song) if song in queue else 0)
            self.queue_changed.emit(self._queue)
        try:
            idx = self._queue.index(song)
        except ValueError:
            self._queue.append(song)
            idx = len(self._queue) - 1
            self.queue_changed.emit(self._queue)
        self._play_index(idx)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def toggle_play_pause(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def stop(self):
        self._player.stop()
        self._current_song = None
        self.song_changed.emit(None)
        self.playback_state_changed.emit("stopped")

    def next(self):
        if not self._queue:
            return
        if self._repeat == "one":
            self._play_index(self._current_index)
            return
        next_idx = self._current_index + 1
        if next_idx >= len(self._queue):
            if self._repeat == "all":
                next_idx = 0
            else:
                self.stop()
                return
        self._play_index(next_idx)

    def previous(self):
        if not self._queue:
            return
        # If more than 3s played, restart current song
        if self._player.position() > 3000:
            self.seek(0)
            return
        prev_idx = self._current_index - 1
        if prev_idx < 0:
            if self._repeat == "all":
                prev_idx = len(self._queue) - 1
            else:
                prev_idx = 0
        self._play_index(prev_idx)

    def seek(self, position_seconds: float):
        self._player.setPosition(int(position_seconds * 1000))

    def set_volume(self, volume: float):
        """Set volume 0.0 to 1.0"""
        volume = max(0.0, min(1.0, volume))
        self._volume = volume
        self._audio_output.setVolume(volume)
        self.volume_changed.emit(volume)
        self.db.update_setting("volume", volume)

    def set_shuffle(self, enabled: bool):
        self._shuffle = enabled
        if enabled and self._queue:
            self._apply_shuffle(self._current_index)
        elif not enabled:
            current = self._current_song
            self._queue = list(self._original_queue)
            if current and current in self._queue:
                self._current_index = self._queue.index(current)
            self.queue_changed.emit(self._queue)
        self.shuffle_changed.emit(enabled)
        self.db.update_setting("shuffle", enabled)

    def set_repeat(self, mode: str):
        """mode: 'none' | 'one' | 'all'"""
        self._repeat = mode
        self.repeat_changed.emit(mode)
        self.db.update_setting("repeat_mode", mode)

    def cycle_repeat(self):
        modes = ["none", "all", "one"]
        idx = modes.index(self._repeat)
        self.set_repeat(modes[(idx + 1) % len(modes)])

    def add_to_queue(self, song: Song):
        self._queue.append(song)
        self._original_queue.append(song)
        self.queue_changed.emit(self._queue)

    def remove_from_queue(self, index: int):
        if 0 <= index < len(self._queue):
            self._queue.pop(index)
            if index < self._current_index:
                self._current_index -= 1
            self.queue_changed.emit(self._queue)

    def move_in_queue(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < len(self._queue) and 0 <= to_idx < len(self._queue):
            song = self._queue.pop(from_idx)
            self._queue.insert(to_idx, song)
            if from_idx == self._current_index:
                self._current_index = to_idx
            self.queue_changed.emit(self._queue)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def current_song(self) -> Optional[Song]:
        return self._current_song

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def position(self) -> float:
        return self._player.position() / 1000.0

    @property
    def duration(self) -> float:
        return self._player.duration() / 1000.0

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def repeat(self) -> str:
        return self._repeat

    @property
    def queue(self) -> list[Song]:
        return list(self._queue)

    @property
    def current_index(self) -> int:
        return self._current_index

    # ── Internal ──────────────────────────────────────────────────────────────

    def _play_index(self, index: int):
        if not self._queue or index < 0 or index >= len(self._queue):
            return
        self._current_index = index
        self._current_song = self._queue[index]

        url = QUrl.fromLocalFile(self._current_song.file_path)
        self._player.setSource(url)
        self._player.play()

        self.song_changed.emit(self._current_song)
        self.db.increment_play_count(self._current_song.id)
        self.db.add_to_history(self._current_song.id)
        self.db.update_setting("last_song_id", self._current_song.id)

    def _apply_shuffle(self, current_index: int = 0):
        if not self._queue:
            return
        current = self._queue[current_index] if 0 <= current_index < len(self._queue) else None
        rest = [s for s in self._queue if s != current]
        random.shuffle(rest)
        self._queue = ([current] + rest) if current else rest
        self._current_index = 0
        self.queue_changed.emit(self._queue)

    # ── Qt Slots ──────────────────────────────────────────────────────────────

    def _on_playback_state_changed(self, state):
        state_map = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
            QMediaPlayer.PlaybackState.StoppedState: "stopped",
        }
        self.playback_state_changed.emit(state_map.get(state, "stopped"))

    def _on_position_changed(self, position_ms: int):
        self.position_changed.emit(position_ms / 1000.0)
        self.db.update_setting("last_position", position_ms / 1000.0)

    def _on_duration_changed(self, duration_ms: int):
        self.duration_changed.emit(duration_ms / 1000.0)

    def _on_error(self, error, error_string: str):
        self.error_occurred.emit(f"Playback error: {error_string}")

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next()
