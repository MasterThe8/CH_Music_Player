"""
Right Panel - Now Playing sidebar
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QLinearGradient, QFont, QFontMetrics, QPaintEvent

from utils.scanner import SongPackage, format_duration
from utils.marquee import MarqueeLabel


class CoverArtWidget(QLabel):
    """Rounded square cover art display."""

    def __init__(self, size=200, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setObjectName("coverArt")
        self._draw_placeholder()

    def _draw_placeholder(self):
        px = QPixmap(self._size, self._size)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self._size, self._size)
        grad.setColorAt(0, QColor("#0d2145"))
        grad.setColorAt(1, QColor("#091428"))
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._size, self._size, 16, 16)
        painter.fillPath(path, QBrush(grad))
        painter.setPen(QColor("#1e4080"))
        f = QFont("Segoe UI", int(self._size * 0.3))
        painter.setFont(f)
        painter.drawText(px.rect(), Qt.AlignCenter, "♪")
        painter.end()
        self.setPixmap(px)

    def load_cover(self, image_path: Optional[str]):
        """Load album art from file path, or show placeholder if None."""
        if not image_path:
            self._draw_placeholder()
            return

        import os
        if not os.path.exists(image_path):
            self._draw_placeholder()
            return

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self._draw_placeholder()
            return

        # Scale and clip to rounded rect
        scaled = pixmap.scaled(
            self._size, self._size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        # Center crop
        x = (scaled.width() - self._size) // 2
        y = (scaled.height() - self._size) // 2
        cropped = scaled.copy(x, y, self._size, self._size)

        # Apply rounded corners
        result = QPixmap(self._size, self._size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._size, self._size, 16, 16)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()

        self.setPixmap(result)


class NowPlayingPanel(QWidget):
    lyrics_toggled = Signal()
    stems_mixer_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nowPlayingPanel")
        self.setFixedWidth(280)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("panelHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Now Playing")
        title.setObjectName("panelTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)
        layout.addWidget(self._divider())

        # Song Info
        song_info = QWidget()
        song_info.setObjectName("nowPlayingInfo")
        song_info.setMinimumHeight(420)

        si_layout = QVBoxLayout(song_info)
        si_layout.setContentsMargins(24, 24, 24, 16)
        si_layout.setSpacing(12)
        si_layout.setAlignment(Qt.AlignHCenter)

        self.cover_art = CoverArtWidget(size=200)
        si_layout.addWidget(self.cover_art, 0, Qt.AlignCenter)

        self.song_title = MarqueeLabel("No song playing")
        self.song_title.setObjectName("npSongTitle")
        self.song_title.setAlignment(Qt.AlignCenter)
        self.song_title.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
        """)

        self.song_artist = MarqueeLabel("—")
        self.song_artist.setObjectName("npSongArtist")
        self.song_artist.setAlignment(Qt.AlignCenter)
        self.song_artist.setStyleSheet("""
            font-size: 17px;
            font-weight: 500;
        """)

        self.song_album = MarqueeLabel("")
        self.song_album.setObjectName("npSongAlbum")
        self.song_album.setAlignment(Qt.AlignCenter)
        self.song_album.setStyleSheet("""
            font-size: 14px;
        """)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self.genre_label = QLabel("")
        self.genre_label.setObjectName("npStat")
        self.genre_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 600;
        """)

        stats_row.addStretch()
        stats_row.addWidget(self.genre_label)
        stats_row.addStretch()

        si_layout.addWidget(self.song_title)
        si_layout.addWidget(self.song_artist)
        si_layout.addWidget(self.song_album)
        si_layout.addLayout(stats_row)

        si_layout.addStretch()

        layout.addWidget(song_info)
        layout.addWidget(self._divider())

        # Action buttons
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(24, 12, 24, 12)
        btn_layout.setSpacing(8)
        
        self.btn_lyrics_view = QPushButton("♩ Lyrics")
        self.btn_lyrics_view.setObjectName("viewToggleBtn")
        self.btn_lyrics_view.setCheckable(True)
        self.btn_lyrics_view.setCursor(Qt.PointingHandCursor)
        self.btn_lyrics_view.clicked.connect(self.lyrics_toggled.emit)
        
        self.btn_stems_mixer = QPushButton("🎚 Stems Mixer")
        self.btn_stems_mixer.setObjectName("stemsMixerBtn")
        self.btn_stems_mixer.setCursor(Qt.PointingHandCursor)
        self.btn_stems_mixer.setEnabled(False)
        self.btn_stems_mixer.clicked.connect(self.stems_mixer_toggled.emit)
        
        btn_layout.addWidget(self.btn_lyrics_view)
        btn_layout.addWidget(self.btn_stems_mixer)
        
        layout.addLayout(btn_layout)
        layout.addStretch(1)

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("panelDivider")
        return line

    # ── Public Update Methods ─────────────────────────────────────────────────

    def update_song(self, song: SongPackage):
        """Update all song information from a SongPackage."""
        self.song_title.setText(song.name)
        self.song_artist.setText(song.artist)
        self.song_album.setText(song.album)
        self.genre_label.setText(song.genre)
        self.cover_art.load_cover(song.album_art)
        
        has_stems = len(song.audio_tracks) > 1 if song.audio_tracks else False
        self.btn_stems_mixer.setEnabled(has_stems)

    def clear(self):
        """Reset to no-song state."""
        self.song_title.setText("No song playing")
        self.song_artist.setText("—")
        self.song_album.setText("")
        self.genre_label.setText("")
        self.cover_art._draw_placeholder()
        self.btn_stems_mixer.setEnabled(False)
