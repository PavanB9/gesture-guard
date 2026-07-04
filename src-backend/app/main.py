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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

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

# Only the app's own webview (and the Vite dev server) may talk to the engine.
# A wildcard here would let any webpage in any local browser POST /api/config
# and silently disarm the guard mid-call.
ALLOWED_ORIGINS = [
    "tauri://localhost",       # macOS / Linux webview
    "http://tauri.localhost",  # Windows webview (WebView2)
    "https://tauri.localhost",
    "http://localhost:1420",   # Vite dev server
    "http://127.0.0.1:1420",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
    try:
        return engine.update_config(partial).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False))


@app.websocket("/ws/process")
async def ws_process(ws: WebSocket):
    # Browsers always send an Origin header on WebSocket handshakes; reject
    # pages that are not our webview / dev server. (Non-browser clients on this
    # machine could always talk to localhost directly — they are out of scope.)
    origin = ws.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await ws.close(code=1008)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    try:
        while True:
            data = await ws.receive_bytes()
            # Run the CPU-bound detection off the event loop.
            jpeg, status = await loop.run_in_executor(None, engine.process_jpeg, data)
            await ws.send_text(json.dumps(status))
            # Always return a binary frame so the client can pace the next send.
            await ws.send_bytes(jpeg if jpeg is not None else data)
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
