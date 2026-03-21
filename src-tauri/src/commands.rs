use serde::{Deserialize, Serialize};
use reqwest::Client;
use tauri::api::process::Command as TauriSidecar;
use uuid::Uuid;

#[derive(Serialize)]
pub struct ChatResponse {
    pub reply: String,
    pub status: String,
}

#[derive(Serialize, Deserialize)]
pub struct ChatRequest {
    pub prompt: String,
    pub mode: String,
    pub session_id: String,
}

// ------------------------------------------------------------------
// 1. HARDWARE VRAM CHECK (Windows Specific via WMI)
// ------------------------------------------------------------------
#[tauri::command]
pub async fn get_system_vram() -> Result<u64, String> {
    #[cfg(target_os = "windows")]
    {
        use wmi::{COMLibrary, WMIConnection};
        use std::collections::HashMap;

        let com_con = COMLibrary::new().map_err(|e| e.to_string())?;
        let wmi_con = WMIConnection::new(com_con).map_err(|e| e.to_string())?;
        
        let results: Vec<HashMap<String, wmi::Variant>> = wmi_con
            .raw_query("SELECT AdapterRAM FROM Win32_VideoController")
            .map_err(|e| e.to_string())?;

        if let Some(gpu) = results.get(0) {
            if let Some(wmi::Variant::I8(ram)) = gpu.get("AdapterRAM") {
                let vram_mb = (*ram as u64) / (1024 * 1024);
                return Ok(vram_mb);
            }
        }
    }
    Ok(8192)
}

// ------------------------------------------------------------------
// 2. SPAWN PYTHON AI BACKEND (Using Tauri Sidecar)
// ------------------------------------------------------------------
#[tauri::command]
pub fn spawn_python_backend() -> Result<String, String> {
    match TauriSidecar::new_sidecar("backend_service")
        .expect("Failed to locate backend_service sidecar binary")
        .args(["--port", "8080"])
        .spawn()
    {
        Ok((_rx, child)) => {
            Ok(format!("AI Core Initialized. PID: {}", child.pid()))
        }
        Err(e) => Err(format!("Failed to start AI Core Sidecar: {}", e)),
    }
}

// ------------------------------------------------------------------
// 3. SEND CHAT TO QWEN 3.5 (Via local HTTP - Port 8080)
// ------------------------------------------------------------------
#[tauri::command]
pub async fn send_chat_message(prompt: String, mode: String, session_id: String) -> Result<ChatResponse, String> {
    let client = Client::new();
    let payload = ChatRequest { prompt, mode, session_id };

    let res = client.post("http://127.0.0.1:8080/api/chat")
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        let response_text = res.text().await.map_err(|e| e.to_string())?;
        Ok(ChatResponse {
            reply: response_text,
            status: "success".into(),
        })
    } else {
        Err(format!("Backend returned error: {}", res.status()))
    }
}

// ------------------------------------------------------------------
// 4. GOOGLE OAUTH LOGIN NATIVE (Supabase Direct)
// ------------------------------------------------------------------
#[tauri::command]
pub async fn trigger_google_auth(window: tauri::Window) -> Result<String, String> {
    let supabase_auth_url = "https://YOUR_PROJECT_ID.supabase.co/auth/v1/authorize?provider=google&redirect_to=hackt://auth-callback";
    
    tauri::api::shell::open(
        &window.shell_scope(), 
        supabase_auth_url, 
        None
    ).map_err(|e| e.to_string())?;
    
    Ok("Auth flow initiated".to_string())
}

