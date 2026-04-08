#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod commands;
mod permissions;

use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu,
    SystemTrayMenuItem, WindowEvent,
};
use std::sync::Mutex;

// ==============================================================================
// 1. SYSTEM TRAY BUILDER
// ==============================================================================
fn build_tray_menu() -> SystemTray {
    let toggle_mic = CustomMenuItem::new("toggle_mic".to_string(), "🎤 Mic: Toggle");
    let toggle_vision = CustomMenuItem::new("toggle_vision".to_string(), "👁️ Vision: Toggle");
    let toggle_think = CustomMenuItem::new("toggle_think".to_string(), "🧠 Thinking: Toggle");
    
    let tray_menu = SystemTrayMenu::new()
        .add_item(CustomMenuItem::new("status".to_string(), "PASSIVE MONITOR ACTIVE").disabled())
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(toggle_mic)
        .add_item(toggle_vision)
        .add_item(toggle_think)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(CustomMenuItem::new("open".to_string(), "Restore Dashboard"))
        .add_item(CustomMenuItem::new("quit".to_string(), "Terminate Engine"));
        
    SystemTray::new().with_menu(tray_menu)
}

// ==============================================================================
// 2. SETUP COMPLETE MARKER (Thread-Safe)
// ==============================================================================
#[tauri::command]
fn mark_setup_complete(app_handle: tauri::AppHandle) -> Result<(), String> {
    let app_dir = app_handle.path_resolver().app_data_dir()
        .ok_or("Failed to resolve app data dir")?;
    std::fs::create_dir_all(&app_dir).map_err(|e| e.to_string())?;
    
    let setup_flag = app_dir.join("setup_complete");
    std::fs::File::create(setup_flag).map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    // Register the custom protocol handler BEFORE the app boots
    tauri_plugin_deep_link::prepare("com.hackt.runtime");

    tauri::Builder::default()
        // 🔥 FIX: Properly manage the BackendState so the app doesn't panic
        .manage(commands::BackendState(Mutex::new(None)))
        
        // ==============================================================================
        // 3. SYSTEM TRAY EVENT LISTENER
        // ==============================================================================
        .system_tray(build_tray_menu())
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick { .. } => {
                if let Some(window) = app.get_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "open" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "quit" => {
                    println!("🛑 OS-Level Shutdown sequence initiated...");
                    
                    // ✅ FIX: Use .inner() to satisfy the borrow checker during tray shutdown
                    let state = app.state::<commands::BackendState>();
                    if let Ok(mut backend_guard) = state.inner().0.lock() {
                        if let Some(mut child) = backend_guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    } else {
                        eprintln!("⚠️ Failed to acquire backend state lock during shutdown");
                    }
                    
                    app.exit(0);
                }
                "toggle_vision" => { let _ = app.emit_all("tray_toggle_vision", ()); }
                "toggle_mic" => { let _ = app.emit_all("tray_toggle_mic", ()); }
                "toggle_think" => { let _ = app.emit_all("tray_toggle_think", ()); }
                _ => {}
            },
            _ => {}
        })
        
        // ==============================================================================
        // 4. WINDOW HIJACKING (Zombie Prevention)
        // ==============================================================================
        .on_window_event(|event| match event.event() {
            WindowEvent::CloseRequested { api, .. } => {
                api.prevent_close();
                let _ = event.window().hide();
            }
            _ => {}
        })

        // ==============================================================================
        // 5. LIFECYCLE & STARTUP HOOKS (Deep Link Registered Here)
        // ==============================================================================
        .setup(|app| {
            let handle = app.handle();

            // ✅ FIX: Deep link registration belongs in setup(), not as a plugin()
            let _ = tauri_plugin_deep_link::register("hackt", move |request| {
                println!("🔗 Deep link received: {}", request);
                // Broadcast to React
                let _ = handle.emit_all("oauth_callback", request);
            });

            // App data directory and setup flag
            let app_dir = app.path_resolver().app_data_dir().unwrap_or_default();
            let _ = std::fs::create_dir_all(&app_dir);
            let setup_flag = app_dir.join("setup_complete");

            if setup_flag.exists() {
                let state = app.state::<commands::BackendState>();
                let _ = commands::spawn_python_backend(app.app_handle(), state);
            } else {
                if let Some(window) = app.get_window("main") {
                    let _ = window.eval("window.location.hash = '/setup'");
                    
                    let window_clone = window.clone();
                    std::thread::spawn(move || {
                        std::thread::sleep(std::time::Duration::from_millis(100));
                        let _ = window_clone.show();
                        let _ = window_clone.set_focus();
                    });
                    
                    if let Some(splash) = app.get_window("splashscreen") {
                        let _ = splash.close();
                    }
                }
            }

            Ok(())
        })
        
        // ==============================================================================
        // 6. IPC COMMAND REGISTRATION 
        // ==============================================================================
        .invoke_handler(tauri::generate_handler![
            commands::run_model_bootstrapper,
            commands::spawn_python_backend,
            commands::trigger_google_auth,
            commands::generate_new_session,
            commands::close_splashscreen,
            commands::get_system_info,

            // Permission Helpers (permissions.rs)
            permissions::request_microphone_permission,
            permissions::request_screen_capture_permission,
            permissions::set_startup_enabled,
            
            // Setup Marker (main.rs)
            mark_setup_complete
        ])
        .run(tauri::generate_context!())
        .expect("🔥 Critical Error: HackT runtime failed to initialize");
}