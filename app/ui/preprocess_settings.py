from __future__ import annotations

import os
import sys
from typing import Optional

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QGroupBox,
)

from ..core.preprocess import apply_preprocess
from .fluent import PrimaryPushButton, PushButton


class PreprocessSettingsDialog(QDialog):
    def __init__(self, cfg: dict, current_frame: Optional[object] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('预处理设置')
        self.resize(720, 560)
        self._cfg = cfg
        self._current_frame = current_frame
        self._build_ui()
        self._load_from_config(cfg)

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Camera resolution group
        grp_cam = QGroupBox('相机分辨率')
        cam_form = QFormLayout()
        from PySide6.QtWidgets import QAbstractSpinBox
        self.sp_width = QSpinBox(); self.sp_width.setRange(160, 7680); self.sp_width.setSingleStep(64); self.sp_width.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sp_height = QSpinBox(); self.sp_height.setRange(120, 4320); self.sp_height.setSingleStep(64); self.sp_height.setButtonSymbols(QAbstractSpinBox.NoButtons)
        cam_form.addRow('宽度', self.sp_width)
        cam_form.addRow('高度', self.sp_height)
        grp_cam.setLayout(cam_form)
        root.addWidget(grp_cam)

        # Preprocess group
        grp_pp = QGroupBox('图像预处理')
        pp_form = QFormLayout()
        self.cb_enable = QCheckBox('启用预处理')
        pp_form.addRow(self.cb_enable)

        self.cb_gray = QCheckBox('转为灰度')
        pp_form.addRow(self.cb_gray)

        self.cb_morph = QCheckBox('启用形态学')
        pp_form.addRow(self.cb_morph)

        self.cb_denoise = QCheckBox('启用去噪')
        pp_form.addRow(self.cb_denoise)

        # 亮度/对比度
        from PySide6.QtWidgets import QAbstractSpinBox
        self.sp_brightness = QDoubleSpinBox(); self.sp_brightness.setRange(0.1, 3.0); self.sp_brightness.setSingleStep(0.1); self.sp_brightness.setDecimals(2); self.sp_brightness.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sp_contrast = QDoubleSpinBox(); self.sp_contrast.setRange(0.1, 3.0); self.sp_contrast.setSingleStep(0.1); self.sp_contrast.setDecimals(2); self.sp_contrast.setButtonSymbols(QAbstractSpinBox.NoButtons)
        pp_form.addRow('亮度', self.sp_brightness)
        pp_form.addRow('对比度', self.sp_contrast)

        # 形态学参数
        self.cmb_morph_type = QComboBox(); self.cmb_morph_type.addItems(['open', 'close', 'dilate', 'erode'])
        self.sp_kernel = QSpinBox(); self.sp_kernel.setRange(1, 31); self.sp_kernel.setSingleStep(2); self.sp_kernel.setButtonSymbols(QAbstractSpinBox.NoButtons)
        pp_form.addRow('形态学类型', self.cmb_morph_type)
        pp_form.addRow('核大小', self.sp_kernel)

        grp_pp.setLayout(pp_form)
        root.addWidget(grp_pp)

        # Preview area
        self.lbl_preview = QLabel('预览区')
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumHeight(200)
        root.addWidget(self.lbl_preview)

        # Buttons
        btns = QHBoxLayout()
        self.btn_preview = PushButton('预览')
        self.btn_preview.setProperty('fluentSecondary', True)
        self.btn_test_ocr = PushButton('测试 OCR 接口')
        self.btn_test_ocr.setProperty('fluentSecondary', True)
        self.btn_save = PrimaryPushButton('保存')
        self.btn_cancel = PushButton('取消')
        for b in (self.btn_preview, self.btn_test_ocr):
            btns.addWidget(b)
        btns.addStretch(1)
        for b in (self.btn_save, self.btn_cancel):
            btns.addWidget(b)
        root.addLayout(btns)

        # Connects
        self.btn_preview.clicked.connect(self._on_preview)
        self.btn_test_ocr.clicked.connect(self._on_test_ocr)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.cb_enable.toggled.connect(self._on_enable_toggled)
        # sub-feature enable/disable
        self.cb_morph.toggled.connect(lambda c: self._set_widgets_enabled([self.cmb_morph_type, self.sp_kernel], c))

    def _load_from_config(self, cfg: dict):
        cam = cfg.get('camera', {})
        self.sp_width.setValue(int(cam.get('width', 1280)))
        self.sp_height.setValue(int(cam.get('height', 720)))

        pp = cfg.get('preprocess', {})
        self.cb_enable.setChecked(bool(pp.get('enable_preprocess', True)))
        self.cb_gray.setChecked(bool(pp.get('convert_to_gray', True)))
        self.cb_morph.setChecked(bool(pp.get('morphology_enabled', True)))
        self.cb_denoise.setChecked(bool(pp.get('denoising_enabled', True)))
        # brightness/contrast
        try:
            self.sp_brightness.setValue(float(pp.get('brightness', 1.0)))
        except Exception:
            self.sp_brightness.setValue(1.0)
        try:
            self.sp_contrast.setValue(float(pp.get('contrast', 1.0)))
        except Exception:
            self.sp_contrast.setValue(1.0)
        # morphology params
        self.cmb_morph_type.setCurrentText(str(pp.get('morphology_type', 'open')))
        self.sp_kernel.setValue(int(pp.get('kernel_size', 5)))
        # apply enable state on controls
        self._apply_controls_enabled(self.cb_enable.isChecked())
        self._sync_sub_features_enabled()

    def _collect_preprocess_cfg(self) -> dict:
        # Build preprocess sub-config dict
        cfg = {
            'enable_preprocess': bool(self.cb_enable.isChecked()),
            'convert_to_gray': bool(self.cb_gray.isChecked()),
            'brightness': float(self.sp_brightness.value()),
            'contrast': float(self.sp_contrast.value()),

            'morphology_enabled': bool(self.cb_morph.isChecked()),
            'morphology_type': str(self.cmb_morph_type.currentText()),
            'kernel_size': int(self.sp_kernel.value()),

            'denoising_enabled': bool(self.cb_denoise.isChecked()),
        }
        return cfg

    def _apply_controls_enabled(self, enabled: bool):
        widgets = [
            self.cb_gray,
            self.cb_morph,
            self.cmb_morph_type,
            self.sp_kernel,
            self.cb_denoise,
            self.sp_brightness,
            self.sp_contrast,
        ]
        for w in widgets:
            w.setEnabled(bool(enabled))

    def _on_enable_toggled(self, checked: bool):
        self._apply_controls_enabled(bool(checked))
        if checked:
            self._sync_sub_features_enabled()

    def _set_widgets_enabled(self, widgets, enabled: bool):
        for w in widgets:
            try:
                w.setEnabled(bool(enabled))
            except Exception:
                pass

    def _sync_sub_features_enabled(self):
        # reflect current master toggles to their parameter widgets
        self._set_widgets_enabled([self.cmb_morph_type, self.sp_kernel], self.cb_morph.isChecked())
        

    def _on_preview(self):
        if self._current_frame is None:
            QMessageBox.information(self, '提示', '当前无相机画面，无法预览。')
            return
        frame = self._current_frame.copy()
        pp_cfg = self._collect_preprocess_cfg()
        if not pp_cfg.get('enable_preprocess', True):
            img = frame
        else:
            img = apply_preprocess(frame, pp_cfg)
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, w * 3, QImage.Format_BGR888)
        pix = QPixmap.fromImage(qimg).scaled(self.lbl_preview.width(), self.lbl_preview.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(pix)

    def _on_test_ocr(self):
        # Mimic OCRWorker import behavior
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        try:
            from PPOCR_api import GetOcrApi
            paths = self._cfg.get('paths', {})
            exe_path = paths.get('paddleocr_json_exe')
            models_path = paths.get('paddleocr_models_path')
            if not os.path.isfile(exe_path) or not os.path.isdir(models_path):
                raise RuntimeError('OCR 程序或模型目录不存在')
            ocr = GetOcrApi(exePath=exe_path, modelsPath=models_path, argument=None, ipcMode='pipe')
            del ocr
            QMessageBox.information(self, '测试结果', 'OCR 接口可用。')
        except Exception as e:
            QMessageBox.warning(self, '测试失败', f'OCR 接口不可用：{e}')

    def _on_save(self):
        # Write back to config object
        cam = self._cfg.setdefault('camera', {})
        cam['width'] = int(self.sp_width.value())
        cam['height'] = int(self.sp_height.value())
        self._cfg['preprocess'] = self._collect_preprocess_cfg()
        self.accept()


