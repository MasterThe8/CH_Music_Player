"""
Stems Mixer - Sub-window for controlling individual stem volumes.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QGraphicsDropShadowEffect, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


# ═══════════════════════════════════════════════════════════════════════════
# STEM DISPLAY NAMES & ICONS
# ═══════════════════════════════════════════════════════════════════════════

STEM_INFO = {
    "song":     {"label": "Song",     "icon": "🎵"},
    "guitar":   {"label": "Guitar",   "icon": "🎸"},
    "bass":     {"label": "Bass",     "icon": "🎸"},
    "drums":    {"label": "Drums",    "icon": "🥁"},
    "drums_1":  {"label": "Drums 1",  "icon": "🥁"},
    "drums_2":  {"label": "Drums 2",  "icon": "🥁"},
    "drums_3":  {"label": "Drums 3",  "icon": "🥁"},
    "drums_4":  {"label": "Drums 4",  "icon": "🥁"},
    "vocals":   {"label": "Vocals",   "icon": "🎤"},
    "keys":     {"label": "Keys",     "icon": "🎹"},
    "rhythm":   {"label": "Rhythm",   "icon": "🎶"},
    "crowd":    {"label": "Crowd",    "icon": "👥"},
}


# ═══════════════════════════════════════════════════════════════════════════
# SINGLE STEM CHANNEL STRIP
# ═══════════════════════════════════════════════════════════════════════════

class StemChannel(QWidget):
    """A single vertical channel strip for one stem."""

    volume_changed = Signal(str, float)   # stem_name, volume (0.0-1.0)
    mute_toggled   = Signal(str, bool)    # stem_name, is_muted
    solo_toggled   = Signal(str, bool)    # stem_name, is_soloed

    def __init__(self, stem_name: str, parent=None):
        super().__init__(parent)
        self.stem_name = stem_name
        self._volume = 100        # 0-100
        self._is_muted = False
        self._is_soloed = False
        self._pre_mute_volume = 100

        self.setObjectName("stemChannel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(76)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 14, 6, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignHCenter)

        # ── Icon ──────────────────────────────────────────────────────────
        info = STEM_INFO.get(self.stem_name, {"label": self.stem_name.title(), "icon": "🎵"})

        icon_label = QLabel(info["icon"])
        icon_label.setObjectName("stemIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        layout.addWidget(icon_label)

        # ── Label ─────────────────────────────────────────────────────────
        name_label = QLabel(info["label"])
        name_label.setObjectName("stemLabel")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("""
            font-size: 10px;
            font-weight: 600;
            color: #8899bb;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(name_label)

        # ── Vertical Volume Slider ────────────────────────────────────────
        self.slider = QSlider(Qt.Vertical)
        self.slider.setObjectName("stemVolumeSlider")
        self.slider.setContentsMargins(0, 4, 0, 4)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setMinimumHeight(140)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 0, Qt.AlignHCenter)

        # ── Volume Value Label ────────────────────────────────────────────
        self.vol_label = QLabel("100%")
        self.vol_label.setObjectName("stemVolLabel")
        self.vol_label.setAlignment(Qt.AlignCenter)
        self.vol_label.setStyleSheet("""
            font-size: 10px;
            font-family: "Consolas", "SF Mono", monospace;
            color: #4a608a;
            background: transparent;
        """)
        layout.addWidget(self.vol_label)

        # ── Mute Button ──────────────────────────────────────────────────
        self.btn_mute = QPushButton("M")
        self.btn_mute.setObjectName("stemMuteBtn")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setMinimumSize(28, 28)
        self.btn_mute.setCursor(Qt.PointingHandCursor)
        self.btn_mute.setToolTip("Mute")
        self.btn_mute.clicked.connect(self._on_mute_clicked)
        layout.addWidget(self.btn_mute, 0, Qt.AlignHCenter)

        # ── Solo Button ──────────────────────────────────────────────────
        self.btn_solo = QPushButton("S")
        self.btn_solo.setObjectName("stemSoloBtn")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setMinimumSize(28, 28)
        self.btn_solo.setCursor(Qt.PointingHandCursor)
        self.btn_solo.setToolTip("Solo")
        self.btn_solo.clicked.connect(self._on_solo_clicked)
        layout.addWidget(self.btn_solo, 0, Qt.AlignHCenter)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_slider_changed(self, value: int):
        self._volume = value
        self.vol_label.setText(f"{value}%")
        self.volume_changed.emit(self.stem_name, value / 100.0)

    def _on_mute_clicked(self, checked: bool):
        self._is_muted = checked
        if checked:
            self._pre_mute_volume = self.slider.value()
            self.slider.setValue(0)
            self.slider.setEnabled(False)
        else:
            self.slider.setEnabled(True)
            self.slider.setValue(self._pre_mute_volume)
        self.mute_toggled.emit(self.stem_name, checked)

    def _on_solo_clicked(self, checked: bool):
        self._is_soloed = checked
        self.solo_toggled.emit(self.stem_name, checked)

    # ── Public API ────────────────────────────────────────────────────────

    def set_volume(self, value: int):
        """Set slider value (0-100) without emitting signal loop."""
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._volume = value
        self.vol_label.setText(f"{value}%")

    def set_muted(self, muted: bool):
        """Externally set mute state (used by solo logic)."""
        self.btn_mute.blockSignals(True)
        self.btn_mute.setChecked(muted)
        self.btn_mute.blockSignals(False)
        self._is_muted = muted
        if muted:
            self._pre_mute_volume = self._volume
            self.slider.setEnabled(False)
            self.slider.setValue(0)
        else:
            self.slider.setEnabled(True)
            self.slider.setValue(self._pre_mute_volume)

    def reset(self):
        """Reset channel to defaults."""
        self.btn_mute.setChecked(False)
        self.btn_solo.setChecked(False)
        self._is_muted = False
        self._is_soloed = False
        self.slider.setEnabled(True)
        self.set_volume(100)


