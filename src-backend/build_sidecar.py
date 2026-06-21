"""Freeze the privacy engine (one-folder) into ``src-tauri/resources/engine/``.

The folder is bundled by Tauri as a resource and spawned at runtime. On macOS,
every Mach-O in the folder is ad-hoc signed so the launcher and everything it
dlopen's (MediaPipe, OpenCV, the Python framework, ...) share one signature —
a one-file build would unpack a mismatched Python.framework at runtime, which
Apple Silicon refuses to load ("different Team IDs").

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
    script = (
        f'find "{folder}" -type f \\( -name "*.so" -o -name "*.dylib" -o -name "Python" \\) '
        f"-exec codesign --force --sign - {{}} + ; "
        f'codesign --force --sign - "{folder}/privacy-engine"'
    )
    subprocess.run(["bash", "-c", script], check=False)


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

    built_dir = HERE / "dist" / "privacy-engine"
    if not built_dir.is_dir():
        raise FileNotFoundError(f"build output not found: {built_dir}")

    # 3. Place the whole folder into the Tauri resources dir.
    if RESOURCE_DIR.exists():
        shutil.rmtree(RESOURCE_DIR)
    RESOURCE_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built_dir, RESOURCE_DIR)

    # 4. Sign in place (macOS only).
    if platform.system() == "Darwin":
        adhoc_sign_macos(RESOURCE_DIR)

    exe = "privacy-engine.exe" if platform.system() == "Windows" else "privacy-engine"
    print(f"\nEngine bundled at: {RESOURCE_DIR}")
    print(f"  launcher: {RESOURCE_DIR / exe}")


if __name__ == "__main__":
    main()
