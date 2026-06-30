"""
Main Panel - Center content area
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QScrollArea, QAbstractItemView, QStackedWidget,
    QStyledItemDelegate, QFileDialog, QSizePolicy, QTextBrowser,
    QMenu, QDialog, QCheckBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor, QBrush
from utils.scanner import SongPackage, format_duration
from utils.marquee import MarqueeLabel
from typing import List
import re
import os


# ═══════════════════════════════════════════════════════════════
# SORT CONSTANTS
# ═══════════════════════════════════════════════════════════════

SORT_TITLE = "title"
SORT_ARTIST = "artist"
SORT_ALBUM = "album"
SORT_YEAR = "year"
SORT_GENRE = "genre"
SORT_CHARTER = "charter"
SORT_DURATION = "duration"
SORT_DATE_ADDED = "date_added"

SORT_OPTIONS = [
    (SORT_TITLE, "Title"),
    (SORT_ARTIST, "Artist"),
    (SORT_ALBUM, "Album"),
    (SORT_YEAR, "Year"),
    (SORT_GENRE, "Genre"),
    (SORT_CHARTER, "Charter"),
    (SORT_DURATION, "Duration"),
    (SORT_DATE_ADDED, "Last Added"),
]


# ═══════════════════════════════════════════════════════════════
# SORT BAR WIDGET
# ═══════════════════════════════════════════════════════════════

class SortBar(QWidget):
    """Horizontal bar with sort-field buttons and asc/desc toggle."""

    sort_changed = Signal(str, bool)   # (sort_key, ascending)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sortBar")
        self.setFixedHeight(38)

        self._current_key = SORT_TITLE
        self._ascending = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(6)

        # Label
        lbl = QLabel("Sort:")
        lbl.setObjectName("sortLabel")
        layout.addWidget(lbl)

        # Sort field buttons
        self._buttons = {}

        for key, label in SORT_OPTIONS:
            btn = QPushButton(label)
            btn.setObjectName("sortFieldBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(key == self._current_key)
            btn.clicked.connect(
                lambda checked, k=key: self._on_field_clicked(k)
            )
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

        # Asc/Desc toggle
        self._order_btn = QPushButton("↑ A-Z")
        self._order_btn.setObjectName("sortOrderBtn")
        self._order_btn.setCursor(Qt.PointingHandCursor)
        self._order_btn.clicked.connect(self._toggle_order)
        layout.addWidget(self._order_btn)

    # ---------------------------------------------------------

    def _on_field_clicked(self, key: str):
        """User clicked a sort-field button."""

        if key == self._current_key:
            # same field → toggle direction
            self._toggle_order()
            return

        self._current_key = key
        self._ascending = True
        self._update_ui()
        self.sort_changed.emit(
            self._current_key,
            self._ascending
        )

    def _toggle_order(self):
        self._ascending = not self._ascending
        self._update_ui()
        self.sort_changed.emit(
            self._current_key,
            self._ascending
        )

    def _update_ui(self):
        # Update checked state
        for key, btn in self._buttons.items():
            btn.setChecked(key == self._current_key)

        # Update order button text
        if self._ascending:
            self._order_btn.setText("↑ A-Z")
        else:
            self._order_btn.setText("↓ Z-A")

    # ---------------------------------------------------------

    @property
    def current_key(self):
        return self._current_key

    @property
    def ascending(self):
        return self._ascending

class RowHoverDelegate(QStyledItemDelegate):
    """Delegate that paints hover background for the entire row."""
    HOVER_BG = QColor("#0d1e3a")

    def __init__(self, table, parent=None):
        super().__init__(parent)
        self._table = table

    def paint(self, painter, option, index):
        if index.row() == self._table.hovered_row:
            painter.save()
            painter.fillRect(option.rect, self.HOVER_BG)
            painter.restore()
        super().paint(painter, option, index)

class TableMarqueeLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

        self.px = 0
        self.text_width = 0
        self.spacing = 40
        self.left_padding = 10
        self.speed = 1

        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_position)
        self._timer.start(35)

        self.update_metrics()

    def setText(self, text):
        super().setText(text or "—")
        self.px = 0
        self.update_metrics()
        self.update()

    def setFont(self, font):
        super().setFont(font)
        self.update_metrics()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_metrics()

    def update_metrics(self):
        fm = QFontMetrics(self.font())
        self.text_width = fm.horizontalAdvance(self.text())

    def update_position(self):
        available_width = max(0, self.width() - self.left_padding * 2)

        if self.text_width > available_width:
            self.px -= self.speed

            if -self.px >= self.text_width + self.spacing:
                self.px = 0

            self.update()
        else:
            if self.px != 0:
                self.px = 0
                self.update()

    def paintEvent(self, event):
        available_width = max(0, self.width() - self.left_padding * 2)

        if self.text_width > available_width:
            painter = QPainter(self)
            painter.setClipRect(self.rect())
            painter.setPen(self.palette().windowText().color())

            fm = QFontMetrics(self.font())
            y = (self.height() + fm.ascent() - fm.descent()) // 2

            x = self.left_padding + self.px

            painter.drawText(x, y, self.text())
            painter.drawText(
                x + self.text_width + self.spacing,
                y,
                self.text()
            )
        else:
            painter = QPainter(self)
            painter.setPen(self.palette().windowText().color())

            fm = QFontMetrics(self.font())
            y = (self.height() + fm.ascent() - fm.descent()) // 2

            painter.drawText(
                self.left_padding,
                y,
                self.text()
            )

class SongTableWidget(QTableWidget):
    song_double_clicked = Signal(int)
    add_to_playlist = Signal(str, int)      # folder_path, playlist_id
    add_to_new_playlist = Signal(str)       # folder_path
    COLUMNS = [
        "Title",
        "Artist",
        "Album",
        "Year",
        "Genre",
        "Charter",
        "Duration",
    ]

    (
        COL_TITLE,
        COL_ARTIST,
        COL_ALBUM,
        COL_YEAR,
        COL_GENRE,
        COL_CHARTER,
        COL_DURATION,
    ) = range(7)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_row = -1
        self._songs: List[SongPackage] = []
        self._playing_row = -1
        self._playlists = []  # [(id, name), ...]
        self._setup_table()
        self._setup_row_hover()

    def _setup_table(self):
        self.setObjectName("songTable")

        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # ==========================================
        # TABLE BEHAVIOR
        # ==========================================

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setShowGrid(False)
        self.setAlternatingRowColors(False)

        self.verticalHeader().setVisible(False)

        self.doubleClicked.connect(
            lambda idx: self.song_double_clicked.emit(idx.row())
        )

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # ==========================================
        # HEADER
        # ==========================================

        header = self.horizontalHeader()

        header.setObjectName("tableHeader")
        header.setHighlightSections(False)

        header.setSectionsMovable(False)
        header.setSectionResizeMode(QHeaderView.Fixed)

        # Better UX
        header.setMinimumSectionSize(80)

        # ==========================================
        # COLUMN WIDTHS
        # ==========================================

        self.setColumnWidth(self.COL_ARTIST, 200)
        self.setColumnWidth(self.COL_ALBUM, 200)
        self.setColumnWidth(self.COL_YEAR, 80)
        self.setColumnWidth(self.COL_GENRE, 140)
        self.setColumnWidth(self.COL_CHARTER, 160)
        self.setColumnWidth(self.COL_DURATION, 90)

        # Title stretches to fill available space
        header.setSectionResizeMode(
            self.COL_TITLE,
            QHeaderView.Stretch
        )

        header.setSectionResizeMode(
            self.COL_YEAR,
            QHeaderView.Fixed
        )

        header.setSectionResizeMode(
            self.COL_DURATION,
            QHeaderView.Fixed
        )

        # ==========================================
        # SCROLL
        # ==========================================

        self.setHorizontalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.setVerticalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        # ==========================================
        # ROW SIZE
        # ==========================================

        self.verticalHeader().setDefaultSectionSize(54)

        # ==========================================
        # STYLE TWEAKS
        # ==========================================

        self.setWordWrap(False)

        # Prevent ugly dotted focus border
        self.setFocusPolicy(Qt.NoFocus)

    def _setup_row_hover(self):
        """Enable full-row hover highlighting via viewport mouse tracking."""
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self.setItemDelegate(RowHoverDelegate(self, self))

    def eventFilter(self, obj, event):
        if obj is self.viewport():
            if event.type() == QEvent.MouseMove:
                index = self.indexAt(event.pos())
                new_row = index.row() if index.isValid() else -1
                if new_row != self.hovered_row:
                    old_row = self.hovered_row
                    self.hovered_row = new_row
                    self._refresh_row(old_row)
                    self._refresh_row(new_row)
            elif event.type() == QEvent.Leave:
                old_row = self.hovered_row
                self.hovered_row = -1
                self._refresh_row(old_row)
        return super().eventFilter(obj, event)

    def _refresh_row(self, row):
        """Request repaint for all cells in a row."""
        if row < 0:
            return
        for col in range(self.columnCount()):
            idx = self.model().index(row, col)
            self.update(idx)

    def set_playlists(self, playlists):
        """Update the cached playlist list for context menu.
        playlists: list of dicts with 'id' and 'name' keys.
        """
        self._playlists = [(pl["id"], pl["name"]) for pl in playlists]

    def _show_context_menu(self, position):
        index = self.indexAt(position)

        if not index.isValid():
            return

        row = index.row()

        if row < 0 or row >= len(self._songs):
            return

        self.selectRow(row)

        menu_style = """
            QMenu {
                background-color: #1e2638;
                color: #ffffff;
                border: 1px solid #3a4763;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2a3854;
            }
            QMenu::separator {
                height: 1px;
                background: #3a4763;
                margin: 4px 8px;
            }
        """

        menu = QMenu(self)
        menu.setStyleSheet(menu_style)

        action_play = menu.addAction("\u25b6  Play")
        action_open_folder = menu.addAction("\U0001f4c2  Open folder location")
        menu.addSeparator()

        # ── Add to Playlist submenu ──
        playlist_submenu = menu.addMenu("\u229e  Add to Playlist")
        playlist_submenu.setStyleSheet(menu_style)

        action_new_playlist = playlist_submenu.addAction("\u2795  New Playlist...")

        if self._playlists:
            playlist_submenu.addSeparator()

        playlist_actions = {}
        for pl_id, pl_name in self._playlists:
            action = playlist_submenu.addAction(f"\u266a  {pl_name}")
            playlist_actions[action] = pl_id

        selected_action = menu.exec(self.viewport().mapToGlobal(position))

        if not selected_action:
            return

        song = self._songs[row]

        if selected_action == action_play:
            self.song_double_clicked.emit(row)
        elif selected_action == action_open_folder:
            if hasattr(os, 'startfile'):
                os.startfile(song.folder_path)
        elif selected_action == action_new_playlist:
            self.add_to_new_playlist.emit(song.folder_path)
        elif selected_action in playlist_actions:
            pl_id = playlist_actions[selected_action]
            self.add_to_playlist.emit(song.folder_path, pl_id)

    def load_songs(
        self,
        songs: List[SongPackage],
        sort_key: str = SORT_TITLE,
        ascending: bool = True
    ):
        """Populate the table with scanned SongPackage data."""

        self._songs = list(songs)  # keep a mutable copy

        # Apply sort
        self._sort_songs(sort_key, ascending)

        self._populate_table()

    # ---------------------------------------------------------

    def _sort_songs(
        self,
        sort_key: str,
        ascending: bool
    ):
        """Sort _songs list in place."""
        if not sort_key:
            return

        key_map = {
            SORT_TITLE:    lambda s: (s.name or "").lower(),
            SORT_ARTIST:   lambda s: (s.artist or "").lower(),
            SORT_ALBUM:    lambda s: (s.album or "").lower(),
            SORT_YEAR:     lambda s: int(s.year) if str(s.year).isdigit() else 0,
            SORT_GENRE:    lambda s: (s.genre or "").lower(),
            SORT_CHARTER:  lambda s: (s.charter or "").lower(),
            SORT_DURATION: lambda s: s.duration_ms or 0,
            SORT_DATE_ADDED: lambda s: s.created_at or 0,
        }

        key_fn = key_map.get(
            sort_key,
            key_map[SORT_TITLE]
        )

        self._songs.sort(
            key=key_fn,
            reverse=not ascending
        )

    def resort(
        self,
        sort_key: str,
        ascending: bool
    ):
        """Re-sort current songs without reloading."""
        self._sort_songs(sort_key, ascending)
        self._populate_table()

    # ---------------------------------------------------------

    def _populate_table(self):
        """Fill table rows from _songs list."""

        self._playing_row = -1
        self.clearSelection()

        # Penting:
        # bersihkan cell widget lama agar marquee label lama tidak menumpuk
        self.setRowCount(0)
        self.setRowCount(len(self._songs))

        muted = QColor("#8899bb")

        for row, song in enumerate(self._songs):

            # ==========================================
            # MARQUEE TEXT CELLS
            # ==========================================

            self._set_marquee_cell(
                row,
                self.COL_TITLE,
                song.name,
                is_title=True
            )

            self._set_marquee_cell(
                row,
                self.COL_ARTIST,
                song.artist
            )

            self._set_marquee_cell(
                row,
                self.COL_ALBUM,
                song.album
            )

            self._set_marquee_cell(
                row,
                self.COL_GENRE,
                song.genre
            )

            self._set_marquee_cell(
                row,
                self.COL_CHARTER,
                song.charter
            )

            # ==========================================
            # NORMAL TEXT CELLS
            # ==========================================

            year = QTableWidgetItem(song.year or "—")
            year.setTextAlignment(Qt.AlignCenter)
            year.setForeground(muted)
            self.setItem(row, self.COL_YEAR, year)

            # Duration from song.ini song_length (ms → seconds)
            dur_text = (
                format_duration(song.duration_ms / 1000)
                if song.duration_ms > 0
                else "—"
            )

            d = QTableWidgetItem(dur_text)
            d.setTextAlignment(Qt.AlignCenter)
            d.setForeground(muted)
            self.setItem(row, self.COL_DURATION, d)

    def get_song(self, row: int) -> SongPackage:
        """Return the SongPackage for a given row index."""
        return self._songs[row]

    def get_songs(self) -> List[SongPackage]:
        """Return all loaded songs."""
        return self._songs

    def song_count(self) -> int:
        """Return the number of songs in the table."""
        return len(self._songs)

    def _set_marquee_cell(self, row, column, text, is_title=False):
        label = TableMarqueeLabel(text or "—")
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if is_title:
            label.setStyleSheet("""
                color: #e8eefc;
                background: transparent;
                font-size: 14px;
                font-weight: 600;
            """)
        else:
            label.setStyleSheet("""
                color: #8899bb;
                background: transparent;
                font-size: 13px;
                font-weight: 500;
            """)

        self.setCellWidget(row, column, label)

    def highlight_playing(self, row: int):
        """Highlight the currently playing row."""
        old_row = self._playing_row
        self._playing_row = row

        playing_color = QColor("#1a8cff")
        normal_title = QColor("#ffffff")
        muted = QColor("#8899bb")

        # Reset old row
        if 0 <= old_row < self.rowCount():
            item = self.item(old_row, self.COL_TITLE)
            if item:
                item.setForeground(normal_title)

        # Highlight new row
        if 0 <= row < self.rowCount():
            item = self.item(row, self.COL_TITLE)
            if item:
                item.setForeground(playing_color)
            self.selectRow(row)


class LyricsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("lyricsView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(20)

        # =========================================================
        # Scroll Area
        # =========================================================

        scroll = QScrollArea()
        scroll.setObjectName("lyricsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        # =========================================================
        # Container
        # =========================================================

        container = QWidget()
        container.setObjectName("lyricsContainer")

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # =========================================================
        # Lyrics Text
        # =========================================================

        self.lyrics_text = QTextBrowser()

        self.lyrics_text.setObjectName("lyricsText")

        self.lyrics_text.setReadOnly(True)

        self.lyrics_text.setFrameShape(QFrame.NoFrame)

        self.lyrics_text.setOpenExternalLinks(False)

        self.lyrics_text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.lyrics_text.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.lyrics_text.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.lyrics_text.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
            }
        """)

        container_layout.addWidget(self.lyrics_text)

        scroll.setWidget(container)

        # =========================================================
        # Add Widgets
        # =========================================================
        layout.addWidget(scroll, 1)

    # =============================================================
    # Convert <color=#xxxxxx>
    # =============================================================

    def convert_color_tag(self, plain_text):

        color_start_tag = "<color="
        color_end_tag = "</color>"

        converted_text = plain_text

        start_index = converted_text.find(color_start_tag)

        while start_index != -1:

            end_index = converted_text.find(
                ">",
                start_index
            )

            hex_start_index = (
                start_index + len(color_start_tag)
            )

            hex_end_index = converted_text.find(
                ">",
                hex_start_index
            )

            text_start_index = end_index + 1

            text_end_index = converted_text.find(
                color_end_tag,
                text_start_index
            )

            if (
                end_index != -1 and
                hex_end_index != -1 and
                text_end_index != -1
            ):

                hex_value = converted_text[
                    hex_start_index:hex_end_index
                ]

                text = converted_text[
                    text_start_index:text_end_index
                ]

                span = (
                    f"<span style='color:{hex_value};'>"
                    f"{text}"
                    f"</span>"
                )

                converted_text = (
                    converted_text[:start_index]
                    + span
                    + converted_text[
                        text_end_index + len(color_end_tag):
                    ]
                )

            else:
                break

            start_index = converted_text.find(
                color_start_tag
            )

        return converted_text

    # =============================================================
    # Convert custom tags
    # =============================================================

    def convert_html_tag(self, plain_text):

        tag_pattern = r"<(\/?)(b|i|lowercase|uppercase)>"

        matches = re.finditer(tag_pattern, plain_text)

        rich_text = ""

        last_end = 0

        for match in matches:

            tag_type = match.group(1)

            tag_name = match.group(2)

            start_index = match.start()

            end_index = match.end()

            rich_text += plain_text[last_end:start_index]

            if tag_type == "/":

                rich_text += "</span>"

            else:

                if tag_name == "b":

                    rich_text += (
                        "<span style='font-weight:bold;'>"
                    )

                elif tag_name == "i":

                    rich_text += (
                        "<span style='font-style:italic;'>"
                    )

                elif tag_name == "lowercase":

                    rich_text += (
                        "<span style='text-transform:lowercase;'>"
                    )

                elif tag_name == "uppercase":

                    rich_text += (
                        "<span style='text-transform:uppercase;'>"
                    )

            last_end = end_index

        rich_text += plain_text[last_end:]

        return rich_text

    # =============================================================
    # Update Lyrics
    # =============================================================

    def update_lyrics(
        self,
        lyrics: str
    ):

        if not lyrics:

            self.lyrics_text.setHtml("""
                <div style="
                    color:#777;
                    font-size:20px;
                    text-align:center;
                    margin-top:80px;
                ">
                    No lyrics available.
                </div>
            """)

            return

        # Convert tags
        lyrics = self.convert_html_tag(lyrics)

        lyrics = self.convert_color_tag(lyrics)

        # Preserve line breaks
        lyrics = lyrics.replace("\n", "<br>")

        # Final HTML
        html = f"""
        <html>
        <head>
            <style>

                body {{
                    background: transparent;
                    color: #EAEAEA;
                    font-size: 16px;
                    text-align: center;
                    font-weight: 500;
                    padding: 10px 20px;
                }}

            </style>
        </head>

        <body>
            {lyrics}
        </body>
        </html>
        """

        self.lyrics_text.setHtml(html)

