from __future__ import annotations
import cv2
import numpy as np


def _maybe_to_gray(img, cfg):
    if cfg.get('convert_to_gray', True):
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _apply_brightness_contrast(img, cfg):
    brightness = float(cfg.get('亮度因子', cfg.get('brightness', 1.0)))
    contrast = float(cfg.get('对比度因子', cfg.get('contrast', 1.0)))
    if brightness != 1.0 or contrast != 1.0:
        return cv2.convertScaleAbs(img, alpha=contrast, beta=(brightness - 1.0) * 128)
    return img


def _apply_binarization(img_gray, cfg):
    enabled = bool(cfg.get('启用二值化', cfg.get('binarization_enabled', False)))
    if not enabled:
        return img_gray
    method = str(cfg.get('二值化方法', cfg.get('binarization_method', 'adaptive_mean')))
    thr = int(cfg.get('二值化阈值', cfg.get('binarization_threshold', 127)))
    if method == 'simple':
        _, out = cv2.threshold(img_gray, thr, 255, cv2.THRESH_BINARY)
    elif method in ('adaptive_mean', 'cnn_adaptive'):
        out = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
    elif method == 'adaptive_gaussian':
        out = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN, cv2.THRESH_BINARY, 11, 2)
    elif method == 'otsu':
        _, out = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        out = img_gray
    return out


def _apply_morphology(img_gray, cfg):
    if not bool(cfg.get('形态学操作', cfg.get('morphology_enabled', False))):
        return img_gray
    kernel_size = int(cfg.get('核大小', cfg.get('kernel_size', 5)))
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    morph_type = str(cfg.get('形态学操作类型', cfg.get('morphology_type', 'open')))
    if morph_type == 'open':
        return cv2.morphologyEx(img_gray, cv2.MORPH_OPEN, kernel)
    if morph_type == 'close':
        return cv2.morphologyEx(img_gray, cv2.MORPH_CLOSE, kernel)
    if morph_type == 'dilate':
        return cv2.dilate(img_gray, kernel, iterations=1)
    if morph_type == 'erode':
        return cv2.erode(img_gray, kernel, iterations=1)
    return img_gray


def _apply_denoise(img_gray, cfg):
    if not bool(cfg.get('去噪', cfg.get('denoising_enabled', False))):
        return img_gray
    return cv2.fastNlMeansDenoising(img_gray, None, 10, 7, 21)


def _apply_resize(img, cfg):
    if not bool(cfg.get('调整大小', cfg.get('resize_enabled', False))):
        return img
    max_size = int(cfg.get('最大尺寸', cfg.get('max_size', 1024)))
    h, w = img.shape[:2]
    scale = min(1.0, float(max_size) / max(h, w))
    if scale >= 1.0:
        return img
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _apply_border(img, cfg):
    if not bool(cfg.get('添加边框', cfg.get('add_border', False))):
        return img
    size = int(cfg.get('边框大小', cfg.get('border_size', 0)))
    if size <= 0:
        return img
    return cv2.copyMakeBorder(img, size, size, size, size, borderType=cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _apply_crop(img, cfg):
    if not bool(cfg.get('裁剪图像', cfg.get('crop_enabled', False))):
        return img
    rect = cfg.get('裁剪区域', cfg.get('crop_rect'))
    if not rect:
        return img
    # 支持 "(x1, y1) - (x2, y2)" 或 [x1, y1, x2, y2]
    x1 = y1 = x2 = y2 = None
    if isinstance(rect, str) and '-' in rect:
        try:
            left, right = rect.split('-')
            x1y1 = left.strip().strip('()').split(',')
            x2y2 = right.strip().strip('()').split(',')
            x1, y1 = float(x1y1[0]), float(x1y1[1])
            x2, y2 = float(x2y2[0]), float(x2y2[1])
        except Exception:
            return img
    elif isinstance(rect, (list, tuple)) and len(rect) == 4:
        x1, y1, x2, y2 = map(float, rect)
    else:
        return img

    h, w = img.shape[:2]
    # 如果坐标在 0-1 之间，按归一化解析；否则按像素
    def to_px(v, maxv):
        if 0.0 <= v <= 1.0:
            return int(v * maxv)
        return int(v)

    x1 = max(0, min(w - 1, to_px(x1, w)))
    y1 = max(0, min(h - 1, to_px(y1, h)))
    x2 = max(0, min(w, to_px(x2, w)))
    y2 = max(0, min(h, to_px(y2, h)))
    if x2 - x1 <= 1 or y2 - y1 <= 1:
        return img
    return img[y1:y2, x1:x2].copy()


def apply_preprocess(frame, cfg: dict):
    cfg = cfg or {}
    img = frame.copy()
    # brightness/contrast first on BGR
    img = _apply_brightness_contrast(img, cfg)
    # crop/border/resize in BGR domain
    img = _apply_crop(img, cfg)
    img = _apply_border(img, cfg)
    img = _apply_resize(img, cfg)

    # convert to gray if needed
    gray = _maybe_to_gray(img, cfg)

    # binarize/morph/denoise on gray
    gray = _apply_binarization(gray, cfg)
    gray = _apply_morphology(gray, cfg)
    gray = _apply_denoise(gray, cfg)

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


