"""Runtime configuration for the privacy guard.

A single ``sensitivity`` slider (0..1) drives the spatial thresholds for every
detector, while the feature toggles decide which detectors are armed. The model
is validated with pydantic so partial updates coming from the dashboard over
REST are sanitised before they ever reach the capture loop.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Temporal constants (seconds) ---------------------------------------------
# How long a condition must hold before it counts as a violation, and how long
# the guard stays engaged after the condition clears (hysteresis) so the HUD
# does not flicker on/off.
YAWN_HOLD_S = 1.5  # spec: yawn must persist > 1.5s
TOUCH_HOLD_S = 0.45  # face touching / nose picking: a brief threshold
INTRUSION_HOLD_S = 0.6  # a second person lingering in frame
RELEASE_S = 0.6  # keep guarding this long after the trigger clears

GuardAction = Literal["blur", "brb"]


class GuardConfig(BaseModel):
    """Mutable guard configuration, shared with the dashboard."""

    # Master switch — when False the feed is always passed through untouched.
    guard_enabled: bool = True

    # Individual detector toggles.
    yawn_guard: bool = True
    face_touch_guard: bool = True
    intrusion_guard: bool = True

    # What to do when a violation fires.
    guard_action: GuardAction = "blur"

    # 0 = least sensitive (hard to trigger), 1 = most sensitive (easy).
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)

    # Webcam device index (0 is the default camera).
    camera_index: int = Field(default=0, ge=0)

    # Mirror the preview like a selfie cam.
    mirror: bool = True

    # Draw landmark debug overlay on the passthrough feed.
    show_overlay: bool = False

    # Phase 2: also push the guarded feed to a system virtual camera so video
    # call apps (Zoom/Teams) consume the protected stream. Requires a virtual
    # camera driver (e.g. OBS Virtual Camera) to be installed on the machine.
    virtual_cam: bool = False

    # --- Derived thresholds ---------------------------------------------------
    def yawn_mar_threshold(self) -> float:
        """Mouth-aspect-ratio cut-off. Higher sensitivity -> lower bar."""
        return 0.62 - 0.22 * self.sensitivity  # ~0.62 (s=0) .. ~0.40 (s=1)

    def touch_distance_ratio(self) -> float:
        """Hand-to-face distance as a fraction of face width.

        A hand point closer than this (relative to the face width, so it is
        scale invariant) counts as touching the face. Higher sensitivity ->
        larger catch radius.
        """
        return 0.30 + 0.35 * self.sensitivity  # 0.30 .. 0.65
