from __future__ import annotations
import json
import os
from typing import Tuple
from .db import get_session, AppConfig


# Project root -> qt_ocr_app/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'app_data')
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    'camera': {
        'device_index': 0,
        'width': 1280,
        'height': 720,
        'auto_capture': True,
        'capture_interval_ms': 1000,
        'roi_norm': None
    },
    'sensor': {
        'enabled': False,
        'type': 'serial',
        'port': 'COM3',
        'baudrate': 9600
    },
    'paths': {
        # PaddleOCR-json exe and models (defaults point to project lib/)
        'paddleocr_json_exe': os.path.abspath(os.path.join(PROJECT_ROOT, 'lib', 'PaddleOCR-json.exe')),
        'paddleocr_models_path': os.path.abspath(os.path.join(PROJECT_ROOT, 'lib', 'models')),

        # Legacy fields kept for backward compatibility (unused now)
        'det_model_path': './inference/det_model',
        'rec_model_path': './inference/rec_model',
        'dict_path': './ppocr/utils/dict/custom_chinese_date_dict.txt',

        'snapshot_dir': os.path.abspath(os.path.join(PROJECT_ROOT, 'snapshots'))
    },
    'ui': {
        'theme': 'auto',   # 'auto' | 'light' | 'dark'
        'accent': '#0078d7'
    },
    'preprocess': {
        'enable_preprocess': True,
        'convert_to_gray': True,

        'binarization_enabled': True,
        'binarization_method': 'adaptive_mean',
        'binarization_threshold': 127,

        'morphology_enabled': True,
        'morphology_type': 'open',
        'kernel_size': 5,

        'denoising_enabled': True,

        'brightness': 1.0,
        'contrast': 1.0,

        'resize_enabled': False,
        'max_size': 1024,

        'add_border': False,
        'border_size': 0,

        'crop_enabled': False,
        'crop_rect': None  # [x1, y1, x2, y2]; supports pixels (>1) or normalized (0-1)
    },
}


def load_config():
    session = get_session()
    try:
        row = session.get(AppConfig, 'app_config')
        if row is None:
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        cfg = json.loads(row.value)
        # Validate and auto-fix critical paths if they are invalid
        changed = False
        try:
            paths = cfg.setdefault('paths', {})
            default_exe = DEFAULT_CONFIG['paths']['paddleocr_json_exe']
            default_models = DEFAULT_CONFIG['paths']['paddleocr_models_path']

            exe_path = paths.get('paddleocr_json_exe')
            if not exe_path or not os.path.isfile(exe_path):
                if os.path.isfile(default_exe):
                    paths['paddleocr_json_exe'] = default_exe
                    changed = True

            models_path = paths.get('paddleocr_models_path')
            if not models_path or not os.path.isdir(models_path):
                if os.path.isdir(default_models):
                    paths['paddleocr_models_path'] = default_models
                    changed = True
        except Exception:
            # In case of any unexpected structure, fall back to defaults
            cfg['paths'] = {
                'paddleocr_json_exe': DEFAULT_CONFIG['paths']['paddleocr_json_exe'],
                'paddleocr_models_path': DEFAULT_CONFIG['paths']['paddleocr_models_path'],
                'det_model_path': DEFAULT_CONFIG['paths']['det_model_path'],
                'rec_model_path': DEFAULT_CONFIG['paths']['rec_model_path'],
                'dict_path': DEFAULT_CONFIG['paths']['dict_path'],
                'snapshot_dir': DEFAULT_CONFIG['paths']['snapshot_dir'],
            }
            changed = True

        if changed:
            save_config(cfg)
        return cfg
    finally:
        session.close()


def save_config(cfg: dict):
    session = get_session()
    try:
        row = session.get(AppConfig, 'app_config')
        if row is None:
            from json import dumps as json_dumps
            row = AppConfig(key='app_config', value=json_dumps(cfg, ensure_ascii=False))
            session.add(row)
        else:
            from json import dumps as json_dumps
            row.value = json_dumps(cfg, ensure_ascii=False)
        session.commit()
    finally:
        session.close()


