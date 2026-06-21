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

# One-FOLDER build (not one-file): on macOS, one-file unpacks Python.framework
# to a temp dir at runtime, and ad-hoc signing the app re-signs the launcher so
# its signature no longer matches the unpacked framework ("different Team IDs"),
# which macOS refuses to load. One-folder keeps everything signed in place.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="privacy-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Tauri spawns with CREATE_NO_WINDOW, so no console pops up.
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
    name="privacy-engine",
)

import sys as _sys

if _sys.platform == "darwin":
    # On macOS, PyInstaller's BUNDLE produces the correct .app layout (libs under
    # Contents/Frameworks where the bootloader expects them). The .app carries its
    # own NSCameraUsageDescription so the engine can prompt for the camera.
    # build_sidecar.py signs the inner Mach-O individually (NOT `codesign --deep`,
    # which mangles the bundled Python framework).
    app = BUNDLE(
        coll,
        name="privacy-engine.app",
        icon=None,
        bundle_identifier="com.pavanb9.gestureguard.engine",
        info_plist={
            "NSCameraUsageDescription": "Gesture Guard analyzes your webcam locally to "
            "blur the feed when it detects unprofessional gestures. Video never leaves "
            "your device.",
            "LSUIElement": True,
            "CFBundleName": "Gesture Guard Engine",
            "CFBundleDisplayName": "Gesture Guard Engine",
        },
    )
