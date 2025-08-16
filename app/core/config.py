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


def get_user_data_path(relative_path=''):
    """获取用户数据目录的绝对路径，用于保存用户生成的文件"""
    if getattr(sys, 'frozen', False):
        # 打包后使用用户文档目录
        import platform
        if platform.system() == 'Windows':
            user_data_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'OCRCamera')
        else:
            user_data_dir = os.path.join(os.path.expanduser('~'), '.ocrcamera')
    else:
        # 开发环境使用项目目录下的app_data
        user_data_dir = DATA_DIR
    
    os.makedirs(user_data_dir, exist_ok=True)
    
    if relative_path:
        full_path = os.path.join(user_data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path
    
    return user_data_dir


DEFAULT_CONFIG = {
    'camera': {
        'device_index': 0,
        'width': 1280,
        'height': 720,
        'auto_capture': True,
        'capture_interval_ms': 1000,
        'roi_norm': None
    },
    'onnx_ocr': {
        'enabled': True,
        'image_path': get_resource_path('test.jpg'),
        'det_onnx': get_resource_path('lib/models/custom_det_model/det.onnx'),
        'rec_onnx': get_resource_path('lib/models/custom_rec_model/rec.onnx'),
        'dict_path': get_resource_path('lib/models/dict_custom_chinese_date.txt'),
        'vis_out_dir': get_user_data_path('out'),
        'rec_img_shape': [3, 48, 320],
        'det_box_thresh': 0.3,
        'det_thresh': 0.1,
        'det_unclip_ratio': 2.0,
        'fallback_threshold': 0.95
    },
    'ui': {
        'theme': 'auto',   # 'auto' | 'light' | 'dark'
        'accent': '#0078d7'
    },
    'preprocess': {
        'enable_preprocess': True,
        'convert_to_gray': True,
        'brightness': 1.0,
        'contrast': 1.0,
        'denoising_enabled': True
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
        # Ensure basic structure exists
        cfg.setdefault('camera', DEFAULT_CONFIG['camera'])
        cfg.setdefault('onnx_ocr', DEFAULT_CONFIG['onnx_ocr'])
        cfg.setdefault('ui', DEFAULT_CONFIG['ui'])
        cfg.setdefault('preprocess', DEFAULT_CONFIG['preprocess'])
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


