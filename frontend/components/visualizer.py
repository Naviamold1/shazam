from PyQt6.QtGui import QPainter, QColor
import math
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget


class VisualizerWidget(QWidget):
    """A lightweight playback indicator that animates only while audio plays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("visualizer")
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self.bars = 10
        self.phase = 0.0
        self.heights = [0.08] * self.bars
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_heights)
        self.timer.setInterval(60)

    def set_active(self, active: bool):
        if active:
            if not self.timer.isActive():
                self.timer.start()
            return

        self.timer.stop()
        self.heights = [0.08] * self.bars
        self.update()

    def _update_heights(self):
        self.phase += 0.22
        for i in range(self.bars):
            wave = (math.sin(self.phase + i * 0.72) + 1) / 2
            pulse = (math.sin(self.phase * 0.55 + i * 1.31) + 1) / 2
            target = 0.16 + 0.7 * wave * (0.65 + 0.35 * pulse)
            self.heights[i] += (target - self.heights[i]) * 0.35
        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        available_width = max(width - 20, self.bars)
        spacing = available_width / self.bars
        bar_width = max(3, min(12, int(spacing * 0.55)))

        for i in range(self.bars):
            bar_height = max(4, int((height - 8) * self.heights[i]))
            x = 10 + i * spacing + (spacing - bar_width) / 2
            painter.setBrush(QColor(29, 185, 84, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(x),
                height - bar_height - 4,
                bar_width,
                bar_height,
                3,
                3,
            )
