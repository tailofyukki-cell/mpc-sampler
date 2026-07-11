# -*- mode: python ; coding: utf-8 -*-
# MPC Sampler - PyInstaller spec
# 依存: pygame + PyQt5 のみ（ffmpeg/miniaudio/pydub 不要）
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        *collect_dynamic_libs('pygame'),
    ],
    datas=[
        *collect_data_files('pygame'),
    ],
    hiddenimports=[
        'pygame',
        'pygame.mixer',
        'pygame.time',
        'pygame.display',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'json',
        'os',
        'threading',
        'wave',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pydub',
        'miniaudio',
        'cffi',
        '_cffi_backend',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MPCSampler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
