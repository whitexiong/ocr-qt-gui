# -*- coding: utf-8 -*-
"""
RapidOCR 运行时钩子，用于修复打包后的路径问题
"""

import os
import sys
from pathlib import Path

def _fix_rapidocr_paths():
    """修复 RapidOCR 的路径问题"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        base_path = sys._MEIPASS
        rapidocr_path = os.path.join(base_path, 'rapidocr')
        
        # 设置 RapidOCR 的环境变量
        os.environ['RAPIDOCR_HOME'] = rapidocr_path
        
        # 修复默认模型路径
        default_models_path = os.path.join(rapidocr_path, 'default_models.yaml')
        if os.path.exists(default_models_path):
            os.environ['RAPIDOCR_DEFAULT_MODELS'] = default_models_path

# 在模块导入时执行
_fix_rapidocr_paths()