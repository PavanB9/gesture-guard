"""Validation trace (spec requirement #4).

Opens the default camera and prints the live NumPy-derived metrics so the
mouth-aspect-ratio, hand-to-face proximity and face-count math can be verified
against real frames before the UI is wired up.

    cd src-backend
    .venv/Scripts/python -m app.checks        # Windows
    .venv/bin/python -m app.checks            # macOS/Linux

Yawn  -> `mar` climbs above the threshold.
Touch -> `touch_ratio` drops below the threshold when a hand nears the face.
Intrusion -> `faces` becomes 2 when a second person enters frame.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import platform
import time

import cv2

from .config import GuardConfig
from .detectors import FaceHandsAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="Live metrics validation trace")
    parser.add_argument(
        "--camera", type=int, default=0, help="OpenCV camera index (default 0)"
    )
    index = parser.parse_args().camera
    cfg = GuardConfig()
    cap = (
        cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if platform.system() == "Windows"
        else cv2.VideoCapture(index)
    )
    if not cap.isOpened():
        print(f"ERROR: could not open camera {index}")
        return

    analyzer = FaceHandsAnalyzer()
    print("Validation trace running (Ctrl+C to stop)...")
    print(f"  yawn MAR threshold     = {cfg.yawn_mar_threshold():.3f}")
    print(f"  touch distance ratio   = {cfg.touch_distance_ratio():.3f}")
    last = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            scale = 640.0 / w if w > 640 else 1.0
            small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1.0 else frame
            sh, sw = small.shape[:2]
            m = analyzer.analyze(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), sw, sh)
            now = time.time()
            if now - last >= 0.4:
                last = now
                touch = "inf" if m.touch_ratio == float("inf") else f"{m.touch_ratio:.3f}"
                print(
                    f"faces={m.face_count} face={int(m.face_found)} "
                    f"mar={m.mar:.3f} | hand={int(m.hand_found)} touch_ratio={touch}"
                )
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        cap.release()
        analyzer.close()


if __name__ == "__main__":
    main()
