from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget, QHBoxLayout,
)

from backend.db import DBManager


class HistoryPage(QWidget):
    def __init__(self, db_path: str, play_callback):
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
            if item.widget():
                item.widget().deleteLater()

        self.tracks = self.db.get_history()

        for index, track in enumerate(self.tracks):
            row = QFrame()
            row.setObjectName("historyRow")
            layout = QHBoxLayout(row)

            text = QVBoxLayout()
            text.addWidget(QLabel(track["title"]))
            text.addWidget(QLabel(f"{track['artist']} • {track['played_at']}"))

            play = QPushButton()
            play.setObjectName("playSmallButton")
            play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            play.setToolTip("Play")
            play.setCursor(Qt.CursorShape.PointingHandCursor)
            play.setFixedSize(34, 34)
            play.clicked.connect(
                lambda _checked=False, i=index: self.play_callback(self.tracks, i)
            )

            layout.addLayout(text)
            layout.addStretch()
            layout.addWidget(play)
            self.rows_layout.addWidget(row)

        self.rows_layout.addStretch()
