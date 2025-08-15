from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsTextItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from ...utils.chinese_text_renderer import get_chinese_text_renderer


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
        self._detection_boxes = []  # 存储检测框
        self._text_items = []  # 存储文本项
        self._chinese_renderer = get_chinese_text_renderer()

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
        self._clear_detection_boxes()
        self._clear_text_items()
        self.scene.update()
        
    def _clear_detection_boxes(self):
        # 清除所有检测框
        for box_item in self._detection_boxes:
            if box_item in self.scene.items():
                self.scene.removeItem(box_item)
        self._detection_boxes = []
        
    def _clear_text_items(self):
        # 清除所有文本项
        for text_item in self._text_items:
            if text_item in self.scene.items():
                self.scene.removeItem(text_item)
        self._text_items = []

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
        
    def set_detection_boxes(self, boxes):
        """设置检测框并显示在视图上
        
        Args:
            boxes: 检测框列表，每个框是四个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        """
        # 清除旧的检测框
        self._clear_detection_boxes()
        
        if not boxes:
            return
            
        # 获取图像区域
        pix_rect = self.pixmap_item.boundingRect()
        
        # 添加新的检测框
        for box in boxes:
            # 将检测框坐标转换为场景坐标
            scene_points = []
            for x, y in box:
                scene_x = pix_rect.left() + x
                scene_y = pix_rect.top() + y
                scene_points.append((scene_x, scene_y))
                
            # 创建多边形并添加到场景
            pen = QPen(QColor(255, 0, 0), 2)  # 红色边框
            box_item = self.scene.addPolygon(
                QPolygonF([QPointF(x, y) for x, y in scene_points]),
                pen
            )
            self._detection_boxes.append(box_item)
        
        self.scene.update()
    
    def set_ocr_results(self, boxes, texts=None, scores=None):
        """设置OCR结果并显示检测框和中文文本
        
        Args:
            boxes: 检测框列表，每个框是四个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
            texts: 文本内容列表（可选）
            scores: 置信度列表（可选）
        """
        # 清除旧的检测框和文本
        self._clear_detection_boxes()
        self._clear_text_items()
        
        if not boxes:
            return
            
        # 获取图像区域
        pix_rect = self.pixmap_item.boundingRect()
        
        # 添加新的检测框
        for i, box in enumerate(boxes):
            # 将检测框坐标转换为场景坐标
            scene_points = []
            for x, y in box:
                scene_x = pix_rect.left() + x
                scene_y = pix_rect.top() + y
                scene_points.append((scene_x, scene_y))
                
            # 创建多边形并添加到场景
            pen = QPen(QColor(0, 255, 0), 2)  # 绿色边框
            box_item = self.scene.addPolygon(
                QPolygonF([QPointF(x, y) for x, y in scene_points]),
                pen
            )
            self._detection_boxes.append(box_item)
            
            # 添加中文文本（如果提供了文本和置信度）
            if texts and i < len(texts):
                text = texts[i] if texts[i] else ""
                score = scores[i] if scores and i < len(scores) else 0.0
                
                if text:
                    # 确保文本正确编码
                    if isinstance(text, bytes):
                        text = text.decode('utf-8', errors='ignore')
                    elif not isinstance(text, str):
                        text = str(text)
                    
                    # 创建文本显示
                    text_with_score = f"{text} ({score:.2f})"
                    
                    # 获取文本框左上角坐标
                    x, y = scene_points[0]
                    
                    # 创建文本项
                    text_item = QGraphicsTextItem(text_with_score)
                    text_item.setPos(x, y - 30)  # 在检测框上方显示
                    
                    # 设置中文字体
                    font = QFont("Microsoft YaHei", 12)
                    text_item.setFont(font)
                    text_item.setDefaultTextColor(QColor(255, 255, 255))  # 白色文字
                    
                    # 添加背景
                    text_item.setHtml(f'<div style="background-color: rgba(0, 255, 0, 128); padding: 2px;">{text_with_score}</div>')
                    
                    self.scene.addItem(text_item)
                    self._text_items.append(text_item)
        
        self.scene.update()
    
    def set_image_with_chinese_text(self, qimg: QImage, boxes=None, texts=None, scores=None):
        """设置图像并在图像上绘制中文文本
        
        Args:
            qimg: Qt图像
            boxes: 检测框列表（可选）
            texts: 文本内容列表（可选）
            scores: 置信度列表（可选）
        """
        if boxes and texts:
            # 使用中文渲染器在图像上绘制文本
            qimg_with_text = self._chinese_renderer.draw_text_on_qimage(qimg, boxes, texts, scores or [])
            self.setImage(qimg_with_text)
        else:
            self.setImage(qimg)
        
        # 同时在场景中显示检测框（可选）
        if boxes:
            self.set_ocr_results(boxes, texts, scores)