class MainPanel(QWidget):
    # Signals emitted to MainWindow
    song_selected = Signal(int)
    folder_added = Signal(str, bool)
    list_changed = Signal()
    open_database_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mainPanel")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ─────────────────────────────────
        top_bar = QWidget()
        top_bar.setObjectName("mainTopBar")
        top_bar.setFixedHeight(64)

        tb = QHBoxLayout(top_bar)
        tb.setContentsMargins(24, 0, 24, 0)
        tb.setSpacing(12)

        self.title_label = QLabel("All Songs")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("0 songs")
        self.subtitle_label.setObjectName("mainSubtitle")

        tc = QVBoxLayout()
        tc.setSpacing(2)
        tc.addWidget(self.title_label)
        tc.addWidget(self.subtitle_label)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("  🔍  Search songs...")
        self.search_box.setFixedWidth(240)

        self.btn_play_all = QPushButton("▶ Play All")
        self.btn_play_all.setObjectName("playAllBtn")
        self.btn_play_all.setCursor(Qt.PointingHandCursor)

        self.btn_add_folder = QPushButton("⊕ Add Folder")
        self.btn_add_folder.setObjectName("addFolderBtn")
        self.btn_add_folder.setCursor(Qt.PointingHandCursor)
        self.btn_add_folder.clicked.connect(self._on_add_folder)

        self.btn_open_database = QPushButton("▣ Open Database")
        self.btn_open_database.setObjectName("openDatabaseBtn")
        self.btn_open_database.setCursor(Qt.PointingHandCursor)
        self.btn_open_database.clicked.connect(self.open_database_requested.emit)

        tb.addLayout(tc)
        tb.addStretch()
        tb.addWidget(self.search_box)
        tb.addWidget(self.btn_play_all)
        tb.addWidget(self.btn_add_folder)
        tb.addWidget(self.btn_open_database)

        layout.addWidget(top_bar)

        accent = QFrame()
        accent.setObjectName("accentLine")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        # ── Sort bar ────────────────────────────────
        self.sort_bar = SortBar()
        self.sort_bar.sort_changed.connect(self._on_sort_changed)
        layout.addWidget(self.sort_bar)

        # ── Stacked pages ───────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")
        self.song_table = SongTableWidget()
        self.stack.addWidget(self.song_table)
        self.lyrics_view = LyricsView()
        self.stack.addWidget(self.lyrics_view)
        layout.addWidget(self.stack, 1)

        # Connect table double-click → emit song_selected
        self.song_table.song_double_clicked.connect(
            self.song_selected.emit
        )

    # ─────────────────────────────────────────────────────────
    # SORT
    # ─────────────────────────────────────────────────────────

    def _on_sort_changed(self, sort_key: str, ascending: bool):
        """Re-sort the current table data."""
        self.song_table.resort(sort_key, ascending)
        self.list_changed.emit()

    # ─────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────

    def _on_add_folder(self):
        """Open Add Folder dialog and emit folder path + import lyrics flag."""
        dialog = AddFolderDialog(self)
        if dialog.exec() == QDialog.Accepted:
            folder = dialog.folder_path()
            import_lyrics = dialog.import_lyrics()
            if folder:
                self.folder_added.emit(folder, import_lyrics)

    def load_songs(self, songs: List[SongPackage], apply_sort: bool = True):
        """Load songs into the table and update subtitle."""
        if apply_sort:
            sort_key = self.sort_bar.current_key
            ascending = self.sort_bar.ascending
        else:
            sort_key = None
            ascending = False

        self.song_table.load_songs(
            songs,
            sort_key=sort_key,
            ascending=ascending
        )
        self.subtitle_label.setText(f"{len(songs)} songs")
        self.list_changed.emit()

    def _toggle_view(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)


