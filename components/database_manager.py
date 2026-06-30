"""
Database Manager - View and manage SQLite database content.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.database import Database


class DatabaseManager(QDialog):
    database_changed = Signal()

    TABLES = [
        "songs",
        "scan_roots",
        "playlists",
        "playlist_songs",
        "play_history",
    ]

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)

        self.db = db
        self.current_table = "songs"
        self.rows = []

        self.setWindowTitle("Database Manager")
        self.resize(1100, 650)
        self.setMinimumSize(900, 500)

        self._build_ui()
        self._connect_signals()
        self.load_table("songs")

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        self.setObjectName("databaseManager")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # =================================================
        # TOP BAR
        # =================================================

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        title = QLabel("Database Manager")
        title.setObjectName("databaseManagerTitle")

        self.table_combo = QComboBox()
        self.table_combo.setObjectName("databaseTableCombo")
        self.table_combo.addItems(self.TABLES)
        self.table_combo.setFixedWidth(180)

        self.btn_refresh = QPushButton("↻ Refresh")
        self.btn_refresh.setObjectName("databaseRefreshBtn")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)

        self.btn_delete_selected = QPushButton("🗑 Delete Selected Row(s)")
        self.btn_delete_selected.setObjectName("databaseDeleteBtn")
        self.btn_delete_selected.setCursor(Qt.PointingHandCursor)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("databaseCloseBtn")
        self.btn_close.setCursor(Qt.PointingHandCursor)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Table:"))
        top_bar.addWidget(self.table_combo)
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_delete_selected)
        top_bar.addWidget(self.btn_close)

        layout.addLayout(top_bar)

        # =================================================
        # INFO LABEL
        # =================================================

        self.info_label = QLabel("")
        self.info_label.setObjectName("databaseInfoLabel")
        layout.addWidget(self.info_label)

        # =================================================
        # TABLE
        # =================================================

        self.table = QTableWidget()
        self.table.setObjectName("databaseViewerTable")

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(80)

        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        layout.addWidget(self.table, 1)

        self.setStyleSheet("""
            QDialog#databaseManager {
                background: #0a1628;
                color: #e8edf7;
            }

            QLabel#databaseManagerTitle {
                color: #e8edf7;
                font-size: 18px;
                font-weight: 700;
                background: transparent;
            }

            QLabel#databaseInfoLabel {
                color: #8899bb;
                font-size: 13px;
                background: transparent;
            }

            QComboBox#databaseTableCombo {
                background: #0f2040;
                color: #e8edf7;
                border: 1px solid #1a305d;
                border-radius: 6px;
                padding: 6px 10px;
            }

            QPushButton {
                border: none;
                border-radius: 7px;
                padding: 8px 12px;
                font-weight: 600;
            }

            QPushButton#databaseRefreshBtn {
                background: #10284f;
                color: #dbe7ff;
            }

            QPushButton#databaseRefreshBtn:hover {
                background: #163766;
            }

            QPushButton#databaseDeleteBtn {
                background: #5a1420;
                color: #ffdce2;
            }

            QPushButton#databaseDeleteBtn:hover {
                background: #7f1d2d;
            }

            QPushButton#databaseCloseBtn {
                background: #1a305d;
                color: #e8edf7;
            }

            QPushButton#databaseCloseBtn:hover {
                background: #2563eb;
            }

            QTableWidget#databaseViewerTable {
                background: #081225;
                color: #dbe7ff;
                border: 1px solid #14284f;
                border-radius: 8px;
                selection-background-color: #173b70;
                selection-color: #ffffff;
            }

            QTableWidget#databaseViewerTable::item {
                padding: 6px;
                border-bottom: 1px solid #0f2040;
            }

            QHeaderView::section {
                background: #0f2040;
                color: #9fb4d8;
                border: none;
                border-right: 1px solid #14284f;
                padding: 8px;
                font-weight: 700;
            }
        """)

    def _connect_signals(self):
        self.table_combo.currentTextChanged.connect(self.load_table)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_delete_selected.clicked.connect(self.delete_selected_rows)
        self.btn_close.clicked.connect(self.close)

    # =====================================================
    # LOAD DATABASE TABLE
    # =====================================================

    def load_table(self, table_name: str):
        if table_name not in self.TABLES:
            return

        self.current_table = table_name

        try:
            self.rows = self.db.fetchall(f"""
                SELECT *
                FROM {table_name}
            """)

            self._fill_table(self.rows)
            self._update_info()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to load table '{table_name}'.\n\n{e}"
            )

    def refresh(self):
        self.load_table(self.current_table)

    def _fill_table(self, rows):
        self.table.clear()

        if not rows:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        columns = rows[0].keys()

        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(columns)

        for row_idx, row in enumerate(rows):
            for col_idx, column in enumerate(columns):
                value = row[column]

                if value is None:
                    text = "NULL"
                else:
                    text = str(value)

                item = QTableWidgetItem(text)
                item.setToolTip(text)

                if column == "id":
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor("#8fa3c7"))

                elif column.endswith("_path") or column == "root_path":
                    item.setForeground(QColor("#b7d7ff"))

                else:
                    item.setForeground(QColor("#dbe7ff"))

                self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()

        # Biar kolom path tidak terlalu gila lebarnya
        for col_idx in range(self.table.columnCount()):
            width = self.table.columnWidth(col_idx)
            if width > 360:
                self.table.setColumnWidth(col_idx, 360)

    def _update_info(self):
        row_count = len(self.rows)

        if self.current_table == "songs":
            self.info_label.setText(
                f"Showing table: songs — {row_count} chart folders"
            )

        elif self.current_table == "scan_roots":
            self.info_label.setText(
                f"Showing table: scan_roots — {row_count} scan root folder(s). "
                "Deleting a scan root also removes all chart records inside it."
            )

        elif self.current_table == "playlists":
            self.info_label.setText(
                f"Showing table: playlists — {row_count} playlist(s). "
                "Deleting a playlist also removes its playlist song entries."
            )

        else:
            self.info_label.setText(
                f"Showing table: {self.current_table} — {row_count} rows"
            )

        self.btn_delete_selected

    def delete_selected_rows(self):
        selected_rows = sorted({
            index.row()
            for index in self.table.selectedIndexes()
        })

        if not selected_rows:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select one or more row(s) to delete."
            )
            return

        table = self.current_table

        if table == "songs":
            self._delete_from_songs(selected_rows)

        elif table == "scan_roots":
            self._delete_from_scan_roots(selected_rows)

        elif table == "playlists":
            self._delete_from_playlists(selected_rows)

        elif table == "playlist_songs":
            self._delete_from_playlist_songs(selected_rows)

        elif table == "play_history":
            self._delete_from_play_history(selected_rows)

        else:
            QMessageBox.warning(
                self,
                "Unsupported Table",
                f"Delete is not supported for table: {table}"
            )

    def _get_cell_text(self, row: int, column_name: str, default=""):
        col = self._column_index(column_name)

        if col < 0:
            return default

        item = self.table.item(row, col)

        if not item:
            return default

        return item.text()


    def _confirm_delete(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        return reply == QMessageBox.Yes


    def _after_delete(self, deleted_count: int):
        self.refresh()
        self.database_changed.emit()

        QMessageBox.information(
            self,
            "Deleted",
            f"Deleted {deleted_count} selected row(s)."
        )

    def _delete_from_songs(self, selected_rows):
        id_col = self._column_index("id")

        if id_col < 0:
            QMessageBox.critical(
                self,
                "Database Error",
                "Column 'id' was not found in songs table."
            )
            return

        song_ids = []
        preview = []

        for row in selected_rows:
            song_id = self._get_cell_text(row, "id")
            title = self._get_cell_text(row, "title", "Unknown Title")
            artist = self._get_cell_text(row, "artist", "Unknown Artist")

            if song_id:
                song_ids.append(song_id)
                preview.append(f"• {artist} - {title}")

        if not song_ids:
            return

        preview_text = "\n".join(preview[:10])

        if len(preview) > 10:
            preview_text += f"\n...and {len(preview) - 10} more"

        if not self._confirm_delete(
            "Delete Chart Record(s)",
            "This will remove the selected chart record(s) from the database.\n\n"
            "It will NOT delete the actual chart folder/files from disk.\n\n"
            f"{preview_text}\n\n"
            "Continue?"
        ):
            return

        try:
            self.db.cursor.executemany(
                """
                DELETE FROM songs
                WHERE id = ?
                """,
                [(song_id,) for song_id in song_ids]
            )

            self.db.conn.commit()
            self._after_delete(len(song_ids))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete selected song row(s).\n\n{e}"
            )

    def _delete_from_scan_roots(self, selected_rows):
        id_col = self._column_index("id")
        root_col = self._column_index("root_path")

        if id_col < 0 or root_col < 0:
            QMessageBox.critical(
                self,
                "Database Error",
                "Required columns 'id' and 'root_path' were not found."
            )
            return

        roots = []

        for row in selected_rows:
            root_id = self._get_cell_text(row, "id")
            root_path = self._get_cell_text(row, "root_path")

            if root_id and root_path:
                roots.append({
                    "id": root_id,
                    "root_path": root_path
                })

        if not roots:
            return

        preview_text = "\n".join(
            f"• {root['root_path']}"
            for root in roots[:8]
        )

        if len(roots) > 8:
            preview_text += f"\n...and {len(roots) - 8} more"

        affected_song_count = 0

        try:
            for root in roots:
                normalized_root = root["root_path"].replace("\\", "/").rstrip("/")

                result = self.db.fetchone(
                    """
                    SELECT COUNT(*) AS total
                    FROM songs
                    WHERE
                        REPLACE(folder_path, '\\', '/') = ?
                        OR REPLACE(folder_path, '\\', '/') LIKE ?
                    """,
                    (
                        normalized_root,
                        normalized_root + "/%"
                    )
                )

                affected_song_count += result["total"] if result else 0

        except Exception:
            affected_song_count = 0

        if not self._confirm_delete(
            "Delete Scan Root(s)",
            "This will remove the selected scan root folder(s) from the database.\n\n"
            "It will also remove all chart records inside those scan root folder(s).\n\n"
            "It will NOT delete actual folders/files from disk.\n\n"
            f"{preview_text}\n\n"
            f"Chart records affected: {affected_song_count}\n\n"
            "Continue?"
        ):
            return

        try:
            for root in roots:
                normalized_root = root["root_path"].replace("\\", "/").rstrip("/")

                # Delete all songs inside this scan root
                self.db.execute(
                    """
                    DELETE FROM songs
                    WHERE
                        REPLACE(folder_path, '\\', '/') = ?
                        OR REPLACE(folder_path, '\\', '/') LIKE ?
                    """,
                    (
                        normalized_root,
                        normalized_root + "/%"
                    )
                )

                # Delete scan root itself
                self.db.execute(
                    """
                    DELETE FROM scan_roots
                    WHERE id = ?
                    """,
                    (root["id"],)
                )

            self._after_delete(len(roots))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete selected scan root(s).\n\n{e}"
            )

    def _delete_from_playlists(self, selected_rows):
        playlist_ids = []
        preview = []

        for row in selected_rows:
            playlist_id = self._get_cell_text(row, "id")
            name = self._get_cell_text(row, "name", "Untitled Playlist")

            if playlist_id:
                playlist_ids.append(playlist_id)
                preview.append(f"• {name}")

        if not playlist_ids:
            return

        preview_text = "\n".join(preview[:10])

        if len(preview) > 10:
            preview_text += f"\n...and {len(preview) - 10} more"

        if not self._confirm_delete(
            "Delete Playlist(s)",
            "This will delete the selected playlist(s).\n\n"
            "Songs will NOT be deleted from the library.\n"
            "Only playlist data and playlist-song relations will be removed.\n\n"
            f"{preview_text}\n\n"
            "Continue?"
        ):
            return

        try:
            self.db.cursor.executemany(
                """
                DELETE FROM playlists
                WHERE id = ?
                """,
                [(playlist_id,) for playlist_id in playlist_ids]
            )

            self.db.conn.commit()
            self._after_delete(len(playlist_ids))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete selected playlist(s).\n\n{e}"
            )

    def _delete_from_playlist_songs(self, selected_rows):
        entries = []

        playlist_id_col = self._column_index("playlist_id")
        song_id_col = self._column_index("song_id")

        if playlist_id_col < 0 or song_id_col < 0:
            QMessageBox.critical(
                self,
                "Database Error",
                "Required columns 'playlist_id' and 'song_id' were not found."
            )
            return

        for row in selected_rows:
            playlist_id = self._get_cell_text(row, "playlist_id")
            song_id = self._get_cell_text(row, "song_id")

            if playlist_id and song_id:
                entries.append((playlist_id, song_id))

        if not entries:
            return

        if not self._confirm_delete(
            "Delete Playlist Song Relation(s)",
            "This will remove the selected song(s) from their playlist(s).\n\n"
            "Songs will NOT be deleted from the library.\n\n"
            f"Selected relation(s): {len(entries)}\n\n"
            "Continue?"
        ):
            return

        try:
            self.db.cursor.executemany(
                """
                DELETE FROM playlist_songs
                WHERE playlist_id = ?
                AND song_id = ?
                """,
                entries
            )

            self.db.conn.commit()
            self._after_delete(len(entries))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete selected playlist song relation(s).\n\n{e}"
            )

    def _delete_from_play_history(self, selected_rows):
        history_ids = []

        id_col = self._column_index("id")

        if id_col < 0:
            QMessageBox.critical(
                self,
                "Database Error",
                "Column 'id' was not found in play_history table."
            )
            return

        for row in selected_rows:
            history_id = self._get_cell_text(row, "id")

            if history_id:
                history_ids.append(history_id)

        if not history_ids:
            return

        if not self._confirm_delete(
            "Delete Play History",
            "This will remove the selected play history row(s).\n\n"
            f"Selected row(s): {len(history_ids)}\n\n"
            "Continue?"
        ):
            return

        try:
            self.db.cursor.executemany(
                """
                DELETE FROM play_history
                WHERE id = ?
                """,
                [(history_id,) for history_id in history_ids]
            )

            self.db.conn.commit()
            self._after_delete(len(history_ids))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete selected play history row(s).\n\n{e}"
            )

    def _column_index(self, column_name: str) -> int:
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item and item.text() == column_name:
                return col

        return -1