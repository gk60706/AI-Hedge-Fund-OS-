# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the local A-share workbench."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "market_app" / "static"), "market_app/static"),
]
datas += collect_data_files("baostock")

hiddenimports = [
    "market_app",
    "market_app.config",
    "market_app.indicators",
    "market_app.data_sources",
    "market_app.analytics",
    "market_app.signal_quality",
    "market_app.signal_ledger",
    "market_app.costs",
    "market_app.server",
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
    "requests",
    "baostock",
]
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("baostock")
hiddenimports += collect_submodules("webview")

a = Analysis(
    [str(ROOT / "market_app" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter.test",
        "pytest",
        "IPython",
        "notebook",
        "matplotlib",
        "torch",
        "tensorflow",
        "sklearn",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AStockWorkbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AStockWorkbench",
)
