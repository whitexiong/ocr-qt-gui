from __future__ import annotations
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMenuBar,
    QMenu,
    QAbstractItemView,
    QSizePolicy,
)
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import Qt, Signal, QEvent
from .fluent import set_theme, set_accent_color, PrimaryPushButton, PushButton, ComboBox
from .widgets import RoiGraphicsView, ResultItemDelegate

 

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
    preprocessToggled = Signal(bool)

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
        # 文件菜单与“导入配置”已移除
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
        # Preprocess controls
        self.act_preprocess_enable = menu_view.addAction('启用预处理')
        self.act_preprocess_enable.setCheckable(True)
        self.act_open_settings = menu_view.addAction('预处理设置')
        # Debug mode
        self.act_open_debug = menu_view.addAction('调试模式')
        # Global preprocess toggle
        self.act_toggle_preprocess = menu_view.addAction('启用预处理')
        self.act_toggle_preprocess.setCheckable(True)

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
        # Hide scrollbars and disable wheel scrolling; we paginate responsively instead
        try:
            self.results.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        self.results.itemClicked.connect(self._on_result_clicked)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._on_results_menu)
        self.results.setMouseTracking(True)
        self.results.viewport().setAttribute(Qt.WA_Hover, True)
        self.results.setSpacing(6)
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setItemDelegate(ResultItemDelegate(self.results))
        self.results.setUniformItemSizes(True)
        # small bottom safety margin to avoid last item clipping
        try:
            self.results.setViewportMargins(0, 0, 0, 2)
        except Exception:
            pass
        # Also watch wheel events to block scrolling
        self.results.installEventFilter(self)
        # lazy-load on scroll bottom (disabled by default due to instability across platforms)
        self._disable_scroll_trigger = True
        self.results.verticalScrollBar().valueChanged.connect(self._on_results_scrolled)
        # watch viewport resize to recalc page size
        self.results.viewport().installEventFilter(self)
        self._last_page_size = None

        # Results list
        left.addWidget(self.results)

        # Pager toolbar (always visible below the list)
        pager_bar = QHBoxLayout()
        self.lbl_page = QLabel('')
        self.lbl_page.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.btn_prev_page = PushButton('上一页')
        self.btn_prev_page.setProperty('fluentSecondary', True)
        self.btn_next_page = PrimaryPushButton('下一页')
        self.btn_prev_page.setFixedHeight(28)
        self.btn_next_page.setFixedHeight(28)
        pager_bar.addWidget(self.lbl_page)
        pager_bar.addStretch(1)
        pager_bar.addWidget(self.btn_prev_page)
        pager_bar.addWidget(self.btn_next_page)
        left.addLayout(pager_bar)

        self.btn_prev_page.clicked.connect(lambda: self.prevPage.emit())
        self.btn_next_page.clicked.connect(lambda: self.nextPage.emit())

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
        splitter.addWidget(rw)
        splitter.addWidget(lw)
        # responsive split: left (camera) takes 2 parts, right (list) 1 part
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        lw.setMinimumWidth(280)
        layout.addWidget(splitter)

        # Use native status bar for current time

        # actions
        # Camera menu actions
        self.act_cam_refresh.triggered.connect(self.on_refresh)
        self.act_cam_start.triggered.connect(self.startCamera.emit)
        self.act_cam_stop.triggered.connect(self.stopCamera.emit)
        self.act_cam_capture.triggered.connect(self.captureNow.emit)
        self.act_theme_auto.triggered.connect(lambda: self.apply_theme('auto'))
        self.act_theme_light.triggered.connect(lambda: self.apply_theme('light'))
        self.act_theme_dark.triggered.connect(lambda: self.apply_theme('dark'))
        self.act_open_settings.triggered.connect(self.open_settings)
        self.act_open_debug.triggered.connect(self.open_debug)
        self.act_preprocess_enable.triggered.connect(lambda checked: self.preprocessToggled.emit(bool(checked)))
        self.act_toggle_preprocess.toggled.connect(self._on_toggle_preprocess)
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

    def set_preprocess_enabled(self, enabled: bool):
        try:
            self.act_preprocess_enable.setChecked(bool(enabled))
        except Exception:
            pass

    def on_refresh(self):
        pass

    def open_settings(self):
        # signal-like callback for controller
        if hasattr(self, 'onOpenSettings') and callable(self.onOpenSettings):
            self.onOpenSettings()

    def open_debug(self):
        # signal-like callback for controller
        if hasattr(self, 'onOpenDebug') and callable(self.onOpenDebug):
            self.onOpenDebug()

    def _on_toggle_preprocess(self, checked: bool):
        # signal-like callback for controller
        if hasattr(self, 'onTogglePreprocess') and callable(self.onTogglePreprocess):
            self.onTogglePreprocess(bool(checked))

    # 已移除外部配置导入，改为菜单进入“预处理设置”对话框

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

    def set_page_label(self, page: int, total_pages: int, page_count: int, total_count: int):
        page = max(1, int(page or 1))
        total_pages = max(1, int(total_pages or 1))
        page_count = max(0, int(page_count or 0))
        total_count = max(0, int(total_count or 0))
        self.lbl_page.setText(f'第 {page}/{total_pages} 页 · 本页 {page_count} 条 · 共 {total_count} 条（按时间倒序）')

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

    def set_preprocess_enabled(self, enabled: bool):
        try:
            self.act_toggle_preprocess.blockSignals(True)
            self.act_toggle_preprocess.setChecked(bool(enabled))
        finally:
            self.act_toggle_preprocess.blockSignals(False)

    def add_result_item(self, rid: int, date_text: str, confidence: float):
        item = QListWidgetItem(f"#{rid}  {date_text}  ({confidence:.2f})")
        self.results.addItem(item)
        self.results.scrollToBottom()

    def set_results(self, rows: list[tuple]):
        self.results.clear()
        # When there is no data, show a default placeholder item on the left list
        if not rows:
            placeholder = QListWidgetItem()
            # Do not set Qt.UserRole (rid) so clicks won't emit selection
            placeholder.setData(Qt.UserRole + 1, '生产日期：xxxx/xx/xx 合格')
            placeholder.setData(Qt.UserRole + 4, '')
            self.results.addItem(placeholder)
            return
        # rows can be (..., created_at_str) at the end
        for row in rows:
            rid = row[0]
            text = row[1] or '生产日期：xxxx/xx/xx 合格'
            conf = float(row[2] or 0.0)
            img_path = row[3] if len(row) >= 4 else None
            proc_path = row[4] if len(row) >= 5 else None
            created_at = row[5] if len(row) >= 6 else ''
            item = QListWidgetItem()
            item.setData(Qt.UserRole, int(rid))
            item.setData(Qt.UserRole + 1, text)
            item.setData(Qt.UserRole + 2, float(conf))
            # store both original and processed image paths
            item.setData(Qt.UserRole + 3, f"{img_path or ''}|{proc_path or ''}" if img_path or proc_path else '')
            item.setData(Qt.UserRole + 4, created_at)
            self.results.addItem(item)

    def append_results(self, rows: list[tuple]):
        # rows are expected in descending id order (newest -> oldest)
        for row in rows:
            rid = row[0]
            text = row[1] or '生产日期：xxxx/xx/xx 合格'
            conf = float(row[2] or 0.0)
            img_path = row[3] if len(row) >= 4 else None
            proc_path = row[4] if len(row) >= 5 else None
            created_at = row[5] if len(row) >= 6 else ''
            item = QListWidgetItem()
            item.setData(Qt.UserRole, int(rid))
            item.setData(Qt.UserRole + 1, text)
            item.setData(Qt.UserRole + 2, float(conf))
            item.setData(Qt.UserRole + 3, f"{img_path or ''}|{proc_path or ''}" if img_path or proc_path else '')
            item.setData(Qt.UserRole + 4, created_at)
            self.results.addItem(item)

    def set_result_detail(self, text: str, confidence: float):
        # 确保文本正确编码
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        elif not isinstance(text, str):
            text = str(text)
        
        self.lbl_detail_text.setText(f'文本：{text or ""}')
        self.lbl_detail_conf.setText(f'置信度：{confidence:.3f}')
        
    def show_result_text(self, text: str, confidence: float):
        """在状态栏显示识别结果"""
        # 确保文本正确编码
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        elif not isinstance(text, str):
            text = str(text)
        
        self.statusBar().showMessage(f'识别结果: {text} (置信度: {confidence:.2f})', 5000)

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
        # subtract frame and a tiny safety to avoid clipping the last item
        try:
            frame_bw = int(getattr(self.results, 'frameWidth', lambda: 0)() or 0)
        except Exception:
            frame_bw = 0
        effective_h = max(0, viewport_h - frame_bw * 2 - 2)
        # use delegate's known item height hint for our three-line layout
        item_h = self._item_height_hint()
        spacing = int(getattr(self.results, 'spacing', lambda: 6)()) if callable(getattr(self.results, 'spacing', None)) else 6
        denom = max(1, item_h + spacing)
        count = effective_h // denom
        # return number of fully visible items only (no forced minimum)
        return int(max(1, count))

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
        # Recompute page size upon viewport resize
        if obj is self.results.viewport() and event.type() == QEvent.Resize:
            self._maybe_emit_page_size()
            return False
        # Block wheel scrolling on the list and its viewport to avoid showing scrollbars
        if (obj is self.results or obj is self.results.viewport()) and event.type() == QEvent.Wheel:
            return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._maybe_emit_page_size()

    def showEvent(self, event):
        super().showEvent(event)
        # ensure initial page size is computed after the widget is first shown
        self._maybe_emit_page_size()

    def _position_pager(self):
        # No-op: pager is now in a fixed toolbar below the list
        return

    def set_pager(self, has_prev: bool, has_next: bool):
        # Always visible; enable/disable per availability
        self.btn_prev_page.setEnabled(bool(has_prev))
        self.btn_next_page.setEnabled(bool(has_next))

    def current_result(self):
        """获取当前选中的结果项"""
        item = self.results.currentItem()
        if not item:
            return None
        rid = item.data(Qt.UserRole)
        if not isinstance(rid, int):
            return None
        return {
            'id': rid,
            'date_text': item.data(Qt.UserRole + 1),
            'confidence': item.data(Qt.UserRole + 2),
            'image_path': item.data(Qt.UserRole + 3).split('|')[0] if item.data(Qt.UserRole + 3) else '',
            'processed_image_path': item.data(Qt.UserRole + 3).split('|')[1] if item.data(Qt.UserRole + 3) and '|' in item.data(Qt.UserRole + 3) else '',
            'created_at': item.data(Qt.UserRole + 4)
        }


 