# ═══════════════════════════════════════════════════════════════════════════
# STEMS MIXER WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class StemsMixer(QWidget):
    """
    Floating sub-window that displays per-stem volume controls.
    Connected to the AudioEngine to control individual stem volumes.
    """

    def __init__(self, audio_engine, parent=None):
        super().__init__(parent)
        self.audio_engine = audio_engine
        self._channels: dict[str, StemChannel] = {}

        self.setWindowTitle("Stems Mixer")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setObjectName("stemsMixerWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(360)
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # Reusable

        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(20, 20, 20, 20)
        self._root_layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("🎚  Stems Mixer")
        title.setObjectName("stemsMixerTitle")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #e8edf7;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        header.addWidget(title)
        header.addStretch()

        # Reset all button
        self.btn_reset = QPushButton("↻ Reset")
        self.btn_reset.setObjectName("stemsResetBtn")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_all)
        header.addWidget(self.btn_reset)

        self._root_layout.addLayout(header)

        # ── Divider ───────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("panelDivider")
        self._root_layout.addWidget(divider)

        # ── Channel strip container ──────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setObjectName("stemChannelScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._channel_container = QWidget()
        self._channel_container.setObjectName("stemChannelContainer")

        self._channel_layout = QHBoxLayout(self._channel_container)
        self._channel_layout.setContentsMargins(0, 0, 0, 0)
        self._channel_layout.setSpacing(10)
        self._channel_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._scroll.setWidget(self._channel_container)
        self._root_layout.addWidget(self._scroll, 1)

        # ── Placeholder ──────────────────────────────────────────────────
        self._placeholder = QLabel("No stems loaded")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("""
            font-size: 13px;
            color: #4a608a;
            padding: 40px;
        """)
        self._channel_layout.addWidget(self._placeholder)

    def _apply_style(self):
        self.setStyleSheet("""
            #stemsMixerWindow {
                background: #091428;
                border: 1px solid #1a3050;
            }

            #stemChannel {
                background: #0d1e3a;
                border: 1px solid #152a4a;
                border-radius: 10px;
            }

            #stemVolumeSlider::groove:vertical {
                background: #112347;
                width: 4px;
                border-radius: 2px;
            }
            #stemVolumeSlider::handle:vertical {
                background: #ffffff;
                width: 12px;
                height: 12px;
                margin: 0 -4px;
                border-radius: 6px;
            }
            #stemVolumeSlider::handle:vertical:hover {
                background: #3b82f6;
            }
            #stemVolumeSlider::sub-page:vertical {
                background: #112347;
                border-radius: 2px;
            }
            #stemVolumeSlider::add-page:vertical {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border-radius: 2px;
            }

            #stemMuteBtn {
                background: #112347;
                border: 1px solid #1a3050;
                border-radius: 6px;
                color: #8899bb;
                font-size: 11px;
                font-weight: 700;
            }
            #stemMuteBtn:hover {
                border-color: #ef4444;
                color: #ef4444;
            }
            #stemMuteBtn:checked {
                background: #3b1515;
                border-color: #ef4444;
                color: #ef4444;
            }

            #stemSoloBtn {
                background: #112347;
                border: 1px solid #1a3050;
                border-radius: 6px;
                color: #8899bb;
                font-size: 11px;
                font-weight: 700;
            }
            #stemSoloBtn:hover {
                border-color: #f59e0b;
                color: #f59e0b;
            }
            #stemSoloBtn:checked {
                background: #3b2e0a;
                border-color: #f59e0b;
                color: #f59e0b;
            }

            #stemsResetBtn {
                background: #0d1e3a;
                border: 1px solid #1a3050;
                border-radius: 8px;
                padding: 5px 14px;
                color: #8899bb;
                font-size: 12px;
            }
            #stemsResetBtn:hover {
                border-color: #3b82f6;
                color: #3b82f6;
            }

            #stemChannelContainer {
                background: transparent;
            }
        """)

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    def set_engine(self, engine):
        """Re-bind the mixer to a different audio engine."""
        self.audio_engine = engine

    def load_stems(self, stem_names: list[str]):
        """
        Build channel strips for the given stem names.
        Called when a new song is loaded.
        """
        # Clear old channels
        self._clear_channels()

        if not stem_names or len(stem_names) <= 1:
            self._placeholder.setVisible(True)
            self.resize(300, 360)
            return

        self._placeholder.setVisible(False)

        # Determine display order
        ORDER = [
            "song", "vocals", "guitar", "bass", "rhythm",
            "keys", "drums", "drums_1", "drums_2", "drums_3", "drums_4",
            "crowd"
        ]
        ordered = sorted(
            stem_names,
            key=lambda s: ORDER.index(s) if s in ORDER else 99
        )

        # Create channel strips
        for stem_name in ordered:
            ch = StemChannel(stem_name)
            ch.volume_changed.connect(self._on_volume_changed)
            ch.mute_toggled.connect(self._on_mute_toggled)
            ch.solo_toggled.connect(self._on_solo_toggled)
            self._channels[stem_name] = ch
            self._channel_layout.addWidget(ch)

        # Allow window to resize naturally based on DPI, avoiding layout squishing
        content_width = len(self._channels) * 92 + 60
        window_width = min(max(360, content_width), 900)

        self.setMinimumSize(360, 380)
        self.resize(window_width, 400)

    def _clear_channels(self):
        """Remove all channel strip widgets."""
        for ch in self._channels.values():
            self._channel_layout.removeWidget(ch)
            ch.deleteLater()
        self._channels.clear()

    # ═══════════════════════════════════════════════════════════════════════
    # SLOTS
    # ═══════════════════════════════════════════════════════════════════════

    def _on_volume_changed(self, stem_name: str, volume: float):
        """Forward volume change to audio engine."""
        self.audio_engine.set_stem_volume(stem_name, volume)

    def _on_mute_toggled(self, stem_name: str, is_muted: bool):
        """Mute/unmute a stem in the audio engine."""
        if is_muted:
            self.audio_engine.mute_stem(stem_name)
        else:
            # Restore to channel slider value
            ch = self._channels.get(stem_name)
            if ch:
                self.audio_engine.set_stem_volume(stem_name, ch._pre_mute_volume / 100.0)

    def _on_solo_toggled(self, stem_name: str, is_soloed: bool):
        """
        Solo logic: when a stem is soloed, mute all others.
        Multiple solos are allowed — only soloed stems play.
        If no solos active, restore all to their previous state.
        """
        soloed_stems = [
            name for name, ch in self._channels.items() if ch._is_soloed
        ]

        if soloed_stems:
            # Mute everything that isn't soloed
            for name, ch in self._channels.items():
                if name in soloed_stems:
                    # Ensure soloed stem is audible
                    if ch._is_muted:
                        ch.set_muted(False)
                    self.audio_engine.set_stem_volume(name, ch._volume / 100.0)
                else:
                    self.audio_engine.mute_stem(name)
        else:
            # No solo active — restore all to their slider volumes
            for name, ch in self._channels.items():
                if ch._is_muted:
                    self.audio_engine.mute_stem(name)
                else:
                    self.audio_engine.set_stem_volume(name, ch._volume / 100.0)

    def _reset_all(self):
        """Reset all channels to 100% volume, unmuted, unsoloed."""
        for name, ch in self._channels.items():
            ch.reset()
            self.audio_engine.set_stem_volume(name, 1.0)

    # ═══════════════════════════════════════════════════════════════════════
    # OVERRIDE
    # ═══════════════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        """Hide instead of destroy so we can reopen."""
        self.hide()
        event.ignore()
