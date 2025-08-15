from __future__ import annotations
import json
import os
import sys
from typing import Tuple
from .db import get_session, AppConfig


# Project root -> qt_ocr_app/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'app_data')
os.makedirs(DATA_DIR, exist_ok=True)


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包后的路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的路径
        base_path = sys._MEIPASS
    else:
        # 开发环境路径
        base_path = PROJECT_ROOT
    
    return os.path.join(base_path, relative_path)


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
        'paddleocr_json_exe': get_resource_path('lib/PaddleOCR-json.exe'),
        'paddleocr_models_path': get_resource_path('lib/models'),

        # Legacy fields kept for backward compatibility (unused now)
        'det_model_path': './inference/det_model',
        'rec_model_path': './inference/rec_model',
        'dict_path': './ppocr/utils/dict/custom_chinese_date_dict.txt',

        'snapshot_dir': get_resource_path('snapshots'),

        # Optional custom Paddle models (Python pipeline), not used by PaddleOCR-json
        'custom_det_model': get_resource_path('lib/models/custom_det_model'),
        'custom_rec_model': get_resource_path('lib/models/custom_rec_model'),
    },
    'onnx_ocr': {
        'enabled': True,
        'image_path': get_resource_path('test.jpg'),
        'det_onnx': get_resource_path('lib/models/custom_det_model/det.onnx'),
        'rec_onnx': get_resource_path('lib/models/custom_rec_model/rec.onnx'),
        'dict_path': get_resource_path('lib/models/dict_custom_chinese_date.txt'),
        'vis_out_dir': get_resource_path('out'),
        'rec_img_shape': [3, 48, 320],
        'det_box_thresh': 0.3,
        'det_thresh': 0.1,
        'det_unclip_ratio': 2.0,
        'fallback_threshold': 0.95
    },
    'websocket_ocr': {
        'url': 'wss://olmocr.allen.ai/api/ws',
        'prompt': '请只提取图中的生产日期，并按格式返回：生产日期：YYYY/MM/DD 合格。不要返回其他内容。',
        'chunk_size': 65536,
        'enabled': True
    },
    # Optional PaddleOCR-json arguments (passed to engine)
    'paddleocr_json_args': {
        # 'config_path': '',  # e.g. os.path.join(PROJECT_ROOT, 'lib', 'models', 'config.json')
        # 'models_path': '',  # override models root; by default we use paths.paddleocr_models_path
        'ensure_ascii': True,
        'det': True,
        'cls': False,
        'use_angle_cls': False,
        'enable_mkldnn': True,
        'limit_side_len': 960,
    },
    'ui': {
        'theme': 'auto',   # 'auto' | 'light' | 'dark'
        'accent': '#0078d7'
    },
    'preprocess': {
        'enable_preprocess': True,
        'convert_to_gray': True,

        'binarization_enabled': False,
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


