from __future__ import annotations
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout,
                               QListWidget, QListWidgetItem, QSpinBox, QSplitter, QGraphicsView, QGraphicsScene,
                               QGraphicsPixmapItem, QFileDialog, QMenuBar, QMenu, QPushButton, QStyledItemDelegate,
                               QAbstractItemView, QStyle, QSizePolicy)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF, Signal, QSize
from .fluent import set_theme, set_accent_color, PrimaryPushButton, PushButton, ComboBox

class RoiGraphicsView(QGraphicsView):
    roiChanged = Signal(object)  # (x1,y1,x2,y2) normalized

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self._dragging = False
        self._start = None
        self._rect_item = None

    def setImage(self, qimg: QImage):
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def clearImage(self):
        self.pixmap_item.setPixmap(QPixmap())
        if self._rect_item:
            self.scene.removeItem(self._rect_item)
            self._rect_item = None
        self.scene.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # keep image fitted when the view size changes
        pix = self.pixmap_item.pixmap()
        if not pix.isNull():
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._start = event.position()
            if self._rect_item:
                self.scene.removeItem(self._rect_item)
                self._rect_item = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._start is not None:
            end = event.position()
            rect = QRectF(self._start, end).normalized()
            if self._rect_item:
                self.scene.removeItem(self._rect_item)
            self._rect_item = self.scene.addRect(rect, QPen(QColor(0,255,0), 2))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton and self._rect_item:
            view_rect = self._rect_item.rect()
            pix_rect = self.pixmap_item.boundingRect()
            nx1 = (view_rect.left() - pix_rect.left()) / max(1.0, pix_rect.width())
            ny1 = (view_rect.top() - pix_rect.top()) / max(1.0, pix_rect.height())
            nx2 = (view_rect.right() - pix_rect.left()) / max(1.0, pix_rect.width())
            ny2 = (view_rect.bottom() - pix_rect.top()) / max(1.0, pix_rect.height())
            self.roiChanged.emit((max(0.0,min(1.0,nx1)), max(0.0,min(1.0,ny1)), max(0.0,min(1.0,nx2)), max(0.0,min(1.0,ny2))))
        self._dragging = False
        self._start = None
        super().mouseReleaseEvent(event)

