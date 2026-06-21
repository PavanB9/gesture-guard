"""Frame helpers and cross-platform resource resolution.

All path handling goes through :func:`resource_path` which uses ``pathlib`` so
it behaves identically whether the engine runs from source on Windows/macOS or
from a PyInstaller one-file bundle (where data lives under ``sys._MEIPASS``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def resource_path(*parts: str) -> Path:
    """Resolve a bundled resource path across dev and every frozen layout.

    PyInstaller places data differently for one-file, one-folder, and macOS
    ``.app`` BUNDLE builds, so we search a few candidate roots (joins use
    ``pathlib`` for cross-platform safety) and return the first that exists.
    """
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        candidates += [Path(base) / "app", Path(base)]
    # Dev (running from source): this file lives in .../app/utils.py
    candidates.append(Path(__file__).resolve().parent)
    for root in candidates:
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
    return candidates[0].joinpath(*parts)


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> Optional[bytes]:
    """Encode a BGR frame to JPEG bytes for streaming over the WebSocket."""
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return buf.tobytes()


def heavy_blur(frame: np.ndarray) -> np.ndarray:
    """Return a heavily obscured copy of the frame (frosted/pixelated blur)."""
    h, w = frame.shape[:2]
    # Downscale hard then back up to destroy detail, then Gaussian to soften.
    small = cv2.resize(
        frame, (max(1, w // 14), max(1, h // 14)), interpolation=cv2.INTER_LINEAR
    )
    up = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    k = max(31, (w // 18) | 1)  # force odd kernel size
    return cv2.GaussianBlur(up, (k, k), 0)


def _put_centered(
    img: np.ndarray,
    text: str,
    cy: int,
    scale: float,
    color: tuple,
    thickness: int,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x = (img.shape[1] - tw) // 2
    cv2.putText(img, text, (x, cy + th // 2), font, scale, color, thickness, cv2.LINE_AA)


def draw_brb(width: int, height: int, subtitle: str = "") -> np.ndarray:
    """Render a clean dark 'Be Right Back' screen (drawn, never a file)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (16, 12, 10)  # near-black, faint warm tint (BGR)
    base = min(width, height)
    _put_centered(img, "BE RIGHT BACK", int(height * 0.44), base / 420.0, (235, 235, 235), 3)
    _put_centered(
        img, "Privacy guard active", int(height * 0.56), base / 900.0, (90, 200, 255), 1
    )
    if subtitle:
        _put_centered(img, subtitle, int(height * 0.64), base / 1100.0, (120, 120, 130), 1)
    return img


def draw_message(width: int, height: int, text: str) -> np.ndarray:
    """A generic dark placeholder frame (e.g. camera errors / test mode)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (20, 18, 18)
    _put_centered(img, text, height // 2, min(width, height) / 700.0, (160, 160, 170), 2)
    return img
