// Gesture Guard — Tauri core process.
//
// Owns the lifecycle of the Python privacy-engine:
//   * pick a free localhost port,
//   * spawn the engine (dev: project venv; release: the bundled one-folder
//     build under the app's resource dir),
//   * expose the port to the webview via `get_backend_port`,
//   * kill the engine (whole tree) when the window is destroyed.

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, State, WindowEvent};

struct BackendState {
    port: u16,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_backend_port(state: State<BackendState>) -> u16 {
    state.port
}

/// Ask the OS for a free TCP port on the loopback interface.
fn find_free_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .unwrap_or(8000)
}

#[allow(unused_variables)]
fn spawn_engine(app: &tauri::AppHandle, port: u16) -> std::io::Result<Child> {
    let port = port.to_string();
    let args = ["--host", "127.0.0.1", "--port", port.as_str()];

    #[cfg(debug_assertions)]
    {
        // Dev: run straight from the project venv so you don't re-freeze on
        // every change. Path is resolved at compile time relative to src-tauri.
        let backend = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("src-tauri has a parent")
            .join("src-backend");
        #[cfg(target_os = "windows")]
        let python = backend.join(".venv").join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let python = backend.join(".venv").join("bin").join("python");

        Command::new(python)
            .arg("-m")
            .arg("app.main")
            .args(args)
            .current_dir(&backend)
            .spawn()
    }

    #[cfg(not(debug_assertions))]
    {
        // Release: the bundled one-folder engine lives under <resources>/engine.
        #[cfg(target_os = "windows")]
        let rel = "engine/privacy-engine.exe";
        #[cfg(not(target_os = "windows"))]
        let rel = "engine/privacy-engine";

        let exe = app
            .path()
            .resolve(rel, tauri::path::BaseDirectory::Resource)
            .expect("failed to resolve bundled engine path");
        let mut cmd = Command::new(exe);
        cmd.args(args);
        // The engine is a console-subsystem exe; a windows_subsystem="windows"
        // parent has no console to inherit, so without this flag Windows pops a
        // brand-new visible console window for the engine.
        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        cmd.spawn()
    }
}

/// Kill the engine and any child processes it spawned.
fn kill_engine(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendState>() {
        if let Some(mut child) = state.child.lock().unwrap().take() {
            let pid = child.id();
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                let _ = Command::new("taskkill")
                    .args(["/F", "/T", "/PID", &pid.to_string()])
                    .creation_flags(0x0800_0000) // CREATE_NO_WINDOW
                    .output();
            }
            #[cfg(not(target_os = "windows"))]
            {
                let _ = Command::new("pkill")
                    .args(["-TERM", "-P", &pid.to_string()])
                    .output();
            }
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[allow(unused_mut)]
    let mut builder = tauri::Builder::default().plugin(tauri_plugin_opener::init());

    // macOS: native camera-permission plugin so the app registers with the system
    // (prompts + shows up in System Settings -> Privacy & Security -> Camera).
    #[cfg(target_os = "macos")]
    {
        builder = builder.plugin(tauri_plugin_macos_permissions::init());
    }

    builder
        .setup(|app| {
            let port = find_free_port();
            let child = spawn_engine(app.handle(), port).expect("failed to spawn privacy engine");
            app.manage(BackendState {
                port,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                kill_engine(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
