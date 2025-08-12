from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, QRectF, Signal


class RoiGraphicsView(QGraphicsView):
    roiChanged = Signal(object)  # (x1,y1,x2,y2) normalized

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.roi_enabled = False
        self._dragging = False
        self._start = None
        self._rect_item = None
        self._placeholder_text: str | None = None

    def setImage(self, qimg: QImage):
        # disable placeholder when showing an image
        self._placeholder_text = None
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def clearImage(self):
        self.pixmap_item.setPixmap(QPixmap())
        if self._rect_item:
            self.scene.removeItem(self._rect_item)
            self._rect_item = None
        self.scene.update()

    def setPlaceholder(self, text: str | None):
        self._placeholder_text = text or None
        if self._placeholder_text:
            # ensure pixmap is cleared so only placeholder shows
            self.pixmap_item.setPixmap(QPixmap())
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # keep image fitted when the view size changes
        pix = self.pixmap_item.pixmap()
        if not pix.isNull():
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def mousePressEvent(self, event):
        if self.roi_enabled and event.button() == Qt.LeftButton:
            self._dragging = True
            self._start = event.position()
            if self._rect_item:
                self.scene.removeItem(self._rect_item)
                self._rect_item = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.roi_enabled and self._dragging and self._start is not None:
            end = event.position()
            rect = QRectF(self._start, end).normalized()
            if self._rect_item:
                self.scene.removeItem(self._rect_item)
            self._rect_item = self.scene.addRect(rect, QPen(QColor(0, 255, 0), 2))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self.roi_enabled
            and self._dragging
            and event.button() == Qt.LeftButton
            and self._rect_item
        ):
            view_rect = self._rect_item.rect()
            pix_rect = self.pixmap_item.boundingRect()
            nx1 = (view_rect.left() - pix_rect.left()) / max(1.0, pix_rect.width())
            ny1 = (view_rect.top() - pix_rect.top()) / max(1.0, pix_rect.height())
            nx2 = (view_rect.right() - pix_rect.left()) / max(1.0, pix_rect.width())
            ny2 = (view_rect.bottom() - pix_rect.top()) / max(1.0, pix_rect.height())
            self.roiChanged.emit(
                (
                    max(0.0, min(1.0, nx1)),
                    max(0.0, min(1.0, ny1)),
                    max(0.0, min(1.0, nx2)),
                    max(0.0, min(1.0, ny2)),
                )
            )
        self._dragging = False
        self._start = None
        super().mouseReleaseEvent(event)

    def drawForeground(self, painter: QPainter, rect):
        # Render a full-viewport placeholder overlay when requested
        if self._placeholder_text:
            painter.save()
            painter.resetTransform()
            vr = self.viewport().rect()
            painter.fillRect(vr, QColor(30, 30, 30))
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.setFont(QFont('Microsoft YaHei', 20))
            painter.drawText(vr, Qt.AlignCenter, self._placeholder_text)
            painter.restore()
        super().drawForeground(painter, rect)


