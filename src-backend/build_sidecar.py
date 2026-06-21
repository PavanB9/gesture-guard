"""Freeze the privacy engine and place it in ``src-tauri/resources/engine/``.

- Windows/Linux: a PyInstaller **one-folder** build (``resources/engine/privacy-engine[.exe]``).
- macOS: PyInstaller's **.app BUNDLE** (correct Contents/Frameworks layout) carrying its
  own ``NSCameraUsageDescription`` so the engine can prompt for camera access. Each inner
  Mach-O is ad-hoc signed individually -- NOT ``codesign --deep`` on the .app, which mangles
  the bundled Python framework (the v0.1.3 ``_struct`` failure).

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


def sign_and_dump(appdir: Path) -> None:
    # Sign every Mach-O individually so they load with consistent ad-hoc signatures.
    subprocess.run(
        ["bash", "-c",
         f'find "{appdir}" -type f \\( -name "*.so" -o -name "*.dylib" -o -name "Python" \\) '
         f"-exec codesign --force --sign - {{}} +"],
        check=False,
    )
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(appdir / "Contents" / "MacOS" / "privacy-engine")],
        check=False,
    )
    # Dump the layout into the build log for ground truth if anything misbehaves.
    subprocess.run(
        ["bash", "-c", f'echo "--- engine .app layout ---"; find "{appdir}" -maxdepth 4 | head -100'],
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

    # 2. Freeze with PyInstaller (uses this interpreter == the venv).
    print("Running PyInstaller (takes a few minutes)...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "gesture_guard.spec"],
        cwd=str(HERE),
        check=True,
    )

    # 3. Place into a fresh Tauri resources dir.
    if RESOURCE_DIR.exists():
        shutil.rmtree(RESOURCE_DIR)
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Darwin":
        built = HERE / "dist" / "privacy-engine.app"
        if not built.is_dir():
            raise FileNotFoundError(f"build output not found: {built}")
        dest = RESOURCE_DIR / "privacy-engine.app"
        shutil.copytree(built, dest, symlinks=True)
        sign_and_dump(dest)
        launcher = dest / "Contents" / "MacOS" / "privacy-engine"
    else:
        built = HERE / "dist" / "privacy-engine"
        if not built.is_dir():
            raise FileNotFoundError(f"build output not found: {built}")
        _copy_into(built, RESOURCE_DIR)
        launcher = RESOURCE_DIR / "privacy-engine.exe"

    print(f"\nEngine bundled at: {RESOURCE_DIR}")
    print(f"  launcher: {launcher}")


if __name__ == "__main__":
    main()
