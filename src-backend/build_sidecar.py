"""Freeze the privacy engine (one-folder) into ``src-tauri/resources/engine/``.

The engine no longer opens the camera, so no macOS .app wrapper / camera
entitlement is needed -- this plain one-folder layout runs reliably on both
Windows and macOS. On macOS every Mach-O is ad-hoc signed individually so the
libraries load with consistent signatures.

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


def adhoc_sign_macos(folder: Path) -> None:
    print("Ad-hoc signing engine Mach-O files for macOS...")
    subprocess.run(
        ["bash", "-c",
         f'find "{folder}" -type f \\( -name "*.so" -o -name "*.dylib" -o -name "Python" \\) '
         f"-exec codesign --force --sign - {{}} + ; "
         f'codesign --force --sign - "{folder}/privacy-engine"'],
        check=False,
    )


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

    # 3. Place the folder contents into a fresh Tauri resources dir.
    if RESOURCE_DIR.exists():
        shutil.rmtree(RESOURCE_DIR)
    _copy_into(built, RESOURCE_DIR)

    if platform.system() == "Darwin":
        adhoc_sign_macos(RESOURCE_DIR)
        launcher = RESOURCE_DIR / "privacy-engine"
    else:
        launcher = RESOURCE_DIR / "privacy-engine.exe"

    print(f"\nEngine bundled at: {RESOURCE_DIR}")
    print(f"  launcher: {launcher}")


if __name__ == "__main__":
    main()
