from PyQt6.QtCore import QThread, Qt, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .workers import YouTubeSearchWorker, YouTubeStreamWorker


def format_duration(seconds: int | None):
    if not seconds:
        return "--:--"
    minutes, remaining = divmod(int(seconds), 60)
    return f"{minutes}:{remaining:02d}"


class ResultRow(QFrame):
    def __init__(self, result: dict, index: int):
        super().__init__()
        self.result = result
        self.setObjectName("resultRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        rank = QLabel(str(index))
        rank.setObjectName("resultRank")
        rank.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rank.setFixedWidth(26)

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

        play = QPushButton("Play")
        play.setObjectName("playSmallButton")
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.setFixedWidth(72)

        layout.addWidget(rank)
        layout.addLayout(text_stack, stretch=1)
        layout.addWidget(play)

        self.play_button = play


class SpotifyPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.search_thread: QThread | None = None
        self.search_worker: YouTubeSearchWorker | None = None
        self.stream_thread: QThread | None = None
        self.stream_worker: YouTubeStreamWorker | None = None
        self.current_result: dict | None = None

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.playbackStateChanged.connect(self.sync_play_button)
        self.media_player.errorOccurred.connect(self.show_player_error)

        self.setObjectName("playerPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(5)

        eyebrow = QLabel("YOUTUBE PLAYER")
        eyebrow.setObjectName("eyebrow")

        title = QLabel("Spotify-ish")
        title.setObjectName("playerTitle")

        subtitle = QLabel("Search YouTube and play the result inside this app.")
        subtitle.setObjectName("mutedText")

        header.addWidget(eyebrow)
        header.addWidget(title)
        header.addWidget(subtitle)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search for a song...")
        self.search_input.returnPressed.connect(self.search)

        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("primaryButton")
        self.search_button.clicked.connect(self.search)

        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.search_button)

        self.status_label = QLabel("Type a song name to begin.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(8)
        self.results_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("resultsArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.results_container)

        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("nowPlaying")
        self.now_playing.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setObjectName("primaryButton")
        self.play_pause_button.clicked.connect(self.toggle_playback)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("ghostButton")
        self.stop_button.clicked.connect(self.stop_playback)

        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()

        player_bar = QFrame()
        player_bar.setObjectName("playerBar")
        player_layout = QVBoxLayout(player_bar)
        player_layout.setContentsMargins(16, 14, 16, 14)
        player_layout.setSpacing(10)
        player_layout.addWidget(self.now_playing)
        player_layout.addLayout(controls)

        root.addLayout(header)
        root.addLayout(search_row)
        root.addWidget(self.status_label)
        root.addWidget(scroll_area, stretch=1)
        root.addWidget(player_bar)

    def search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Search needs a song name.")
            return

        self.set_search_busy(True)
        self.clear_results()
        self.status_label.setText(f"Searching YouTube for {query}...")

        self.search_thread = QThread()
        self.search_worker = YouTubeSearchWorker(query)
        self.search_worker.moveToThread(self.search_thread)
        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.finished.connect(self.show_results)
        self.search_worker.failed.connect(self.show_error)
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.failed.connect(self.search_thread.quit)
        self.search_thread.finished.connect(self.search_thread.deleteLater)
        self.search_thread.finished.connect(self.release_search_worker)
        self.search_thread.start()

    def show_results(self, results: list[dict]) -> None:
        self.clear_results()
        if not results:
            self.status_label.setText("No YouTube results found.")
            return

        self.status_label.setText(f"Found {len(results)} results.")
        for index, result in enumerate(results, start=1):
            row = ResultRow(result, index)
            row.play_button.clicked.connect(
                lambda _checked=False, selected=result: self.play_result(selected)
            )
            self.results_layout.insertWidget(index - 1, row)

    def play_result(self, result: dict) -> None:
        self.set_stream_busy(True)
        self.current_result = result
        self.status_label.setText(f"Loading {result['title']}...")

        self.stream_thread = QThread()
        self.stream_worker = YouTubeStreamWorker(result)
        self.stream_worker.moveToThread(self.stream_thread)
        self.stream_thread.started.connect(self.stream_worker.run)
        self.stream_worker.finished.connect(self.start_stream)
        self.stream_worker.failed.connect(self.show_error)
        self.stream_worker.finished.connect(self.stream_thread.quit)
        self.stream_worker.failed.connect(self.stream_thread.quit)
        self.stream_thread.finished.connect(self.stream_thread.deleteLater)
        self.stream_thread.finished.connect(self.release_stream_worker)
        self.stream_thread.start()

    def start_stream(self, result: dict) -> None:
        self.current_result = result
        self.now_playing.setText(f"{result['title']} - {result['artist']}")
        self.media_player.setSource(QUrl(result["stream_url"]))
        self.media_player.play()
        self.status_label.setText("Playing from YouTube.")

    def toggle_playback(self) -> None:
        if self.media_player.source().isEmpty():
            self.status_label.setText("Choose a search result first.")
            return

        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_playback(self) -> None:
        self.media_player.stop()
        self.play_pause_button.setText("Play")

    def sync_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        self.play_pause_button.setText(
            "Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play"
        )

    def show_player_error(self) -> None:
        error = self.media_player.errorString()
        if error:
            self.status_label.setText(error)

    def show_error(self, message: str) -> None:
        self.status_label.setText(message)

    def set_search_busy(self, busy: bool) -> None:
        self.search_button.setEnabled(not busy)
        self.search_input.setEnabled(not busy)

    def set_stream_busy(self, busy: bool) -> None:
        self.play_pause_button.setEnabled(not busy)
        self.stop_button.setEnabled(not busy)

    def release_search_worker(self) -> None:
        self.search_worker = None
        self.search_thread = None
        self.set_search_busy(False)

    def release_stream_worker(self) -> None:
        self.stream_worker = None
        self.stream_thread = None
        self.set_stream_busy(False)

    def clear_results(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
