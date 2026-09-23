# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/Jadyev wok/Mirracle test macbookto/MACK TO TEST/miracle_bridge/miracle_bridge/miracle_bridge_agent.py'],
    pathex=['E:/Jadyev wok/Mirracle test macbookto/MACK TO TEST/miracle_bridge/backend'],
    binaries=[],
    datas=[],
    hiddenimports=['core', 'core.config', 'core.utils', 'dbf_handler', 'ai_memory', 'routers', 'routers.vouchers', 'dbfread', 'dbf', 'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageEnhance', 'winreg', 'pypdf', 'requests', 'sqlite3', 'openpyxl', 'multipart', 'python_multipart'],
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
    name='MiracleBridge',
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
