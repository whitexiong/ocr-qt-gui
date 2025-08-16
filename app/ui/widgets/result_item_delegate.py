from __future__ import annotations

from PySide6.QtWidgets import QStyledItemDelegate, QApplication
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPalette
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtWidgets import QStyle


class ResultItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.radius = 8
        self.margin = 10
    
    def _get_text_color(self):
        """根据当前主题获取文字颜色"""
        app = QApplication.instance()
        if app is None:
            return QColor(0, 0, 0)  # 默认黑色
        
        # 获取当前调色板
        palette = app.palette()
        base_color = palette.color(QPalette.Base)
        
        # 判断是否为深色主题
        is_dark = (0.2126 * base_color.redF() + 0.7152 * base_color.greenF() + 0.0722 * base_color.blueF()) < 0.5
        
        # 深色主题使用白色文字，浅色主题使用黑色文字
        return QColor(255, 255, 255) if is_dark else QColor(0, 0, 0)
    
    def _get_secondary_text_color(self):
        """获取次要文字颜色（稍微淡一些）"""
        app = QApplication.instance()
        if app is None:
            return QColor(128, 128, 128)  # 默认灰色
        
        # 获取当前调色板
        palette = app.palette()
        base_color = palette.color(QPalette.Base)
        
        # 判断是否为深色主题
        is_dark = (0.2126 * base_color.redF() + 0.7152 * base_color.greenF() + 0.0722 * base_color.blueF()) < 0.5
        
        # 深色主题使用浅灰色，浅色主题使用深灰色
        return QColor(180, 180, 180) if is_dark else QColor(90, 90, 90)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        rect = option.rect.adjusted(0, 0, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        # Background by state
        if option.state & QStyle.State_Selected:
            bg = QColor(0, 120, 215, 30)
            border = QColor(0, 120, 215, 160)
        elif option.state & QStyle.State_MouseOver:
            bg = QColor(0, 0, 0, 15)
            border = QColor(0, 0, 0, 30)
        else:
            bg = QColor(0, 0, 0, 8)
            border = QColor(0, 0, 0, 16)
        painter.fillPath(path, bg)
        pen = QPen(border)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        # Data
        text = index.data(Qt.UserRole + 1) or ''
        conf_raw = index.data(Qt.UserRole + 2)
        conf = float(conf_raw) if conf_raw is not None else 0.0
        created_at = index.data(Qt.UserRole + 4) or ''

        # Texts in three lines: 时间、文本、置信度
        left = rect.left() + self.margin
        width = rect.width() - self.margin * 2
        line_h = 20
        y = rect.top() + 10

        # If this is a placeholder item (no rid), only draw the center bold text
        rid = index.data(Qt.UserRole)
        if rid is None:
            painter.setPen(QPen(self._get_text_color()))
            painter.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
            painter.drawText(QRectF(left, rect.top() + (rect.height() - line_h) / 2, width, line_h),
                             Qt.TextSingleLine | Qt.AlignVCenter, text)
            painter.restore()
            return

        # 绘制时间（次要文字颜色）
        painter.setPen(QPen(self._get_secondary_text_color()))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(QRectF(left, y, width, line_h), Qt.TextSingleLine | Qt.AlignVCenter, created_at)
        y += line_h + 4

        # 绘制主要文本（主要文字颜色）
        painter.setPen(QPen(self._get_text_color()))
        painter.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
        painter.drawText(QRectF(left, y, width, line_h + 2), Qt.TextSingleLine | Qt.AlignVCenter, text)
        y += line_h + 6

        # 绘制置信度（次要文字颜色）
        painter.setPen(QPen(self._get_secondary_text_color()))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(QRectF(left, y, width, line_h), Qt.TextSingleLine | Qt.AlignVCenter, f'置信度 {conf:.3f}')

        painter.restore()

    def sizeHint(self, option, index):
        # Height to fit three lines + paddings
        return QSize(option.rect.width(), 10 + 20 + 4 + 22 + 6 + 20 + 10)


