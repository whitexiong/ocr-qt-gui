from __future__ import annotations
import os
import cv2
import numpy as np
from datetime import datetime
import math
import time
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPalette
import json
from PIL import Image, ImageDraw, ImageFont

from ..ui.main_window import MainWindow
from ..services.camera import CameraWorker
from ..core.db import get_session, OcrResult
from ..core.config import load_config, save_config, get_resource_path
from ..core.preprocess import apply_preprocess
from ..ui.image_viewer import ImageViewerDialog

# RapidOCR导入
try:
    from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion
except ImportError:
    RapidOCR = None

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
        self.win.clearAllData.connect(self.clear_all_data)
        self.win.deleteCurrentData.connect(self.delete_current_data)
        # self.win.realtimeOcrToggled.connect(self.on_realtime_ocr_toggled)
        
        # theme
        try:
            from ..ui.fluent import set_theme as _set_theme  # type: ignore
            _set_theme(self.cfg.get('ui', {}).get('theme', 'auto'), self.win)
        except Exception:
            pass
        self.win.onThemeChangedCallback = self.on_theme_changed

        self.camera = None
        self.current_frame = None
        self.roi_norm = self.cfg['camera'].get('roi_norm')
        self.page_size = 6
        # 移除实时检测状态（性能考虑）
        # self.realtime_ocr_enabled = False
        # self.last_detection_time = 0
        # self.detection_interval = 5.0  # 每5秒检测一次
        # self.detection_display_time = 3.0  # 检测结果显示3秒
        # self.last_detection_result = None
        # self.detection_start_time = 0
        # page-based pagination
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self._has_prev = False
        self._has_next = False

        # 初始化RapidOCR
        self.ocr = None
        self._init_rapidocr()

        self.refresh_devices()
        self.load_latest()
        self.win.show()
        self._update_pager_buttons()
        # init preprocess toggle state from config
        self.win.set_preprocess_enabled(bool(self.cfg.get('preprocess', {}).get('enable_preprocess', True)))

    def _init_rapidocr(self):
        """初始化RapidOCR"""
        if RapidOCR is None:
            QMessageBox.critical(self.win, '错误', 'RapidOCR未安装，请安装rapidocr-onnxruntime包')
            return
        
        try:
            # 获取模型路径
            from ..core.config import get_resource_path
            det_path = get_resource_path('lib/models/custom_det_model/det.onnx')
            rec_path = get_resource_path('lib/models/custom_rec_model/rec.onnx')
            dict_path = get_resource_path('lib/models/dict_custom_chinese_date.txt')
            
            # 配置RapidOCR参数（与test_camera_ocr.py保持一致）
            params = {
                'Global.use_cls': False,
                'Det.engine_type': EngineType.ONNXRUNTIME,
                'Rec.engine_type': EngineType.ONNXRUNTIME,
                'Det.lang_type': LangDet.CH,
                'Rec.lang_type': LangRec.CH,
                'Det.model_type': ModelType.MOBILE,
                'Rec.model_type': ModelType.MOBILE,
                'Det.ocr_version': OCRVersion.PPOCRV5,
                'Rec.ocr_version': OCRVersion.PPOCRV5,
                'Det.box_thresh': 0.3,
                'Det.thresh': 0.1,
                'Det.unclip_ratio': 2.0,
                'Rec.rec_img_shape': [3, 48, 320],
            }
            
            # 只有当模型文件存在时才设置模型路径
            if all(os.path.exists(p) for p in [det_path, rec_path, dict_path]):
                params['Det.model_path'] = det_path
                params['Rec.model_path'] = rec_path
                params['Rec.rec_keys_path'] = dict_path
                print("使用自定义模型")
            else:
                print("模型文件不存在，使用默认模型")
            
            self.ocr = RapidOCR(params=params)
            print("RapidOCR初始化成功")
        except Exception as e:
            print(f"RapidOCR初始化失败: {e}")
            # 使用默认配置
            try:
                self.ocr = RapidOCR()
                print("使用默认RapidOCR配置")
            except Exception as e2:
                QMessageBox.critical(self.win, '错误', f'RapidOCR初始化完全失败: {e2}')
                self.ocr = None
    
    def get_chinese_font(self, size=20):
        """获取中文字体（跨平台）"""
        try:
            search_paths = []
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            project_fonts = [
                os.path.join(root, 'assets', 'fonts', 'NotoSansSC-Regular.otf'),
                os.path.join(root, 'assets', 'fonts', 'NotoSansSC-Regular.ttf'),
                os.path.join(root, 'assets', 'fonts', 'msyh.ttc'),
            ]
            search_paths.extend(project_fonts)

            win_fonts = [
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/simsun.ttc",
                "C:/Windows/Fonts/msyh.ttf",
            ]
            search_paths.extend(win_fonts)

            linux_fonts = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/arphic/ukai.ttf",
                "/usr/share/fonts/truetype/arphic/uming.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            search_paths.extend(linux_fonts)

            for font_path in search_paths:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception:
                        continue
            return ImageFont.load_default()
        except Exception as e:
            print(f"字体加载失败: {e}")
            return ImageFont.load_default()
    
    def _get_text_color_for_pil(self):
        """获取PIL绘制用的文字颜色"""
        app = QApplication.instance()
        if app is None:
            return (0, 0, 0)  # 默认黑色
        
        # 获取当前调色板
        palette = app.palette()
        base_color = palette.color(QPalette.Base)
        
        # 判断是否为深色主题
        is_dark = (0.2126 * base_color.redF() + 0.7152 * base_color.greenF() + 0.0722 * base_color.blueF()) < 0.5
        
        # 深色主题使用白色文字，浅色主题使用黑色文字
        return (255, 255, 255) if is_dark else (0, 0, 0)
    
    def draw_chinese_text(self, image, boxes, texts, scores):
        """在图像上绘制中文文本"""
        # 将OpenCV图像转换为PIL图像
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)
        
        # 获取中文字体
        font = self.get_chinese_font(20)
        
        # 获取动态文字颜色
        text_color = self._get_text_color_for_pil()
        
        for box, text, score in zip(boxes, texts, scores):
            # 获取文本框的左上角坐标
            x, y = int(box[0][0]), int(box[0][1])
            
            # 绘制文本和置信度
            text_with_score = f"{text} ({score:.2f})"
            
            # 绘制文本背景
            bbox = draw.textbbox((x, y-25), text_with_score, font=font)
            draw.rectangle(bbox, fill=(0, 255, 0, 128))
            
            # 绘制文本，使用动态颜色
            draw.text((x, y-25), text_with_score, font=font, fill=text_color)
        
        # 将PIL图像转换回OpenCV格式
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    def _process_with_rapidocr(self, image):
        """使用RapidOCR处理图像"""
        if self.ocr is None:
            self.win.statusBar().showMessage("OCR未初始化")
            return
        
        try:
            self.win.statusBar().showMessage("正在识别...")
            
            # 执行OCR识别
            result = self.ocr(image)
            
            if result is None:
                self.win.statusBar().showMessage("识别失败")
                return
                
            # 检查result.boxes是否存在且不为空
            if not hasattr(result, 'boxes') or result.boxes is None or len(result.boxes) == 0:
                self.win.statusBar().showMessage("未检测到文本")
                return
            
            # 处理识别结果
            boxes = result.boxes
            texts = result.txts
            scores = result.scores
            
            # 对文本进行排序（从左到右，从上到下）
            sorted_results = self._sort_text_by_position(boxes, texts, scores)
            boxes, texts, scores = zip(*sorted_results) if sorted_results else ([], [], [])
            
            print(f"检测到 {len(boxes)} 个文本框:")
            for i, (box, text, score) in enumerate(zip(boxes, texts, scores)):
                # 确保文本正确编码
                if isinstance(text, bytes):
                    text = text.decode('utf-8', errors='ignore')
                elif not isinstance(text, str):
                    text = str(text)
                
                print(f"文本 {i+1}: {text} (置信度: {score:.3f})")
            
            # 在图像上绘制检测框
            result_image = image.copy()
            for box in boxes:
                box = np.array(box, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(result_image, [box], True, (0, 255, 0), 2)
            
            # 使用PIL绘制中文文本
            result_image_with_text = self.draw_chinese_text(result_image, boxes, texts, scores)
            
            # 保存识别结果
            self._save_recognition_result(result_image_with_text, texts, scores, boxes)
            
            self.win.statusBar().showMessage(f"识别完成，检测到 {len(boxes)} 个文本框")
            
        except Exception as e:
            print(f"识别失败: {e}")
            import traceback
            traceback.print_exc()
            self.win.statusBar().showMessage(f"识别失败: {str(e)}")

    # ---------- settings & theme ----------
    def on_theme_changed(self, mode: str):
        ui_cfg = self.cfg.setdefault('ui', {})
        ui_cfg['theme'] = mode
        save_config(self.cfg)
        
        # 刷新ROI视图中的文字颜色
        if hasattr(self.win, 'view') and hasattr(self.win.view, 'refresh_text_colors'):
            self.win.view.refresh_text_colors()

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
        
        # 直接显示普通帧（移除实时检测功能）
        self.win.show_frame(frame)

    # ---------- capture & ocr ----------
    def capture_once(self):
        if self.current_frame is None:
            return
        frame = self.current_frame.copy()
        roi_frame = self._get_roi_frame(frame)
        
        # 应用预处理（如果启用）
        pp_cfg = self.cfg.get('preprocess', {})
        if pp_cfg.get('enable_preprocess', True):
            roi_frame = apply_preprocess(roi_frame, pp_cfg)
        
        self._process_with_rapidocr(roi_frame)





    def _save_recognition_result(self, result_image, texts, scores, boxes):
        """保存识别结果"""
        try:
            # 创建快照目录
            from ..core.config import get_user_data_path
            snapshot_dir = get_user_data_path('snapshots')
            os.makedirs(snapshot_dir, exist_ok=True)
            
            # 生成时间戳
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            result_path = os.path.join(snapshot_dir, f'result_{ts}.jpg')
            
            # 保存结果图像
            cv2.imwrite(result_path, result_image)
            
            # 合并所有文本，验证排序是否正确
            combined_text = ' '.join(texts) if texts else ''
            
            # 验证文本排序是否符合要求格式
            expected_pattern = r'生产日期\s+\d{4}/\d{2}/\d{2}\s+CH\s+合格'
            import re
            if not re.search(expected_pattern, combined_text):
                print(f"警告：识别结果可能不符合预期格式。当前结果: {combined_text}")
                print(f"预期格式: 生产日期 YYYY/MM/DD CH 合格")
            avg_confidence = sum(scores) / len(scores) if scores else 0.0
            
            # 转换检测框为JSON格式
            try:
                import numpy as np
                det_boxes_json = json.dumps([np.asarray(b).tolist() for b in (boxes or [])], ensure_ascii=False)
            except Exception:
                det_boxes_json = '[]'
            
            # 保存到数据库
            rid = self.save_result(combined_text, avg_confidence, result_path, result_path, det_boxes_json)
            
            # 更新界面
            self.load_latest()
            
            # 在界面上显示识别结果
            self.win.set_result_detail(combined_text, avg_confidence)
            
            return rid
            
        except Exception as e:
            print(f"保存识别结果失败: {e}")
            return None
    
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
        # 不进行ROI裁剪，直接返回原始帧
        return frame

    def _extract_roi(self, frame):
        return self._get_roi_frame(frame)



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

    def clear_all_data(self):
        """清空所有图片和列表数据"""
        try:
            # 显示确认对话框
            reply = QMessageBox.question(
                self.win, 
                '确认清空', 
                '确定要清空所有图片和识别数据吗？此操作不可撤销！',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 删除数据库中的所有记录
                with get_session() as session:
                    session.query(OcrResult).delete()
                    session.commit()
                
                # 清空界面显示
                self.win.results.clear()
                self.win.set_page_label(1, 1, 0, 0)
                self.current_page = 1
                self.total_pages = 1
                self.total_count = 0
                self._update_pager_buttons()
                
                # 显示成功消息
                self.win.statusBar().showMessage('所有数据已清空')
                QMessageBox.information(self.win, '操作完成', '所有数据已成功清空！')
                
        except Exception as e:
            QMessageBox.critical(self.win, '错误', f'清空数据失败: {str(e)}')
    
    def delete_current_data(self, rid: int):
        """删除当前选中的数据"""
        try:
            # 显示确认对话框
            reply = QMessageBox.question(
                self.win,
                '确认删除',
                '确定要删除这条识别记录吗？此操作不可撤销！',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 从数据库中删除记录
                with get_session() as session:
                    result = session.query(OcrResult).filter(OcrResult.id == rid).first()
                    if result:
                        session.delete(result)
                        session.commit()
                        
                        # 重新加载当前页面
                        self.load_latest()
                        
                        # 显示成功消息
                        self.win.statusBar().showMessage('数据已删除')
                    else:
                        QMessageBox.warning(self.win, '警告', '未找到要删除的记录')
                        
        except Exception as e:
            QMessageBox.critical(self.win, '错误', f'删除数据失败: {str(e)}')
    
    # def on_realtime_ocr_toggled(self, enabled: bool):
    #     """实时OCR检测开关回调"""
    #     self.realtime_ocr_enabled = enabled
    #     if enabled:
    #         self.win.statusBar().showMessage('实时OCR检测已启用')
    #         print("实时OCR检测已启用")
    #     else:
    #         self.win.statusBar().showMessage('实时OCR检测已关闭')
    #         print("实时OCR检测已关闭")
    #         # 清除当前显示的检测框
    #         if self.current_frame is not None:
    #             self.win.show_frame(self.current_frame)
    
    # def _perform_frame_detection(self, frame):
    #     """执行抽帧OCR检测，返回带检测框的帧（优化版本）"""
    #     try:
    #         # 直接在原图上画一些模拟文本区域的检测框
    #         display_frame = frame.copy()
    #         h, w = frame.shape[:2]
    #         
    #         # 预定义一些合理的文本框位置（模拟常见的文本区域）
    #         text_regions = [
    #             # 上方区域（标题类文本）
    #             (w//4, h//6, w//4 + 200, h//6 + 40),
    #             # 中间区域（正文类文本）
    #             (w//6, h//2, w//6 + 300, h//2 + 25),
    #             # 下方区域（标签类文本）
    #             (w//3, h*2//3, w//3 + 150, h*2//3 + 30)
    #         ]
    #         
    #         # 随机选择1-2个区域显示
    #         import random
    #         selected_regions = random.sample(text_regions, random.randint(1, 2))
    #         
    #         for x1, y1, x2, y2 in selected_regions:
    #             # 确保框在图像范围内
    #             x1 = max(10, min(x1, w-200))
    #             y1 = max(30, min(y1, h-50))
    #             x2 = max(x1+100, min(x2, w-10))
    #             y2 = max(y1+20, min(y2, h-10))
    #             
    #             # 绘制检测框（使用更合适的颜色和线宽）
    #             cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    #             
    #             # 绘制置信度（位置更合理）
    #             confidence = random.uniform(0.75, 0.92)
    #             cv2.putText(display_frame, f"{confidence:.2f}", (x1, y1-5), 
    #                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    #         
    #         return display_frame
    #             
    #     except Exception as e:
    #         print(f"演示检测错误: {e}")
    #         return None
    
    def _draw_realtime_results(self, frame, boxes, texts, scores):
        """在帧上绘制实时检测结果（简化版本）"""
        try:
            # 计算ROI偏移量（如果有ROI的话）
            roi_offset_x, roi_offset_y = 0, 0
            if self.roi_norm:
                h, w = frame.shape[:2]
                roi_offset_x = int(self.roi_norm[0] * w)
                roi_offset_y = int(self.roi_norm[1] * h)
            
            # 使用OpenCV直接绘制，避免PIL转换开销
            for i, (box, text, score) in enumerate(zip(boxes, texts, scores)):
                # 调整坐标（加上ROI偏移）
                adjusted_box = []
                for point in box:
                    x, y = point
                    adjusted_box.append([int(x + roi_offset_x), int(y + roi_offset_y)])
                
                # 绘制检测框
                pts = np.array(adjusted_box, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                
                # 简化文本绘制（只显示置信度，避免中文渲染开销）
                if adjusted_box:
                    text_x, text_y = adjusted_box[0]
                    text_y = max(20, text_y - 10)
                    confidence_text = f"{score:.2f}"
                    cv2.putText(frame, confidence_text, (text_x, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            return frame
            
        except Exception as e:
            print(f"绘制实时结果错误: {e}")
            return frame

    def _sort_text_by_position(self, boxes, texts, scores):
        """根据文本内容和位置对文本进行智能排序，确保正确的语义顺序"""
        if len(boxes) == 0 or len(texts) == 0:
            return []
        
        # 创建包含位置信息和文本内容的元组列表
        text_items = []
        for box, text, score in zip(boxes, texts, scores):
            # 确保文本正确编码
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='ignore')
            elif not isinstance(text, str):
                text = str(text)
            
            # 计算文本框的中心点
            if len(box) >= 4:
                x_coords = [point[0] for point in box]
                y_coords = [point[1] for point in box]
                center_x = sum(x_coords) / len(x_coords)
                center_y = sum(y_coords) / len(y_coords)
                text_items.append((center_x, center_y, box, text, score))
        
        # 定义期望的文本顺序和优先级
        def get_text_priority(text):
            text = text.strip()
            if '生产日期' in text:
                return 1
            elif '/' in text and len(text.split('/')) == 3:  # 日期格式 YYYY/MM/DD
                return 2
            elif text == 'CH':
                return 3
            elif '合格' in text:
                return 4
            else:
                return 5  # 其他文本
        
        # 首先按照文本内容的语义优先级排序，然后按位置排序
        text_items.sort(key=lambda item: (get_text_priority(item[3]), item[1], item[0]))
        
        # 返回排序后的结果
        return [(item[2], item[3], item[4]) for item in text_items]

    # ---------- global error handling ----------
    def on_error(self, message: str):
        try:
            QMessageBox.critical(self.win, '错误', str(message))
        except Exception:
            # Fallback to stderr in case UI cannot show
            import sys
            print(f"[ERROR] {message}", file=sys.stderr)
