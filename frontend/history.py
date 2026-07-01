from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from backend.db import DBManager


class HistoryPage(QWidget):
    def __init__(self, db_path: Path, play_callback):
        super().__init__()
        self.db = DBManager(db_path)
        self.play_callback = play_callback
        self.tracks: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("History")
        title.setObjectName("playerTitle")

        self.status_label = QLabel()
        self.status_label.setObjectName("mutedText")

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("historyScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.rows_container)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(scroll_area, stretch=1)

        self.reload_history()

    def record_track(self, result: dict):
        webpage_url = result.get("webpage_url")
        if not webpage_url:
            return
        self.db.add_history_entry(
            result["title"],
            result.get("artist"),
            webpage_url,
        )
        self.reload_history()

    def reload_history(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.tracks = self.db.get_history()
        self.status_label.setText(
            f"{len(self.tracks)} recent play{'s' if len(self.tracks) != 1 else ''}"
            if self.tracks
            else "No playback history yet."
        )

        for index, track in enumerate(self.tracks):
            row = QFrame()
            row.setObjectName("historyRow")
            row_layout = QGridLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)

            title = QLabel(track["title"])
            title.setObjectName("historyTitle")
            artist = QLabel(track["artist"])
            artist.setObjectName("mutedText")
            played_at = QLabel(track["played_at"])
            played_at.setObjectName("mutedText")

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

            row_layout.addWidget(title, 0, 0)
            row_layout.addWidget(artist, 1, 0)
            row_layout.addWidget(played_at, 0, 1, 2, 1)
            row_layout.addWidget(play_button, 0, 2, 2, 1)
            row_layout.setColumnStretch(0, 1)
            self.rows_layout.addWidget(row)

        self.rows_layout.addStretch()
