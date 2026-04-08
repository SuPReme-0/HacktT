use tauri::command;

/// Request microphone permission on Windows
#[command]
pub async fn request_microphone_permission() -> Result<bool, String> {
    // Windows 10/11 natively prompts the user the first time the audio stream
    // is physically opened by the backend. We return true here to 
    // allow the React UI to proceed smoothly through the Setup Wizard.
    Ok(true)
}

/// Request screen capture permission on Windows
#[command]
pub async fn request_screen_capture_permission() -> Result<bool, String> {
    // Windows handles screen capture permissions at the OS level implicitly 
    // for standard desktop Win32 applications. No pre-flight API call needed.
    Ok(true)
}

/// Add app to Windows startup via Registry (AV-Safe Method)
#[command]
pub async fn set_startup_enabled(enabled: bool) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        use std::env;
        use std::process::Command;
        
        let exe_path = env::current_exe().map_err(|e| e.to_string())?;
        let exe_path_str = exe_path.to_str().unwrap_or_default();
        
        // Using standard Windows reg.exe is much safer than spawning PowerShell.
        // It modifies the CurrentVersion\Run registry key natively without triggering EDRs.
        if enabled {
            let output = Command::new("reg")
                .args([
                    "add", 
                    "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                    "/v", "HackT Sovereign Core", 
                    "/t", "REG_SZ", 
                    "/d", &format!("\"{}\"", exe_path_str), 
                    "/f"
                ])
                .output()
                .map_err(|e| format!("Failed to execute reg.exe: {}", e))?;
                
            if !output.status.success() {
                return Err("Registry modification failed. Ensure proper permissions.".to_string());
            }
        } else {
            // Remove from Run key
            let _ = Command::new("reg")
                .args([
                    "delete", 
                    "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                    "/v", "HackT Sovereign Core", 
                    "/f"
                ])
                .output(); // Ignore errors here in case the key doesn't exist yet
        }
        
        Ok(())
    }
    
    #[cfg(not(target_os = "windows"))]
    Ok(())
}