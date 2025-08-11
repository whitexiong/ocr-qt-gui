from __future__ import annotations
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout,
                               QListWidget, QListWidgetItem, QSpinBox, QSplitter, QGraphicsView, QGraphicsScene,
                               QGraphicsPixmapItem, QFileDialog, QMenuBar, QMenu, QPushButton, QStyledItemDelegate,
                               QAbstractItemView, QStyle, QSizePolicy)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QEvent
from .fluent import set_theme, set_accent_color, PrimaryPushButton, PushButton, ComboBox

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
            self._rect_item = self.scene.addRect(rect, QPen(QColor(0,255,0), 2))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.roi_enabled and self._dragging and event.button() == Qt.LeftButton and self._rect_item:
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

class MainWindow(QMainWindow):
    startCamera = Signal()
    stopCamera = Signal()
    captureNow = Signal()
    resultSelected = Signal(int)
    showOriginal = Signal()
    showProcessed = Signal()
    editText = Signal(int)
    loadMore = Signal()
    pageSizeChanged = Signal(int)
    nextPage = Signal()
    prevPage = Signal()

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
        self.results.setUniformItemSizes(True)
        # lazy-load on scroll bottom (disabled by default due to instability across platforms)
        self._disable_scroll_trigger = True
        self.results.verticalScrollBar().valueChanged.connect(self._on_results_scrolled)
        # watch viewport resize to recalc page size
        self.results.viewport().installEventFilter(self)
        self._last_page_size = None

        # Floating pager buttons overlayed on results (do not affect layout)
        self.btn_prev_page = PrimaryPushButton('上一页', self.results)
        self.btn_next_page = PrimaryPushButton('下一页', self.results)
        for btn in (self.btn_prev_page, self.btn_next_page):
            btn.setVisible(False)
            btn.setFixedHeight(28)
        self.btn_prev_page.clicked.connect(lambda: self.prevPage.emit())
        self.btn_next_page.clicked.connect(lambda: self.nextPage.emit())
        self._position_pager()

        left.addWidget(self.results)

        # Result detail panel (removed per requirement)
        # keep placeholders but hide them; no labels on right side
        self.lbl_detail_text = QLabel('')
        self.lbl_detail_conf = QLabel('')

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
        # moved actions into context menu only; no bottom buttons

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
        # Overlay placeholder that fills the viewport and centers text
        self.view.setPlaceholder(text)

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
            item.setData(Qt.UserRole, int(rid))
            item.setData(Qt.UserRole + 1, text or '')
            item.setData(Qt.UserRole + 2, float(conf))
            # prefer processed image if exists
            item.setData(Qt.UserRole + 3, (proc_path or img_path or ''))
            item.setData(Qt.UserRole + 4, created_at)
            self.results.addItem(item)

    def append_results(self, rows: list[tuple]):
        # rows are expected in descending id order (newest -> oldest)
        for row in rows:
            rid = row[0]
            text = row[1]
            conf = float(row[2] or 0.0)
            img_path = row[3] if len(row) >= 4 else None
            proc_path = row[4] if len(row) >= 5 else None
            created_at = row[5] if len(row) >= 6 else ''
            item = QListWidgetItem()
            item.setData(Qt.UserRole, int(rid))
            item.setData(Qt.UserRole + 1, text or '')
            item.setData(Qt.UserRole + 2, float(conf))
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
        act_view_rec = menu.addAction('查看处理图')
        act_view_orig = menu.addAction('查看原图')
        act_edit_text = menu.addAction('编辑识别文本')
        action = menu.exec(self.results.mapToGlobal(pos))
        if action == act_view_rec:
            # 设置当前项后，弹出查看处理图的对话框（由控制器处理）
            it = self.results.findItems('', Qt.MatchContains)
            # 确保当前项为选中项
            row = self.results.row(item)
            if row >= 0:
                self.results.setCurrentRow(row)
            # 触发显示处理图（控制器将以弹窗形式显示）
            self.showProcessed.emit()
        elif action == act_view_orig:
            row = self.results.row(item)
            if row >= 0:
                self.results.setCurrentRow(row)
            self.showOriginal.emit()
        elif action == act_edit_text:
            self.editText.emit(rid)

    def _on_results_scrolled(self, value: int):
        if getattr(self, '_disable_scroll_trigger', False):
            return
        bar = self.results.verticalScrollBar()
        if not bar or not bar.isEnabled():
            return
        # 更稳健的触底判断：基于滚动条范围
        # 只有当 value 接近 maximum 时触发，阈值 2 像素
        try:
            if bar.maximum() > 0 and (bar.maximum() - value) <= 2:
                self.loadMore.emit()
        except Exception:
            pass

    def estimate_page_size(self) -> int:
        viewport_h = max(0, self.results.viewport().height())
        # use delegate's known item height hint for our three-line layout
        item_h = self._item_height_hint()
        spacing = int(getattr(self.results, 'spacing', lambda: 6)()) if callable(getattr(self.results, 'spacing', None)) else 6
        denom = max(1, item_h + spacing)
        count = viewport_h // denom
        return int(max(7, max(1, count)))

    def _item_height_hint(self) -> int:
        # keep in sync with ResultItemDelegate.sizeHint
        return 10 + 20 + 4 + 22 + 6 + 20 + 10  # = 92

    def _maybe_emit_page_size(self):
        ps = self.estimate_page_size()
        if ps != self._last_page_size:
            self._last_page_size = ps
            try:
                self.pageSizeChanged.emit(ps)
            except Exception:
                pass

    def eventFilter(self, obj, event):
        if obj is self.results.viewport() and event.type() == QEvent.Resize:
            self._maybe_emit_page_size()
            self._position_pager()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._maybe_emit_page_size()
        self._position_pager()

    def showEvent(self, event):
        super().showEvent(event)
        # ensure initial page size is computed after the widget is first shown
        self._maybe_emit_page_size()
        self._position_pager()

    def _position_pager(self):
        if not hasattr(self, 'btn_next_page') or not hasattr(self, 'btn_prev_page'):
            return
        vp = self.results.viewport().geometry()
        margin = 10
        btn_w = 96
        # next button bottom-right
        self.btn_next_page.resize(btn_w, self.btn_next_page.height())
        nx = max(vp.left(), vp.right() - btn_w - margin)
        ny = max(vp.top(), vp.bottom() - self.btn_next_page.height() - margin)
        self.btn_next_page.move(nx, ny)
        # prev button bottom-left
        self.btn_prev_page.resize(btn_w, self.btn_prev_page.height())
        px = vp.left() + margin
        py = ny
        self.btn_prev_page.move(px, py)

    def set_pager(self, has_prev: bool, has_next: bool):
        self.btn_prev_page.setVisible(bool(has_prev))
        self.btn_next_page.setVisible(bool(has_next))


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
        conf = float(index.data(Qt.UserRole + 2) or 0.0)
        created_at = index.data(Qt.UserRole + 4) or ''

        # Texts in three lines: 时间、文本、置信度
        left = rect.left() + self.margin
        width = rect.width() - self.margin * 2
        line_h = 20
        y = rect.top() + 10

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
