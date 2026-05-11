"""
Bottom Player Bar - Fixed bottom bar with playback controls
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from utils.database import Song
from utils.scanner import format_duration


class ClickableSlider(QSlider):
    """Slider that seeks to clicked position instead of stepping."""

    seek_requested = Signal(float)  # 0.0 to 1.0

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._seek(event.position().x())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._seek(event.position().x())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def _seek(self, x: float):
        ratio = max(0.0, min(1.0, x / self.width()))
        value = int(ratio * self.maximum())
        self.setValue(value)
        self.seek_requested.emit(ratio)


class IconButton(QPushButton):
    def __init__(self, icon_text: str, tooltip: str = "", size: int = 36, parent=None):
        super().__init__(icon_text, parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setObjectName("iconBtn")


class PlayerBar(QWidget):
    """
    Fixed bottom playback bar.
    Signals connect to audio engine slots.
    """

    # User action signals
    play_pause_clicked = Signal()
    next_clicked = Signal()
    prev_clicked = Signal()
    seek_requested = Signal(float)        # seconds
    volume_changed = Signal(float)        # 0.0-1.0
    shuffle_toggled = Signal(bool)
    repeat_toggled = Signal()
    lyrics_view_toggled = Signal(bool)    # show lyrics

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBar")
        self.setFixedHeight(88)
        self._duration: float = 0.0
        self._position: float = 0.0
        self._is_lyrics_visible: bool = False

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top accent line
        accent = QFrame()
        accent.setObjectName("playerAccentLine")
        accent.setFixedHeight(1)
        outer.addWidget(accent)

        # Main row
        main_row = QWidget()
        main_row.setObjectName("playerBarInner")
        row_layout = QHBoxLayout(main_row)
        row_layout.setContentsMargins(20, 0, 20, 0)
        row_layout.setSpacing(0)

        # ── Left: Song info ───────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(280)
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.mini_cover = QLabel("♪")
        self.mini_cover.setObjectName("miniCover")
        self.mini_cover.setFixedSize(52, 52)
        self.mini_cover.setAlignment(Qt.AlignCenter)

        song_info = QVBoxLayout()
        song_info.setSpacing(3)
        song_info.setContentsMargins(0, 0, 0, 0)

        self.song_title = QLabel("No song playing")
        self.song_title.setObjectName("playerSongTitle")
        self.song_title.setMaximumWidth(180)

        self.song_artist = QLabel("—")
        self.song_artist.setObjectName("playerSongArtist")
        self.song_artist.setMaximumWidth(180)

        song_info.addWidget(self.song_title)
        song_info.addWidget(self.song_artist)

        self.btn_lyrics_toggle = IconButton("♩", "Toggle Lyrics View", 30)
        self.btn_lyrics_toggle.setObjectName("lyricsToggleBtn")
        self.btn_lyrics_toggle.setCheckable(True)
        self.btn_lyrics_toggle.clicked.connect(self._on_lyrics_toggle)

        left_layout.addWidget(self.mini_cover)
        left_layout.addLayout(song_info, 1)
        left_layout.addWidget(self.btn_lyrics_toggle)

        # ── Center: Controls + Progress ───────────────────────────────────────
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(20, 8, 20, 8)
        center_layout.setSpacing(6)

        # Control buttons
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.setAlignment(Qt.AlignCenter)

        self.btn_shuffle = IconButton("⇌", "Shuffle", 30)
        self.btn_shuffle.setObjectName("controlBtn")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.clicked.connect(lambda checked: self.shuffle_toggled.emit(checked))

        self.btn_prev = IconButton("⏮", "Previous", 30)
        self.btn_prev.setObjectName("controlBtn")
        self.btn_prev.clicked.connect(self.prev_clicked)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(52, 52)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.play_pause_clicked)

        self.btn_next = IconButton("⏭", "Next", 30)
        self.btn_next.setObjectName("controlBtn")
        self.btn_next.clicked.connect(self.next_clicked)

        self.btn_repeat = IconButton("↺", "Repeat", 30)
        self.btn_repeat.setObjectName("controlBtn")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.clicked.connect(self.repeat_toggled)

        controls.addWidget(self.btn_shuffle)
        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_next)
        controls.addWidget(self.btn_repeat)

        # Progress row
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        progress_row.setAlignment(Qt.AlignVCenter)

        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("timeLabel")
        self.time_current.setFixedWidth(38)
        self.time_current.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setObjectName("progressSlider")
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.seek_requested.connect(self._on_seek_ratio)

        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("timeLabel")
        self.time_total.setFixedWidth(38)
        self.time_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        progress_row.addWidget(self.time_current)
        progress_row.addWidget(self.progress_slider, 1)
        progress_row.addWidget(self.time_total)

        center_layout.addLayout(controls)
        center_layout.addLayout(progress_row)

        # ── Right: Volume + extras ────────────────────────────────────────────
        right = QWidget()
        right.setFixedWidth(280)
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Volume icon
        self.vol_icon = QLabel("🔊")
        self.vol_icon.setObjectName("volIcon")

        self.volume_slider = ClickableSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.seek_requested.connect(
            lambda ratio: self.volume_changed.emit(ratio)
        )
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_changed.emit(v / 100.0)
        )

        right_layout.addStretch()
        right_layout.addWidget(self.vol_icon)
        right_layout.addWidget(self.volume_slider)

        # Assemble main row
        row_layout.addWidget(left)
        row_layout.addWidget(center, 1)
        row_layout.addWidget(right)

        outer.addWidget(main_row, 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_song(self, song: Optional[Song]):
        if song:
            # Truncate long titles
            title = song.title if len(song.title) <= 30 else song.title[:27] + "..."
            artist = song.artist if len(song.artist) <= 28 else song.artist[:25] + "..."
            self.song_title.setText(title)
            self.song_artist.setText(artist)
            self.mini_cover.setText("♪")  # placeholder; can update with cover
        else:
            self.song_title.setText("No song playing")
            self.song_artist.setText("—")

    def set_playback_state(self, state: str):
        if state == "playing":
            self.btn_play.setText("⏸")
            self.btn_play.setObjectName("playBtnActive")
        else:
            self.btn_play.setText("▶")
            self.btn_play.setObjectName("playBtn")
        # Re-apply stylesheet
        self.btn_play.style().unpolish(self.btn_play)
        self.btn_play.style().polish(self.btn_play)

    def set_position(self, position: float):
        self._position = position
        self.time_current.setText(format_duration(position))
        if self._duration > 0:
            ratio = position / self._duration
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(ratio * 1000))
            self.progress_slider.blockSignals(False)

    def set_duration(self, duration: float):
        self._duration = duration
        self.time_total.setText(format_duration(duration))

    def set_volume(self, volume: float):
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(int(volume * 100))
        self.volume_slider.blockSignals(False)
        # Update icon
        if volume == 0:
            self.vol_icon.setText("🔇")
        elif volume < 0.4:
            self.vol_icon.setText("🔈")
        elif volume < 0.7:
            self.vol_icon.setText("🔉")
        else:
            self.vol_icon.setText("🔊")

    def set_shuffle(self, enabled: bool):
        self.btn_shuffle.setChecked(enabled)

    def set_repeat(self, mode: str):
        self.btn_repeat.setChecked(mode != "none")
        repeat_icons = {"none": "↺", "all": "↻", "one": "①"}
        self.btn_repeat.setText(repeat_icons.get(mode, "↺"))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_seek_ratio(self, ratio: float):
        if self._duration > 0:
            self.seek_requested.emit(ratio * self._duration)

    def _on_lyrics_toggle(self, checked: bool):
        self._is_lyrics_visible = checked
        self.lyrics_view_toggled.emit(checked)
