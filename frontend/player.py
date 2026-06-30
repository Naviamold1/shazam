import random
from PyQt6.QtCore import QThread, Qt, QUrl, QSettings, QTimer
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSlider, QVBoxLayout, QWidget, QComboBox,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from .workers import YouTubeSearchWorker, YouTubeStreamWorker


def format_duration(seconds: int | None):
    if not seconds:
        return "--:--"
    minutes, remaining = divmod(int(seconds), 60)
    return f"{minutes}:{remaining:02d}"


def format_duration_ms(ms: int) -> str:
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


class VisualizerWidget(QWidget):
    """Animated equalizer bars ? no audio probe needed."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self.bars = 10
        self.heights = [0.0] * self.bars
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_heights)
        self.timer.start(80)

    def _update_heights(self):
        for i in range(self.bars):
            target = random.random()
            self.heights[i] += (target - self.heights[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        bar_width = max(4, (width - 20) // self.bars - 4)
        spacing = (width - 20) / self.bars

        for i in range(self.bars):
            h = int(height * self.heights[i] * 0.9)
            x = 10 + i * spacing + (spacing - bar_width) / 2
            painter.setBrush(QColor(29, 185, 84, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), height - h, int(bar_width), h, 3, 3)


class ResultRow(QFrame):
    def __init__(self, result: dict, index: int, network_manager: QNetworkAccessManager):
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
        thumb_url = result.get("thumbnail")
        if thumb_url:
            reply = network_manager.get(QNetworkRequest(QUrl(thumb_url)))
            reply.finished.connect(lambda r=reply, label=self.thumbnail: self._set_thumb(r, label))
        else:
            self.thumbnail.setText("No img")

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

        layout.addWidget(self.thumbnail)
        layout.addWidget(rank)
        layout.addLayout(text_stack, stretch=1)
        layout.addWidget(play)

        self.play_button = play

    def _set_thumb(self, reply: QNetworkReply, label: QLabel):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            label.setPixmap(pixmap)
        reply.deleteLater()


class SpotifyPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.search_thread: QThread | None = None
        self.search_worker: YouTubeSearchWorker | None = None
        self.stream_thread: QThread | None = None
        self.stream_worker: YouTubeStreamWorker | None = None
        self.current_result: dict | None = None
        self.results_list: list[dict] = []
        self.current_index: int = -1

        self.settings = QSettings("SpotiRec", "Player")

        self.audio_output = QAudioOutput()
        saved_vol = self.settings.value("volume", 80, type=int)
        self.audio_output.setVolume(saved_vol / 100)
        self.audio_output.setMuted(self.settings.value("muted", False, type=bool))
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.playbackStateChanged.connect(self.sync_play_button)
        self.media_player.errorOccurred.connect(self.show_player_error)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)

        self.network_manager = QNetworkAccessManager(self)

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

        # ---------- Player bar ----------
        player_bar = QFrame()
        player_bar.setObjectName("playerBar")
        player_layout = QVBoxLayout(player_bar)
        player_layout.setContentsMargins(16, 14, 16, 14)
        player_layout.setSpacing(10)

        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("nowPlaying")
        self.now_playing.setWordWrap(True)

        # Visualizer (no audio argument)
        self.visualizer = VisualizerWidget()

        # Seek row
        seek_row = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        self.elapsed_label.setObjectName("elapsedLabel")
        self.elapsed_label.setFixedWidth(45)
        self.duration_label = QLabel("0:00")
        self.duration_label.setObjectName("durationLabel")
        self.duration_label.setFixedWidth(45)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        self.seek_slider.setEnabled(False)
        seek_row.addWidget(self.elapsed_label)
        seek_row.addWidget(self.seek_slider, 1)
        seek_row.addWidget(self.duration_label)

        # Controls row ? NO fixed widths on main buttons
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.setObjectName("ghostButton")
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setToolTip("Toggle shuffle")
        self.shuffle_btn.toggled.connect(self.toggle_shuffle)

        self.repeat_btn = QPushButton("Repeat")
        self.repeat_btn.setObjectName("ghostButton")
        self.repeat_btn.setToolTip("Repeat: Off / All / One")
        self.repeat_btn.clicked.connect(self.cycle_repeat)

        self.prev_btn = QPushButton("Prev")
        self.prev_btn.setObjectName("ghostButton")
        self.prev_btn.setToolTip("Previous track")
        self.prev_btn.clicked.connect(self.play_previous)

        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setObjectName("primaryButton")
        self.play_pause_button.clicked.connect(self.toggle_playback)

        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("ghostButton")
        self.next_btn.setToolTip("Next track")
        self.next_btn.clicked.connect(self.play_next)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("ghostButton")
        self.stop_button.clicked.connect(self.stop_playback)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self.set_speed)
        self.speed_combo.setObjectName("speedCombo")

        # Volume
        volume_layout = QHBoxLayout()
        self.mute_button = QPushButton("Mute" if self.audio_output.isMuted() else "Vol")
        self.mute_button.setObjectName("muteButton")
        self.mute_button.setFixedWidth(50)
        self.mute_button.setToolTip("Toggle mute")
        self.mute_button.clicked.connect(self.toggle_mute)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(saved_vol)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self.set_volume)

        volume_layout.addWidget(self.mute_button)
        volume_layout.addWidget(self.volume_slider)

        controls.addWidget(self.shuffle_btn)
        controls.addWidget(self.repeat_btn)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.speed_combo)
        controls.addStretch()
        controls.addLayout(volume_layout)

        player_layout.addWidget(self.now_playing)
        player_layout.addWidget(self.visualizer)
        player_layout.addLayout(seek_row)
        player_layout.addLayout(controls)

        root.addLayout(header)
        root.addLayout(search_row)
        root.addWidget(self.status_label)
        root.addWidget(scroll_area, stretch=1)
        root.addWidget(player_bar)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.toggle_playback()
        elif event.key() == Qt.Key.Key_Right:
            self.media_player.setPosition(self.media_player.position() + 5000)
        elif event.key() == Qt.Key.Key_Left:
            self.media_player.setPosition(self.media_player.position() - 5000)
        elif event.key() == Qt.Key.Key_Up:
            self.volume_slider.setValue(min(self.volume_slider.value() + 5, 100))
        elif event.key() == Qt.Key.Key_Down:
            self.volume_slider.setValue(max(self.volume_slider.value() - 5, 0))
        else:
            super().keyPressEvent(event)

    def search(self, query: str | None = None):
        if query is None:
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

    def show_results(self, results: list[dict]):
        self.clear_results()
        if not results:
            self.status_label.setText("No YouTube results found.")
            return

        self.results_list = results
        self.current_index = -1
        self.status_label.setText(f"Found {len(results)} results.")
        for index, result in enumerate(results, start=1):
            row = ResultRow(result, index, self.network_manager)
            row.play_button.clicked.connect(
                lambda _checked=False, selected=result: self.play_result(selected)
            )
            self.results_layout.insertWidget(index - 1, row)

    def play_result(self, result: dict):
        self.set_stream_busy(True)
        self.current_result = result
        if result in self.results_list:
            self.current_index = self.results_list.index(result)
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

    def start_stream(self, result: dict):
        self.current_result = result
        self.now_playing.setText(f"{result['title']} - {result['artist']}")
        self.media_player.setSource(QUrl(result["stream_url"]))
        self.media_player.play()
        self.status_label.setText("Playing from YouTube.")

    def play_next(self):
        if not self.results_list or self.current_index == -1:
            return
        if self.shuffle_btn.isChecked():
            next_idx = random.randint(0, len(self.results_list) - 1)
        else:
            next_idx = (self.current_index + 1) % len(self.results_list)
        self.play_result(self.results_list[next_idx])

    def play_previous(self):
        if not self.results_list or self.current_index == -1:
            return
        prev_idx = (self.current_index - 1) % len(self.results_list)
        self.play_result(self.results_list[prev_idx])

    def toggle_shuffle(self, checked):
        pass

    def cycle_repeat(self):
        current = self.repeat_btn.text()
        if current == "Repeat":
            self.repeat_btn.setText("Repeat One")
            self.media_player.mediaStatusChanged.connect(self._handle_repeat_one)
        elif current == "Repeat One":
            self.repeat_btn.setText("Repeat All")
            self.media_player.mediaStatusChanged.disconnect(self._handle_repeat_one)
        else:
            self.repeat_btn.setText("Repeat")
            self.media_player.mediaStatusChanged.disconnect(self._handle_repeat_one)

    def _handle_repeat_one(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()

    def toggle_playback(self):
        if self.media_player.source().isEmpty():
            self.status_label.setText("Choose a search result first.")
            return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_playback(self):
        self.media_player.stop()
        self.play_pause_button.setText("Play")
        self.seek_slider.setValue(0)
        self.elapsed_label.setText("0:00")

    def sync_play_button(self, state: QMediaPlayer.PlaybackState):
        self.play_pause_button.setText(
            "Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play"
        )

    def update_position(self, position_ms):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.blockSignals(True)
            duration = self.media_player.duration()
            if duration > 0:
                self.seek_slider.setValue(int(position_ms / duration * 1000))
            self.elapsed_label.setText(format_duration_ms(position_ms))
            self.seek_slider.blockSignals(False)

    def update_duration(self, duration_ms):
        self.duration_label.setText(format_duration_ms(duration_ms))
        self.seek_slider.setEnabled(duration_ms > 0)

    def seek_position(self, slider_value):
        duration = self.media_player.duration()
        if duration > 0:
            self.media_player.setPosition(int(slider_value / 1000 * duration))

    def set_volume(self, value):
        self.audio_output.setVolume(value / 100)
        self.settings.setValue("volume", value)

    def toggle_mute(self):
        muted = not self.audio_output.isMuted()
        self.audio_output.setMuted(muted)
        self.mute_button.setText("Mute" if muted else "Vol")
        self.settings.setValue("muted", muted)

    def set_speed(self, text):
        speed_map = {"0.5x": 0.5, "1x": 1.0, "1.5x": 1.5, "2x": 2.0}
        self.media_player.setPlaybackRate(speed_map.get(text, 1.0))

    def show_player_error(self):
        error = self.media_player.errorString()
        if error:
            self.status_label.setText(error)

    def show_error(self, message: str):
        self.status_label.setText(message)

    def set_search_busy(self, busy: bool):
        self.search_button.setEnabled(not busy)
        self.search_input.setEnabled(not busy)

    def set_stream_busy(self, busy: bool):
        self.play_pause_button.setEnabled(not busy)
        self.stop_button.setEnabled(not busy)

    def release_search_worker(self):
        self.search_worker = None
        self.search_thread = None
        self.set_search_busy(False)

    def release_stream_worker(self):
        self.stream_worker = None
        self.stream_thread = None
        self.set_stream_busy(False)

    def clear_results(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
