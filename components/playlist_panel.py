"""
Left Panel - Playlist sidebar
"""

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QMenu, QInputDialog,
    QMessageBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal


class SectionHeader(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionHeader")


class NavItem(QPushButton):
    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("navItem")
        self.setCheckable(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        icon_lbl = QLabel(icon_text)
        icon_lbl.setObjectName("navIcon")
        icon_lbl.setFixedWidth(20)
        icon_lbl.setAlignment(Qt.AlignCenter)
        text_lbl = QLabel(label)
        text_lbl.setObjectName("navText")
        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)
        layout.addStretch()
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)


class PlaylistItem(QWidget):
    clicked = Signal(int)  # playlist_id
    rename_requested = Signal(int, str)  # playlist_id, current_name
    delete_requested = Signal(int, str)  # playlist_id, name

    def __init__(self, playlist_id: int, name: str, count: int, parent=None):
        super().__init__(parent)
        self._playlist_id = playlist_id
        self._name = name
        self.setObjectName("playlistItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        self.cover = QLabel("♪")
        self.cover.setFixedSize(40, 40)
        self.cover.setObjectName("playlistCover")
        self.cover.setAlignment(Qt.AlignCenter)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.name_label = QLabel(name)
        self.name_label.setObjectName("playlistName")
        self.count_label = QLabel(f"{count} song{'s' if count != 1 else ''}")
        self.count_label.setObjectName("playlistCount")
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.count_label)
        layout.addWidget(self.cover)
        layout.addLayout(text_layout)
        layout.addStretch()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._playlist_id)

    def _show_context_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
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
        """)

        action_rename = menu.addAction("✎  Rename")
        menu.addSeparator()
        action_delete = menu.addAction("✕  Delete")

        selected = menu.exec(self.mapToGlobal(position))

        if selected == action_rename:
            self.rename_requested.emit(self._playlist_id, self._name)
        elif selected == action_delete:
            self.delete_requested.emit(self._playlist_id, self._name)


class PlaylistPanel(QWidget):
    navigate = Signal(str)                # "library", "recent"
    playlist_selected = Signal(int)       # playlist_id
    new_playlist_requested = Signal()     # user clicks "+"
    playlist_delete_requested = Signal(int, str)   # playlist_id, name
    playlist_rename_requested = Signal(int, str)   # playlist_id, current_name
    engine_changed = Signal(int)          # 0 = VLC, 1 = Precision

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlistPanel")
        self.setFixedWidth(260)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Logo / App Name
        header = QWidget()
        header.setObjectName("panelHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        logo = QLabel()
        logo.setObjectName("logoIcon")

        pixmap = QPixmap("assets/icon.ico")
        logo.setPixmap(
            pixmap.scaled(
                28, 28,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )
        app_name = QLabel("CH Music Player")
        app_name.setObjectName("appName")
        h_layout.addWidget(logo)
        h_layout.addWidget(app_name)
        h_layout.addStretch()
        main_layout.addWidget(header)
        main_layout.addWidget(self._divider())

        # Navigation
        nav_section = QWidget()
        nav_layout = QVBoxLayout(nav_section)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)
        nav_layout.addWidget(SectionHeader("  Library"))
        self.btn_all = NavItem("⊞", "All Songs")
        self.btn_recent = NavItem("◷", "Recently Played")
        self.btn_all.setChecked(True)
        for btn in (self.btn_all, self.btn_recent):
            nav_layout.addWidget(btn)
        self.btn_all.clicked.connect(lambda: self._nav_clicked("library", self.btn_all))
        self.btn_recent.clicked.connect(lambda: self._nav_clicked("recent", self.btn_recent))
        main_layout.addWidget(nav_section)
        main_layout.addWidget(self._divider())

        # Playlists
        playlist_header = QWidget()
        ph_layout = QHBoxLayout(playlist_header)
        ph_layout.setContentsMargins(16, 12, 16, 4)
        ph_layout.addWidget(SectionHeader("  Playlists"))
        ph_layout.addStretch()
        self.btn_new_playlist = QPushButton("+")
        self.btn_new_playlist.setObjectName("addPlaylistBtn")
        self.btn_new_playlist.setFixedSize(26, 26)
        self.btn_new_playlist.setCursor(Qt.PointingHandCursor)
        self.btn_new_playlist.setToolTip("New playlist")
        self.btn_new_playlist.clicked.connect(self.new_playlist_requested.emit)
        ph_layout.addWidget(self.btn_new_playlist)
        main_layout.addWidget(playlist_header)

        # Scrollable playlist list
        scroll = QScrollArea()
        scroll.setObjectName("playlistScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        self.playlist_container = QWidget()
        self.playlist_container.setObjectName("playlistContainer")
        self.playlist_list_layout = QVBoxLayout(self.playlist_container)
        self.playlist_list_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_list_layout.setSpacing(0)
        self.playlist_list_layout.addStretch()
        scroll.setWidget(self.playlist_container)
        main_layout.addWidget(scroll, 1)

        # Playback Engine options (Moved from Now Playing Panel)
        main_layout.addWidget(self._divider())
        engine_layout = QVBoxLayout()
        engine_layout.setContentsMargins(20, 12, 20, 12)
        engine_layout.setSpacing(8)

        engine_label = QLabel("Playback Engine:")
        engine_label.setStyleSheet("color: #8899bb; font-size: 13px; font-weight: 600;")
        engine_layout.addWidget(engine_label)

        self.radio_stem = QRadioButton("Precision Engine (Stem Mixer)")
        self.radio_stem.setChecked(True)
        self.radio_stem.setCursor(Qt.PointingHandCursor)
        self.radio_stem.setStyleSheet("color: #e8edf7; font-size: 13px;")

        self.radio_vlc = QRadioButton("VLC Engine")
        self.radio_vlc.setCursor(Qt.PointingHandCursor)
        self.radio_vlc.setStyleSheet("color: #e8edf7; font-size: 13px;")

        # Group them logically
        self.engine_group = QButtonGroup(self)
        self.engine_group.addButton(self.radio_stem, 1)
        self.engine_group.addButton(self.radio_vlc, 0)
        self.engine_group.idClicked.connect(self.engine_changed.emit)

        engine_layout.addWidget(self.radio_stem)
        engine_layout.addWidget(self.radio_vlc)

        main_layout.addLayout(engine_layout)



    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("panelDivider")
        return line

    def _nav_clicked(self, route: str, sender_btn: NavItem):
        for btn in (self.btn_all, self.btn_recent):
            btn.setChecked(btn == sender_btn)
        self.navigate.emit(route)

    # ── Public Methods ────────────────────────────────────────────────────────

    def load_playlists(self, playlists):
        """
        Load playlists from database rows.
        Each row should have: id, name, song_count
        """
        # Clear existing playlist items (keep the stretch)
        while self.playlist_list_layout.count() > 1:
            item = self.playlist_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add playlist items
        for pl in playlists:
            widget = PlaylistItem(
                playlist_id=pl["id"],
                name=pl["name"],
                count=pl["song_count"]
            )
            widget.clicked.connect(self.playlist_selected.emit)
            widget.delete_requested.connect(self.playlist_delete_requested.emit)
            widget.rename_requested.connect(self.playlist_rename_requested.emit)
            # Insert before the stretch
            self.playlist_list_layout.insertWidget(
                self.playlist_list_layout.count() - 1,
                widget
            )
