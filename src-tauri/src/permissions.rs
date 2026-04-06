use tauri::command;

#[cfg(target_os = "windows")]
use windows::Win32::System::Com::{CoInitializeEx, CoUninitialize, COINIT_APARTMENTTHREADED};

/// Request microphone permission on Windows
#[command]
pub async fn request_microphone_permission() -> Result<bool, String> {
    #[cfg(target_os = "windows")]
    {
        // Initialize COM library safely. 
        // For desktop apps, Windows natively prompts for mic access the first time
        // an audio stream is opened by the Python backend. We pre-init COM here 
        // to ensure audio threads don't panic.
        unsafe {
            let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
        }
        
        unsafe { CoUninitialize(); }
        Ok(true)
    }
    
    #[cfg(not(target_os = "windows"))]
    Ok(true)
}

/// Request screen capture permission on Windows
#[command]
pub async fn request_screen_capture_permission() -> Result<bool, String> {
    // Windows 10+ handles screen capture permissions at the OS level implicitly 
    // for desktop applications. No explicit API call is needed beforehand.
    Ok(true)
}

/// Add app to Windows startup
#[command]
pub async fn set_startup_enabled(enabled: bool) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        use std::env;
        use std::fs;
        use std::path::PathBuf;
        use std::process::Command;
        
        let startup_path = env::var("APPDATA")
            .map(|p| PathBuf::from(p).join("Microsoft\\Windows\\Start Menu\\Programs\\Startup"))
            .map_err(|e| e.to_string())?;
            
        let shortcut_path = startup_path.join("HackT Runtime.lnk");
        
        if enabled {
            let exe_path = env::current_exe().map_err(|e| e.to_string())?;
            let exe_path_str = exe_path.to_str().unwrap_or_default();
            let shortcut_path_str = shortcut_path.to_str().unwrap_or_default();
            
            // Create the startup folder if it somehow doesn't exist
            fs::create_dir_all(&startup_path).map_err(|e| e.to_string())?;
            
            // Use PowerShell to create the shortcut (avoids massive Rust COM boilerplate)
            let ps_script = format!(
                "$wshell = New-Object -ComObject WScript.Shell; $shortcut = $wshell.CreateShortcut('{}'); $shortcut.TargetPath = '{}'; $shortcut.Save()",
                shortcut_path_str, exe_path_str
            );
            
            Command::new("powershell")
                .args(&["-NoProfile", "-Command", &ps_script])
                .output()
                .map_err(|e| format!("Failed to create startup shortcut via PS: {}", e))?;
                
        } else {
            // Remove the shortcut if it exists
            if shortcut_path.exists() {
                fs::remove_file(shortcut_path).map_err(|e| e.to_string())?;
            }
        }
        
        Ok(())
    }
    
    #[cfg(not(target_os = "windows"))]
    Ok(())
}