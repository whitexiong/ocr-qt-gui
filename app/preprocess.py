from __future__ import annotations
import cv2
import numpy as np


def apply_preprocess(frame, cfg: dict):
    img = frame.copy()
    # brightness/contrast
    brightness = float(cfg.get('brightness', 1.0))
    contrast = float(cfg.get('contrast', 1.0))
    if brightness != 1.0 or contrast != 1.0:
        img = cv2.convertScaleAbs(img, alpha=contrast, beta=(brightness-1.0)*128)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if cfg.get('binarization_enabled', False):
        method = cfg.get('binarization_method', 'adaptive_mean')
        thr = int(cfg.get('binarization_threshold', 127))
        if method == 'simple':
            _, img = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        elif method == 'adaptive_mean':
            img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
        elif method == 'adaptive_gaussian':
            img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        elif method == 'otsu':
            _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    else:
        img = gray

    if cfg.get('morphology_enabled', False):
        kernel_size = int(cfg.get('kernel_size', 5))
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        morph_type = cfg.get('morphology_type', 'open')
        if morph_type == 'open':
            img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        elif morph_type == 'close':
            img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
        elif morph_type == 'dilate':
            img = cv2.dilate(img, kernel, iterations=1)
        elif morph_type == 'erode':
            img = cv2.erode(img, kernel, iterations=1)

    if cfg.get('denoising_enabled', False):
        img = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)

    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
