"""Camera-free smoke test for CI and quick local verification.

Exercises the whole detection/gating pipeline on synthetic frames so it can run
on a headless machine without a webcam:

    cd src-backend
    .venv/Scripts/python -m app.selftest
"""

from __future__ import annotations

import sys

import numpy as np

from .config import GuardConfig
from .detectors import FaceHandsAnalyzer, TemporalGate
from . import utils


def _check(name: str, cond: bool) -> None:
    print(f"  [{'OK' if cond else 'FAIL'}] {name}")
    if not cond:
        raise SystemExit(f"selftest failed: {name}")


def main() -> int:
    print("Gesture Guard self-test (no camera)")

    # 1. Config + derived thresholds + partial validation.
    cfg = GuardConfig()
    _check("default sensitivity 0.5", abs(cfg.sensitivity - 0.5) < 1e-9)
    hi = GuardConfig(sensitivity=1.0).yawn_mar_threshold()
    lo = GuardConfig(sensitivity=0.0).yawn_mar_threshold()
    _check("higher sensitivity lowers yawn threshold", hi < lo)
    _check(
        "touch ratio grows with sensitivity",
        GuardConfig(sensitivity=1.0).touch_distance_ratio()
        > GuardConfig(sensitivity=0.0).touch_distance_ratio(),
    )

    # 2. Temporal gate: needs to hold before firing, lingers on release.
    gate = TemporalGate(on_time=1.0, off_time=0.5)
    _check("gate off initially", gate.update(True, 0.0) is False)
    _check("gate still off before hold met", gate.update(True, 0.9) is False)
    _check("gate fires after hold", gate.update(True, 1.1) is True)
    _check("gate latches during release window", gate.update(False, 1.3) is True)
    _check("gate releases after off_time", gate.update(False, 1.8) is False)

    # 3. MediaPipe graphs load and analyze() runs on synthetic frames.
    analyzer = FaceHandsAnalyzer()
    try:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        m1 = analyzer.analyze(blank, 640, 480)
        _check("no face on blank frame", m1.face_found is False and m1.face_count == 0)
        noise = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        analyzer.analyze(noise, 640, 480)  # must not raise
        _check("analyze handles noise frame", True)
    finally:
        analyzer.close()

    # 4. Frame helpers produce valid JPEGs / shapes.
    brb = utils.draw_brb(960, 540)
    _check("BRB frame shape", brb.shape == (540, 960, 3))
    jpeg = utils.encode_jpeg(brb)
    _check("JPEG encodes", jpeg is not None and jpeg[:2] == b"\xff\xd8")
    blurred = utils.heavy_blur(noise)
    _check("blur preserves shape", blurred.shape == noise.shape)

    # 5. Virtual-camera dependency present (phase 2). We do not open a device
    #    here (that needs a system driver), just verify the module + format.
    import pyvirtualcam

    _check("pyvirtualcam available", hasattr(pyvirtualcam.PixelFormat, "BGR"))

    # 6. End-to-end frame processing (browser sends a JPEG -> safe JPEG back).
    from .privacy_engine import PrivacyEngine

    eng = PrivacyEngine()
    eng.start()
    try:
        in_jpeg = utils.encode_jpeg(np.zeros((480, 640, 3), dtype=np.uint8))
        out_jpeg, st = eng.process_jpeg(in_jpeg)
        _check("process_jpeg returns a JPEG", out_jpeg is not None and out_jpeg[:2] == b"\xff\xd8")
        _check("process_jpeg returns status", isinstance(st, dict) and "guard_active" in st)
    finally:
        eng.stop()

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
