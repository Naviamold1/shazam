from __future__ import annotations
import uvicorn

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.recognizer import SongCandidate, SongRecognizer, record_microphone_clip


ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "data1.db"


class RecognitionWorker(QObject):
    finished = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, mode: str, wav_path: Path | None = None):
        super().__init__()
        self.mode = mode
        self.wav_path = wav_path

    def run(self) -> None:
        temp_path: Path | None = None
        try:
            if self.mode == "microphone":
                temp_path = record_microphone_clip()
                source_path = temp_path
                source_label = "microphone recording"
            elif self.wav_path is not None:
                source_path = self.wav_path
                source_label = self.wav_path.name
            else:
                raise RuntimeError("No audio source was selected.")

            recognizer = SongRecognizer(DB_PATH)
            candidates = recognizer.recognize_file(source_path)
            self.finished.emit(candidates, source_label)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


class CandidateCard(QFrame):
    def __init__(self, candidate: SongCandidate, rank: int):
        super().__init__()
        self.setObjectName("candidateCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        rank_label = QLabel(f"#{rank}")
        rank_label.setObjectName("rankLabel")
        rank_label.setFixedWidth(42)
        rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_stack = QVBoxLayout()
        text_stack.setSpacing(4)

        title = QLabel(candidate.title)
        title.setObjectName("candidateTitle")
        title.setWordWrap(True)

        detail = QLabel(
            f"song id {candidate.song_id} | votes {candidate.votes} | offset {candidate.offset}"
        )
        detail.setObjectName("candidateDetail")
        detail.setWordWrap(True)

        text_stack.addWidget(title)
        text_stack.addWidget(detail)

        confidence = QLabel(f"{candidate.confidence:.0f}%")
        confidence.setObjectName("confidenceLabel")
        confidence.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        confidence.setFixedWidth(72)

        layout.addWidget(rank_label)
        layout.addLayout(text_stack, stretch=1)
        layout.addWidget(confidence)


class ShazamWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker_thread: QThread | None = None
        self.worker: RecognitionWorker | None = None

        self.setWindowTitle("Shazam Style Recognizer")
        self.setMinimumSize(520, 720)

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(22)

        header = QVBoxLayout()
        header.setSpacing(8)

        eyebrow = QLabel("local audio fingerprinting")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Shazam")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Tap to listen, or test with a WAV clip from your library.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        header.addWidget(eyebrow)
        header.addWidget(title)
        header.addWidget(subtitle)

        self.find_button = QPushButton("Find Song")
        self.find_button.setObjectName("findButton")
        self.find_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.find_button.clicked.connect(self.start_microphone_recognition)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.find_button)
        button_row.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.open_button = QPushButton("Open WAV")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(self.pick_wav_file)

        self.open_button = QPushButton("Open to LAN")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(self.open_to_lan)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("ghostButton")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear_results)

        actions.addStretch()
        actions.addWidget(self.open_button)
        actions.addWidget(self.clear_button)
        actions.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(12)
        self.results_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("resultsArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.results_container)

        root.addLayout(header)
        root.addSpacing(8)
        root.addLayout(button_row)
        root.addLayout(actions)
        root.addWidget(self.status_label)
        root.addWidget(scroll_area, stretch=1)

        self.apply_styles()

    def start_microphone_recognition(self) -> None:
        self.start_worker("microphone")

    def pick_wav_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a WAV clip",
            str(ROOT_DIR / "assets"),
            "WAV files (*.wav)",
        )
        if file_path:
            self.start_worker("file", Path(file_path))

    def start_worker(self, mode: str, wav_path: Path | None = None) -> None:
        self.set_busy(True)
        self.status_label.setText("Listening..." if mode == "microphone" else "Fingerprinting file...")
        self.clear_result_cards()

        self.worker_thread = QThread()
        self.worker = RecognitionWorker(mode, wav_path)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_results)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.release_worker)
        self.worker_thread.start()

    def show_results(self, candidates: list[SongCandidate], source_label: str) -> None:
        self.clear_result_cards()
        if not candidates:
            self.status_label.setText(f"No confident match found for {source_label}.")
            return

        best = candidates[0]
        self.status_label.setText(f"Best match: {best.title}")
        for index, candidate in enumerate(candidates, start=1):
            self.results_layout.insertWidget(index - 1, CandidateCard(candidate, index))

    def open_to_lan(self):
        uvicorn.run("backend.web:app")

    def show_error(self, message: str) -> None:
        self.clear_result_cards()
        self.status_label.setText(message)

    def clear_results(self) -> None:
        self.clear_result_cards()
        self.status_label.setText("Ready")

    def clear_result_cards(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def release_worker(self) -> None:
        self.worker = None
        self.worker_thread = None
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        self.find_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)

    def apply_styles(self) -> None:
        app_font = QFont("Inter")
        if not app_font.exactMatch():
            app_font = QFont("Arial")
        QApplication.instance().setFont(app_font)

        self.setStyleSheet(
            """
            #appRoot {
                background: qradialgradient(cx: 0.5, cy: 0.22, radius: 0.92,
                    fx: 0.5, fy: 0.22,
                    stop: 0 #1098f7,
                    stop: 0.46 #072b5f,
                    stop: 1 #07111f);
                color: #f6fbff;
            }

            #eyebrow {
                color: #a5dcff;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0px;
                text-transform: uppercase;
            }

            #appTitle {
                color: #ffffff;
                font-size: 56px;
                font-weight: 800;
            }

            #subtitle {
                color: #d6eeff;
                font-size: 16px;
                line-height: 22px;
            }

            #findButton {
                background: #04a9ff;
                border: 10px solid rgba(255, 255, 255, 0.22);
                border-radius: 104px;
                color: #ffffff;
                font-size: 24px;
                font-weight: 800;
                min-width: 208px;
                max-width: 208px;
                min-height: 208px;
                max-height: 208px;
            }

            #findButton:hover {
                background: #27b8ff;
            }

            #findButton:pressed {
                background: #0486d2;
            }

            #findButton:disabled,
            #secondaryButton:disabled,
            #ghostButton:disabled {
                color: rgba(255, 255, 255, 0.55);
                background: rgba(255, 255, 255, 0.12);
            }

            #secondaryButton,
            #ghostButton {
                border: 1px solid rgba(255, 255, 255, 0.28);
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                min-width: 116px;
                min-height: 38px;
                padding: 0 16px;
            }

            #secondaryButton {
                background: rgba(255, 255, 255, 0.18);
            }

            #secondaryButton:hover,
            #ghostButton:hover {
                background: rgba(255, 255, 255, 0.26);
            }

            #ghostButton {
                background: transparent;
            }

            #statusLabel {
                color: #f3fbff;
                font-size: 16px;
                font-weight: 700;
                min-height: 34px;
            }

            #resultsArea {
                background: transparent;
            }

            #candidateCard {
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.20);
                border-radius: 8px;
            }

            #rankLabel {
                color: #8bd6ff;
                font-size: 18px;
                font-weight: 800;
            }

            #candidateTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 800;
            }

            #candidateDetail {
                color: #c8dced;
                font-size: 13px;
            }

            #confidenceLabel {
                color: #93f1d2;
                font-size: 22px;
                font-weight: 800;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = ShazamWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
