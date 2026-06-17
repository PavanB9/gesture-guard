# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: freeze the privacy engine into a single-file sidecar.
#
# MediaPipe and OpenCV ship binary graph/model data that PyInstaller does not
# pick up automatically, so we `collect_all` them. Our own model bundles and
# assets (app/assets/**) are added as data so `utils.resource_path` resolves
# them under sys._MEIPASS at runtime.

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

for pkg in ("mediapipe", "cv2", "pyvirtualcam"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Uvicorn / websockets load protocol implementations dynamically.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("websockets")

# Our local model files + any other assets.
datas += [("app/assets", "app/assets")]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="privacy-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # Tauri spawns with CREATE_NO_WINDOW, so no console pops up.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
