"""Frame processing + detection + guard logic.

The engine does **not** own the camera. The app window captures the webcam
(via the browser's getUserMedia, so the OS grants the camera to the app itself)
and streams JPEG frames here over the WebSocket. For each frame the engine runs
detection, decides whether any armed detector is violating, and returns the
*safe* frame (passthrough, heavy blur, or a Be-Right-Back screen) plus a status.

This sidesteps the macOS problem where a separate helper process can't get its
own camera permission.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Set, Tuple

import cv2
import numpy as np

from . import utils
from .config import (
    INTRUSION_HOLD_S,
    RELEASE_S,
    TOUCH_HOLD_S,
    YAWN_HOLD_S,
    GuardConfig,
)
from .detectors import FaceHandsAnalyzer, FrameMetrics, TemporalGate

VIOLATION_LABELS = {
    "yawn": "Yawning",
    "face_touch": "Face touching",
    "intrusion": "Background person",
}


class PrivacyEngine:
    def __init__(self, config: Optional[GuardConfig] = None) -> None:
        self._lock = threading.Lock()  # guards config
        self._proc_lock = threading.Lock()  # serialises frame processing
        self._config = config or GuardConfig()

        self._analyzer: Optional[FaceHandsAnalyzer] = None
        self._running = False

        self._gates = {
            "yawn": TemporalGate(YAWN_HOLD_S, RELEASE_S),
            "face_touch": TemporalGate(TOUCH_HOLD_S, RELEASE_S),
            "intrusion": TemporalGate(INTRUSION_HOLD_S, RELEASE_S),
        }
        self._detect_every = 2  # run MediaPipe every Nth frame to save CPU
        self._frame_i = 0
        self._last_metrics: Optional[FrameMetrics] = None
        self._fps = 0.0
        self._last_t = time.time()

        # Phase 2: virtual camera output (lazy; degrades gracefully).
        self._vcam = None
        self._vcam_dims = None
        self._vcam_error: Optional[str] = None

    # --- lifecycle ------------------------------------------------------------
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        with self._proc_lock:
            self._close_vcam()
            if self._analyzer is not None:
                self._analyzer.close()
                self._analyzer = None

    # --- config ---------------------------------------------------------------
    def get_config(self) -> GuardConfig:
        with self._lock:
            return self._config.model_copy()

    def update_config(self, partial: dict) -> GuardConfig:
        with self._lock:
            merged = self._config.model_dump()
            merged.update({k: v for k, v in partial.items() if k in merged})
            new_cfg = GuardConfig(**merged)
            self._config = new_cfg
            return new_cfg.model_copy()

    # --- frame processing -----------------------------------------------------
    def process_jpeg(self, data: bytes) -> Tuple[Optional[bytes], Dict]:
        """Decode a browser-supplied JPEG frame, guard it, return safe JPEG + status."""
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, {"guard_active": False, "violations": [], "error": "decode failed"}
        return self._process(frame)

    def _process(self, frame: np.ndarray) -> Tuple[Optional[bytes], Dict]:
        with self._proc_lock:
            if self._analyzer is None:
                self._analyzer = FaceHandsAnalyzer()
            cfg = self.get_config()

            if cfg.mirror:
                frame = cv2.flip(frame, 1)

            metrics = self._maybe_detect(frame)
            now = time.time()
            violations = self._evaluate(cfg, metrics, now)
            guard_active = cfg.guard_enabled and bool(violations)
            out = self._apply_guard(frame, cfg, guard_active, metrics)

            # Phase 2: mirror the SAFE frame to a virtual camera if enabled.
            oh, ow = out.shape[:2]
            self._ensure_vcam(cfg, ow, oh)
            self._send_vcam(out)

            dt = now - self._last_t
            self._last_t = now
            if 0 < dt < 1.0:
                self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)

            jpeg = utils.encode_jpeg(out, 80)
            status = {
                "guard_active": guard_active,
                "violations": sorted(violations),
                "violation_labels": [VIOLATION_LABELS[v] for v in sorted(violations)],
                "action": cfg.guard_action,
                "fps": round(self._fps, 1),
                "virtual_cam_active": self._vcam is not None,
                "virtual_cam_error": self._vcam_error,
            }
            if metrics is not None:
                status.update(metrics.as_status())
            return jpeg, status

    # --- helpers --------------------------------------------------------------
    def _maybe_detect(self, frame: np.ndarray) -> Optional[FrameMetrics]:
        self._frame_i += 1
        if self._frame_i % self._detect_every != 0 and self._last_metrics is not None:
            return self._last_metrics
        h, w = frame.shape[:2]
        scale = 640.0 / w if w > 640 else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1.0 else frame
        sh, sw = small.shape[:2]
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        self._last_metrics = self._analyzer.analyze(rgb, sw, sh)
        return self._last_metrics

    def _evaluate(self, cfg: GuardConfig, metrics: Optional[FrameMetrics], now: float) -> Set[str]:
        violations: Set[str] = set()
        if metrics is None:
            for g in self._gates.values():
                g.update(False, now)
            return violations

        yawn_cond = cfg.yawn_guard and metrics.face_found and metrics.mar >= cfg.yawn_mar_threshold()
        if self._gates["yawn"].update(yawn_cond, now):
            violations.add("yawn")

        touch_cond = (
            cfg.face_touch_guard
            and metrics.hand_found
            and metrics.touch_ratio <= cfg.touch_distance_ratio()
        )
        if self._gates["face_touch"].update(touch_cond, now):
            violations.add("face_touch")

        intrusion_cond = cfg.intrusion_guard and metrics.face_count >= 2
        if self._gates["intrusion"].update(intrusion_cond, now):
            violations.add("intrusion")

        return violations

    def _apply_guard(
        self,
        frame: np.ndarray,
        cfg: GuardConfig,
        guard_active: bool,
        metrics: Optional[FrameMetrics],
    ) -> np.ndarray:
        if guard_active:
            if cfg.guard_action == "brb":
                h, w = frame.shape[:2]
                return utils.draw_brb(w, h)
            return utils.heavy_blur(frame)
        if cfg.show_overlay and metrics is not None and metrics.face_box is not None:
            frame = self._draw_overlay(frame.copy(), cfg, metrics)
        return frame

    @staticmethod
    def _draw_overlay(frame: np.ndarray, cfg: GuardConfig, m: FrameMetrics) -> np.ndarray:
        x0, y0, x1, y1 = (int(v) for v in m.face_box)
        cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 220, 140), 1)
        cv2.putText(
            frame,
            f"MAR {m.mar:.2f}/{cfg.yawn_mar_threshold():.2f}  faces {m.face_count}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 140),
            1,
            cv2.LINE_AA,
        )
        return frame

    # --- virtual camera (phase 2) --------------------------------------------
    def _ensure_vcam(self, cfg: GuardConfig, w: int, h: int) -> None:
        if not cfg.virtual_cam:
            if self._vcam is not None or self._vcam_error is not None:
                self._close_vcam()
                self._vcam_error = None
            return
        if self._vcam is not None and self._vcam_dims == (w, h):
            return
        if self._vcam is None and self._vcam_error is not None:
            return  # already failed; wait for a toggle off/on
        self._close_vcam()
        try:
            import pyvirtualcam

            self._vcam = pyvirtualcam.Camera(
                width=w, height=h, fps=30, fmt=pyvirtualcam.PixelFormat.BGR, print_fps=False
            )
            self._vcam_dims = (w, h)
            self._vcam_error = None
        except Exception as exc:  # no driver installed, busy, etc.
            self._vcam = None
            self._vcam_dims = None
            self._vcam_error = f"Virtual camera unavailable: {exc}"

    def _send_vcam(self, frame: np.ndarray) -> None:
        if self._vcam is None:
            return
        try:
            self._vcam.send(frame)
        except Exception as exc:
            self._vcam_error = f"Virtual camera send failed: {exc}"
            self._close_vcam()

    def _close_vcam(self) -> None:
        if self._vcam is not None:
            try:
                self._vcam.close()
            except Exception:
                pass
        self._vcam = None
        self._vcam_dims = None
