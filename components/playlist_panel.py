"""
Left Panel - Playlist sidebar
Shows library navigation, playlists, and quick actions
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QScrollArea,
    QInputDialog, QMessageBox, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap

from utils.database import DatabaseManager, Playlist


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
    clicked = Signal(object)       # Playlist
    rename_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, playlist: Playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.setObjectName("playlistItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(56)
        self._selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Cover art placeholder
        self.cover = QLabel()
        self.cover.setFixedSize(40, 40)
        self.cover.setObjectName("playlistCover")
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setText("♪")

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLabel(playlist.name)
        self.name_label.setObjectName("playlistName")

        count = len(playlist.song_ids)
        self.count_label = QLabel(f"{count} song{'s' if count != 1 else ''}")
        self.count_label.setObjectName("playlistCount")

        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.count_label)

        layout.addWidget(self.cover)
        layout.addLayout(text_layout)
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.playlist)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setObjectName("contextMenu")
        rename_action = menu.addAction("✏  Rename")
        delete_action = menu.addAction("🗑  Delete")
        action = menu.exec(event.globalPos())
        if action == rename_action:
            self.rename_requested.emit(self.playlist)
        elif action == delete_action:
            self.delete_requested.emit(self.playlist)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def update_playlist(self, playlist: Playlist):
        self.playlist = playlist
        self.name_label.setText(playlist.name)
        count = len(playlist.song_ids)
        self.count_label.setText(f"{count} song{'s' if count != 1 else ''}")


class PlaylistPanel(QWidget):
    """
    Left sidebar panel. Shows navigation links and user playlists.
    """

    # Signals to main window
    navigate = Signal(str)           # "library" | "recent" | "favorites"
    playlist_selected = Signal(object)  # Playlist
    playlist_created = Signal(object)
    playlist_deleted = Signal(str)       # playlist_id

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("playlistPanel")
        self.setFixedWidth(260)
        self._playlist_widgets: dict[str, PlaylistItem] = {}
        self._active_playlist_id: str = ""

        self._build_ui()
        self._load_playlists()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Logo / App Name ───────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("panelHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("◈")
        logo.setObjectName("logoIcon")
        app_name = QLabel("LUMINA")
        app_name.setObjectName("appName")

        h_layout.addWidget(logo)
        h_layout.addWidget(app_name)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # Divider
        main_layout.addWidget(self._divider())

        # ── Navigation ────────────────────────────────────────────────────────
        nav_section = QWidget()
        nav_layout = QVBoxLayout(nav_section)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)

        nav_layout.addWidget(SectionHeader("  Library"))

        self.btn_all = NavItem("⊞", "All Songs")
        self.btn_recent = NavItem("◷", "Recently Played")
        self.btn_favorites = NavItem("♡", "Favorites")
        self.btn_folders = NavItem("⊡", "Folders")

        self.btn_all.setChecked(True)

        for btn in (self.btn_all, self.btn_recent, self.btn_favorites, self.btn_folders):
            nav_layout.addWidget(btn)

        self.btn_all.clicked.connect(lambda: self._nav_clicked("library", self.btn_all))
        self.btn_recent.clicked.connect(lambda: self._nav_clicked("recent", self.btn_recent))
        self.btn_favorites.clicked.connect(lambda: self._nav_clicked("favorites", self.btn_favorites))
        self.btn_folders.clicked.connect(lambda: self._nav_clicked("folders", self.btn_folders))

        main_layout.addWidget(nav_section)
        main_layout.addWidget(self._divider())

        # ── Playlists ─────────────────────────────────────────────────────────
        playlist_header = QWidget()
        ph_layout = QHBoxLayout(playlist_header)
        ph_layout.setContentsMargins(16, 12, 16, 4)

        pl_label = SectionHeader("  Playlists")
        ph_layout.addWidget(pl_label)
        ph_layout.addStretch()

        self.btn_new_playlist = QPushButton("+")
        self.btn_new_playlist.setObjectName("addPlaylistBtn")
        self.btn_new_playlist.setFixedSize(26, 26)
        self.btn_new_playlist.setCursor(Qt.PointingHandCursor)
        self.btn_new_playlist.setToolTip("New playlist")
        self.btn_new_playlist.clicked.connect(self._create_playlist)
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

        # ── Bottom actions ────────────────────────────────────────────────────
        main_layout.addWidget(self._divider())
        bottom = QWidget()
        bottom.setObjectName("panelBottom")
        b_layout = QHBoxLayout(bottom)
        b_layout.setContentsMargins(16, 12, 16, 12)

        self.btn_settings = QPushButton("⚙  Settings")
        self.btn_settings.setObjectName("settingsBtn")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        b_layout.addWidget(self.btn_settings)

        main_layout.addWidget(bottom)

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("panelDivider")
        return line

    def _nav_clicked(self, route: str, sender_btn: NavItem):
        for btn in (self.btn_all, self.btn_recent, self.btn_favorites, self.btn_folders):
            btn.setChecked(btn == sender_btn)
        # Deselect playlists
        for w in self._playlist_widgets.values():
            w.set_selected(False)
        self._active_playlist_id = ""
        self.navigate.emit(route)

    # ── Playlist Management ───────────────────────────────────────────────────

    def _load_playlists(self):
        for playlist in self.db.get_all_playlists():
            self._add_playlist_widget(playlist)

    def _add_playlist_widget(self, playlist: Playlist):
        widget = PlaylistItem(playlist)
        widget.clicked.connect(self._on_playlist_clicked)
        widget.rename_requested.connect(self._rename_playlist)
        widget.delete_requested.connect(self._delete_playlist)

        # Insert before the stretch
        layout = self.playlist_list_layout
        layout.insertWidget(layout.count() - 1, widget)
        self._playlist_widgets[playlist.id] = widget

    def _on_playlist_clicked(self, playlist: Playlist):
        # Deselect all nav buttons
        for btn in (self.btn_all, self.btn_recent, self.btn_favorites, self.btn_folders):
            btn.setChecked(False)
        # Highlight selected playlist
        for pid, w in self._playlist_widgets.items():
            w.set_selected(pid == playlist.id)
        self._active_playlist_id = playlist.id
        self.playlist_selected.emit(playlist)

    def _create_playlist(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            playlist = self.db.create_playlist(name.strip())
            self._add_playlist_widget(playlist)
            self.playlist_created.emit(playlist)

    def _rename_playlist(self, playlist: Playlist):
        name, ok = QInputDialog.getText(
            self, "Rename Playlist", "New name:", text=playlist.name
        )
        if ok and name.strip():
            playlist.name = name.strip()
            self.db.update_playlist(playlist)
            if playlist.id in self._playlist_widgets:
                self._playlist_widgets[playlist.id].update_playlist(playlist)

    def _delete_playlist(self, playlist: Playlist):
        reply = QMessageBox.question(
            self, "Delete Playlist",
            f'Delete "{playlist.name}"?\nThis cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_playlist(playlist.id)
            widget = self._playlist_widgets.pop(playlist.id, None)
            if widget:
                widget.deleteLater()
            self.playlist_deleted.emit(playlist.id)

    def refresh_playlist(self, playlist_id: str):
        """Called after songs are added/removed from a playlist."""
        playlist = self.db.get_playlist(playlist_id)
        if playlist and playlist_id in self._playlist_widgets:
            self._playlist_widgets[playlist_id].update_playlist(playlist)
