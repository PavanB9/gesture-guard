"""MediaPipe-backed facial/hand analysis and temporal violation gating.

Uses the MediaPipe **Tasks** API (Face Landmarker + Hand Landmarker, loaded from
local ``.task`` bundles fetched once by ``fetch_models.py``). The 478-point face
mesh and 21-point hand landmark indices match the classic solutions, so the
geometry below is unchanged. Each processed frame is reduced to scale-invariant
NumPy metrics:

* ``mar``         - mouth aspect ratio (yawn signal)
* ``touch_ratio`` - nearest hand point to nose/eyes, as a fraction of face width
* ``face_count``  - number of faces (background-intrusion signal)

Temporal gating (hold time + hysteresis) lives in :class:`TemporalGate` so the
raw geometry stays stateless and verifiable via ``python -m app.checks``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

from . import utils

_VIDEO = vision.RunningMode.VIDEO

# --- Face mesh landmark indices (478-point refined mesh) ----------------------
LIP_VERTICAL_PAIRS = [(13, 14), (81, 178), (311, 402)]
MOUTH_CORNERS = (78, 308)  # inner mouth corners -> mouth width
NOSE_TIP = 1
LEFT_EYE = (33, 133)  # outer / inner corner -> eye centre
RIGHT_EYE = (362, 263)
FACE_LEFT = 234  # cheek edges -> face width (scale reference)
FACE_RIGHT = 454
FOREHEAD = 10
CHIN = 152


@dataclass
class FrameMetrics:
    face_found: bool = False
    face_count: int = 0
    mar: float = 0.0
    hand_found: bool = False
    touch_ratio: float = float("inf")  # nearest hand->face dist / face width
    face_box: Optional[Tuple[float, float, float, float]] = None  # x0,y0,x1,y1 px

    def as_status(self) -> dict:
        return {
            "face_count": self.face_count,
            "mar": round(self.mar, 3),
            "hand_found": self.hand_found,
            "touch_ratio": (
                None if self.touch_ratio == float("inf") else round(self.touch_ratio, 3)
            ),
        }


def _pt(landmark, w: int, h: int) -> np.ndarray:
    return np.array([landmark.x * w, landmark.y * h], dtype=np.float32)


class FaceHandsAnalyzer:
    """Wraps the MediaPipe Tasks landmarkers and produces :class:`FrameMetrics`."""

    def __init__(self) -> None:
        face_model = utils.resource_path("assets", "models", "face_landmarker.task")
        hand_model = utils.resource_path("assets", "models", "hand_landmarker.task")
        for path in (face_model, hand_model):
            if not path.exists():
                raise FileNotFoundError(
                    f"MediaPipe model missing: {path}\n"
                    "Run `python fetch_models.py` in src-backend first."
                )

        self.face = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(face_model)),
                running_mode=_VIDEO,
                num_faces=2,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self.hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(hand_model)),
                running_mode=_VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._t0 = time.monotonic()
        self._last_ts = -1

    def _next_ts(self) -> int:
        # VIDEO mode requires strictly increasing millisecond timestamps.
        ts = int((time.monotonic() - self._t0) * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts
        return ts

    def close(self) -> None:
        try:
            self.face.close()
        finally:
            self.hands.close()

    def analyze(self, rgb: np.ndarray, w: int, h: int) -> FrameMetrics:
        """Run both landmarkers on an RGB frame of size ``w`` x ``h``."""
        m = FrameMetrics()
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        ts = self._next_ts()
        face_res = self.face.detect_for_video(image, ts)
        hand_res = self.hands.detect_for_video(image, ts)

        faces = face_res.face_landmarks or []
        m.face_count = len(faces)
        if not faces:
            return m

        # Primary face = the widest (closest to camera / the user).
        primary = max(faces, key=lambda f: abs(f[FACE_RIGHT].x - f[FACE_LEFT].x))
        lm = primary
        m.face_found = True

        # --- Mouth aspect ratio (yawn) ---
        mouth_w = (
            np.linalg.norm(_pt(lm[MOUTH_CORNERS[0]], w, h) - _pt(lm[MOUTH_CORNERS[1]], w, h))
            + 1e-6
        )
        vsum = 0.0
        for a, b in LIP_VERTICAL_PAIRS:
            vsum += float(np.linalg.norm(_pt(lm[a], w, h) - _pt(lm[b], w, h)))
        m.mar = (vsum / len(LIP_VERTICAL_PAIRS)) / mouth_w

        # --- Geometry for the touch test (scale invariant via face width) ---
        face_w_px = (
            np.linalg.norm(_pt(lm[FACE_LEFT], w, h) - _pt(lm[FACE_RIGHT], w, h)) + 1e-6
        )
        nose = _pt(lm[NOSE_TIP], w, h)
        leye = (_pt(lm[LEFT_EYE[0]], w, h) + _pt(lm[LEFT_EYE[1]], w, h)) / 2.0
        reye = (_pt(lm[RIGHT_EYE[0]], w, h) + _pt(lm[RIGHT_EYE[1]], w, h)) / 2.0
        targets = (nose, leye, reye)

        m.face_box = (
            float(lm[FACE_LEFT].x * w),
            float(lm[FOREHEAD].y * h),
            float(lm[FACE_RIGHT].x * w),
            float(lm[CHIN].y * h),
        )

        # --- Hand proximity to nose / eyes ---
        hands_lm = hand_res.hand_landmarks or []
        if hands_lm:
            m.hand_found = True
            best = float("inf")
            for hand in hands_lm:
                for hp in hand:
                    p = _pt(hp, w, h)
                    for t in targets:
                        d = float(np.linalg.norm(p - t))
                        if d < best:
                            best = d
            m.touch_ratio = best / face_w_px
        return m


class TemporalGate:
    """Debounced latch: turns on after ``on_time`` of truth, off after
    ``off_time`` of falsehood (hysteresis)."""

    def __init__(self, on_time: float, off_time: float) -> None:
        self.on_time = on_time
        self.off_time = off_time
        self.active = False
        self._true_since: Optional[float] = None
        self._false_since: Optional[float] = None

    def reset(self) -> None:
        self.active = False
        self._true_since = None
        self._false_since = None

    def update(self, condition: bool, now: float) -> bool:
        if condition:
            self._false_since = None
            if self._true_since is None:
                self._true_since = now
            if not self.active and (now - self._true_since) >= self.on_time:
                self.active = True
        else:
            self._true_since = None
            if self.active:
                if self._false_since is None:
                    self._false_since = now
                if (now - self._false_since) >= self.off_time:
                    self.active = False
            else:
                self._false_since = None
        return self.active
