from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontMetrics, QPaintEvent

class MarqueeLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.px = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_position)
        self._timer.start(30)
        self.text_width = 0
        self.spacing = 30
        self.setAlignment(Qt.AlignCenter)

    def setText(self, text):
        super().setText(text)
        self.update_metrics()
        self.px = 0
        
    def setFont(self, font):
        super().setFont(font)
        self.update_metrics()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_metrics()

    def update_metrics(self):
        fm = QFontMetrics(self.font())
        self.text_width = fm.horizontalAdvance(self.text())

    def update_position(self):
        if self.text_width > self.width():
            self.px -= 1
            if -self.px >= self.text_width + self.spacing:
                self.px = 0
            self.update()
        else:
            if self.px != 0:
                self.px = 0
                self.update()

    def paintEvent(self, event: QPaintEvent):
        if self.text_width > self.width():
            painter = QPainter(self)
            painter.setClipRect(self.rect())
            painter.setPen(self.palette().windowText().color())
            fm = QFontMetrics(self.font())
            y = (self.height() + fm.ascent() - fm.descent()) // 2
            
            painter.drawText(self.px, y, self.text())
            painter.drawText(self.px + self.text_width + self.spacing, y, self.text())
        else:
            super().paintEvent(event)