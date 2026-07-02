from pathlib import Path

from PyQt6.QtCore import Qt
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

        self.play_all_button = self.button_component(
            QStyle.StandardPixmap.SP_MediaPlay,
            "Play all",
            self.play_all,
        )
        self.download_button = self.button_component(
            QStyle.StandardPixmap.SP_ArrowDown,
            "Download all songs",
            self.download_all,
        )
        self.fingerprint_button = self.button_component(
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

    def button_component(self, icon_type, tooltip, callback):
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
            return
        destination = QFileDialog.getExistingDirectory(
            self,
            "Download playlist",
        )
        if destination:
            self._start_task(
                PlaylistDownloadWorker(self.tracks, destination),
                "Downloading playlist...",
            )

    def fingerprint_all(self):
        if not self.tracks:
            return
        self._start_task(
            PlaylistFingerprintWorker(self.tracks, self.db.db_path),
            "Fingerprinting playlist...",
        )

    def _start_task(self, worker, message: str):
        if self.task_worker is not None:
            return
        self.status_label.setText(message)
        self.download_button.setEnabled(False)
        self.fingerprint_button.setEnabled(False)

        self.task_worker = worker
        worker.result_ready.connect(self.status_label.setText)
        worker.failed.connect(self.status_label.setText)
        worker.finished.connect(self._release_task)
        worker.start()

    def _release_task(self):
        self.task_worker = None
        self.download_button.setEnabled(True)
        self.fingerprint_button.setEnabled(True)

    def reload_tracks(self):
        while self.track_layout.count():
            item = self.track_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.tracks = self.db.get_playlist_tracks(self.playlist_id)

        if not self.tracks:
            self.track_layout.addWidget(QLabel("This playlist is empty."))
            self.track_layout.addStretch()
            return

        for index, track in enumerate(self.tracks):
            row = QFrame()
            row.setObjectName("playlistTrackRow")
            layout = QHBoxLayout(row)

            text = QVBoxLayout()

            title = QLabel(track["title"])
            title.setObjectName("playlistTrackTitle")

            artist = QLabel(track["artist"])
            artist.setObjectName("mutedText")

            text.addWidget(title)
            text.addWidget(artist)

            play_button = QPushButton()
            play_button.setObjectName("playSmallButton")
            play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            play_button.setToolTip("Play")
            play_button.setCursor(Qt.CursorShape.PointingHandCursor)
            play_button.setFixedSize(34, 34)
            play_button.clicked.connect(
                lambda _checked=False, i=index:
                    self.play_callback(self.tracks, i)
            )

            layout.addLayout(text)
            layout.addStretch()
            layout.addWidget(play_button)

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
