# -*- mode: python ; coding: utf-8 -*-

import sys ; sys.setrecursionlimit(sys.getrecursionlimit() * 5)

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
# 只包含必要的模块，减少体积
hiddenimports += ['app', 'app.core', 'app.controllers', 'app.services', 'app.ui', 'rapidocr', 'rapidocr.onnxruntime', 'rapidocr.utils', 'rapidocr.main', 'rapidocr.ch_ppocr_det', 'rapidocr.ch_ppocr_rec', 'rapidocr.ch_ppocr_cls']



a = Analysis(['app/main.py'],
             pathex=['.'],
             binaries=[],
             datas=[('lib/**', 'lib'),
                    ('app/ui/**', 'app/ui'),
                    ('app/core/**', 'app/core'),
                    ('app/services/**', 'app/services'),
                    ('app_data/**', 'app_data')] + collect_data_files('rapidocr'),
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=['rapidocr_runtime_hook.py'],
             excludes=['matplotlib', 'numpy.tests', 'PIL.tests', 'paddle.tests', 'ppocr.tests', 'cv2.tests'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='OCRCamera',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=[],
               name='OCRCamera')
