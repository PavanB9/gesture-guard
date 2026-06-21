import { useRef, useState } from "react";

import Dashboard from "./components/Dashboard";
import { useBackendPort } from "./hooks/useBackendPort";
import { useCameraDevices } from "./hooks/useCameraDevices";
import { useGuardConfig } from "./hooks/useGuardConfig";
import { useGuardProcessor } from "./hooks/useGuardProcessor";

export default function App() {
  const { port, error } = useBackendPort();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [deviceId, setDeviceId] = useState<string | null>(null);

  const { config, update, updateDebounced } = useGuardConfig(port);
  const { status, connected, cameraError, started } = useGuardProcessor(
    port,
    canvasRef,
    deviceId,
  );
  const devices = useCameraDevices(started);

  return (
    <Dashboard
      connected={connected}
      portError={error}
      cameraError={cameraError}
      status={status}
      config={config}
      canvasRef={canvasRef}
      devices={devices}
      deviceId={deviceId}
      setDeviceId={setDeviceId}
      update={update}
      updateDebounced={updateDebounced}
    />
  );
}
