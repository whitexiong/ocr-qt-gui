from __future__ import annotations

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtWidgets import QStyle


class ResultItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.radius = 8
        self.margin = 10

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
            painter.setPen(QPen(QColor(30, 30, 30)))
            painter.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
            painter.drawText(QRectF(left, rect.top() + (rect.height() - line_h) / 2, width, line_h),
                             Qt.TextSingleLine | Qt.AlignVCenter, text)
            painter.restore()
            return

        painter.setPen(QPen(QColor(60, 60, 60)))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(QRectF(left, y, width, line_h), Qt.TextSingleLine | Qt.AlignVCenter, created_at)
        y += line_h + 4

        painter.setPen(QPen(QColor(30, 30, 30)))
        painter.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
        painter.drawText(QRectF(left, y, width, line_h + 2), Qt.TextSingleLine | Qt.AlignVCenter, text)
        y += line_h + 6

        painter.setPen(QPen(QColor(90, 90, 90)))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(QRectF(left, y, width, line_h), Qt.TextSingleLine | Qt.AlignVCenter, f'置信度 {conf:.3f}')

        painter.restore()

    def sizeHint(self, option, index):
        # Height to fit three lines + paddings
        return QSize(option.rect.width(), 10 + 20 + 4 + 22 + 6 + 20 + 10)


