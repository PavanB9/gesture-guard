"""FastAPI app exposing the privacy engine over localhost.

Endpoints
---------
* ``GET  /healthz``     - liveness probe (the UI waits on this before connecting)
* ``GET  /api/config``  - current guard configuration
* ``POST /api/config``  - partial config update (toggles, sensitivity, action)
* ``WS   /ws/process``  - the app sends webcam JPEG frames; the engine returns a
                          JSON status line + the safe JPEG frame for each one.

The app window owns the camera (browser getUserMedia); the engine only processes
the frames it is sent.
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine.start()
    try:
        yield
    finally:
        engine.stop()


app = FastAPI(title="Gesture Guard Engine", version="0.1.0", lifespan=lifespan)

# Local-only app; allow any origin for the REST endpoints (the webview origin is
# tauri://localhost / http://localhost).
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
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


@app.websocket("/ws/process")
async def ws_process(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_event_loop()
    try:
        while True:
            # We still wait for a message from the client to act as a backpressure "tick"
            _ = await ws.receive_bytes()
            # Capture and process the next frame
            jpeg, status = await loop.run_in_executor(None, engine.process_next_frame)
            await ws.send_text(json.dumps(status))
            # Always return a binary frame so the client can pace the next send.
            await ws.send_bytes(jpeg if jpeg is not None else b"")
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
        help="Run the camera-free pipeline smoke test and exit.",
    )
    args = parser.parse_args()

    if args.selftest:
        from .selftest import main as selftest_main

        raise SystemExit(selftest_main())

    print(f"GESTURE_GUARD_ENGINE host={args.host} port={args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
