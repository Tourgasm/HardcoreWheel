# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for modularized Spartan Wheel Server (import-safe)

# NOTE: PyInstaller provides SPECPATH (directory containing this .spec).
# Using SPECPATH avoids relying on __file__ (not always defined in spec exec env).

a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[
        'wheel_config',
        'wheel_logic',
        'wheel_server',
        'wheel_gui',
        'pytchat',
        'socketio',
        'websockets',
        'flask',
        'flask_cors',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wheel_server_python',
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