# ═══════════════════════════════════════════════════════════════
# ADD FOLDER DIALOG
# ═══════════════════════════════════════════════════════════════

class AddFolderDialog(QDialog):
    """Custom dialog for adding a song folder with optional lyrics import."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Folder")
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QDialog {
                background: #0a1628;
                color: #e8edf7;
            }
            QLabel {
                color: #c0ccdd;
                font-size: 13px;
                background: transparent;
            }
            QLineEdit {
                background: #0f2040;
                color: #e8edf7;
                border: 1px solid #1a305d;
                border-radius: 4px;
                padding: 8px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton#browseBtn {
                background: #1a305d;
                color: #e8edf7;
                border: none;
                border-radius: 4px;
                padding: 8px 14px;
                font-size: 13px;
            }
            QPushButton#browseBtn:hover {
                background: #2563eb;
            }
            QCheckBox {
                color: #c0ccdd;
                font-size: 13px;
                spacing: 8px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #1a305d;
                border-radius: 4px;
                background: #0f2040;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border-color: #3b82f6;
            }
            QDialogButtonBox QPushButton {
                background: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 600;
            }
            QDialogButtonBox QPushButton:hover {
                background: #2563eb;
            }
            QDialogButtonBox QPushButton[text="Cancel"] {
                background: #1a305d;
            }
            QDialogButtonBox QPushButton[text="Cancel"]:hover {
                background: #243b6a;
            }
        """)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Add Songs Folder")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #e8edf7;"
        )
        layout.addWidget(title)

        # Path row
        path_label = QLabel("Folder Path:")
        layout.addWidget(path_label)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Select a folder...")

        btn_browse = QPushButton("📁 Browse")
        btn_browse.setObjectName("browseBtn")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_folder)

        path_row.addWidget(self._path_input, 1)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)

        # Checkbox
        self._chk_lyrics = QCheckBox("Import Lyrics (may take longer)")
        self._chk_lyrics.setChecked(True)
        self._chk_lyrics.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._chk_lyrics)

        # Spacer
        layout.addSpacing(8)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Songs Folder"
        )
        if folder:
            self._path_input.setText(folder)

    def folder_path(self) -> str:
        return self._path_input.text().strip()

    def import_lyrics(self) -> bool:
        return self._chk_lyrics.isChecked()
