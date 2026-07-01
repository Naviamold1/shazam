from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.recognizer import SongCandidate
from scripts.serve_web import get_lan_ip, local_hostname
from .workers import RecognitionWorker, ServerThread


class CandidateCard(QFrame):
    search_requested = pyqtSignal(str)

    def __init__(self, candidate: SongCandidate, rank: int):
        super().__init__()
        self.setObjectName("candidateCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        rank_label = QLabel(str(rank))
        rank_label.setObjectName("rankLabel")
        rank_label.setFixedWidth(28)
        rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_stack = QVBoxLayout()
        text_stack.setSpacing(4)

        title = QLabel(candidate.title)
        title.setObjectName("candidateTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        detail = QLabel(
            f"ID: {candidate.song_id} | Votes: {candidate.votes} | Offset: {candidate.offset}"
        )
        detail.setObjectName("candidateDetail")
        detail.setWordWrap(True)

        confidence = QLabel(f"{candidate.confidence:.0f}%")
        confidence.setObjectName("confidenceLabel")
        confidence.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        confidence.setFixedWidth(60)

        yt_btn = QPushButton("Search")
        yt_btn.setObjectName("playSmallButton")
        yt_btn.setFixedWidth(72)
        yt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        yt_btn.clicked.connect(lambda: self.search_requested.emit(candidate.title))

        text_stack.addWidget(title)
        text_stack.addWidget(detail)
        layout.addWidget(rank_label)
        layout.addLayout(text_stack, stretch=1)
        layout.addWidget(confidence)
        layout.addWidget(yt_btn)


class ShazamPanel(QWidget):
    search_requested = pyqtSignal(str)

    def __init__(self, root_dir: Path, db_path: Path):
        super().__init__()
        self.root_dir = root_dir
        self.db_path = db_path
        self.worker_thread: QThread | None = None
        self.worker: RecognitionWorker | None = None
        self.server_thread: ServerThread | None = None

        self.setObjectName("shazamPanel")
        self.setWindowTitle("Finder")
        self.setMinimumSize(500, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Shazam")
        title.setObjectName("shazamTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Find from mic, a WAV file, or mobile LAN.")
        subtitle.setObjectName("mutedText")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        self.find_button = QPushButton("Find Song")
        self.find_button.setObjectName("findButton")
        self.find_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.find_button.clicked.connect(self.start_microphone_recognition)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(29, 185, 84, 70))
        shadow.setOffset(0, 4)
        self.find_button.setGraphicsEffect(shadow)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.find_button)
        button_row.addStretch()

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.open_button = QPushButton("Open WAV")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.open_button.clicked.connect(self.pick_wav_file)
        self.lan_button = QPushButton("LAN")
        self.lan_button.setObjectName("secondaryButton")
        self.lan_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.lan_button.clicked.connect(self.open_to_lan)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.clear_button.clicked.connect(self.clear_results)
        action_row.addWidget(self.open_button, stretch=1)
        action_row.addWidget(self.lan_button, stretch=1)
        action_row.addWidget(self.clear_button, stretch=1)

        self.url_address = QLabel("LAN URL appears here.")
        self.url_address.setObjectName("urlAddress")
        self.url_address.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_address.setWordWrap(True)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)
        self.results_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("resultsArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setWidget(self.results_container)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addLayout(button_row)
        root.addLayout(action_row)
        root.addWidget(self.url_address)
        root.addWidget(self.status_label)
        root.addWidget(scroll_area, stretch=1)

    def start_microphone_recognition(self):
        self.start_worker("microphone")

    def pick_wav_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a WAV clip",
            str(self.root_dir / "assets"),
            "WAV files (*.wav)",
        )
        if file_path:
            self.start_worker("file", Path(file_path))

    def start_worker(self, mode: str, wav_path: Path | None = None):
        self.set_busy(True)
        self.status_label.setText(
            "Listening..." if mode == "microphone" else "Fingerprinting file..."
        )
        self.clear_result_cards()

        self.worker_thread = QThread()
        self.worker = RecognitionWorker(self.db_path, mode, wav_path)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_results)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.release_worker)
        self.worker_thread.start()

    def show_results(self, candidates: list[SongCandidate], source_label: str):
        self.clear_result_cards()
        if not candidates:
            self.status_label.setText(f"No match found for {source_label}.")
            return

        best = candidates[0]
        self.status_label.setText(f"Best match: {best.title}")
        for index, candidate in enumerate(candidates, start=1):
            card = CandidateCard(candidate, index)
            card.search_requested.connect(self.search_requested.emit)
            self.results_layout.insertWidget(index - 1, card)

    def open_to_lan(self):
        self.lan_button.setEnabled(False)
        self.lan_button.setText("Opening...")
        self.server_thread = ServerThread()
        self.server_thread.server_started.connect(self.server_open)
        self.server_thread.start()

    def server_open(self, _url: str):
        QTimer.singleShot(
            1000,
            lambda: (
                self.lan_button.setText("Connected"),
                self.url_address.setText(
                    f"https://{get_lan_ip()}:8443 or https://{local_hostname()}:8443"
                ),
            ),
        )

    def show_error(self, message: str):
        self.clear_result_cards()
        self.status_label.setText(message)

    def clear_results(self):
        self.clear_result_cards()
        self.status_label.setText("Ready")

    def clear_result_cards(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def release_worker(self):
        self.worker = None
        self.worker_thread = None
        self.set_busy(False)

    def set_busy(self, busy: bool):
        self.find_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.lan_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
