import qdarktheme
from pathlib import Path
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget, QFrame
from .player import SpotifyPlayer
from .shazam import ShazamPanel


class MusicAppWindow(QMainWindow):
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.db_path = root_dir / "data1.db"

        self.setWindowTitle("SpotiRec")
        self.setMinimumSize(1100, 700)

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        self.shazam = ShazamPanel(root_dir, self.db_path)
        self.shazam.setMinimumWidth(360)

        self.player = SpotifyPlayer()

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("panelSeparator")

        main_layout.addWidget(self.shazam, stretch=2)
        main_layout.addWidget(separator)
        main_layout.addWidget(self.player, stretch=3)

        # Cross?panel: YT Search from Shazam
        self.shazam._emit_search_request = self.player.search

        self.apply_styles()

    def apply_styles(self) -> None:
        with open("frontend/style.qss", "r") as f:
            custom_qss = f.read()
        qdarktheme.setup_theme(
            theme="dark",
            additional_qss=custom_qss,
        )