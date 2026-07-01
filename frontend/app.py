import qdarktheme
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)
from .search import SearchResultsPanel
from .components.player import PlayerControls
from .history import HistoryPage
from .playlists import PlaylistsPage
from .shazam import ShazamPanel


class MusicAppWindow(QMainWindow):
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.db_path = root_dir / "data.db"

        self.setWindowTitle("SpotiRec")
        self.setMinimumSize(900, 700)

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 12, 20, 20)
        main_layout.setSpacing(8)

        self.shazam = ShazamPanel(root_dir, self.db_path)
        self.shazam.setWindowTitle("Find a song")

        self.search_panel = SearchResultsPanel()
        self.player = PlayerControls()

        self.shazam_button = QPushButton("S")
        self.shazam_button.setObjectName("shazamToggleButton")
        self.shazam_button.setFixedSize(32, 32)
        self.shazam_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shazam_button.setToolTip("Find a song")
        self.shazam_button.clicked.connect(self.toggle_shazam_window)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        left_balance = QWidget()
        left_balance.setFixedSize(self.shazam_button.size())
        top_bar.addWidget(left_balance)
        top_bar.addStretch()

        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("mainTabBar")
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)
        self.tab_bar.addTab("Home")
        self.tab_bar.addTab("Playlists")
        self.tab_bar.addTab("History")

        top_bar.addWidget(self.tab_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        top_bar.addStretch()
        top_bar.addWidget(self.shazam_button)
        main_layout.addLayout(top_bar)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("tabPages")
        self.tab_bar.currentChanged.connect(self.page_stack.setCurrentIndex)

        home_page = QWidget()
        home_layout = QVBoxLayout(home_page)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.addWidget(self.search_panel, stretch=1)
        self.page_stack.addWidget(home_page)

        self.playlists_page = PlaylistsPage(
            self.db_path,
            self.player.play_collection,
        )
        self.page_stack.addWidget(self.playlists_page)

        self.history_page = HistoryPage(
            self.db_path,
            self.player.play_collection,
        )
        self.page_stack.addWidget(self.history_page)

        main_layout.addWidget(self.page_stack, stretch=1)
        main_layout.addWidget(self.player)

        # Search YouTube directly from a recognition result.
        self.shazam._emit_search_request = self.search_panel.search
        self.search_panel.play_requested.connect(self.player.play_collection)
        self.search_panel.add_to_playlist_requested.connect(
            self.playlists_page.prompt_add_song
        )
        self.player.status_changed.connect(self.search_panel.set_status)
        self.player.track_started.connect(self.history_page.record_track)

        self.apply_styles()

    def toggle_shazam_window(self):
        if self.shazam.isVisible():
            self.shazam.hide()
        else:
            self.shazam.show()

    def apply_styles(self):
        with open("frontend/style.qss", "r") as f:
            custom_qss = f.read()

        qdarktheme.setup_theme(
            theme="dark",
            custom_colors={"primary": "#1db954"},
            additional_qss=custom_qss,
        )
