"""
Right Panel - Now Playing sidebar
Shows current song info, cover art, and queue
"""

import base64
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QScrollArea,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QLinearGradient

from utils.database import Song
from utils.scanner import format_duration


class CoverArtWidget(QLabel):
    """Rounded square cover art display."""

    def __init__(self, size=200, parent=None):
        super().__init__(parent)
        self._size = size
        self._pixmap: Optional[QPixmap] = None
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setObjectName("coverArt")
        self._draw_placeholder()

    def _draw_placeholder(self):
        px = QPixmap(self._size, self._size)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background gradient
        grad = QLinearGradient(0, 0, self._size, self._size)
        grad.setColorAt(0, QColor("#0d2145"))
        grad.setColorAt(1, QColor("#091428"))
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._size, self._size, 16, 16)
        painter.fillPath(path, QBrush(grad))

        # Music note
        painter.setPen(QColor("#1e4080"))
        painter.setFont(self.font())
        from PySide6.QtGui import QFont
        f = QFont("Segoe UI", int(self._size * 0.3))
        painter.setFont(f)
        painter.drawText(px.rect(), Qt.AlignCenter, "♪")
        painter.end()
        self.setPixmap(px)

    def set_cover(self, b64_data: Optional[str]):
        if not b64_data:
            self._draw_placeholder()
            return
        try:
            raw = base64.b64decode(b64_data)
            px = QPixmap()
            px.loadFromData(raw)
            if not px.isNull():
                px = px.scaled(self._size, self._size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # Crop to square
                x = (px.width() - self._size) // 2
                y = (px.height() - self._size) // 2
                px = px.copy(x, y, self._size, self._size)
                # Rounded corners mask
                rounded = QPixmap(self._size, self._size)
                rounded.fill(Qt.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(0, 0, self._size, self._size, 16, 16)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, px)
                painter.end()
                self.setPixmap(rounded)
                return
        except Exception:
            pass
        self._draw_placeholder()


class QueueItemWidget(QWidget):
    def __init__(self, song: Song, index: int, is_current: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("queueItem")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Position / playing indicator
        pos_label = QLabel("▶" if is_current else str(index + 1))
        pos_label.setObjectName("queueItemCurrent" if is_current else "queueItemIndex")
        pos_label.setFixedWidth(24)
        pos_label.setAlignment(Qt.AlignCenter)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.setContentsMargins(0, 0, 0, 0)

        title = QLabel(song.title)
        title.setObjectName("queueItemTitle" + ("Active" if is_current else ""))
        title.setMaximumWidth(160)

        artist = QLabel(song.artist)
        artist.setObjectName("queueItemArtist")
        artist.setMaximumWidth(160)

        text_col.addWidget(title)
        text_col.addWidget(artist)

        dur = QLabel(format_duration(song.duration))
        dur.setObjectName("queueItemDuration")
        dur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(pos_label)
        layout.addLayout(text_col, 1)
        layout.addWidget(dur)


class NowPlayingPanel(QWidget):
    """
    Right sidebar panel showing current song and queue.
    """

    queue_song_activated = Signal(int)  # queue index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nowPlayingPanel")
        self.setFixedWidth(280)
        self._songs: list[Song] = []
        self._current_index: int = -1

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
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

        # ── Song Info ─────────────────────────────────────────────────────────
        song_info = QWidget()
        song_info.setObjectName("nowPlayingInfo")
        si_layout = QVBoxLayout(song_info)
        si_layout.setContentsMargins(24, 24, 24, 16)
        si_layout.setSpacing(12)
        si_layout.setAlignment(Qt.AlignHCenter)

        self.cover_art = CoverArtWidget(size=200)
        si_layout.addWidget(self.cover_art, 0, Qt.AlignCenter)

        self.song_title = QLabel("—")
        self.song_title.setObjectName("npSongTitle")
        self.song_title.setAlignment(Qt.AlignCenter)
        self.song_title.setWordWrap(True)

        self.song_artist = QLabel("—")
        self.song_artist.setObjectName("npSongArtist")
        self.song_artist.setAlignment(Qt.AlignCenter)

        self.song_album = QLabel("")
        self.song_album.setObjectName("npSongAlbum")
        self.song_album.setAlignment(Qt.AlignCenter)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self.play_count_label = QLabel("Plays: —")
        self.play_count_label.setObjectName("npStat")
        self.genre_label = QLabel("")
        self.genre_label.setObjectName("npStat")

        stats_row.addStretch()
        stats_row.addWidget(self.play_count_label)
        stats_row.addWidget(self.genre_label)
        stats_row.addStretch()

        # Favorite button
        fav_row = QHBoxLayout()
        self.btn_favorite = QPushButton("♡")
        self.btn_favorite.setObjectName("favBtn")
        self.btn_favorite.setFixedSize(36, 36)
        self.btn_favorite.setCursor(Qt.PointingHandCursor)
        self.btn_favorite.setCheckable(True)

        fav_row.addStretch()
        fav_row.addWidget(self.btn_favorite)
        fav_row.addStretch()

        si_layout.addWidget(self.song_title)
        si_layout.addWidget(self.song_artist)
        si_layout.addWidget(self.song_album)
        si_layout.addLayout(stats_row)
        si_layout.addLayout(fav_row)

        layout.addWidget(song_info)
        layout.addWidget(self._divider())

        # ── Queue ─────────────────────────────────────────────────────────────
        queue_header = QWidget()
        qh_layout = QHBoxLayout(queue_header)
        qh_layout.setContentsMargins(20, 8, 20, 8)

        queue_label = QLabel("UP NEXT")
        queue_label.setObjectName("sectionHeader")
        self.queue_count = QLabel("")
        self.queue_count.setObjectName("queueCount")

        qh_layout.addWidget(queue_label)
        qh_layout.addStretch()
        qh_layout.addWidget(self.queue_count)

        layout.addWidget(queue_header)

        # Queue scroll
        scroll = QScrollArea()
        scroll.setObjectName("queueScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.queue_container = QWidget()
        self.queue_container.setObjectName("queueContainer")
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(0)
        self.queue_layout.addStretch()

        scroll.setWidget(self.queue_container)
        layout.addWidget(scroll, 1)

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("panelDivider")
        return line

    # ── Public API ────────────────────────────────────────────────────────────

    def set_current_song(self, song: Optional[Song]):
        if song:
            self.song_title.setText(song.title)
            self.song_artist.setText(song.artist)
            self.song_album.setText(song.album)
            self.play_count_label.setText(f"Plays: {song.play_count}")
            self.genre_label.setText(song.genre or "")
            self.cover_art.set_cover(song.cover_art)
        else:
            self.song_title.setText("—")
            self.song_artist.setText("—")
            self.song_album.setText("")
            self.play_count_label.setText("Plays: —")
            self.genre_label.setText("")
            self.cover_art.set_cover(None)

    def update_queue(self, songs: list[Song], current_index: int):
        self._songs = songs
        self._current_index = current_index

        # Clear existing
        while self.queue_layout.count() > 1:
            item = self.queue_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Show next songs (skip current, show up to 20)
        shown = 0
        for i, song in enumerate(songs):
            if i <= current_index:
                continue
            widget = QueueItemWidget(song, i, is_current=False)
            self.queue_layout.insertWidget(shown, widget)
            shown += 1
            if shown >= 20:
                break

        remaining = max(0, len(songs) - current_index - 1)
        self.queue_count.setText(f"{remaining} songs")
