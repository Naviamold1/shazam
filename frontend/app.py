import qdarktheme
from pathlib import Path

from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget, QPushButton

from .player import SpotifyPlayer
from .shazam import ShazamPanel


class MusicAppWindow(QMainWindow):
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.db_path = root_dir / "data1.db"

        self.setWindowTitle("SpotiRec")
        self.setMinimumSize(1060, 720)

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        self.player = SpotifyPlayer()
        self.shazam = ShazamPanel(root_dir, self.db_path)

        layout.addWidget(self.player, stretch=3)
        # layout.addWidget(self.shazam, stretch=1)
        self.shazam_button = QPushButton("Find the song!")
        self.shazam_button.clicked.connect(self.toggle_shazam_window)
        layout.addWidget(self.shazam_button)

        self.apply_styles()

    def toggle_shazam_window(self):
        if self.shazam.isVisible():
            self.shazam.hide()

        else:
            self.shazam.show()

    def apply_styles(self) -> None:
        with open("frontend/style.qss", "r") as f:
            # self.setStyleSheet(f.read())
            qdarktheme.setup_theme(additional_qss=f.read())
