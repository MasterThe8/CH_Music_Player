import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QSizePolicy, QFrame,
    QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from utils.scanner import format_duration, SongPackage
from components.now_playing_panel import CoverArtWidget

class ClickableSlider(QSlider):


    seek_requested = Signal(float)   # 0.0 – 1.0

    def __init__(
        self,
        orientation=Qt.Horizontal,
        parent=None,
        *,
        emit_seek: bool = True,
    ):
        super().__init__(orientation, parent)
        self._dragging  = False
        self._emit_seek = emit_seek

    # ------------------------------------------------------------------
    # Mouse events — jump-to-click behaviour
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._apply(event.position().x(), final=False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._apply(event.position().x(), final=False)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._apply(event.position().x(), final=True)
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply(self, x: float, final: bool = True):
        ratio = max(0.0, min(1.0, x / max(self.width(), 1)))
        value = int(ratio * self.maximum())
        self.blockSignals(True)
        self.setValue(value)
        self.blockSignals(False)
        if self._emit_seek and final:
            self.seek_requested.emit(ratio)


# ──────────────────────────────────────────────────────────────────────────────
# IconButton
# ──────────────────────────────────────────────────────────────────────────────

class IconButton(QPushButton):
    def __init__(
        self,
        icon_text: str,
        tooltip: str = "",
        size: int = 36,
        parent=None,
    ):
        super().__init__(icon_text, parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setObjectName("iconBtn")


# ──────────────────────────────────────────────────────────────────────────────
# PlayerBar
# ──────────────────────────────────────────────────────────────────────────────

class PlayerBar(QWidget):
    """
    Fixed bottom playback bar.

    Signal contract
    ───────────────
    seek_requested(float)   →  target position in **seconds**
                               Connect directly to AudioEngine.seek().

    volume_changed(float)   →  0.0 – 1.0
    """

    play_pause_clicked  = Signal()
    next_clicked        = Signal()
    prev_clicked        = Signal()
    seek_requested      = Signal(float)   # seconds
    volume_changed      = Signal(float)   # 0.0 – 1.0
    shuffle_toggled     = Signal(bool)
    repeat_toggled      = Signal()
    lyrics_view_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBar")
        self.setFixedHeight(88)

        self._duration_ms: int = 0   # kept so we can convert ratio → seconds
        self._is_muted: bool = False
        self._pre_mute_volume: int = 70

        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────

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

        # ── Left: Song info ───────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(280)
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.mini_cover = CoverArtWidget(size=52)
        self.mini_cover.setObjectName("miniCover")

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
        self.btn_lyrics_toggle.clicked.connect(
            lambda checked: self.lyrics_view_toggled.emit(checked)
        )

        left_layout.addWidget(self.mini_cover)
        left_layout.addLayout(song_info, 1)

        # ── Centre: Controls + Progress ───────────────────────────────
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(20, 8, 20, 8)
        center_layout.setSpacing(6)

        # Transport buttons
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.setAlignment(Qt.AlignCenter)

        self.btn_shuffle = IconButton("⇌", "Shuffle", 30)
        self.btn_shuffle.setObjectName("controlBtn")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.toggled.connect(self._on_shuffle_changed)
        self._update_button_icon(self.btn_shuffle, "assets/shuffle_off.png", "⇌")

        self.btn_prev = IconButton("⏮", "Previous", 30)
        self.btn_prev.setObjectName("controlBtn")
        self.btn_prev.clicked.connect(self.prev_clicked)
        self._update_button_icon(self.btn_prev, "assets/previous.png", "⏮")

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(52, 52)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.play_pause_clicked)
        self._update_button_icon(self.btn_play, "assets/play.png", "▶")

        self.btn_next = IconButton("⏭", "Next", 30)
        self.btn_next.setObjectName("controlBtn")
        self.btn_next.clicked.connect(self.next_clicked)
        self._update_button_icon(self.btn_next, "assets/next.png", "⏭")

        self.btn_repeat = IconButton("↺", "Repeat", 30)
        self.btn_repeat.setObjectName("controlBtn")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.clicked.connect(lambda checked: self.repeat_toggled.emit())
        self._update_button_icon(self.btn_repeat, "assets/repeat_off.png", "↺")

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
        self.time_current.setFixedWidth(48)
        self.time_current.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # emit_seek=True  →  clicking this bar emits seek_requested
        self.progress_slider = ClickableSlider(
            Qt.Horizontal, emit_seek=True
        )
        self.progress_slider.setObjectName("progressSlider")
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)

        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("timeLabel")
        self.time_total.setFixedWidth(48)
        self.time_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        progress_row.addWidget(self.time_current)
        progress_row.addWidget(self.progress_slider, 1)
        progress_row.addWidget(self.time_total)

        center_layout.addLayout(controls)
        center_layout.addLayout(progress_row)

        # ── Right: Volume + Skip ─────────────────────────────────────────────
        right = QWidget()
        right.setFixedWidth(420)
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.chk_skip_silence = QCheckBox("Skip Silence (ms):")
        self.chk_skip_silence.setObjectName("skipSilenceChk")
        self.chk_skip_silence.setCursor(Qt.PointingHandCursor)
        self.chk_skip_silence.setStyleSheet("color: #8899bb; font-size: 12px;")
        self.chk_skip_silence.setChecked(True)

        self.spin_skip_ms = QSpinBox()
        self.spin_skip_ms.setRange(0, 60000)
        self.spin_skip_ms.setValue(2000)
        self.spin_skip_ms.setSingleStep(500)
        self.spin_skip_ms.setFixedWidth(70)
        self.spin_skip_ms.setStyleSheet("""
            QSpinBox {
                background: #0f2040;
                color: #e8edf7;
                border: 1px solid #1a305d;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 12px;
            }
        """)

        self.vol_icon = QPushButton("🔊")
        self.vol_icon.setObjectName("volIcon")
        self.vol_icon.setCursor(Qt.PointingHandCursor)
        self.vol_icon.setFlat(True)
        self.vol_icon.setStyleSheet("background: transparent; border: none; padding: 0;")
        self.vol_icon.clicked.connect(self._toggle_mute)

        # emit_seek=False  →  dragging volume bar does NOT seek
        self.volume_slider = ClickableSlider(
            Qt.Horizontal, emit_seek=False
        )
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)

        right_layout.addStretch()
        right_layout.addWidget(self.chk_skip_silence)
        right_layout.addWidget(self.spin_skip_ms)

        # Spacing before volume
        spacing = QLabel()
        spacing.setFixedWidth(15)
        right_layout.addWidget(spacing)

        right_layout.addWidget(self.vol_icon)
        right_layout.addWidget(self.volume_slider)

        # Assemble
        row_layout.addWidget(left)
        row_layout.addWidget(center, 1)
        row_layout.addWidget(right)

        outer.addWidget(main_row, 1)

    # ──────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────

    def _update_button_icon(self, btn: QPushButton, image_path: str, fallback_text: str):
        if os.path.exists(image_path):
            btn.setText("")
            btn.setIcon(QIcon(image_path))
            
            # Scale icon size proportionally to button size
            if btn.width() > 40:
                icon_size = 28
            else:
                icon_size = 18
            btn.setIconSize(QSize(icon_size, icon_size))
        else:
            btn.setIcon(QIcon())
            btn.setText(fallback_text)

    def _on_shuffle_changed(self, checked: bool):
        if checked:
            self._update_button_icon(self.btn_shuffle, "assets/shuffle_on.png", "⇌")
        else:
            self._update_button_icon(self.btn_shuffle, "assets/shuffle_off.png", "⇌")
        self.shuffle_toggled.emit(checked)

    # ──────────────────────────────────────────────────────────────────
    # Signal wiring
    # ──────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        # Convert 0-1 ratio from the slider into seconds for the engine
        self.progress_slider.seek_requested.connect(self._on_seek_ratio)

        # Volume: valueChanged fires both on user drag AND programmatic set;
        # ClickableSlider.blockSignals() in _apply() prevents double-emit.
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)

    def _on_volume_slider_changed(self, value: int):
        if value > 0 and self._is_muted:
            self._is_muted = False
            self.vol_icon.setText("🔊")
        elif value == 0 and not self._is_muted:
            self._is_muted = True
            self.vol_icon.setText("🔇")
        self.volume_changed.emit(value / 100.0)

    def _toggle_mute(self):
        if self._is_muted:
            # Unmute
            self.volume_slider.setValue(self._pre_mute_volume if self._pre_mute_volume > 0 else 70)
        else:
            # Mute
            self._pre_mute_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)

    def _on_seek_ratio(self, ratio: float):
        """Convert slider ratio to seconds and forward to engine."""
        if self._duration_ms > 0:
            seconds = ratio * self._duration_ms / 1000.0
            self.seek_requested.emit(seconds)

    # ──────────────────────────────────────────────────────────────────
    # Public update methods  (called by the controller / main window)
    # ──────────────────────────────────────────────────────────────────

    def update_song_info(self, song: SongPackage):
        self.song_title.setText(song.name)
        self.song_artist.setText(song.artist)
        self.mini_cover.load_cover(song.album_art)

    def update_progress(self, position_ms: int, duration_ms: int):
        self._duration_ms = duration_ms

        # Abaikan posisi yang melebihi durasi (nilai VLC tidak valid)
        if duration_ms > 0 and position_ms > duration_ms:
            return

        if duration_ms > 0 and not self.progress_slider._dragging:
            ratio = position_ms / duration_ms
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(ratio * 1000))
            self.progress_slider.blockSignals(False)

        self.time_current.setText(format_duration(position_ms / 1000))
        self.time_total.setText(format_duration(duration_ms / 1000))

    def set_repeat_mode(self, mode: int):
        self.btn_repeat.blockSignals(True)
        if mode == 0:
            self._update_button_icon(self.btn_repeat, "assets/repeat_off.png", "↺")
            self.btn_repeat.setChecked(False)
            self.btn_repeat.setToolTip("Repeat: Off")
        elif mode == 1:
            self._update_button_icon(self.btn_repeat, "assets/repeat_on.png", "🔁")
            self.btn_repeat.setChecked(True)
            self.btn_repeat.setToolTip("Repeat: All")
        elif mode == 2:
            self._update_button_icon(self.btn_repeat, "assets/repeat_one_on.png", "🔂")
            self.btn_repeat.setChecked(True)
            self.btn_repeat.setToolTip("Repeat: One")
        self.btn_repeat.blockSignals(False)

    def set_playing_state(self, is_playing: bool):
        if is_playing:
            self._update_button_icon(self.btn_play, "assets/pause.png", "⏸")
        else:
            self._update_button_icon(self.btn_play, "assets/play.png", "▶")

    def reset(self):
        self._duration_ms = 0
        self.song_title.setText("No song playing")
        self.song_artist.setText("—")
        self.mini_cover._draw_placeholder()
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(0)
        self.progress_slider.blockSignals(False)
        self.time_current.setText("0:00")
        self.time_total.setText("0:00")
        self._update_button_icon(self.btn_play, "assets/play.png", "▶")

    def set_seek_enabled(self, enabled: bool):
        """Enable or disable seek capability on the progress slider."""
        self.progress_slider._emit_seek = enabled
        self.chk_skip_silence.setEnabled(enabled)
        self.spin_skip_ms.setEnabled(enabled)