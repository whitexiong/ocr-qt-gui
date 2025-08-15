from __future__ import annotations
import os
import cv2
import time
from datetime import datetime
import math
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage
import json

from ..ui.main_window import MainWindow
from ..services.camera import CameraWorker
from ..services.ocr_worker import OCRWorker
from ..core.db import get_session, OcrResult
from ..core.config import load_config, save_config
from ..core.preprocess import apply_preprocess
from ..ui.image_viewer import ImageViewerDialog

class AppController:
    def __init__(self):
        self.cfg = load_config()
        self.win = MainWindow()
        self.win.on_refresh = self.refresh_devices
        self.win.startCamera.connect(self.start_camera)
        self.win.stopCamera.connect(self.stop_camera)
        self.win.captureNow.connect(self.capture_once)
        self.win.view.roiChanged.connect(self.on_roi_changed)
        self.win.resultSelected.connect(self.on_result_selected)
        self.win.editText.connect(self.edit_result_text)
        self.win.showOriginal.connect(lambda: self.show_result_image(original=True))
        self.win.showProcessed.connect(lambda: self.show_result_image(original=False))
        self.win.loadMore.connect(self.on_load_more)
        self.win.pageSizeChanged.connect(self.on_page_size_changed)
        self.win.nextPage.connect(self.go_next_page)
        self.win.prevPage.connect(self.go_prev_page)
        self.win.onOpenSettings = self.open_preprocess_settings
        self.win.onOpenDebug = self.open_debug_dialog
        self.win.preprocessToggled.connect(self.on_preprocess_toggled)
        
        # theme
        try:
            from ..ui.fluent import set_theme as _set_theme  # type: ignore
            _set_theme(self.cfg.get('ui', {}).get('theme', 'auto'), self.win)
        except Exception:
            pass
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
        self.page_size = 6
        # page-based pagination
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self._has_prev = False
        self._has_next = False

        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.auto_capture_tick)
        if self.cfg['camera'].get('auto_capture', True):
            self.auto_timer.start(self.cfg['camera'].get('capture_interval_ms', 1000))

        self.refresh_devices()
        self.load_latest()
        self.win.show()
        self._update_pager_buttons()
        # init preprocess toggle state from config
        self.win.set_preprocess_enabled(bool(self.cfg.get('preprocess', {}).get('enable_preprocess', True)))

    # ---------- settings & theme ----------
    def on_theme_changed(self, mode: str):
        ui_cfg = self.cfg.setdefault('ui', {})
        ui_cfg['theme'] = mode
        save_config(self.cfg)

    # ---------- devices & camera ----------
    def refresh_devices(self):
        try:
            devices = CameraWorker.list_devices()
        except Exception as e:
            QMessageBox.warning(self.win, '设备枚举失败', str(e))
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
        self.current_frame = None
        self.win.clear_frame()
        self.win.show_placeholder('相机已关闭')
        self.win.set_camera_running(False)

    def on_camera_stopped(self):
        self.current_frame = None
        self.win.clear_frame()
        self.win.show_placeholder('相机已关闭')
        self.win.set_camera_running(False)

    def on_frame(self, frame):
        self.current_frame = frame
        self.win.show_frame(frame)

    # ---------- capture & ocr ----------
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
        # Respect global preprocess enable switch
        pp_cfg = self.cfg.get('preprocess', {}) or {}
        if not pp_cfg.get('enable_preprocess', True):
            proc_full = frame.copy()
        else:
            proc_full = apply_preprocess(frame, pp_cfg)
        roi_view = self._extract_roi(proc_full)

        snapshot_dir = self.cfg['paths']['snapshot_dir']
        os.makedirs(snapshot_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        orig_path = os.path.join(snapshot_dir, f'photo_{ts}.jpg')
        proc_path = os.path.join(snapshot_dir, f'photo_{ts}_proc.jpg')
        cv2.imwrite(orig_path, frame)
        cv2.imwrite(proc_path, proc_full)

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
            self.load_latest()
            self._pending_save = None

    def save_result(self, text: str, confidence: float, orig_path: str, proc_path: str, det_boxes_json: str = None):
        from ..core.db import get_session, OcrResult
        session = get_session()
        try:
            rec = OcrResult(image_path=orig_path, processed_image_path=proc_path, date_text=text,
                            confidence=confidence, det_boxes_json=det_boxes_json)
            session.add(rec)
            session.commit()
            return rec.id
        finally:
            session.close()

    # ---------- results list ----------
    def on_result_selected(self, rid: int):
        session = get_session()
        try:
            row = session.query(OcrResult).filter(OcrResult.id == rid).first()
            if not row:
                return
            self.win.set_result_detail('', 0.0)
        finally:
            session.close()

    def show_result_image(self, original: bool):
        item = self.win.results.currentItem()
        if not item:
            return
        rid = item.data(0x0100)
        if not isinstance(rid, int):
            return
        session = get_session()
        path = None
        try:
            row = session.query(OcrResult).filter(OcrResult.id == rid).first()
            if not row:
                return
            path = row.image_path if original else (row.processed_image_path or row.image_path)
        finally:
            session.close()
        if not path or not os.path.exists(path):
            return
        img = cv2.imread(path)
        if img is None:
            return
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, w*3, QImage.Format_BGR888)
        dlg = ImageViewerDialog(self.win)
        dlg.resize(min(960, w), min(720, h))
        dlg.setImage(qimg)
        dlg.exec()

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
        self.load_latest()

    # ---------- roi ----------
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

    # ---------- settings dialog ----------
    def open_preprocess_settings(self):
        from PySide6.QtWidgets import QDialog
        from ..ui.preprocess_settings import PreprocessSettingsDialog
        dlg = PreprocessSettingsDialog(self.cfg, self.current_frame, self.win)
        if dlg.exec() == QDialog.Accepted:
            # save and apply
            save_config(self.cfg)
            # If resolution changed, restart camera to apply
            try:
                cam_w = int(self.cfg['camera'].get('width', 1280))
                cam_h = int(self.cfg['camera'].get('height', 720))
            except Exception:
                cam_w, cam_h = 1280, 720
            if self.camera:
                # If running, stop then start with new resolution
                self.stop_camera()
                self.camera = None
                # restart only if previously enabled via UI start
            # Optionally auto-start after change if auto_capture enabled
            # Here we do nothing; user can start camera manually

    def open_debug_dialog(self):
        try:
            from ..ui.debug_dialog import DebugDialog
        except Exception as e:
            QMessageBox.critical(self.win, '错误', f'无法打开调试模式：{e}')
            return
        dlg = DebugDialog(self.cfg, parent=self.win)
        dlg.exec()

    # ---------- preprocess toggle ----------
    def on_preprocess_toggled(self, enabled: bool):
        pp = self.cfg.setdefault('preprocess', {})
        pp['enable_preprocess'] = bool(enabled)
        save_config(self.cfg)

    # ---------- pagination ----------
    def load_latest(self):
        session = get_session()
        try:
            size = int(self.page_size)
            rows = session.query(OcrResult).order_by(OcrResult.id.desc()).limit(size).all()
            simple = []
            for r in rows:
                ts = r.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(r, 'created_at', None) else ''
                simple.append((r.id, r.date_text or '', float(r.confidence or 0.0), r.image_path, r.processed_image_path, ts))
            self.win.set_results(simple)
            if rows:
                self.loaded_until_id = rows[-1].id
                self._page_anchor_id = rows[0].id
            else:
                self.loaded_until_id = None
                self._page_anchor_id = None
        finally:
            session.close()
        self._recalc_has_prev_next()
        self._update_pager_buttons()

    def on_load_more(self):
        # No-op: list scrolling pagination disabled; we use page toolbar
        return

    def _recalc_has_prev_next(self):
        self._has_prev = bool(self.current_page > 1)
        self._has_next = bool(self.current_page < max(1, self.total_pages))

    def _update_pager_buttons(self):
        if hasattr(self.win, 'set_pager'):
            self.win.set_pager(self._has_prev, self._has_next)

    def go_next_page(self):
        # 下一页：向更新方向移动（页码 +1），最后一页为最新数据
        if self.current_page >= self.total_pages:
            return
        self.current_page += 1
        self._load_page(self.current_page)

    def go_prev_page(self):
        # 上一页：向更旧方向移动（页码 -1）
        if self.current_page <= 1:
            return
        self.current_page -= 1
        self._load_page(self.current_page)

    # ---------- viewport page size ----------
    def on_page_size_changed(self, size: int):
        try:
            new_size = int(size)
        except Exception:
            return
        if new_size <= 0:
            new_size = 1
        if new_size == self.page_size:
            return
        self.page_size = new_size
        # Recalculate total pages; default回到最新页（最后一页）
        self.load_latest()

    # ---------- page-based loading ----------
    def _compute_counts(self):
        session = get_session()
        try:
            self.total_count = int(session.query(OcrResult).count())
            self.total_pages = int(max(1, math.ceil(self.total_count / float(self.page_size or 1))))
        finally:
            session.close()

    def _load_page(self, page: int):
        self._compute_counts()
        if self.total_count == 0:
            self.current_page = 1
            self.total_pages = 1
            self.win.set_results([])
            if hasattr(self.win, 'set_page_label'):
                self.win.set_page_label(1, 1, 0, 0)
            self._recalc_has_prev_next()
            self._update_pager_buttons()
            return
        # Clamp page within range
        page = max(1, min(int(page), int(self.total_pages)))
        self.current_page = page
        offset = (page - 1) * int(self.page_size)
        session = get_session()
        try:
            rows = (session.query(OcrResult)
                    .order_by(OcrResult.id.desc())
                    .offset(offset)
                    .limit(int(self.page_size))
                    .all())
            # Build tuples and reverse within page to show descending (newest first)
            simple = []
            for r in rows:
                ts = r.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(r, 'created_at', None) else ''
                simple.append((r.id, r.date_text or '', float(r.confidence or 0.0), r.image_path, r.processed_image_path, ts))
            self.win.set_results(simple)
            if hasattr(self.win, 'set_page_label'):
                self.win.set_page_label(self.current_page, self.total_pages, len(simple), self.total_count)
        finally:
            session.close()
        self._recalc_has_prev_next()
        self._update_pager_buttons()

    def load_latest(self):
        # Default to page 1 which contains the latest data in descending order
        self._compute_counts()
        self.current_page = 1
        self._load_page(self.current_page)

    # ---------- global error handling ----------
    def on_error(self, message: str):
        try:
            QMessageBox.critical(self.win, '错误', str(message))
        except Exception:
            # Fallback to stderr in case UI cannot show
            import sys
            print(f"[ERROR] {message}", file=sys.stderr)
