// src-tauri/build.rs

fn main() {
    // 1. Create custom Windows attributes
    let mut windows = tauri_build::WindowsAttributes::new();
    
    // 2. Inject your custom app.manifest (forces requireAdministrator)
    windows = windows.app_manifest(include_str!("app.manifest"));
    
    // 3. Build Tauri with the custom attributes
    let attrs = tauri_build::Attributes::new().windows_attributes(windows);
    
    tauri_build::try_build(attrs).expect("Failed to run tauri-build");
}