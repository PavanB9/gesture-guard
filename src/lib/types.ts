export type GuardAction = "blur" | "brb";

export interface GuardConfig {
  guard_enabled: boolean;
  yawn_guard: boolean;
  face_touch_guard: boolean;
  intrusion_guard: boolean;
  guard_action: GuardAction;
  sensitivity: number;
  camera_index: number;
  mirror: boolean;
  show_overlay: boolean;
  virtual_cam: boolean;
}

export interface GuardStatus {
  guard_active: boolean;
  violations: string[];
  violation_labels: string[];
  action: GuardAction;
  fps: number;
  camera_error: string | null;
  virtual_cam_active?: boolean;
  virtual_cam_error?: string | null;
  face_count?: number;
  mar?: number;
  hand_found?: boolean;
  touch_ratio?: number | null;
}
