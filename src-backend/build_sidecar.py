"""Freeze the privacy engine and place it in ``src-tauri/resources/engine/``.

- Windows/Linux: a PyInstaller **one-folder** build (``resources/engine/privacy-engine[.exe]``).
- macOS: a one-folder build wrapped in a **.app bundle** so the engine carries its
  own ``NSCameraUsageDescription`` and can prompt for camera access (a bare helper
  in Resources/ is denied silently). The whole .app is ad-hoc signed so its libs
  share one signature (one-file would unpack a mismatched framework at runtime).

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


def adhoc_sign_macos(app_path: Path) -> None:
    print(f"Ad-hoc signing {app_path.name}...")
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)], check=False)


def main() -> None:
    # 1. Make sure the MediaPipe model bundles exist before freezing.
    sys.path.insert(0, str(HERE))
    import fetch_models  # noqa: E402

    fetch_models.fetch()

    # 2. Freeze with PyInstaller (uses this interpreter == the venv).
    print("Running PyInstaller (one-folder; takes a few minutes)...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "gesture_guard.spec"],
        cwd=str(HERE),
        check=True,
    )

    is_mac = platform.system() == "Darwin"
    built = HERE / "dist" / ("privacy-engine.app" if is_mac else "privacy-engine")
    if not built.exists():
        raise FileNotFoundError(f"build output not found: {built}")

    # 3. Place into a fresh Tauri resources dir.
    if RESOURCE_DIR.exists():
        shutil.rmtree(RESOURCE_DIR)
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)

    if is_mac:
        dest = RESOURCE_DIR / "privacy-engine.app"
        shutil.copytree(built, dest, symlinks=True)
        adhoc_sign_macos(dest)
        launcher = dest / "Contents" / "MacOS" / "privacy-engine"
    else:
        shutil.copytree(built, RESOURCE_DIR, dirs_exist_ok=True)
        launcher = RESOURCE_DIR / "privacy-engine.exe"

    print(f"\nEngine bundled at: {RESOURCE_DIR}")
    print(f"  launcher: {launcher}")


if __name__ == "__main__":
    main()
