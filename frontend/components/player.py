from random import randrange
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from frontend.workers import YouTubeStreamWorker
from PyQt6.QtCore import pyqtSignal, QThread, QSettings, Qt, QSize, QUrl
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QComboBox,
    QSlider,
)
from .visualizer import VisualizerWidget


class ClickSeekSlider(QSlider):
    # Fix for playback slider not working on click
    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if ev.button() != Qt.MouseButton.LeftButton:
            return

        value = QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            int(ev.position().x()),
            max(1, self.width()),
        )
        self.setValue(value)
        self.sliderMoved.emit(value)


def format_duration_ms(ms: int):
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


class PlayerControls(QFrame):
    track_started = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.stream_thread: QThread | None = None
        self.stream_worker: YouTubeStreamWorker | None = None
        self.current_result: dict | None = None
        self.results_list: list[dict] = []
        self.current_index = -1
        self.repeat_mode = "off"

        self.settings = QSettings("SpotiRec", "Player")
        self.audio_output = QAudioOutput()
        saved_volume = self.settings.value("volume", 80, type=int)
        self.audio_output.setVolume(saved_volume / 100)
        self.audio_output.setMuted(self.settings.value("muted", False, type=bool))

        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.playbackStateChanged.connect(self.sync_play_button)
        self.media_player.errorOccurred.connect(self.show_player_error)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self._handle_media_status)

        self.setObjectName("playerBar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("nowPlaying")
        self.now_playing.setWordWrap(True)
        self.visualizer = VisualizerWidget()

        seek_row = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        self.elapsed_label.setObjectName("elapsedLabel")
        self.elapsed_label.setFixedWidth(45)
        self.duration_label = QLabel("0:00")
        self.duration_label.setObjectName("durationLabel")
        self.duration_label.setFixedWidth(45)
        self.seek_slider = ClickSeekSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        self.seek_slider.setEnabled(False)
        seek_row.addWidget(self.elapsed_label)
        seek_row.addWidget(self.seek_slider, stretch=1)
        seek_row.addWidget(self.duration_label)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.shuffle_btn = QPushButton("⇄")
        self.shuffle_btn.setObjectName("mediaButton")
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setToolTip("Shuffle off")
        self.shuffle_btn.toggled.connect(self.toggle_shuffle)

        self.repeat_btn = QPushButton()
        self.repeat_btn.setObjectName("mediaButton")
        self.repeat_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.repeat_btn.setCheckable(True)
        self.repeat_btn.setToolTip("Repeat off")
        self.repeat_btn.clicked.connect(self.cycle_repeat)

        self.prev_btn = self.button_component(
            QStyle.StandardPixmap.SP_MediaSkipBackward,
            "Previous track",
            self.play_previous,
        )
        self.play_pause_button = self.button_component(
            QStyle.StandardPixmap.SP_MediaPlay,
            "Play",
            self.toggle_playback,
            "playMediaButton",
        )
        self.next_btn = self.button_component(
            QStyle.StandardPixmap.SP_MediaSkipForward,
            "Next track",
            self.play_next,
        )
        self.stop_button = self.button_component(
            QStyle.StandardPixmap.SP_MediaStop,
            "Stop",
            self.stop_playback,
        )

        for button in (self.shuffle_btn, self.repeat_btn):
            button.setFixedSize(40, 40)
            button.setIconSize(QSize(20, 20))

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self.set_speed)

        self.mute_button = self.button_component(
            QStyle.StandardPixmap.SP_MediaVolume,
            "Mute",
            self.toggle_mute,
        )
        self._sync_volume_icon()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(saved_volume)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self.set_volume)

        controls.addWidget(self.shuffle_btn)
        controls.addWidget(self.repeat_btn)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.speed_combo)
        controls.addStretch()
        controls.addWidget(self.mute_button)
        controls.addWidget(self.volume_slider)

        layout.addWidget(self.now_playing)
        layout.addWidget(self.visualizer)
        layout.addLayout(seek_row)
        layout.addLayout(controls)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def button_component(
        self, icon_type, tooltip, callback, classname: str = "mediaButton"
    ):
        button = QPushButton()
        button.setObjectName(classname)
        button.setIcon(self.style().standardIcon(icon_type))
        button.setIconSize(QSize(20, 20))
        button.setFixedSize(40, 40)
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    def keyPressEvent(self, event):  # ty:ignore[invalid-method-override]
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

    def play_collection(self, results: list[dict], index: int):
        self.results_list = results
        self.current_index = index
        self.play_result(results[index])

    def play_result(self, result: dict):
        self.set_stream_busy(True)
        self.current_result = result
        if result in self.results_list:
            self.current_index = self.results_list.index(result)
        self.status_changed.emit(f"Loading {result['title']}...")

        self.stream_thread = QThread()
        self.stream_worker = YouTubeStreamWorker(result)
        self.stream_worker.moveToThread(self.stream_thread)
        self.stream_thread.started.connect(self.stream_worker.run)
        self.stream_worker.finished.connect(self.start_stream)
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
        self.status_changed.emit("Playing from YouTube.")
        self.track_started.emit(result)

    def play_next(self):
        if not self.results_list or self.current_index == -1:
            return
        if self.shuffle_btn.isChecked():
            next_index = randrange(len(self.results_list))
        else:
            next_index = (self.current_index + 1) % len(self.results_list)
        self.play_result(self.results_list[next_index])

    def play_previous(self):
        if not self.results_list or self.current_index == -1:
            return
        previous_index = (self.current_index - 1) % len(self.results_list)
        self.play_result(self.results_list[previous_index])

    def toggle_shuffle(self, checked):
        self.shuffle_btn.setToolTip("Shuffle on" if checked else "Shuffle off")

    def cycle_repeat(self):
        modes = {"off": "all", "all": "one", "one": "off"}
        self.repeat_mode = modes[self.repeat_mode]
        self.repeat_btn.setChecked(self.repeat_mode != "off")
        self.repeat_btn.setText("1" if self.repeat_mode == "one" else "")
        self.repeat_btn.setToolTip(f"Repeat {self.repeat_mode}")
        self.repeat_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )

    def _handle_media_status(self, status):
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self.repeat_mode == "one":
            self.media_player.setPosition(0)
            self.media_player.play()
        elif self.repeat_mode == "all":
            self.play_next()

    def toggle_playback(self):
        if self.media_player.source().isEmpty():
            self.status_changed.emit("Select a song!")
            return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_playback(self):
        self.media_player.stop()
        self.seek_slider.setValue(0)
        self.elapsed_label.setText("0:00")

    def sync_play_button(self, state: QMediaPlayer.PlaybackState):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        icon = (
            QStyle.StandardPixmap.SP_MediaPause
            if is_playing
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_pause_button.setIcon(self.style().standardIcon(icon))
        self.play_pause_button.setToolTip("Pause" if is_playing else "Play")

    def update_position(self, position_ms):
        if self.seek_slider.isSliderDown():
            return
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
        self.settings.setValue("muted", muted)
        self._sync_volume_icon()

    def _sync_volume_icon(self):
        icon = (
            QStyle.StandardPixmap.SP_MediaVolumeMuted
            if self.audio_output.isMuted()
            else QStyle.StandardPixmap.SP_MediaVolume
        )
        self.mute_button.setIcon(self.style().standardIcon(icon))
        self.mute_button.setToolTip("Unmute" if self.audio_output.isMuted() else "Mute")

    def set_speed(self, text):
        speeds = {"0.5x": 0.5, "1x": 1.0, "1.5x": 1.5, "2x": 2.0}
        self.media_player.setPlaybackRate(speeds.get(text, 1.0))

    def show_player_error(self):
        error = self.media_player.errorString()
        if error:
            self.status_changed.emit(error)

    def set_stream_busy(self, busy: bool):
        self.play_pause_button.setEnabled(not busy)
        self.stop_button.setEnabled(not busy)

    def release_stream_worker(self):
        self.stream_worker = None
        self.stream_thread = None
        self.set_stream_busy(False)
