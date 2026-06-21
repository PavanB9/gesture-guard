"""Freeze the privacy engine and place it in ``src-tauri/resources/engine/``.

- Windows/Linux: a PyInstaller **one-folder** build (``resources/engine/privacy-engine[.exe]``).
- macOS: the same one-folder build placed inside a **thin hand-built .app** at
  ``Contents/MacOS/`` plus an ``Info.plist`` carrying ``NSCameraUsageDescription``.
  This keeps PyInstaller's exact working layout (no BUNDLE rearranging / framework
  symlinks, which corrupted the internals) while giving the engine its own camera
  usage description so macOS prompts for permission instead of silently denying it.
  Every Mach-O is ad-hoc signed so signatures stay consistent in place.

    cd src-backend
    .venv/Scripts/python build_sidecar.py        # Windows
    .venv/bin/python build_sidecar.py            # macOS
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # src-backend
ROOT = HERE.parent  # repo root
RESOURCE_DIR = ROOT / "src-tauri" / "resources" / "engine"

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>privacy-engine</string>
  <key>CFBundleIdentifier</key><string>com.pavanb9.gestureguard.engine</string>
  <key>CFBundleName</key><string>Gesture Guard Engine</string>
  <key>CFBundleDisplayName</key><string>Gesture Guard Engine</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSCameraUsageDescription</key><string>Gesture Guard analyzes your webcam locally to blur the feed when it detects unprofessional gestures. Video never leaves your device.</string>
</dict>
</plist>
"""


def sign_macos_app(appdir: Path) -> None:
    print(f"Ad-hoc signing {appdir.name}...")
    # 1. Sign every Mach-O so they load with consistent ad-hoc signatures.
    subprocess.run(
        ["bash", "-c",
         f'find "{appdir}" -type f \\( -name "*.so" -o -name "*.dylib" -o -name "Python" \\) '
         f"-exec codesign --force --sign - {{}} +"],
        check=False,
    )
    # 2. Sign the launcher and seal the bundle so its Info.plist/TCC identity is valid.
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(appdir / "Contents" / "MacOS" / "privacy-engine")],
        check=False,
    )
    subprocess.run(["codesign", "--force", "--sign", "-", str(appdir)], check=False)


def _copy_into(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        target = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target)


def main() -> None:
    # 1. Make sure the MediaPipe model bundles exist before freezing.
    sys.path.insert(0, str(HERE))
    import fetch_models  # noqa: E402

    fetch_models.fetch()

    # 2. Freeze with PyInstaller (one-folder; uses this interpreter == the venv).
    print("Running PyInstaller (one-folder; takes a few minutes)...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "gesture_guard.spec"],
        cwd=str(HERE),
        check=True,
    )

    built = HERE / "dist" / "privacy-engine"
    if not built.is_dir():
        raise FileNotFoundError(f"build output not found: {built}")

    # 3. Place into a fresh Tauri resources dir.
    if RESOURCE_DIR.exists():
        shutil.rmtree(RESOURCE_DIR)
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Darwin":
        appdir = RESOURCE_DIR / "privacy-engine.app"
        _copy_into(built, appdir / "Contents" / "MacOS")
        (appdir / "Contents" / "Info.plist").write_text(INFO_PLIST)
        sign_macos_app(appdir)
        launcher = appdir / "Contents" / "MacOS" / "privacy-engine"
    else:
        _copy_into(built, RESOURCE_DIR)
        launcher = RESOURCE_DIR / "privacy-engine.exe"

    print(f"\nEngine bundled at: {RESOURCE_DIR}")
    print(f"  launcher: {launcher}")


if __name__ == "__main__":
    main()
