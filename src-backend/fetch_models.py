"""Download the MediaPipe Tasks model bundles into ``app/assets/models/``.

MediaPipe's modern Tasks API loads detectors from ``.task`` model files instead
of bundling them inside the wheel. Run this once during setup/build (it needs
network access, exactly like ``pip install`` does). After the files are present
the engine runs **fully offline** — they are baked into the PyInstaller sidecar
and never fetched again at runtime.

    cd src-backend
    .venv/Scripts/python fetch_models.py            # Windows
    .venv/bin/python fetch_models.py                # macOS/Linux
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODELS = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    ),
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/1/hand_landmarker.task"
    ),
}


def models_dir() -> Path:
    return Path(__file__).resolve().parent / "app" / "assets" / "models"


def fetch(force: bool = False) -> None:
    target = models_dir()
    target.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        dest = target / name
        if dest.exists() and not force:
            print(f"[skip] {name} ({dest.stat().st_size:,} bytes)")
            continue
        print(f"[get ] {name} <- {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"[done] {name} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    fetch(force="--force" in sys.argv)
