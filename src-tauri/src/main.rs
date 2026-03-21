#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod commands;

use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu,
    SystemTrayMenuItem, WindowEvent,
};

// ==============================================================================
// 1. SYSTEM TRAY BUILDER
// ==============================================================================
fn build_tray_menu() -> SystemTray {
    // Toggles with state indicators
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

fn main() {
    // ==============================================================================
    // 2. DEEP LINK OS REGISTRATION (Windows)
    // Registers 'hackt://' with the Windows Registry before Tauri even boots
    // ==============================================================================
    tauri_plugin_deep_link::prepare("com.hackt.runtime");

    tauri::Builder::default()
        // ==============================================================================
        // 3. SYSTEM TRAY EVENT LISTENER
        // ==============================================================================
        .system_tray(build_tray_menu())
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick { .. } => {
                // Bring GUI to front on left click
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
                    // NUCLEAR KILL SWITCH: Send blocking HTTP request to Python
                    println!("Sending kill signal to Python Core...");
                    let _ = reqwest::blocking::Client::new()
                        .post("http://127.0.0.1:8080/api/system/shutdown")
                        .send();
                    
                    // Once Python is dead, kill the Rust app
                    std::process::exit(0);
                }
                // Route Tray Toggles to React via Global Events
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
                // Prevent the OS from killing the app when "X" is clicked
                api.prevent_close();
                // Hide it to the system tray instead
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

            // B. Listen for incoming Google OAuth deep links
            let handle = app.handle();
            app.listen_global("scheme-request-received", move |event| {
                if let Some(payload) = event.payload() {
                    println!("Intercepted Deep Link: {}", payload);
                    
                    // Forward the URL (containing the Supabase token) to React
                    handle.emit_all("oauth_callback", payload).unwrap();
                    
                    // Automatically pop the window back open so the user sees they logged in
                    if let Some(window) = handle.get_window("main") {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                }
            });

            Ok(())
        })
        
        // ==============================================================================
        // 7. IPC COMMAND REGISTRATION (React -> Rust -> Python)
        // ==============================================================================
        .invoke_handler(tauri::generate_handler![
            commands::get_system_vram,
            commands::send_chat_message,
            commands::trigger_google_auth,
            commands::spawn_python_backend,
            commands::set_monitoring_mode,
            commands::generate_new_session,
            commands::toggle_port_listener,
            commands::trigger_ide_fix_action,
            commands::sync_vault_to_cloud
        ])
        .run(tauri::generate_context!())
        .expect("Critical Error: HackT runtime failed to initialize");
}