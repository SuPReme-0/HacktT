use tauri::Manager;
use std::process::{Command, Stdio, Child};
use std::io::{BufRead, BufReader};
use std::thread;
use std::sync::Mutex;
use uuid::Uuid;

// ==============================================================================
// Shared State for Backend Process Management
// ==============================================================================

/// Holds the Python backend process so we can kill it on exit
pub struct BackendState(pub Mutex<Option<Child>>);

// ==============================================================================
// Event Payloads (Serializable for Tauri -> React)
// ==============================================================================

#[derive(Clone, serde::Serialize)]
pub struct BootstrapperLog {
    pub text: String,
}

#[derive(Clone, serde::Serialize)]
pub struct BackendLog {
    pub text: String,
}

// ==============================================================================
// 1. RUN PYTHON MODEL BOOTSTRAPPER (The Setup Wizard)
// ==============================================================================

#[tauri::command]
pub async fn run_model_bootstrapper(window: tauri::Window) -> Result<String, String> {
    // We call the MAIN executable, but pass the "--bootstrap" flag
    let backend_exe = window.app_handle().path_resolver()
        .resolve_resource("resources/hackt_sovereign_core/hackt_sovereign_core.exe")
        .ok_or("Failed to locate backend executable in resources")?;

    let mut child = Command::new(&backend_exe)
        .arg("--bootstrap") // 🔥 Tells main.py to download models instead of starting the server
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // .creation_flags(0x08000000) // Uncomment on Windows to hide the console window
        .spawn()
        .map_err(|e| format!("Failed to spawn bootstrapper: {}", e))?;

    // Take stdout/stderr BEFORE spawning threads to avoid moving child
    let stdout = child.stdout.take()
        .ok_or("Failed to capture bootstrapper stdout")?;
    let stderr = child.stderr.take()
        .ok_or("Failed to capture bootstrapper stderr")?;
    
    let window_clone_out = window.clone();
    let window_clone_err = window.clone();
    let window_clone_finish = window.clone();

    // Stream stdout to React
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().map_while(Result::ok) {
            let _ = window_clone_out.emit("bootstrapper_log", BootstrapperLog { text: line });
        }
    });

    // Stream stderr to React
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().map_while(Result::ok) {
            let _ = window_clone_err.emit("bootstrapper_log", BootstrapperLog { 
                text: format!("[ERROR] {}", line) 
            });
        }
    });

    // 🔥 FIX: Wait for the process in a detached background thread to prevent UI freezing
    thread::spawn(move || {
        match child.wait() {
            Ok(status) if status.success() => {
                let _ = window_clone_finish.emit("bootstrapper_complete", "success");
            }
            Ok(_) => {
                let _ = window_clone_finish.emit("bootstrapper_complete", "failed_nonzero");
            }
            Err(e) => {
                let _ = window_clone_finish.emit("bootstrapper_complete", format!("failed: {}", e));
            }
        }
    });

    Ok("Bootstrapper initiated".to_string())
}

// ==============================================================================
// 2. SPAWN MAIN PYTHON BACKEND (Manual Start after setup)
// ==============================================================================

#[tauri::command]
pub fn spawn_python_backend(
    app_handle: tauri::AppHandle, 
    state: tauri::State<'_, BackendState>
) -> Result<String, String> {
    
    let resource_path = app_handle.path_resolver()
        .resolve_resource("resources/hackt_sovereign_core/hackt_sovereign_core.exe")
        .ok_or("Failed to locate main backend executable")?;

    let mut child = Command::new(&resource_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start AI Core: {}", e))?;

    let pid = child.id();

    // Stream backend logs to React (with graceful window access)
    if let Some(stdout) = child.stdout.take() {
        // Clone app_handle instead of window to avoid borrow issues
        let app_handle_clone = app_handle.clone();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().map_while(Result::ok) {
                // Try to get window, but don't panic if it's not ready
                if let Some(window) = app_handle_clone.get_window("main") {
                    let _ = window.emit("backend_log", BackendLog { text: line });
                }
            }
        });
    }

    // 🔥 FIX: Lock the Mutex and store the child process so we can kill it when the app closes
    let mut backend_guard = state.0.lock().map_err(|e| format!("Failed to lock backend state: {}", e))?;
    *backend_guard = Some(child);

    Ok(format!("AI Core Initialized. PID: {}", pid))
}

// ==============================================================================
// 3. UTILITIES
// ==============================================================================

#[tauri::command]
pub async fn trigger_google_auth(window: tauri::Window) -> Result<String, String> {
    // 🚀 Make this configurable via tauri.conf.json or env vars in production
    let supabase_auth_url = option_env!("SUPABASE_AUTH_URL")
        .unwrap_or("https://YOUR_PROJECT_ID.supabase.co/auth/v1/authorize?provider=google&redirect_to=hackt://auth-callback");
    
    tauri::api::shell::open(&window.shell_scope(), supabase_auth_url, None)
        .map_err(|e| e.to_string())?;
    Ok("Auth flow initiated".to_string())
}

#[tauri::command]
pub fn generate_new_session() -> String {
    Uuid::new_v4().to_string()
}

#[tauri::command]
pub async fn close_splashscreen(window: tauri::Window) {
    // Gracefully handle missing windows instead of unwrap()
    if let Some(splashscreen) = window.get_window("splashscreen") {
        let _ = splashscreen.close();
    }
    if let Some(main_window) = window.get_window("main") {
        let _ = main_window.show();
        let _ = main_window.set_focus();
    }
}

#[tauri::command]
pub async fn get_system_info() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "platform": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "note": "For accurate hardware stats, query Python backend at /api/health"
    }))
}