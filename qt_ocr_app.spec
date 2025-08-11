# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('paddle')
hiddenimports += collect_submodules('ppocr')
hiddenimports += collect_submodules('tools')


a = Analysis(['app/main.py'],
             pathex=['.'],
             binaries=[],
             datas=[('lib/**', 'lib'),
                    ('app/ui/**', 'app/ui'),
                    ('app/core/**', 'app/core'),
                    ('app/services/**', 'app/services'),
                    ('app_data/**', 'app_data')],
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
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
          upx=True,
           console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='OCRCamera')
