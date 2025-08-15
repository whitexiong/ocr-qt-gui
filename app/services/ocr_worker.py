from __future__ import annotations
import os
import sys
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

# ensure project root is importable to access PPOCR_api
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PPOCR_api import GetOcrApi  # PaddleOCR-json wrapper
from .ocr_pipeline import OCRPipeline


class OCRWorker(QThread):
    detectionDone = Signal(object, object)  # (dt_boxes, rec_res)
    recognitionDone = Signal(object)        # rec_res
    error = Signal(str)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._task_queue: list[dict] = []
        self._running = True
        self._ocr = None
        self._pipeline = OCRPipeline(cfg)

    def _ensure_engine(self):
        if self._ocr is not None:
            return
        exe_path = self.cfg['paths'].get('paddleocr_json_exe', os.path.join(_REPO_ROOT, 'lib', 'PaddleOCR-json.exe'))
        models_path = self.cfg['paths'].get('paddleocr_models_path', os.path.join(_REPO_ROOT, 'lib', 'models'))
        # Fallback if paths are invalid
        if not os.path.isfile(exe_path):
            exe_path = os.path.join(_REPO_ROOT, 'lib', 'PaddleOCR-json.exe')
        if not os.path.isdir(models_path):
            models_path = os.path.join(_REPO_ROOT, 'lib', 'models')
        # Engine arguments from config
        arg_cfg = dict(self.cfg.get('paddleocr_json_args', {}) or {})
        # allow overriding models_path via arguments
        arg_models = arg_cfg.get('models_path') or None
        if arg_models:
            models_path = arg_models
        try:
            self._ocr = GetOcrApi(exePath=exe_path, modelsPath=models_path, argument=arg_cfg, ipcMode='pipe')
        except Exception as e:
            self.error.emit(f'加载PaddleOCR-json失败: {e}')
            self._running = False

    def _run_ocr_on_frame(self, frame) -> tuple[list, list]:
        text, conf, boxes = self._pipeline.recognize(frame)
        # Map to expected legacy outputs: boxes + per-piece rec (single entry with whole text)
        dt_boxes = boxes or []
        rec_res = [(text, float(conf) if conf is not None else 0.0)] if text else []
        return dt_boxes, rec_res

    def run(self):
        self._ensure_engine()
        if self._ocr is None:
            return
        while self._running:
            if not self._task_queue:
                self.msleep(10)
                continue
            task = self._task_queue.pop(0)
            task_type = task['type']
            frame = task['frame']
            try:
                dt_boxes, rec_res = self._run_ocr_on_frame(frame)
                if task_type == 'detect':
                    self.detectionDone.emit(dt_boxes, rec_res)
                else:
                    self.recognitionDone.emit(rec_res)
            except Exception as e:
                self.error.emit(str(e))

    def submit_detect(self, frame):
        self._task_queue.append({'type': 'detect', 'frame': frame})

    def submit_recognize(self, frame):
        self._task_queue.append({'type': 'recognize', 'frame': frame})

    def stop(self):
        self._running = False
        self.wait(1000)


