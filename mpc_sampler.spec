# -*- mode: python ; coding: utf-8 -*-
# MPC Sampler - PyInstaller spec (miniaudio版: ffmpeg不要)
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        *collect_dynamic_libs('miniaudio'),
    ],
    datas=[
        *collect_data_files('pygame'),
        *collect_data_files('miniaudio'),
    ],
    hiddenimports=[
        'pygame',
        'pygame.mixer',
        'pygame.sndarray',
        'miniaudio',
        'numpy',
        'numpy.core._multiarray_umath',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'json',
        'os',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pydub',  # ffmpeg依存のため除外
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
