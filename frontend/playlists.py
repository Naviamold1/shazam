from pathlib import Path

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from backend.db import DBManager
from .workers import PlaylistDownloadWorker, PlaylistFingerprintWorker


class PlaylistWindow(QWidget):
    def __init__(
        self,
        db: DBManager,
        playlist_id: int,
        name: str,
        play_callback,
    ):
        super().__init__()
        self.db = db
        self.playlist_id = playlist_id
        self.play_callback = play_callback
        self.tracks: list[dict] = []
        self.task_thread: QThread | None = None
        self.task_worker = None

        self.setWindowTitle(name)
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(name)
        title.setObjectName("playerTitle")
        header.addWidget(title)
        header.addStretch()

        self.play_all_button = self._action_button(
            QStyle.StandardPixmap.SP_MediaPlay,
            "Play all",
            self.play_all,
        )
        self.download_button = self._action_button(
            QStyle.StandardPixmap.SP_ArrowDown,
            "Download all songs",
            self.download_all,
        )
        self.fingerprint_button = self._action_button(
            QStyle.StandardPixmap.SP_DialogApplyButton,
            "Fingerprint all songs",
            self.fingerprint_all,
        )
        header.addWidget(self.play_all_button)
        header.addWidget(self.download_button)
        header.addWidget(self.fingerprint_button)

        self.status_label = QLabel()
        self.status_label.setObjectName("mutedText")

        layout.addLayout(header)
        layout.addWidget(self.status_label)

        self.track_container = QWidget()
        self.track_layout = QVBoxLayout(self.track_container)
        self.track_layout.setContentsMargins(0, 0, 0, 0)
        self.track_layout.setSpacing(8)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.track_container)
        layout.addWidget(scroll_area, stretch=1)

        self.reload_tracks()

    def _action_button(self, icon_type, tooltip, callback):
        button = QPushButton()
        button.setObjectName("mediaButton")
        button.setIcon(self.style().standardIcon(icon_type))
        button.setToolTip(tooltip)
        button.setFixedSize(40, 40)
        button.clicked.connect(callback)
        return button

    def play_all(self):
        if self.tracks:
            self.play_callback(self.tracks, 0)

    def download_all(self):
        if not self.tracks:
            self.status_label.setText("This playlist is empty.")
            return
        destination = QFileDialog.getExistingDirectory(
            self,
            "Download playlist",
        )
        if destination:
            self._start_task(
                PlaylistDownloadWorker(self.tracks, Path(destination)),
                "Downloading playlist...",
            )

    def fingerprint_all(self):
        if not self.tracks:
            self.status_label.setText("This playlist is empty.")
            return
        self._start_task(
            PlaylistFingerprintWorker(self.tracks, self.db.db_path),
            "Fingerprinting playlist...",
        )

    def _start_task(self, worker, message: str):
        if self.task_thread is not None:
            return
        self.status_label.setText(message)
        self.download_button.setEnabled(False)
        self.fingerprint_button.setEnabled(False)

        self.task_thread = QThread()
        self.task_worker = worker
        worker.moveToThread(self.task_thread)
        self.task_thread.started.connect(worker.run)
        worker.finished.connect(self._task_finished)
        worker.failed.connect(self._task_finished)
        worker.finished.connect(self.task_thread.quit)
        worker.failed.connect(self.task_thread.quit)
        self.task_thread.finished.connect(self.task_thread.deleteLater)
        self.task_thread.finished.connect(self._release_task)
        self.task_thread.start()

    def _task_finished(self, message: str):
        self.status_label.setText(message)

    def _release_task(self):
        self.task_worker = None
        self.task_thread = None
        self.download_button.setEnabled(True)
        self.fingerprint_button.setEnabled(True)

    def reload_tracks(self):
        while self.track_layout.count():
            item = self.track_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.tracks = self.db.get_playlist_tracks(self.playlist_id)
        if not self.tracks:
            empty = QLabel("This playlist is empty.")
            empty.setObjectName("mutedText")
            self.track_layout.addWidget(empty)
            self.track_layout.addStretch()
            return

        for index, track in enumerate(self.tracks):
            row = QFrame()
            row.setObjectName("playlistTrackRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)

            title = QLabel(track["title"])
            title.setObjectName("playlistTrackTitle")
            artist = QLabel(track["artist"])
            artist.setObjectName("mutedText")

            play_button = QPushButton()
            play_button.setObjectName("playSmallButton")
            play_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
            play_button.setToolTip("Play")
            play_button.setFixedSize(34, 34)
            play_button.clicked.connect(
                lambda _checked=False, selected=index: self.play_callback(
                    self.tracks, selected
                )
            )

            content = QGridLayout()
            content.addWidget(title, 0, 0)
            content.addWidget(artist, 1, 0)
            content.addWidget(play_button, 0, 1, 2, 1)
            row_layout.addLayout(content)
            self.track_layout.addWidget(row)

        self.track_layout.addStretch()


class PlaylistsPage(QWidget):
    def __init__(self, db_path: Path, play_callback):
        super().__init__()
        self.db = DBManager(db_path)
        self.play_callback = play_callback
        self.playlist_windows: dict[int, PlaylistWindow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Playlists")
        title.setObjectName("playerTitle")

        self.status_label = QLabel()
        self.status_label.setObjectName("mutedText")

        self.grid_container = QWidget()
        self.grid_container.setObjectName("playlistGrid")
        self.grid = QGridLayout(self.grid_container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("playlistScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.grid_container)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(scroll_area, stretch=1)

        self.reload_playlists()

    def prompt_create_playlist(self):
        name, accepted = QInputDialog.getText(
            self,
            "Create playlist",
            "Playlist name:",
        )
        if accepted:
            self.create_playlist(name)

    def create_playlist(self, name: str):
        name = name.strip()
        if not name:
            self.status_label.setText("Enter a playlist name.")
            return

        self.db.create_playlist(name)
        self.reload_playlists()

    def prompt_add_song(self, result: dict):
        playlists = self.db.get_playlists()
        if not playlists:
            self.status_label.setText("Create a playlist first.")
            return

        names = [name for _playlist_id, name, _created_at in playlists]
        name, accepted = QInputDialog.getItem(
            self,
            "Add to playlist",
            "Playlist:",
            names,
            0,
            False,
        )
        if not accepted:
            return

        playlist_id = next(
            playlist_id
            for playlist_id, playlist_name, _created_at in playlists
            if playlist_name == name
        )
        added = self.db.add_track_to_playlist(
            playlist_id,
            result["title"],
            result.get("artist"),
            result["webpage_url"],
        )
        self.status_label.setText(
            f"Added {result['title']} to {name}."
            if added
            else f"{result['title']} is already in {name}."
        )
        if playlist_id in self.playlist_windows:
            self.playlist_windows[playlist_id].reload_tracks()

    def open_playlist(self, playlist_id: int, name: str):
        if playlist_id not in self.playlist_windows:
            self.playlist_windows[playlist_id] = PlaylistWindow(
                self.db,
                playlist_id,
                name,
                self.play_callback,
            )
        window = self.playlist_windows[playlist_id]
        window.reload_tracks()
        window.show()
        window.raise_()
        window.activateWindow()

    def reload_playlists(self):
        playlists = self.db.get_playlists()

        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        add_button = QPushButton("+")
        add_button.setObjectName("addPlaylistCard")
        add_button.setToolTip("Create playlist")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.prompt_create_playlist)
        add_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.grid.addWidget(add_button, 0, 0)

        for index, (playlist_id, name, created_at) in enumerate(playlists, start=1):
            card = QPushButton(name)
            card.setObjectName("playlistCard")
            card.setToolTip(f"Created {created_at}")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.clicked.connect(
                lambda _checked=False, selected_id=playlist_id, selected_name=name: (
                    self.open_playlist(selected_id, selected_name)
                )
            )

            row, column = divmod(index, 4)
            self.grid.addWidget(card, row, column)

        for column in range(4):
            self.grid.setColumnStretch(column, 1)
        self.grid.setRowStretch((len(playlists) // 4) + 1, 1)

        count = len(playlists)
        self.status_label.setText(
            f"{count} playlist{'s' if count != 1 else ''}"
            if count
            else "No playlists yet."
        )
