from __future__ import annotations

import os
from typing import List, Tuple, Optional, Any

import cv2
import numpy as np

from ..core.config import get_resource_path  # 导入路径处理函数

try:
    # RapidOCR is optional; we gate by config
    from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion  # type: ignore
    pass  # RapidOCR 导入成功
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
    """裁剪四边形区域"""
    try:
        if img is None or img.size == 0:
            print("[ERROR] _crop_quad: 输入图像无效")
            return np.array([], dtype=np.uint8)
        
        if not quad or len(quad) != 4:
            print(f"[ERROR] _crop_quad: 四边形坐标无效: {quad}")
            return np.array([], dtype=np.uint8)
        
        # 输入图像和四边形参数
        
        quad_m = _order_pts(quad)
        (tl, tr, br, bl) = quad_m
        
        # 计算宽度和高度
        wA = np.linalg.norm(br - bl)
        wB = np.linalg.norm(tr - tl)
        hA = np.linalg.norm(tr - br)
        hB = np.linalg.norm(tl - bl)
        
        W = int(max(wA, wB))
        H = int(max(hA, hB))
        
        # 确保最小尺寸
        W = max(8, W)  # 最小宽度8像素
        H = max(8, H)  # 最小高度8像素
        
        # 计算目标尺寸
        
        dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(quad_m, dst)
        cropped = cv2.warpPerspective(img, M, (W, H))
        
        # 裁剪完成
        return cropped
        
    except Exception as e:
        print(f"[ERROR] _crop_quad: 裁剪失败: {e}")
        import traceback
        traceback.print_exc()
        return np.array([], dtype=np.uint8)


class OCRPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._rapid_ocr: Optional[Any] = None

    def _init_rapidocr(self):
        """初始化RapidOCR"""
        if self._rapid_ocr is not None:
            return
        
        if RapidOCR is None:
            print("[ERROR] RapidOCR未安装")
            return
        
        try:
            # 获取模型路径
            det_path = get_resource_path('lib/models/custom_det_model/det.onnx')
            rec_path = get_resource_path('lib/models/custom_rec_model/rec.onnx')
            dict_path = get_resource_path('lib/models/dict_custom_chinese_date.txt')
            
            # 检查模型文件是否存在
            if not all(os.path.exists(p) for p in [det_path, rec_path, dict_path]):
                print("[WARNING] 模型文件不完整，将使用默认模型")
                self._rapid_ocr = RapidOCR()
                return
            
            # 配置RapidOCR参数
            onnx_cfg = self.cfg.get('onnx_ocr', {}) or {}
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
                'Rec.model_path': rec_path,
                'Rec.rec_keys_path': dict_path,
                'Det.box_thresh': float(onnx_cfg.get('det_box_thresh', 0.3)),
                'Det.thresh': float(onnx_cfg.get('det_thresh', 0.1)),
                'Det.unclip_ratio': float(onnx_cfg.get('det_unclip_ratio', 2.0)),
                'Rec.rec_img_shape': list(onnx_cfg.get('rec_img_shape', [3, 48, 320])),
            }
            
            self._rapid_ocr = RapidOCR(params=params)
            print("RapidOCR初始化成功")
        except Exception as e:
            print(f"RapidOCR初始化失败: {e}")
            # 使用默认配置
            try:
                self._rapid_ocr = RapidOCR()
                print("使用默认RapidOCR配置")
            except Exception as e2:
                print(f"RapidOCR初始化完全失败: {e2}")
                self._rapid_ocr = None





    def recognize(self, image: np.ndarray) -> Tuple[str, float, List[List[Tuple[int, int]]]]:
        """使用RapidOCR进行完整的OCR识别"""
        self._init_rapidocr()
        if self._rapid_ocr is None:
            print("[ERROR] RapidOCR未初始化")
            return '', 0.0, []
        
        try:
            # 确保图像格式正确
            if image is None or image.size == 0:
                print("[ERROR] 输入图像无效")
                return '', 0.0, []
            
            # 确保图像是BGR格式
            if len(image.shape) == 3 and image.shape[2] == 3:
                ocr_image = image.copy()
            elif len(image.shape) == 2:
                ocr_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                print(f"[ERROR] 不支持的图像格式: shape={image.shape}")
                return '', 0.0, []
            
            # 执行OCR识别
            result = self._rapid_ocr(ocr_image)
            
            if result is None or len(result.boxes) == 0:
                return '', 0.0, []
            
            # 处理识别结果
            boxes = result.boxes
            texts = result.txts
            scores = result.scores
            
            # 转换检测框格式
            boxes_int = []
            for box in boxes:
                if isinstance(box, (list, tuple)) and len(box) == 4:
                    box_coords = [(int(x), int(y)) for x, y in box]
                    boxes_int.append(box_coords)
                elif isinstance(box, np.ndarray) and box.shape == (4, 2):
                    box_coords = [(int(x), int(y)) for x, y in box]
                    boxes_int.append(box_coords)
            
            # 合并所有文本
            combined_text = ' '.join(texts) if texts else ''
            avg_confidence = sum(scores) / len(scores) if scores else 0.0
            
            return combined_text, avg_confidence, boxes_int
            
        except Exception as e:
            print(f"[ERROR] RapidOCR识别失败: {e}")
            import traceback
            traceback.print_exc()
            return '', 0.0, []