// ------------------------------------------------------------------
// 5. SET MONITORING MODE (Active vs Passive)
// ------------------------------------------------------------------
#[tauri::command]
pub async fn set_monitoring_mode(mode: String) -> Result<String, String> {
    let client = Client::new();
    
    let res = client.post("http://127.0.0.1:8080/api/system/mode")
        .json(&serde_json::json!({ "mode": mode }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok(format!("Backend transitioned to {} mode", mode))
    } else {
        Err("Failed to update backend mode".into())
    }
}

// ------------------------------------------------------------------
// 6. SESSION UUID GENERATOR
// ------------------------------------------------------------------
#[tauri::command]
pub fn generate_new_session() -> String {
    Uuid::new_v4().to_string()
}

// ------------------------------------------------------------------
// 7. TOGGLE PORT LISTENERS (IDE & Browser Telemetry)
// ------------------------------------------------------------------
#[tauri::command]
pub async fn toggle_port_listener(port: u16, service: String, state: bool) -> Result<String, String> {
    let client = Client::new();
    let payload = serde_json::json!({ "port": port, "service": service, "state": state });

    let res = client.post("http://127.0.0.1:8080/api/system/port/toggle")
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok(format!("{} port {} toggled to {}", service, port, state))
    } else {
        Err("Failed to toggle listener port".into())
    }
}

// ------------------------------------------------------------------
// 8. TRIGGER UNIVERSAL CODE INJECTION
// ------------------------------------------------------------------
#[tauri::command]
pub async fn trigger_ide_fix_action(session_id: String, instruction: String) -> Result<String, String> {
    let client = Client::new();
    let payload = serde_json::json!({ "session_id": session_id, "instruction": instruction });

    let res = client.post("http://127.0.0.1:8080/api/action/fix-universal")
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok("Fix injected successfully".into())
    } else {
        Err("Failed to inject fix".into())
    }
}

// ------------------------------------------------------------------
// 9. CLOUD SYNC TRIGGER
// ------------------------------------------------------------------
#[tauri::command]
pub async fn sync_vault_to_cloud() -> Result<String, String> {
    let client = Client::new();
    
    let res = client.post("http://127.0.0.1:8080/api/system/sync")
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok("Vault synchronized to cloud".into())
    } else {
        Err("Failed to synchronize vault".into())
    }
}

// ------------------------------------------------------------------
// 10. VISION & OCR CONTROLS
// ------------------------------------------------------------------
#[tauri::command]
pub async fn start_vision() -> Result<String, String> {
    let client = Client::new();
    let res = client.post("http://127.0.0.1:8080/api/vision/start")
        .send().await.map_err(|e| e.to_string())?;
    if res.status().is_success() { Ok("Vision OCR Engaged".into()) } 
    else { Err("Failed to start Vision".into()) }
}

#[tauri::command]
pub async fn stop_vision() -> Result<String, String> {
    let client = Client::new();
    let res = client.post("http://127.0.0.1:8080/api/vision/stop")
        .send().await.map_err(|e| e.to_string())?;
    if res.status().is_success() { Ok("Vision OCR Disengaged".into()) } 
    else { Err("Failed to stop Vision".into()) }
}

#[tauri::command]
pub async fn trigger_screen_scan() -> Result<String, String> {
    let client = Client::new();
    let res = client.post("http://127.0.0.1:8080/api/vision/scan-now")
        .send().await.map_err(|e| e.to_string())?;
    if res.status().is_success() { Ok("Manual Screen Scan Triggered".into()) } 
    else { Err("Scan failed".into()) }
}

// ------------------------------------------------------------------
// 11. MICROPHONE & STT CONTROLS
// ------------------------------------------------------------------
#[tauri::command]
pub async fn start_mic() -> Result<String, String> {
    let client = Client::new();
    let res = client.post("http://127.0.0.1:8080/api/audio/mic-start")
        .send().await.map_err(|e| e.to_string())?;
    if res.status().is_success() { Ok("Faster-Whisper Listening".into()) } 
    else { Err("Failed to start Microphone".into()) }
}

#[tauri::command]
pub async fn stop_mic() -> Result<String, String> {
    let client = Client::new();
    let res = client.post("http://127.0.0.1:8080/api/audio/mic-stop")
        .send().await.map_err(|e| e.to_string())?;
    if res.status().is_success() { Ok("Microphone Disengaged".into()) } 
    else { Err("Failed to stop Microphone".into()) }
}