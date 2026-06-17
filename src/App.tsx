import { useRef } from "react";

import Dashboard from "./components/Dashboard";
import { useBackendPort } from "./hooks/useBackendPort";
import { useGuardConfig } from "./hooks/useGuardConfig";
import { useGuardStream } from "./hooks/useGuardStream";

export default function App() {
  const { port, error } = useBackendPort();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { config, update, updateDebounced } = useGuardConfig(port);
  const { status, connected } = useGuardStream(port, canvasRef);

  return (
    <Dashboard
      connected={connected}
      portError={error}
      status={status}
      config={config}
      canvasRef={canvasRef}
      update={update}
      updateDebounced={updateDebounced}
    />
  );
}
