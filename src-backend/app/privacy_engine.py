"""The capture + detection + guard loop.

A background thread owns the webcam (``cv2.VideoCapture``), runs detection on a
downscaled frame, decides whether any armed detector is violating, and produces
the *safe* output frame (passthrough, heavy blur, or a Be-Right-Back screen).
The latest encoded JPEG and a status dict are published behind a lock for the
FastAPI WebSocket handler to pick up.

Set ``GESTURE_GUARD_NO_CAMERA=1`` to run the full server stack without ever
opening the webcam (used for automated/CI smoke tests).
"""

from __future__ import annotations

import os
import platform
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
        self._lock = threading.Lock()
        self._config = config or GuardConfig()
        self._no_camera = bool(os.environ.get("GESTURE_GUARD_NO_CAMERA"))

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._analyzer: Optional[FaceHandsAnalyzer] = None
        self._cap = None
        self._reopen = True
        self._cam_error: Optional[str] = None

        self._latest_jpeg: Optional[bytes] = None
        self._seq = 0
        self._status: Dict = {"guard_active": False, "violations": [], "fps": 0.0}

        self._gates = {
            "yawn": TemporalGate(YAWN_HOLD_S, RELEASE_S),
            "face_touch": TemporalGate(TOUCH_HOLD_S, RELEASE_S),
            "intrusion": TemporalGate(INTRUSION_HOLD_S, RELEASE_S),
        }
        self._detect_every = 2  # run MediaPipe every Nth frame to save CPU
        self._frame_i = 0
        self._last_metrics: Optional[FrameMetrics] = None
        self._fps = 0.0

        # Phase 2: virtual camera output (lazy; degrades gracefully).
        self._vcam = None
        self._vcam_dims = None
        self._vcam_error: Optional[str] = None

    # --- public API -----------------------------------------------------------
    def is_running(self) -> bool:
        return self._running

    def get_config(self) -> GuardConfig:
        with self._lock:
            return self._config.model_copy()

    def update_config(self, partial: dict) -> GuardConfig:
        with self._lock:
            merged = self._config.model_dump()
            merged.update({k: v for k, v in partial.items() if k in merged})
            new_cfg = GuardConfig(**merged)
            if new_cfg.camera_index != self._config.camera_index:
                self._reopen = True
            self._config = new_cfg
            return new_cfg.model_copy()

    def get_frame(self) -> Tuple[int, Optional[bytes], Dict]:
        with self._lock:
            return self._seq, self._latest_jpeg, dict(self._status)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="privacy-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    # --- camera ---------------------------------------------------------------
    def _open_camera(self, index: int):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        # DirectShow opens far faster than MSMF on Windows; default elsewhere.
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap

    # --- main loop ------------------------------------------------------------
    def _run(self) -> None:
        if self._no_camera:
            self._run_no_camera()
            return

        self._analyzer = FaceHandsAnalyzer()
        last_t = time.time()
        try:
            while self._running:
                cfg = self.get_config()

                if self._reopen:
                    self._cap = self._open_camera(cfg.camera_index)
                    self._reopen = False
                    if self._cap is None or not self._cap.isOpened():
                        self._cam_error = f"Cannot open camera {cfg.camera_index}"
                        self._publish(utils.draw_message(960, 540, self._cam_error), cfg, set(), None)
                        time.sleep(0.5)
                        continue
                    self._cam_error = None

                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self._cam_error = "Camera read failed"
                    self._publish(utils.draw_message(960, 540, self._cam_error), cfg, set(), None)
                    self._reopen = True
                    time.sleep(0.2)
                    continue

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

                dt = now - last_t
                last_t = now
                if dt > 0:
                    self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)

                self._publish(out, cfg, violations, metrics, guard_active)
        finally:
            self._close_vcam()
            if self._cap is not None:
                self._cap.release()
            if self._analyzer is not None:
                self._analyzer.close()

    def _run_no_camera(self) -> None:
        """Test/CI mode: serve a placeholder, never touch the webcam."""
        frame = utils.draw_message(960, 540, "CAMERA DISABLED (test mode)")
        while self._running:
            cfg = self.get_config()
            self._publish(frame, cfg, set(), None, guard_active=False)
            time.sleep(0.2)

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
        # Already failed to open at this resolution: wait for a toggle off/on
        # instead of hammering the driver every frame.
        if self._vcam is None and self._vcam_error is not None:
            return
        self._close_vcam()
        try:
            import pyvirtualcam

            self._vcam = pyvirtualcam.Camera(
                width=w,
                height=h,
                fps=30,
                fmt=pyvirtualcam.PixelFormat.BGR,
                print_fps=False,
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

    def _publish(
        self,
        out: np.ndarray,
        cfg: GuardConfig,
        violations: Set[str],
        metrics: Optional[FrameMetrics],
        guard_active: bool = False,
    ) -> None:
        jpeg = utils.encode_jpeg(out, 80)
        status = {
            "guard_active": guard_active,
            "violations": sorted(violations),
            "violation_labels": [VIOLATION_LABELS[v] for v in sorted(violations)],
            "action": cfg.guard_action,
            "fps": round(self._fps, 1),
            "camera_error": self._cam_error,
            "virtual_cam_active": self._vcam is not None,
            "virtual_cam_error": self._vcam_error,
        }
        if metrics is not None:
            status.update(metrics.as_status())
        with self._lock:
            if jpeg is not None:
                self._latest_jpeg = jpeg
                self._seq += 1
            self._status = status