class MainWindow(QMainWindow):
    startCamera = Signal()
    stopCamera = Signal()
    captureNow = Signal()
    resultSelected = Signal(int)
    showOriginal = Signal()
    showProcessed = Signal()
    editText = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('OCR Camera')
        self.resize(1280, 800)
        # Apply custom Fluent-like style globally
        set_theme('auto')
        set_accent_color(QColor(0, 120, 215))
        self._build_ui()

    def _build_ui(self):
        # menu
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        menu_file = QMenu('文件', self)
        menubar.addMenu(menu_file)
        self.act_import_config = menu_file.addAction('导入配置 (config.json)')
        menu_cam = QMenu('相机', self)
        menubar.addMenu(menu_cam)
        self.act_cam_refresh = menu_cam.addAction('刷新相机设备')
        self.act_cam_start = menu_cam.addAction('开启相机')
        self.act_cam_stop = menu_cam.addAction('关闭相机')
        self.act_cam_capture = menu_cam.addAction('拍照')
        menu_view = QMenu('视图', self)
        menubar.addMenu(menu_view)
        self.act_theme_auto = menu_view.addAction('主题：自动')
        self.act_theme_light = menu_view.addAction('主题：浅色')
        self.act_theme_dark = menu_view.addAction('主题：深色')

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Left: results list
        left = QVBoxLayout()
        self.cb_devices = ComboBox()

        self.results = QListWidget()
        self.results.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results.itemClicked.connect(self._on_result_clicked)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._on_results_menu)
        self.results.setMouseTracking(True)
        self.results.viewport().setAttribute(Qt.WA_Hover, True)
        self.results.setSpacing(6)
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setItemDelegate(ResultItemDelegate(self.results))

        left.addWidget(self.results)

        # Result detail panel
        detail = QVBoxLayout()
        self.lbl_detail_text = QLabel('文本：')
        self.lbl_detail_conf = QLabel('置信度：')
        btn_row = QHBoxLayout()
        self.btn_show_orig = PushButton('显示原图')
        self.btn_show_proc = PushButton('显示处理图')
        btn_row.addWidget(self.btn_show_orig)
        btn_row.addWidget(self.btn_show_proc)
        detail.addWidget(self.lbl_detail_text)
        detail.addWidget(self.lbl_detail_conf)
        detail.addLayout(btn_row)
        left.addLayout(detail)

        # Right: camera view with ROI
        right = QVBoxLayout()
        self.view = RoiGraphicsView()
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumSize(640, 360)
        right.addWidget(self.view)

        splitter = QSplitter()
        lw = QWidget(); lw.setLayout(left)
        rw = QWidget(); rw.setLayout(right)
        lw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(lw)
        splitter.addWidget(rw)
        # responsive split: right takes 2 parts, left 1 part
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        lw.setMinimumWidth(280)
        layout.addWidget(splitter)

        # Use native status bar for current time

        # actions
        self.act_import_config.triggered.connect(self.on_import_config)
        # Camera menu actions
        self.act_cam_refresh.triggered.connect(self.on_refresh)
        self.act_cam_start.triggered.connect(self.startCamera.emit)
        self.act_cam_stop.triggered.connect(self.stopCamera.emit)
        self.act_cam_capture.triggered.connect(self.captureNow.emit)
        self.act_theme_auto.triggered.connect(lambda: self.apply_theme('auto'))
        self.act_theme_light.triggered.connect(lambda: self.apply_theme('light'))
        self.act_theme_dark.triggered.connect(lambda: self.apply_theme('dark'))
        self.btn_show_orig.clicked.connect(self.showOriginal.emit)
        self.btn_show_proc.clicked.connect(self.showProcessed.emit)

        # initial UI state
        self.set_camera_running(False)
        self.show_placeholder('未开启相机')
        # start clock in status bar
        from PySide6.QtCore import QTimer, QTime
        self.statusBar()
        self._clock = QTimer(self)
        self._clock.timeout.connect(lambda: self.statusBar().showMessage(QTime.currentTime().toString('HH:mm:ss')))
        self._clock.start(1000)

    def apply_theme(self, mode: str):
        set_theme(mode, self)
        # notify controller if connected
        if hasattr(self, 'onThemeChangedCallback') and callable(self.onThemeChangedCallback):
            self.onThemeChangedCallback(mode)

    def on_refresh(self):
        pass

    def on_import_config(self):
        file, _ = QFileDialog.getOpenFileName(self, '选择配置文件', '', 'JSON (*.json)')
        if not file:
            return
        self.import_config_path = file

    def update_devices(self, devices: list[tuple[int,str]]):
        self.cb_devices.clear()
        for idx, name in devices:
            self.cb_devices.addItem(name, idx)

    def current_device(self) -> int:
        return int(self.cb_devices.currentData() or 0)

    def show_frame(self, frame_bgr):
        h, w, _ = frame_bgr.shape
        qimg = QImage(frame_bgr.data, w, h, w*3, QImage.Format_BGR888)
        self.view.setImage(qimg)

    def clear_frame(self):
        self.view.clearImage()

    def show_placeholder(self, text: str):
        # Create a neutral placeholder image with centered text
        w, h = 960, 540
        img = QImage(w, h, QImage.Format_RGB32)
        img.fill(QColor(30, 30, 30))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont('Microsoft YaHei', 20))
        painter.drawText(img.rect(), Qt.AlignCenter, text)
        painter.end()
        self.view.setImage(img)

    def set_page_label(self, page: int):
        self.lbl_page.setText(f'第 {page} 页')

    def page_size(self) -> int:
        return int(self.spin_page_size.value())

    def set_camera_running(self, running: bool):
        # reflect state via menu actions
        if hasattr(self, 'act_cam_start'):
            self.act_cam_start.setEnabled(not running)
        if hasattr(self, 'act_cam_stop'):
            self.act_cam_stop.setEnabled(running)
        if hasattr(self, 'act_cam_capture'):
            self.act_cam_capture.setEnabled(running)

    def add_result_item(self, rid: int, date_text: str, confidence: float):
        item = QListWidgetItem(f"#{rid}  {date_text}  ({confidence:.2f})")
        self.results.addItem(item)
        self.results.scrollToBottom()

    def set_results(self, rows: list[tuple]):
        self.results.clear()
        # rows can be (..., created_at_str) at the end
        for row in rows:
            rid = row[0]
            text = row[1]
            conf = float(row[2] or 0.0)
            img_path = row[3] if len(row) >= 4 else None
            proc_path = row[4] if len(row) >= 5 else None
            created_at = row[5] if len(row) >= 6 else ''
            item = QListWidgetItem()
            item.setSizeHint(QSize(10, 76))
            item.setData(Qt.UserRole, int(rid))
            item.setData(Qt.UserRole + 1, text or '')
            item.setData(Qt.UserRole + 2, float(conf))
            # prefer processed image if exists
            item.setData(Qt.UserRole + 3, (proc_path or img_path or ''))
            item.setData(Qt.UserRole + 4, created_at)
            self.results.addItem(item)

    def set_result_detail(self, text: str, confidence: float):
        self.lbl_detail_text.setText(f'文本：{text or ""}')
        self.lbl_detail_conf.setText(f'置信度：{confidence:.3f}')

    def _on_result_clicked(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        if isinstance(rid, int):
            self.resultSelected.emit(rid)

    def _on_results_menu(self, pos):
        item = self.results.itemAt(pos)
        if not item:
            return
        rid = item.data(Qt.UserRole)
        if not isinstance(rid, int):
            return
        menu = QMenu(self)
        act_view_rec = menu.addAction('查看识别结果')
        act_edit_text = menu.addAction('编辑识别文本')
        action = menu.exec(self.results.mapToGlobal(pos))
        if action == act_view_rec:
            # reuse selection to show processed image by default
            self.resultSelected.emit(rid)
        elif action == act_edit_text:
            self.editText.emit(rid)


class ResultItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.radius = 10
        self.thumb_size = 56
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
        conf = float(index.data(Qt.UserRole + 2) or 0.0)
        img_path = index.data(Qt.UserRole + 3) or ''
        created_at = index.data(Qt.UserRole + 4) or ''

        # Thumbnail (cache in role + 10)
        thumb_rect = QRectF(rect.left() + self.margin, rect.top() + (rect.height() - self.thumb_size) / 2,
                             self.thumb_size, self.thumb_size)
        pix: QPixmap | None = index.data(Qt.UserRole + 10)
        if pix is None and img_path:
            p = QPixmap(img_path)
            if not p.isNull():
                p = p.scaled(self.thumb_size, self.thumb_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                index.model().setData(index, p, Qt.UserRole + 10)
                pix = p
        if isinstance(pix, QPixmap) and not pix.isNull():
            clip = QPainterPath(); clip.addRoundedRect(thumb_rect, 6, 6)
            painter.setClipPath(clip)
            painter.drawPixmap(thumb_rect.toRect(), pix)
            painter.setClipping(False)
        else:
            # placeholder thumb
            ph = QColor(120, 120, 120, 40)
            painter.fillRect(thumb_rect, ph)

        # Texts
        text_left = int(thumb_rect.right() + 12)
        title_rect = QRectF(text_left, rect.top() + 10, rect.width() - text_left - 12, 22)
        sub_rect = QRectF(text_left, title_rect.bottom() + 4, title_rect.width(), 18)
        painter.setPen(QPen(QColor(30, 30, 30)))
        painter.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
        painter.drawText(title_rect, Qt.TextSingleLine | Qt.AlignVCenter, text)
        painter.setPen(QPen(QColor(90, 90, 90)))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(sub_rect, Qt.TextSingleLine | Qt.AlignVCenter, f'{created_at} · 置信度 {conf:.3f}')

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 76)
