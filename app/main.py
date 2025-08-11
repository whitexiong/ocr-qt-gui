from __future__ import annotations
import os
import sys
import cv2
import json
import time
import threading
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

# ensure project root is importable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from .ui.main_window import MainWindow
from .services.camera import CameraWorker
from .services.ocr_worker import OCRWorker
from .core.db import init_db, get_session, OcrResult
from .core.config import load_config, save_config
from .core.preprocess import apply_preprocess
import json

class Controller:
    def __init__(self):
        init_db()
        self.cfg = load_config()

        self.win = MainWindow()
        self.win.on_refresh = self.refresh_devices
        self.win.startCamera.connect(self.start_camera)
        self.win.stopCamera.connect(self.stop_camera)
        self.win.captureNow.connect(self.capture_once)
        self.win.view.roiChanged.connect(self.on_roi_changed)
        # remove pagination wiring; use latest feed
        # import config action
        self.win.act_import_config.triggered.connect(self.import_external_config)
        self.win.resultSelected.connect(self.on_result_selected)
        self.win.editText.connect(self.edit_result_text)
        self.win.showOriginal.connect(lambda: self.show_result_image(original=True))
        self.win.showProcessed.connect(lambda: self.show_result_image(original=False))
        # theme menu sync from cfg
        theme_mode = self.cfg.get('ui', {}).get('theme', 'auto')
        try:
            from .ui.fluent import set_theme as _set_theme  # type: ignore
            _set_theme(theme_mode, self.win)
        except Exception:
            pass
        # hook back theme change persistence
        self.win.onThemeChangedCallback = self.on_theme_changed

        self.camera = None
        self.ocr = OCRWorker(self.cfg)
        self.ocr.detectionDone.connect(self.on_detection)
        self.ocr.recognitionDone.connect(self.on_recognition)
        self.ocr.error.connect(self.on_error)
        self.ocr.start()

        self.current_frame = None
        self.last_capture_ms = 0
        self.roi_norm = self.cfg['camera'].get('roi_norm')
        self.page_size = 100
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.auto_capture_tick)
        if self.cfg['camera'].get('auto_capture', True):
            self.auto_timer.start(self.cfg['camera'].get('capture_interval_ms', 1000))

        self.refresh_devices()
        self.load_latest()
        self.win.show()

    def import_external_config(self):
        # User selected a JSON, parse preprocessing-related fields and merge into cfg['preprocess']
        path = getattr(self.win, 'import_config_path', None)
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.win, '导入失败', f'读取配置失败: {e}')
            return

        # Extract relevant fields
        cfg_block = (data or {}).get('config', {})
        preprocess_block = cfg_block.get('图像预处理', {})
        preprocess_params = cfg_block.get('预处理参数', {})
        binarize_block = cfg_block.get('二值化处理', {})

        # Map incoming keys -> our preprocess cfg
        pre = self.cfg.setdefault('preprocess', {})
        pre['enable_preprocess'] = bool(preprocess_block.get('启用预处理', pre.get('enable_preprocess', True)))
        pre['convert_to_gray'] = bool(preprocess_block.get('转换为灰度', pre.get('convert_to_gray', True)))

        pre['binarization_enabled'] = bool(binarize_block.get('启用二值化', pre.get('binarization_enabled', False)))
        pre['binarization_method'] = str(binarize_block.get('二值化方法', pre.get('binarization_method', 'adaptive_mean')))
        pre['binarization_threshold'] = int(binarize_block.get('二值化阈值', pre.get('binarization_threshold', 127)))

        pre['morphology_enabled'] = bool(preprocess_block.get('形态学操作', pre.get('morphology_enabled', False)))
        pre['morphology_type'] = str(preprocess_block.get('形态学操作类型', pre.get('morphology_type', 'open')))
        pre['kernel_size'] = int(preprocess_params.get('核大小', pre.get('kernel_size', 5)))

        pre['denoising_enabled'] = bool(preprocess_block.get('去噪', pre.get('denoising_enabled', True)))

        pre['brightness'] = float(preprocess_params.get('亮度因子', pre.get('brightness', 1.0)))
        pre['contrast'] = float(preprocess_params.get('对比度因子', pre.get('contrast', 1.0)))

        pre['resize_enabled'] = bool(preprocess_block.get('调整大小', pre.get('resize_enabled', False)))
        pre['max_size'] = int(preprocess_params.get('最大尺寸', pre.get('max_size', 1024)))

        pre['add_border'] = bool(preprocess_block.get('添加边框', pre.get('add_border', False)))
        pre['border_size'] = int(preprocess_params.get('边框大小', pre.get('border_size', 0)))

        pre['crop_enabled'] = bool(preprocess_block.get('裁剪图像', pre.get('crop_enabled', False)))
        pre['crop_rect'] = preprocess_params.get('裁剪区域', pre.get('crop_rect'))

        save_config(self.cfg)
        QMessageBox.information(self.win, '导入成功', '配置已导入并保存。')

    # persist theme into cfg
    def on_theme_changed(self, mode: str):
        ui_cfg = self.cfg.setdefault('ui', {})
        ui_cfg['theme'] = mode
        save_config(self.cfg)

    def refresh_devices(self):
        try:
            devices = CameraWorker.list_devices()
        except ImportError as e:
            QMessageBox.warning(self.win, 'OpenCV 未就绪', str(e))
            devices = []
        except Exception as e:
            QMessageBox.warning(self.win, '设备枚举失败', str(e))
            devices = []
        if not devices:
            devices = [(0, 'Camera 0')]
        self.win.update_devices(devices)

    def start_camera(self):
        if self.camera and self.camera.isRunning():
            return
        dev = self.win.current_device()
        self.camera = CameraWorker(dev, self.cfg['camera']['width'], self.cfg['camera']['height'])
        self.camera.frameReady.connect(self.on_frame)
        self.camera.error.connect(self.on_error)
        self.camera.stopped.connect(self.on_camera_stopped)
        self.camera.start()
        self.win.set_camera_running(True)

    def stop_camera(self):
        if self.camera:
            self.camera.stop()
            self.camera = None
        # clear view and show placeholder
        self.current_frame = None
        self.win.clear_frame()
        self.win.show_placeholder('相机已关闭')
        self.win.set_camera_running(False)

    def on_camera_stopped(self):
        # ensure UI reflects stopped state even if camera thread ends by itself
        self.current_frame = None
        self.win.clear_frame()
        self.win.show_placeholder('相机已关闭')
        self.win.set_camera_running(False)

    def on_frame(self, frame):
        self.current_frame = frame
        self.win.show_frame(frame)

    def capture_once(self):
        if self.current_frame is None:
            return
        frame = self.current_frame.copy()
        roi_frame = self._get_roi_frame(frame)
        self.ocr.submit_detect(roi_frame)

    def on_detection(self, dt_boxes, rec_res):
        frame = self.current_frame
        if frame is None:
            return
        # preprocess full frame and ROI-view
        proc_full = apply_preprocess(frame, self.cfg['preprocess'])
        roi_view = self._extract_roi(proc_full)

        snapshot_dir = self.cfg['paths']['snapshot_dir']
        os.makedirs(snapshot_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        orig_path = os.path.join(snapshot_dir, f'photo_{ts}.jpg')
        proc_path = os.path.join(snapshot_dir, f'photo_{ts}_proc.jpg')
        cv2.imwrite(orig_path, frame)
        cv2.imwrite(proc_path, proc_full)

        # If boxes exist, choose the largest area and crop from ROI view for recognition
        if dt_boxes is not None and len(dt_boxes) > 0:
            import numpy as np
            try:
                areas = [cv2.contourArea(np.array(b, dtype=np.float32)) for b in dt_boxes]
                idx = int(np.argmax(areas))
                poly = np.array(dt_boxes[idx], dtype=np.float32)
                x1 = int(max(0, min(poly[:,0]))); y1 = int(max(0, min(poly[:,1])))
                x2 = int(min(roi_view.shape[1]-1, max(poly[:,0]))); y2 = int(min(roi_view.shape[0]-1, max(poly[:,1])))
                crop = roi_view[y1:y2, x1:x2].copy()
            except Exception:
                crop = roi_view
            self.ocr.submit_recognize(crop)
            # pending save with det boxes
            try:
                import numpy as _np
                det_boxes_json = json.dumps([_np.asarray(b).tolist() for b in (dt_boxes or [])], ensure_ascii=False)
            except Exception:
                det_boxes_json = None
            self._pending_save = {'orig': orig_path, 'proc': proc_path, 'det_boxes_json': det_boxes_json}
        else:
            self.save_result('', 0.0, orig_path, proc_path, det_boxes_json='[]')

    def on_recognition(self, rec_res):
        if rec_res is None or len(rec_res) == 0:
            text, conf = '', 0.0
        else:
            best = max(rec_res, key=lambda r: r[1] if isinstance(r, (list, tuple)) and len(r)>=2 else 0.0)
            text, conf = best
        pending = getattr(self, '_pending_save', None)
        if pending:
            rid = self.save_result(text, float(conf or 0.0), pending['orig'], pending['proc'], pending.get('det_boxes_json'))
            # reload latest list to reflect new record at top
            self.load_latest()
            self._pending_save = None

    def save_result(self, text: str, confidence: float, orig_path: str, proc_path: str, det_boxes_json: str = None):
        session = get_session()
        try:
            rec = OcrResult(image_path=orig_path, processed_image_path=proc_path, date_text=text,
                            confidence=confidence, det_boxes_json=det_boxes_json)
            session.add(rec)
            session.commit()
            return rec.id
        finally:
            session.close()

    def on_result_selected(self, rid: int):
        session = get_session()
        try:
            row = session.query(OcrResult).filter(OcrResult.id == rid).first()
            if not row:
                return
            self.win.set_result_detail(row.date_text or '', float(row.confidence or 0.0))
            # default show processed if exists else original
            path = row.processed_image_path or row.image_path
            if path and os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    self.win.show_frame(img)
        finally:
            session.close()

    def show_result_image(self, original: bool):
        # get selected item id
        item = self.win.results.currentItem()
        if not item:
            return
        rid = item.data(0x0100)  # Qt.UserRole
        if not isinstance(rid, int):
            return
        session = get_session()
        try:
            row = session.query(OcrResult).filter(OcrResult.id == rid).first()
            if not row:
                return
            path = row.image_path if original else (row.processed_image_path or row.image_path)
            if path and os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    self.win.show_frame(img)
        finally:
            session.close()

    def edit_result_text(self, rid: int):
        from PySide6.QtWidgets import QInputDialog
        session = get_session()
        try:
            row = session.query(OcrResult).filter(OcrResult.id == rid).first()
            if not row:
                return
            current = row.date_text or ''
            text, ok = QInputDialog.getText(self.win, '编辑识别文本', '文本：', text=current)
            if not ok:
                return
            row.date_text = text
            session.commit()
        except Exception as e:
            QMessageBox.critical(self.win, '更新失败', str(e))
        finally:
            session.close()
        # refresh visible list
        self.load_latest()

    def on_error(self, msg: str):
        QMessageBox.critical(self.win, '错误', msg)

    def on_roi_changed(self, roi_norm):
        self.roi_norm = roi_norm
        self.cfg['camera']['roi_norm'] = roi_norm
        save_config(self.cfg)

    def _get_roi_frame(self, frame):
        if not self.roi_norm:
            return frame
        h, w = frame.shape[:2]
        x1 = int(self.roi_norm[0] * w); y1 = int(self.roi_norm[1] * h)
        x2 = int(self.roi_norm[2] * w); y2 = int(self.roi_norm[3] * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 <= 2 or y2 - y1 <= 2:
            return frame
        return frame[y1:y2, x1:x2].copy()

    def _extract_roi(self, frame):
        return self._get_roi_frame(frame)

    def auto_capture_tick(self):
        if not self.cfg['camera'].get('auto_capture', True):
            return
        if self.current_frame is None:
            return
        now = time.time() * 1000
        if now - self.last_capture_ms < self.cfg['camera'].get('capture_interval_ms', 1000):
            return
        self.last_capture_ms = now
        roi_frame = self._get_roi_frame(self.current_frame.copy())
        self.ocr.submit_detect(roi_frame)

    def load_latest(self):
        session = get_session()
        try:
            size = int(self.page_size)
            rows = session.query(OcrResult).order_by(OcrResult.id.desc()).limit(size).all()
            # format time
            simple = []
            for r in rows:
                ts = r.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(r, 'created_at', None) else ''
                simple.append((r.id, r.date_text or '', float(r.confidence or 0.0), r.image_path, r.processed_image_path, ts))
            self.win.set_results(simple)
        finally:
            session.close()


def main():
    app = QApplication([])
    ctl = Controller()
    app.exec()

if __name__ == '__main__':
    main()
