from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
)


def format_duration(seconds: int | None):
    if not seconds:
        return "--:--"
    minutes, remaining = divmod(int(seconds), 60)
    return f"{minutes}:{remaining:02d}"


class ResultRow(QFrame):
    add_to_playlist_requested = pyqtSignal(dict)

    def __init__(
        self,
        result: dict,
    ):
        super().__init__()
        self.result = result
        self.setObjectName("resultRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(48, 48)
        self.thumbnail.setObjectName("thumbnail")
        self.thumbnail.setScaledContents(True)

        self.thumbnail.setText("No img")

        text_stack = QVBoxLayout()
        text_stack.setSpacing(4)

        title = QLabel(result["title"])
        title.setObjectName("resultTitle")
        title.setWordWrap(True)

        detail = QLabel(
            f"{result['artist']} | {format_duration(result.get('duration'))}"
        )
        detail.setObjectName("mutedText")
        detail.setWordWrap(True)

        text_stack.addWidget(title)
        text_stack.addWidget(detail)

        play = QPushButton()
        play.setObjectName("playSmallButton")
        play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        play.setToolTip("Play")
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.setFixedSize(34, 34)

        add_button = QPushButton("+")
        add_button.setObjectName("addSmallButton")
        add_button.setToolTip("Add to playlist")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.setFixedSize(34, 34)
        add_button.clicked.connect(
            lambda: self.add_to_playlist_requested.emit(self.result)
        )

        layout.addWidget(self.thumbnail)
        layout.addLayout(text_stack, stretch=1)
        layout.addWidget(play)
        layout.addWidget(add_button)

        self.play_button = play
