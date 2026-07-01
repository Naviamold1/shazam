from PyQt6.QtCore import QThread, pyqtSignal

from PyQt6.QtNetwork import QNetworkAccessManager
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

from .components.result_row import ResultRow
from .workers import YouTubeSearchWorker


class SearchResultsPanel(QWidget):
    play_requested = pyqtSignal(list, int)
    add_to_playlist_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.search_thread: QThread | None = None
        self.search_worker: YouTubeSearchWorker | None = None
        self.results: list[dict] = []
        self.network_manager = QNetworkAccessManager(self)

        self.setObjectName("searchResultsPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 15, 28, 24)
        root.setSpacing(18)

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

        root.addLayout(search_row)
        root.addWidget(self.status_label)
        root.addWidget(scroll_area, stretch=1)

    def search(self, query: str | bool | None = None):
        if not isinstance(query, str):
            query = self.search_input.text().strip()
        else:
            query = query.strip()
            self.search_input.setText(query)
        if not query:
            self.set_status("Search needs a song name.")
            return

        self.set_search_busy(True)
        self.clear_results()
        self.set_status(f"Searching YouTube for {query}...")

        self.search_thread = QThread()
        self.search_worker = YouTubeSearchWorker(query)
        self.search_worker.moveToThread(self.search_thread)
        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.finished.connect(self.show_results)
        self.search_worker.failed.connect(self.set_status)
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.failed.connect(self.search_thread.quit)
        self.search_thread.finished.connect(self.search_thread.deleteLater)
        self.search_thread.finished.connect(self.release_search_worker)
        self.search_thread.start()

    def show_results(self, results: list[dict]):
        self.clear_results()
        self.results = results
        if not results:
            self.set_status("No YouTube results found.")
            return

        self.set_status(f"Found {len(results)} results.")
        for index, result in enumerate(results):
            row = ResultRow(result)
            row.play_button.clicked.connect(
                lambda _checked=False, selected=index: self.play_requested.emit(
                    self.results, selected
                )
            )
            row.add_to_playlist_requested.connect(self.add_to_playlist_requested.emit)
            self.results_layout.insertWidget(index, row)

    def set_status(self, message: str):
        self.status_label.setText(message)

    def set_search_busy(self, busy: bool):
        self.search_button.setEnabled(not busy)
        self.search_input.setEnabled(not busy)

    def release_search_worker(self):
        self.search_worker = None
        self.search_thread = None
        self.set_search_busy(False)

    def clear_results(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
