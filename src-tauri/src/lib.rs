// Gesture Guard — Tauri core process.
//
// Owns the lifecycle of the embedded Python privacy-engine sidecar:
//   * pick a free localhost port at startup,
//   * spawn `gesture-guard --host 127.0.0.1 --port <p>` silently,
//   * expose the chosen port to the webview via `get_backend_port`,
//   * forcefully kill the sidecar when the window is destroyed (no orphans).

use std::sync::Mutex;

use tauri::{Manager, State, WindowEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct BackendState {
    port: u16,
    child: Mutex<Option<CommandChild>>,
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

fn kill_sidecar(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendState>() {
        if let Some(child) = state.child.lock().unwrap().take() {
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = find_free_port();

            let sidecar = app
                .shell()
                .sidecar("gesture-guard")
                .expect("failed to create `gesture-guard` sidecar command")
                .args(["--host", "127.0.0.1", "--port", &port.to_string()]);

            let (mut rx, child) = sidecar
                .spawn()
                .expect("failed to spawn privacy engine sidecar");

            // Forward sidecar output to the Tauri log for debugging.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            print!("[engine] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprint!("[engine] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });

            app.manage(BackendState {
                port,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                kill_sidecar(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
