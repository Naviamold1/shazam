from PyQt6.QtGui import QIcon
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from frontend.app import MusicAppWindow


def main():
    app = QApplication(sys.argv)
    window = MusicAppWindow(Path(__file__).resolve().parent)
    app.setWindowIcon(QIcon("frontend/icon.jpg"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
