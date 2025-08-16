from __future__ import annotations

import os
from typing import List, Tuple

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QGroupBox,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
)

from .fluent import PrimaryPushButton, PushButton
from ..services.ocr_pipeline import OCRPipeline


def _to_qimage(bgr: np.ndarray) -> QImage:
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)


class DebugDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('调试模式')
        self.resize(900, 680)
        self._cfg = cfg
        self._image_bgr = None
        self._boxes: List[List[Tuple[int,int]]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Top: image selector
        grp_io = QGroupBox('测试图像')
        io_form = QFormLayout()
        row = QHBoxLayout()
        self.le_image = QLineEdit()
        self.btn_browse = PushButton('选择图片...')
        self.btn_browse.setProperty('fluentSecondary', True)
        row.addWidget(self.le_image)
        row.addWidget(self.btn_browse)
        io_form.addRow('图片路径', row)
        grp_io.setLayout(io_form)
        root.addWidget(grp_io)

        # Models: custom det/rec directories (deprecated in UI for packaging; kept hidden)
        grp_models = QGroupBox('模型 / 阈值 / 服务 配置（仅调试会话）')
        fm = QFormLayout()
        row_det = QHBoxLayout(); self.le_det = QLineEdit(); self.btn_browse_det = PushButton('浏览...'); self.btn_browse_det.setProperty('fluentSecondary', True); row_det.addWidget(self.le_det); row_det.addWidget(self.btn_browse_det)
        row_rec = QHBoxLayout(); self.le_rec = QLineEdit(); self.btn_browse_rec = PushButton('浏览...'); self.btn_browse_rec.setProperty('fluentSecondary', True); row_rec.addWidget(self.le_rec); row_rec.addWidget(self.btn_browse_rec)
        fm.addRow('DET 模型目录', row_det)
        fm.addRow('REC 模型目录', row_rec)
        # ONNX files
        row_det_onnx = QHBoxLayout(); self.le_det_onnx = QLineEdit(); self.btn_browse_det_onnx = PushButton('浏览...'); self.btn_browse_det_onnx.setProperty('fluentSecondary', True); row_det_onnx.addWidget(self.le_det_onnx); row_det_onnx.addWidget(self.btn_browse_det_onnx)
        row_rec_onnx = QHBoxLayout(); self.le_rec_onnx = QLineEdit(); self.btn_browse_rec_onnx = PushButton('浏览...'); self.btn_browse_rec_onnx.setProperty('fluentSecondary', True); row_rec_onnx.addWidget(self.le_rec_onnx); row_rec_onnx.addWidget(self.btn_browse_rec_onnx)
        fm.addRow('DET onnx 文件', row_det_onnx)
        fm.addRow('REC onnx 文件', row_rec_onnx)
        # dict path
        row_dict = QHBoxLayout(); self.le_dict = QLineEdit(); self.btn_browse_dict = PushButton('浏览...'); self.btn_browse_dict.setProperty('fluentSecondary', True); row_dict.addWidget(self.le_dict); row_dict.addWidget(self.btn_browse_dict)
        fm.addRow('自定义字典', row_dict)
        grp_models.setLayout(fm)
        grp_models.setVisible(False)
        root.addWidget(grp_models)

        # ONNX Configuration group (simplified)
        grp_onnx_config = QGroupBox('ONNX 配置')
        fm2 = QFormLayout()
        self.spin_thresh = QDoubleSpinBox(); self.spin_thresh.setRange(0.0, 1.0); self.spin_thresh.setSingleStep(0.01); self.spin_thresh.setDecimals(2)
        self.chk_olmocr = QCheckBox('启用 OLMOCR 兜底识别')
        fm2.addRow('置信度阈值', self.spin_thresh)
        fm2.addRow('', self.chk_olmocr)
        grp_onnx_config.setLayout(fm2)
        root.addWidget(grp_onnx_config)

        # Center: preview label
        self.lbl_preview = QLabel('预览区')
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumHeight(360)
        root.addWidget(self.lbl_preview)

        # Result text
        grp_out = QGroupBox('识别结果')
        v = QVBoxLayout()
        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        v.addWidget(self.txt_log)
        grp_out.setLayout(v)
        root.addWidget(grp_out)

        # Buttons
        btns = QHBoxLayout()
        self.btn_detect = PushButton('仅检测')
        self.btn_detect.setProperty('fluentSecondary', True)
        self.btn_recognize = PrimaryPushButton('检测并识别')
        self.btn_close = PushButton('关闭')
        btns.addWidget(self.btn_detect)
        btns.addWidget(self.btn_recognize)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        root.addLayout(btns)

        # signals
        self.btn_browse.clicked.connect(self._on_browse)
        self.btn_browse_det.clicked.connect(self._on_browse_det)
        self.btn_browse_rec.clicked.connect(self._on_browse_rec)
        self.btn_browse_det_onnx.clicked.connect(lambda: self._on_browse_file(self.le_det_onnx, '选择 DET onnx'))
        self.btn_browse_rec_onnx.clicked.connect(lambda: self._on_browse_file(self.le_rec_onnx, '选择 REC onnx'))
        self.btn_browse_dict.clicked.connect(lambda: self._on_browse_file(self.le_dict, '选择自定义字典', filter_str='*.txt'))
        self.btn_detect.clicked.connect(self._on_detect)
        self.btn_recognize.clicked.connect(lambda: self._on_detect(recognize=True))
        self.btn_close.clicked.connect(self.reject)

        # init fields from cfg
        onnx_cfg = self._cfg.get('onnx_ocr', {}) or {}
        self.le_det.setText('')  # 移除自定义模型路径
        self.le_rec.setText('')  # 移除自定义模型路径
        self.le_det_onnx.setText(str(onnx_cfg.get('det_onnx', '') or ''))
        self.le_rec_onnx.setText(str(onnx_cfg.get('rec_onnx', '') or ''))
        self.le_dict.setText(str(onnx_cfg.get('dict_path', '') or ''))
        # 直接使用ONNX策略，不需要策略选择
        self.spin_thresh.setValue(float(onnx_cfg.get('fallback_threshold', 0.95)))
        self.chk_olmocr.setChecked(False)  # 移除websocket OCR功能
        self._pipeline = OCRPipeline(self._cfg)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择图片', os.path.expanduser('~'), 'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)')
        if path:
            self.le_image.setText(path)
            img = cv2.imread(path)
            if img is None:
                self._append_log(f'加载失败: {path}')
                return
            self._image_bgr = img
            self._boxes = []
            self._update_preview()

    def _append_log(self, text: str):
        self.txt_log.append(text)

    def _on_browse_det(self):
        d = QFileDialog.getExistingDirectory(self, '选择 DET 模型目录', self.le_det.text() or os.path.expanduser('~'))
        if d:
            self.le_det.setText(d)

    def _on_browse_rec(self):
        d = QFileDialog.getExistingDirectory(self, '选择 REC 模型目录', self.le_rec.text() or os.path.expanduser('~'))
        if d:
            self.le_rec.setText(d)

    def _on_browse_file(self, line_edit: QLineEdit, title: str, filter_str: str = '*'):
        path, _ = QFileDialog.getOpenFileName(self, title, os.path.expanduser('~'), f'Files ({filter_str})')
        if path:
            line_edit.setText(path)

    def _apply_runtime_options(self):
        cfg = dict(self._cfg)
        onnx_cfg = dict((cfg.get('onnx_ocr', {}) or {}))
        # 直接启用ONNX策略
        onnx_cfg['enabled'] = True
        onnx_cfg['fallback_threshold'] = float(self.spin_thresh.value())
        cfg['onnx_ocr'] = onnx_cfg
        self._pipeline = OCRPipeline(cfg)
        return cfg

    def _update_preview(self, rec_text: str = None):
        if self._image_bgr is None:
            self.lbl_preview.setText('预览区')
            return
        vis = self._image_bgr.copy()
        # draw boxes
        if self._boxes:
            for box in self._boxes:
                pts = np.array(box, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(vis, [pts], isClosed=True, color=(0, 200, 0), thickness=2)
        if rec_text:
            y = max(24, int(0.05 * vis.shape[0]))
            cv2.rectangle(vis, (10, y - 22), (10 + min(780, vis.shape[1]-20), y + 8), (0, 0, 0), -1)
            cv2.putText(vis, rec_text, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        qimg = _to_qimage(vis)
        pix = QPixmap.fromImage(qimg).scaled(self.lbl_preview.width(), self.lbl_preview.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(pix)

    def _sort_boxes_left_to_right(self, boxes: List[List[Tuple[int,int]]]) -> List[List[Tuple[int,int]]]:
        def key(box):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            return (min(ys), min(xs))
        return sorted(boxes, key=key)

    def _crop_by_quad(self, img: np.ndarray, quad: List[Tuple[int,int]]):
        pts = np.array(quad, dtype=np.float32)
        w = int(max(np.linalg.norm(pts[0]-pts[1]), np.linalg.norm(pts[2]-pts[3])))
        h = int(max(np.linalg.norm(pts[1]-pts[2]), np.linalg.norm(pts[3]-pts[0])))
        dst = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        crop = cv2.warpPerspective(img, M, (w, h))
        if h > w:
            crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
        return crop

    def _on_detect(self, recognize: bool = False):
        path = self.le_image.text().strip()
        if not path or not os.path.isfile(path):
            self._append_log('请选择有效的图片文件')
            return
        img = cv2.imread(path)
        if img is None:
            self._append_log('图片加载失败')
            return
        self._image_bgr = img

        # Use unified pipeline with runtime options
        self._apply_runtime_options()
        text, conf, boxes = self._pipeline.recognize(img)
        self._boxes = self._sort_boxes_left_to_right(boxes or [])
        self._append_log(f'检测到 {len(self._boxes)} 个矩形（ONNX策略）')
        if recognize:
            self._append_log(f'识别文本：{text or ""}  (min置信度：{conf:.2f})')
            self._update_preview(text or '')
        else:
            self._update_preview()


