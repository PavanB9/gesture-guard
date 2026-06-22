import { useRef } from "react";

import Dashboard from "./components/Dashboard";
import { useBackendPort } from "./hooks/useBackendPort";
import { useGuardConfig } from "./hooks/useGuardConfig";
import { useGuardProcessor } from "./hooks/useGuardProcessor";

export default function App() {
  const { port, error } = useBackendPort();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const { config, update, updateDebounced } = useGuardConfig(port);
  const { status, connected, cameraError } = useGuardProcessor(
    port,
    canvasRef,
  );

  return (
    <Dashboard
      connected={connected}
      portError={error}
      cameraError={cameraError}
      status={status}
      config={config}
      canvasRef={canvasRef}
      update={update}
      updateDebounced={updateDebounced}
    />
  );
}
