from __future__ import annotations
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt

class ImageViewerDialog(QDialog):
    def __init__(self, parent=None, title: str = '查看识别结果'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        lay = QVBoxLayout(self)
        lay.addWidget(self._label)

    def setImage(self, qimg: QImage):
        self._qimg = qimg
        self._update_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self):
        if not hasattr(self, '_qimg') or self._qimg is None:
            return
        self._label.setPixmap(QPixmap.fromImage(self._qimg).scaled(
            self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
