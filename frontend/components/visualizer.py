import random
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget


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

    def paintEvent(self, event):  # ty:ignore[invalid-method-override]
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
