#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod commands;
mod permissions; // <-- ADDED: The permissions module we just built

use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu,
    SystemTrayMenuItem, WindowEvent,
};

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
// NEW: SETUP COMPLETE MARKER
// ==============================================================================
#[tauri::command]
fn mark_setup_complete(app_handle: tauri::AppHandle) -> Result<(), String> {
    let app_dir = app_handle.path_resolver().app_data_dir().ok_or("Failed to resolve app data dir")?;
    std::fs::create_dir_all(&app_dir).map_err(|e| e.to_string())?;
    
    let setup_flag = app_dir.join("setup_complete");
    std::fs::File::create(setup_flag).map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    // ==============================================================================
    // 2. DEEP LINK OS REGISTRATION (Windows)
    // ==============================================================================
    tauri_plugin_deep_link::prepare("com.hackt.runtime");

    tauri::Builder::default()
        // ==============================================================================
        // 3. SYSTEM TRAY EVENT LISTENER
        // ==============================================================================
        .system_tray(build_tray_menu())
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick { .. } => {
                if let Some(window) = app.get_window("main") {
                    window.show().unwrap();
                    window.set_focus().unwrap();
                }
            }
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "open" => {
                    if let Some(window) = app.get_window("main") {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                }
                "quit" => {
                    println!("Sending kill signal to Python Core...");
                    let _ = reqwest::blocking::Client::new()
                        .post("http://127.0.0.1:8080/api/system/shutdown")
                        .send();
                    std::process::exit(0);
                }
                "toggle_vision" => { app.emit_all("tray_toggle_vision", ()).unwrap(); }
                "toggle_mic" => { app.emit_all("tray_toggle_mic", ()).unwrap(); }
                "toggle_think" => { app.emit_all("tray_toggle_think", ()).unwrap(); }
                _ => {}
            },
            _ => {}
        })
        
        // ==============================================================================
        // 4. WINDOW HIJACKING (Zombie Prevention)
        // ==============================================================================
        .on_window_event(|event| match event.event() {
            WindowEvent::CloseRequested { api, .. } => {
                // Prevent actual closing, just hide it to keep the background daemon alive
                api.prevent_close();
                event.window().hide().unwrap();
            }
            _ => {}
        })

        // ==============================================================================
        // 5. INJECT DEEP LINK PLUGIN
        // ==============================================================================
        .plugin(tauri_plugin_deep_link::init())
        
        // ==============================================================================
        // 6. LIFECYCLE & STARTUP HOOKS
        // ==============================================================================
        .setup(|app| {
            // A. Spawn the Python AI Core silently in the background
            let _ = commands::spawn_python_backend();

            // B. FIRST-RUN SETUP CHECK
            let app_dir = app.path_resolver().app_data_dir().unwrap_or_default();
            let _ = std::fs::create_dir_all(&app_dir); // Ensure directory exists
            let setup_flag = app_dir.join("setup_complete");

            if !setup_flag.exists() {
                // It's the first time running! Redirect React to the setup wizard.
                if let Some(window) = app.get_window("main") {
                    // Use eval to safely change the React Router hash
                    window.eval("window.location.hash = '/setup'").unwrap_or_default();
                }
            }

            // C. Listen for incoming Google OAuth deep links
            let handle = app.handle();
            app.listen_global("scheme-request-received", move |event| {
                if let Some(payload) = event.payload() {
                    println!("Intercepted Deep Link: {}", payload);
                    handle.emit_all("oauth_callback", payload).unwrap();
                    
                    if let Some(window) = handle.get_window("main") {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                }
            });

            Ok(())
        })
        
        // ==============================================================================
        // 7. IPC COMMAND REGISTRATION (Cleaned & Expanded)
        // ==============================================================================
        .invoke_handler(tauri::generate_handler![
            // From commands.rs
            commands::close_splashscreen
            commands::get_system_vram,
            commands::send_chat_message,
            commands::trigger_google_auth,
            commands::spawn_python_backend,
            commands::set_monitoring_mode,
            commands::generate_new_session,
            commands::toggle_port_listener,
            commands::trigger_ide_fix_action,
            commands::sync_vault_to_cloud,
            commands::start_vision,
            commands::stop_vision,
            commands::trigger_screen_scan,
            commands::start_mic,
            commands::stop_mic,
            commands::download_model_rust, 

            // From permissions.rs
            permissions::request_microphone_permission,
            permissions::request_screen_capture_permission,
            permissions::set_startup_enabled,
            
            // From main.rs
            mark_setup_complete
        ])
        .run(tauri::generate_context!())
        .expect("Critical Error: HackT runtime failed to initialize");
}