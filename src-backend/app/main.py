"""FastAPI app exposing the privacy engine over localhost.

Endpoints
---------
* ``GET  /healthz``       - liveness probe (Tauri waits on this before connecting)
* ``GET  /api/config``    - current guard configuration
* ``POST /api/config``    - partial config update (toggles, sensitivity, action, camera)
* ``GET  /api/cameras``   - candidate camera indices + the active one
* ``WS   /ws/stream``     - server -> client: JSON status text + binary JPEG frames

The socket is one-directional (the Python side owns the camera); the dashboard
only sends settings via the REST endpoints.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .privacy_engine import PrivacyEngine

engine = PrivacyEngine()

STREAM_INTERVAL = 1.0 / 30.0  # poll cadence for pushing frames (~30 fps)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine.start()
    try:
        yield
    finally:
        engine.stop()


app = FastAPI(title="Gesture Guard Engine", version="0.1.0", lifespan=lifespan)

# Local-only app; the Tauri webview origin is tauri://localhost or
# http://localhost:1420, so we allow any origin for the REST endpoints.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "running": engine.is_running()}


@app.get("/api/config")
async def get_config():
    return engine.get_config().model_dump()


@app.post("/api/config")
async def set_config(partial: dict):
    return engine.update_config(partial).model_dump()


@app.get("/api/cameras")
async def list_cameras():
    # Opening a device just to probe it conflicts with the engine's exclusive
    # hold on Windows, so we expose candidate indices and report failures via
    # the stream's `camera_error` field instead.
    return {
        "cameras": [0, 1, 2, 3],
        "active": engine.get_config().camera_index,
    }


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    last_seq = -1
    try:
        while True:
            seq, jpeg, status = engine.get_frame()
            if jpeg is not None and seq != last_seq:
                last_seq = seq
                await ws.send_text(json.dumps(status))
                await ws.send_bytes(jpeg)
            await asyncio.sleep(STREAM_INTERVAL)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Client vanished or transport broke; just end the coroutine.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Gesture Guard privacy engine")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run the camera-free pipeline smoke test and exit "
        "(verifies bundled MediaPipe models load — handy for the frozen binary).",
    )
    args = parser.parse_args()

    if args.selftest:
        from .selftest import main as selftest_main

        raise SystemExit(selftest_main())

    # Single, explicit ready line that Tauri can log/observe.
    print(f"GESTURE_GUARD_ENGINE host={args.host} port={args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
