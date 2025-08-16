# -*- mode: python ; coding: utf-8 -*-

import sys ; sys.setrecursionlimit(sys.getrecursionlimit() * 5)

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
# 只包含必要的模块，减少体积
hiddenimports += [
    'app', 'app.core', 'app.controllers', 'app.services', 'app.ui', 'app.utils',
    'rapidocr', 'rapidocr.onnxruntime', 'rapidocr.utils', 'rapidocr.main',
    'sqlalchemy.sql.default_comparator',
    'jaraco.text', 'jaraco', 'jaraco.functools', 'jaraco.collections',
    'pkg_resources', 'pkg_resources._vendor', 'pkg_resources.extern',
    'setuptools', 'setuptools._vendor', 'setuptools.extern'
]



a = Analysis(['app/main.py'],
             pathex=['.'],
             binaries=[],
             datas=[
                 ('lib/models', 'lib/models'),
             ] + collect_data_files('rapidocr'),
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=['rapidocr_runtime_hook.py'],
             excludes=[
                 'matplotlib', 'tkinter', 'unittest', 'test', 'tests',
                 'numpy.tests', 'PIL.tests', 'cv2.tests',
                 'paddle', 'paddleocr', 'ppocr',
                 'torch', 'tensorflow', 'sklearn',
                 'jupyter', 'IPython', 'notebook',
                 'sphinx', 'docutils',
                 'websocket', 'websocket_client'
             ],
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
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=[],
               name='OCRCamera')
