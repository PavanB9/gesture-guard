"""Freeze the privacy engine and drop it into ``src-tauri/binaries/``.

Tauri's ``externalBin`` mechanism expects the binary to be suffixed with the
Rust *target triple* (e.g. ``gesture-guard-x86_64-pc-windows-msvc.exe``), so we
build with PyInstaller and then copy the result under the right name.

    cd src-backend
    .venv/Scripts/python build_sidecar.py        # Windows
    .venv/bin/python build_sidecar.py            # macOS/Linux
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # src-backend
ROOT = HERE.parent  # repo root
TAURI_BIN = ROOT / "src-tauri" / "binaries"


def target_triple() -> str:
    out = subprocess.run(
        ["rustc", "-Vv"], capture_output=True, text=True, check=True
    ).stdout
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not determine rustc host triple (is rustc on PATH?)")


def main() -> None:
    # 1. Make sure the MediaPipe model bundles exist before freezing.
    sys.path.insert(0, str(HERE))
    import fetch_models  # noqa: E402

    fetch_models.fetch()

    # 2. Freeze with PyInstaller (uses this interpreter == the venv).
    print("Running PyInstaller (this takes a few minutes)...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "gesture_guard.spec"],
        cwd=str(HERE),
        check=True,
    )

    # 3. Copy to the target-triple name Tauri expects.
    #    NOTE: the sidecar base name ("privacy-engine") must differ from the
    #    Tauri app/Cargo package name ("gesture-guard"). Tauri copies externalBin
    #    into the target dir with the triple stripped, so a matching name would
    #    collide with the app binary and make the app spawn itself recursively.
    triple = target_triple()
    ext = ".exe" if platform.system() == "Windows" else ""
    built = HERE / "dist" / f"privacy-engine{ext}"
    if not built.exists():
        raise FileNotFoundError(f"build output not found: {built}")

    TAURI_BIN.mkdir(parents=True, exist_ok=True)
    # Drop any stale sidecar binaries from earlier builds/names.
    for old in TAURI_BIN.glob("gesture-guard-*"):
        old.unlink()
    dest = TAURI_BIN / f"privacy-engine-{triple}{ext}"
    shutil.copy2(built, dest)
    print(f"\nSidecar ready: {dest}")
    print(f"  size: {dest.stat().st_size / 1_048_576:.1f} MiB")


if __name__ == "__main__":
    main()
