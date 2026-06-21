# Gesture Guard 🛡️

A **completely local, real-time webcam privacy guard** for video calls. It watches
your camera and instantly **blurs the feed** (or shows a *Be Right Back* screen)
the moment it catches unprofessional behaviour:

- 😮 **Yawning** — sustained wide-open mouth
- ✋ **Face touching / nose-picking** — a hand lingering near your nose or eyes
- 👥 **Background intrusion** — a second person appears behind you

Everything — capture, detection, and blurring — runs **on your machine**. No cloud,
no telemetry, no external endpoints. The only network access ever required is a
one-time download of the open-source MediaPipe model files at build time.

---

## Download

Prebuilt installers are published on the
**[Releases](https://github.com/PavanB9/gesture-guard/releases)** page:

- **Windows** — `Gesture Guard_<version>_x64-setup.exe` (or the `.msi`)
- **macOS (Apple Silicon)** — `Gesture Guard_<version>_aarch64.dmg`

> The builds are **unsigned** (no paid Apple Developer / code-signing cert), so the OS
> will warn on first launch:
>
> - **Windows:** SmartScreen → *More info* → *Run anyway*.
> - **macOS:** Gatekeeper quarantines it and may say *"…is damaged and can't be opened."*
>   It is **not** damaged — just unsigned. Remove the quarantine flag once in Terminal:
>   ```bash
>   xattr -cr "/Applications/Gesture Guard.app"
>   ```
>   If it still won't launch (the embedded engine also needs a signature on Apple Silicon),
>   ad-hoc sign it: `sudo codesign --force --deep --sign - "/Applications/Gesture Guard.app"`.

To cut a release, push a version tag — GitHub Actions then builds all three installers
automatically (see `.github/workflows/release.yml`):

```bash
git tag v0.1.0
git push origin v0.1.0
```

---

## Architecture

```
Tauri 2 (Rust shell)
 ├─ picks a free localhost port, spawns the Python sidecar, kills it on exit
 └─ React + Vite + Tailwind dashboard (monitor + controls)
        │  WS  ws://127.0.0.1:<port>/ws/stream   (status JSON + JPEG frames)
        │  REST /api/config                       (toggles, sensitivity, action)
        ▼
Python sidecar (FastAPI + uvicorn) — PyInstaller single-file binary
 └─ OpenCV captures the webcam → MediaPipe Tasks (Face + Hand Landmarker)
    → yawn / face-touch / intrusion detectors → blur or BRB → stream the SAFE frame
```

The **app window owns the camera** (`getUserMedia`, so the OS grants camera access
to the app itself) and streams JPEG frames to the local engine over `/ws/process`;
the engine runs detection, produces the safe frame, and returns it. Nothing leaves
the machine. (Earlier versions had the Python engine open the camera directly, but a
separate helper process can't get its own camera permission on macOS.)

| Area            | Folder         |
| --------------- | -------------- |
| React frontend  | `src/`         |
| Python engine   | `src-backend/` |
| Tauri shell     | `src-tauri/`   |

---

## Prerequisites (one-time, global)

- **Node.js 18+** and npm
- **Rust** (`rustup`, stable toolchain) + a C/C++ toolchain
  - Windows: **Visual Studio C++ Build Tools** (MSVC)
  - macOS: **Xcode Command Line Tools** (`xcode-select --install`)
- **Python 3.12** — MediaPipe has **no 3.13 wheels**, so 3.12 is required for the venv

See <https://tauri.app/start/prerequisites/> for the Tauri/Rust requirements.

---

## Setup (offline-friendly)

All Python packages install into a **local venv** (`src-backend/.venv`); npm packages
into local `node_modules`. Nothing is installed globally beyond the prerequisites above.

```bash
# 1. Frontend deps
npm install

# 2. Python engine — create the local venv with a Python 3.12 interpreter.
#    Do NOT use a bare `python` if it is 3.13 (MediaPipe has no 3.13 wheels).
cd src-backend

# Windows (winget installs 3.12 here; adjust if yours differs):
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# macOS:
#  python3.12 -m venv .venv
#  .venv/bin/python -m pip install -r requirements.txt

# 3. Fetch the MediaPipe model bundles once (~11 MB). Runtime stays offline after this.
.venv\Scripts\python fetch_models.py     # Windows  (.venv/bin/python on macOS)
cd ..
```

---

## Run

### Full desktop app (Tauri)

The sidecar must be frozen first so Tauri can embed it:

```bash
cd src-backend
.venv/Scripts/python build_sidecar.py   # Windows  (.venv/bin/python on macOS)
cd ..

npm run tauri dev      # development
npm run tauri build    # production installer
```

`build_sidecar.py` runs PyInstaller and drops
`privacy-engine-<target-triple>[.exe]` into `src-tauri/binaries/`, which Tauri
bundles as an `externalBin` sidecar. The Rust core spawns it on launch and kills
it when you close the window. (The sidecar is deliberately named differently
from the app binary so Tauri's dev-mode copy doesn't collide with it.)

### Frontend-only dev (no Tauri build)

Useful for fast UI iteration. Run the engine and Vite separately:

```bash
# terminal 1 — engine on the dev fallback port
cd src-backend
.venv/Scripts/python run.py --port 8000

# terminal 2 — Vite dev server (auto-connects to 127.0.0.1:8000 outside Tauri)
npm run dev
```

---

## Verifying the detection math

```bash
cd src-backend
.venv/Scripts/python -m app.checks      # live MAR / touch-ratio / face-count trace
.venv/Scripts/python -m app.selftest    # camera-free pipeline smoke test
```

Yawn → `mar` rises above the threshold • touch your nose → `touch_ratio` drops
below the threshold • have someone step in → `faces` becomes 2.

---

## macOS notes

- Build the sidecar **on the Mac** so PyInstaller emits a native
  `aarch64-apple-darwin` (Apple Silicon) or `x86_64-apple-darwin` (Intel) binary.
- The first launch triggers the **camera permission** prompt (the app ships an
  `NSCameraUsageDescription` in `src-tauri/Info.plist`).

## Virtual camera output

Toggle **Virtual camera** in the dashboard (Output section) to also push the guarded
feed to a system virtual webcam, so Zoom/Teams/Meet can select **"Gesture Guard"**
(or "OBS Virtual Camera") as their camera and receive the already-protected stream.

This requires a virtual-camera driver to be installed on the machine:

- **Windows / macOS:** install [OBS Studio](https://obsproject.com/) and click
  *Start Virtual Camera* once to register the device (`pyvirtualcam` then drives it).
- If no driver is present the toggle reports the error and the app keeps working —
  the in-app preview is unaffected.

## License

For personal/educational use. The bundled MediaPipe models are licensed by Google
under the Apache 2.0 license.
