from __future__ import annotations

import os
import sys
import json
import time
import base64
import tempfile
from typing import List, Tuple, Optional, Any

import cv2
import numpy as np

# ensure project root is importable to access PPOCR_api and test utilities
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PPOCR_api import GetOcrApi
from ..core.config import get_resource_path  # 导入路径处理函数

try:
    # RapidOCR is optional; we gate by config
    from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion  # type: ignore
    print("[DEBUG] RapidOCR 导入成功")
except Exception as e:
    print(f"[ERROR] RapidOCR 导入失败: {e}")
    import traceback
    traceback.print_exc()
    RapidOCR = None  # type: ignore


def _order_pts(pts: List[Tuple[float, float]]) -> np.ndarray:
    p = np.array(pts, dtype=np.float32)
    s = p.sum(axis=1)
    diff = np.diff(p, axis=1).reshape(-1)
    tl = p[np.argmin(s)]
    br = p[np.argmax(s)]
    tr = p[np.argmin(diff)]
    bl = p[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _crop_quad(img: np.ndarray, quad: List[Tuple[float, float]]) -> np.ndarray:
    quad_m = _order_pts(quad)
    (tl, tr, br, bl) = quad_m
    wA = np.linalg.norm(br - bl)
    wB = np.linalg.norm(tr - tl)
    hA = np.linalg.norm(tr - br)
    hB = np.linalg.norm(tl - bl)
    W = int(max(wA, wB)); H = int(max(hA, hB))
    W = max(1, W); H = max(1, H)
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad_m, dst)
    return cv2.warpPerspective(img, M, (W, H))


class OCRPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._rapid_ocr: Optional[Any] = None
        self._paddle_json = None
        self._det_ocr: Optional[Any] = None  # 检测模型缓存
        self._rec_ocr: Optional[Any] = None  # 识别模型缓存

    def _ensure_paddle_json(self):
        if self._paddle_json is not None:
            return
        paths = (self.cfg.get('paths', {}) or {})
        exe_path = paths.get('paddleocr_json_exe')
        models_path = paths.get('paddleocr_models_path')
        arg_cfg = dict(self.cfg.get('paddleocr_json_args', {}) or {})
        if arg_cfg.get('models_path'):
            models_path = arg_cfg['models_path']
        try:
            self._paddle_json = GetOcrApi(exePath=exe_path, modelsPath=models_path, argument=arg_cfg, ipcMode='pipe')
        except Exception:
            self._paddle_json = None

    def _ensure_det_ocr(self):
        """确保检测模型已初始化"""
        if self._det_ocr is not None:
            return
            
        onnx_cfg = self.cfg.get('onnx_ocr', {}) or {}
        det_path = get_resource_path('lib/models/custom_det_model/det.onnx')
        dict_path = get_resource_path('lib/models/dict_custom_chinese_date.txt')
        
        print(f"[DEBUG] 初始化检测模型: det_path={det_path}")
        print(f"[DEBUG] det文件存在: {os.path.isfile(det_path) if det_path else False}")
        print(f"[DEBUG] dict文件存在: {os.path.isfile(dict_path) if dict_path else False}")
        
        if not det_path or not os.path.isfile(det_path) or not dict_path or not os.path.isfile(dict_path):
            print(f"[ERROR] 检测模型文件缺失或路径错误")
            return

        if RapidOCR is None:
            print(f"[ERROR] RapidOCR 未导入成功")
            return

        # 严格按照 test.py 的参数设置
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
            'Det.model_path': det_path,
            'Rec.rec_keys_path': dict_path,
            'Det.box_thresh': float(onnx_cfg.get('det_box_thresh', 0.6)),
            'Det.thresh': float(onnx_cfg.get('det_thresh', 0.3)),
            'Det.unclip_ratio': float(onnx_cfg.get('det_unclip_ratio', 1.5)),
        }

        try:
            self._det_ocr = RapidOCR(params=params)
            print(f"[DEBUG] 检测模型初始化成功")
        except Exception as e:
            print(f"[ERROR] 检测模型初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def _ensure_rec_ocr(self):
        """确保识别模型已初始化"""
        if self._rec_ocr is not None:
            return
            
        onnx_cfg = self.cfg.get('onnx_ocr', {}) or {}
        rec_path = get_resource_path('lib/models/custom_rec_model/rec.onnx')
        dict_path = get_resource_path('lib/models/dict_custom_chinese_date.txt')
        
        print(f"[DEBUG] 初始化识别模型: rec_path={rec_path}")
        print(f"[DEBUG] rec文件存在: {os.path.isfile(rec_path) if rec_path else False}")
        print(f"[DEBUG] dict文件存在: {os.path.isfile(dict_path) if dict_path else False}")
        
        if not (rec_path and os.path.isfile(rec_path) and dict_path and os.path.isfile(dict_path)):
            print(f"[ERROR] 识别模型文件缺失或路径错误")
            return

        if RapidOCR is None:
            print(f"[ERROR] RapidOCR 未导入成功")
            return

        # 严格按照 test.py 的参数设置
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
            'Rec.model_path': rec_path,
            'Rec.rec_keys_path': dict_path,
            'Rec.rec_img_shape': list(onnx_cfg.get('rec_img_shape', [3, 48, 320])),
        }

        try:
            self._rec_ocr = RapidOCR(params=params)
            print(f"[DEBUG] 识别模型初始化成功")
        except Exception as e:
            print(f"[ERROR] 识别模型初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def _detect_boxes(self, image: np.ndarray) -> List[List[Tuple[float, float]]]:
        """使用 ONNX 检测文本框 (使用缓存的模型)"""
        self._ensure_det_ocr()
        if self._det_ocr is None:
            return []

        try:
            res = self._det_ocr(image, use_det=True, use_rec=False, use_cls=False)
            print(f"[DEBUG] 检测完成，结果类型: {type(res)}")
            
            boxes: List[List[Tuple[float, float]]] = []
            
            # 处理返回结果
            if hasattr(res, 'boxes') and isinstance(res.boxes, np.ndarray):
                print(f"[DEBUG] 使用新版本 API，检测到 {len(res.boxes)} 个文本框")
                # res.boxes 是 numpy array，形状为 (N, 4, 2)
                for box in res.boxes:
                    if box.shape == (4, 2):  # 确保是4个点的坐标
                        boxes.append([(float(x), float(y)) for x, y in box])
            elif isinstance(res, tuple) and len(res) >= 1:
                print(f"[DEBUG] 使用旧版本 API，res[0]: {res[0]}")
                for item in res[0] or []:
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        box = item[0] if len(item) >= 3 else item
                        if isinstance(box, (list, tuple)) and len(box) == 4:
                            boxes.append([(float(x), float(y)) for x, y in box])
            else:
                print(f"[DEBUG] 未知的结果格式")
                
            print(f"[DEBUG] 最终检测到 {len(boxes)} 个文本框")
            return boxes
        except Exception as e:
            print(f"[ERROR] ONNX detection failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _rapid_recognize(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """使用 ONNX 识别文本 (使用缓存的模型)"""
        self._ensure_rec_ocr()
        if self._rec_ocr is None:
            return []

        try:
            res = self._rec_ocr(image, use_det=False, use_rec=True, use_cls=False)
            recs: List[Tuple[str, float]] = []

            # 处理返回结果
            if hasattr(res, 'txts') and hasattr(res, 'scores'):
                # 新版本 API
                for t, s in zip(res.txts or [], res.scores or []):
                    if t and s is not None:
                        recs.append((str(t), float(s)))
            elif isinstance(res, tuple) and len(res) >= 1:
                # 兼容旧版本返回格式
                for item in res[0] or []:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        t, s = item[1], item[2]
                        if t and s is not None:
                            recs.append((str(t), float(s)))
            return recs
        except Exception as e:
            print(f"[ERROR] ONNX recognition failed: {e}")
            return []

    def _paddle_json_recognize(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """使用 PaddleOCR-json 识别文本"""
        self._ensure_paddle_json()
        if self._paddle_json is None:
            return []

        ok, buf = cv2.imencode('.jpg', image)
        if not ok:
            return []
        res = self._paddle_json.runBytes(bytes(buf))
        recs: List[Tuple[str, float]] = []
        if isinstance(res, dict) and res.get('code') == 100:
            for line in res.get('data', []) or []:
                t = line.get('text', '')
                s = float(line.get('score', 0.0) or 0.0)
                recs.append((str(t or ''), s))
        return recs

    def _ws_call(self, image: np.ndarray) -> Tuple[str, float]:
        ws_cfg = self.cfg.get('websocket_ocr', {}) or {}
        if not ws_cfg.get('enabled', True):
            return '', 0.0
        try:
            import websocket  # type: ignore
        except Exception:
            return '', 0.0
        url = ws_cfg.get('url', 'wss://olmocr.allen.ai/api/ws')
        prompt = ws_cfg.get('prompt', '')
        chunk_size = int(ws_cfg.get('chunk_size', 65536))
        ok, buf = cv2.imencode('.jpg', image)
        if not ok:
            return '', 0.0
        data = buf.tobytes()
        ws = websocket.create_connection(url)
        ptr = 0
        while ptr < len(data):
            chunk = data[ptr:ptr + chunk_size]
            ptr += len(chunk)
            ws.send(json.dumps({'fileChunk': base64.b64encode(chunk).decode('ascii')}))
        start_time = time.time()
        ws.send(json.dumps({'endOfFile': True, 'prompt': prompt}))
        text = ''
        while True:
            msg = ws.recv()
            payload = json.loads(msg)
            t = payload.get('type')
            d = payload.get('data', {})
            if t == 'page_complete':
                text = (d.get('response', {}) or {}).get('natural_text', '') or ''
                break
            if t == 'error':
                text = ''
                break
        ws.close()
        elapsed = time.time() - start_time
        # Confidence from WS is unknown; return 1.0 as a sentinel if non-empty
        return text.strip(), (1.0 if text.strip() else 0.0)

    def recognize(self, image: np.ndarray) -> Tuple[str, float, List[List[Tuple[int, int]]]]:
        """Run staged OCR and return (text, confidence, boxes).
        Confidence is the min of rec piece confidences where available.
        """
        onnx_cfg = self.cfg.get('onnx_ocr', {}) or {}
        threshold = float(onnx_cfg.get('fallback_threshold', 0.95))

        # 固定使用 ONNX 检测文本框
        boxes = self._detect_boxes(image)
        if not boxes:
            return '', 0.0, []
        boxes_int = [[(int(x), int(y)) for x, y in box] for box in boxes]

        # 对每个文本框进行多级识别
        all_texts: List[str] = []
        all_scores: List[float] = []

        for box in boxes:
            try:
                crop = _crop_quad(image, box)
            except Exception:
                continue

            # Stage 1: ONNX 识别
            if onnx_cfg.get('enabled', True):
                recs = self._rapid_recognize(crop)
                if recs:
                    text, score = recs[0]
                    if text and score >= threshold:
                        all_texts.append(text)
                        all_scores.append(score)
                        continue

            # Stage 2: PaddleOCR-json 识别
            recs = self._paddle_json_recognize(crop)
            if recs:
                text, score = recs[0]
                if text and score >= threshold:
                    all_texts.append(text)
                    all_scores.append(score)
                    continue

            # Stage 3: WebSocket 服务
            ws_cfg = self.cfg.get('websocket_ocr', {}) or {}
            if ws_cfg.get('enabled', True):
                text, score = self._ws_call(crop)
                if text:
                    all_texts.append(text)
                    all_scores.append(score)
                    continue

        if not all_texts:
            return '', 0.0, boxes_int

        # 返回所有识别结果拼接
        return ' '.join(all_texts), min(all_scores), boxes_int