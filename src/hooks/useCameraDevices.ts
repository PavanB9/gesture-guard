import { useEffect, useState } from "react";

/** Lists available video input devices. Labels populate once the user has
 *  granted camera permission (so call after the camera has started once). */
export function useCameraDevices(refreshKey: unknown) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const all = await navigator.mediaDevices.enumerateDevices();
        if (!cancelled) setDevices(all.filter((d) => d.kind === "videoinput"));
      } catch {
        /* enumerateDevices unavailable */
      }
    };
    load();
    navigator.mediaDevices?.addEventListener?.("devicechange", load);
    return () => {
      cancelled = true;
      navigator.mediaDevices?.removeEventListener?.("devicechange", load);
    };
  }, [refreshKey]);

  return devices;
}
