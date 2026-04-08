; Custom NSIS Installer Script for HackT Runtime
; Injects dual-pane UI (Sidebar + Background) and permission routing

!include "MUI2.nsh"

; Define custom pages
!define MUI_PAGE_HEADER_TEXT "HackT Runtime Setup"
!define MUI_PAGE_HEADER_SUBTEXT "Please review the following before installation"

Page custom ShowPermissionsPage SavePermissions
Page custom ShowFirstRunSetup SaveFirstRunSetup

; Variables
Var CheckboxMic
Var CheckboxScreen
Var CheckboxNetwork
Var CheckboxStartup
Var DownloadModels
Var BgImage
Var BgImageHandle
Var SidebarImage
Var SidebarImageHandle

; Extract BOTH images to a temp folder when the installer starts
Function .onInit
    InitPluginsDir
    File "/oname=$PLUGINSDIR\background.bmp" "..\installer-assets\background.bmp"
    File "/oname=$PLUGINSDIR\sidebar.bmp" "..\installer-assets\sidebar.bmp"
FunctionEnd

; ==========================================
; PERMISSIONS PAGE
; ==========================================
Function ShowPermissionsPage
    nsDialogs::Create 1018
    Pop $0

    ; 1. Draw the Sidebar on the Left (0 to 30% width)
    ${NSD_CreateBitmap} 0 0 30% 100% ""
    Pop $SidebarImage
    ${NSD_SetImage} $SidebarImage "$PLUGINSDIR\sidebar.bmp" $SidebarImageHandle

    ; 2. Draw the Background on the Right (30% to 100% width)
    ${NSD_CreateBitmap} 30% 0 70% 100% ""
    Pop $BgImage
    ${NSD_SetImage} $BgImage "$PLUGINSDIR\background.bmp" $BgImageHandle

    ; 3. Create labels (Pushed to X=32% to clear the sidebar)
    ${NSD_CreateLabel} 32% 5u 65% 30u "HackT Runtime requires the following permissions. All data processing occurs locally."
    Pop $1
    SetCtlColors $1 0xFFFFFF transparent ; White text, transparent background

    ; 4. Create Checkboxes (Pushed to X=35% for slight indentation)
    ${NSD_CreateCheckbox} 35% 45u 60% 15u "🎤 Microphone Access (Voice Commands)"
    Pop $CheckboxMic
    SetCtlColors $CheckboxMic 0xFFFFFF transparent

    ${NSD_CreateCheckbox} 35% 65u 60% 15u "👁️ Screen Capture (Threat Detection)"
    Pop $CheckboxScreen
    SetCtlColors $CheckboxScreen 0xFFFFFF transparent

    ${NSD_CreateCheckbox} 35% 85u 60% 15u "🌐 Network Proxy (Phishing Detection)"
    Pop $CheckboxNetwork
    SetCtlColors $CheckboxNetwork 0xFFFFFF transparent

    ${NSD_CreateCheckbox} 35% 105u 60% 15u "🚀 Start with Windows (Optional)"
    Pop $CheckboxStartup
    SetCtlColors $CheckboxStartup 0xFFFFFF transparent

    nsDialogs::Show
    
    ; Clean up image handles from memory to prevent memory leaks
    ${NSD_FreeImage} $BgImageHandle
    ${NSD_FreeImage} $SidebarImageHandle
FunctionEnd

Function SavePermissions
    ${NSD_GetState} $CheckboxMic $0
    ${NSD_GetState} $CheckboxScreen $1
    ${NSD_GetState} $CheckboxNetwork $2
    ${NSD_GetState} $CheckboxStartup $3
    
    WriteRegStr HKCU "Software\HackT\Runtime" "MicEnabled" $0
    WriteRegStr HKCU "Software\HackT\Runtime" "ScreenEnabled" $1
    WriteRegStr HKCU "Software\HackT\Runtime" "NetworkEnabled" $2
    WriteRegStr HKCU "Software\HackT\Runtime" "StartWithWindows" $3
FunctionEnd

; ==========================================
; FIRST RUN SETUP PAGE
; ==========================================
Function ShowFirstRunSetup
    nsDialogs::Create 1018
    Pop $0

    ; Draw the Sidebar
    ${NSD_CreateBitmap} 0 0 30% 100% ""
    Pop $SidebarImage
    ${NSD_SetImage} $SidebarImage "$PLUGINSDIR\sidebar.bmp" $SidebarImageHandle

    ; Draw the Background
    ${NSD_CreateBitmap} 30% 0 70% 100% ""
    Pop $BgImage
    ${NSD_SetImage} $BgImage "$PLUGINSDIR\background.bmp" $BgImageHandle

    ; Content pushed right to X=32%
    ${NSD_CreateLabel} 32% 5u 65% 20u "Model Download Configuration"
    Pop $1
    SetCtlColors $1 0x00F3FF transparent ; Cyberpunk Cyan text

    ${NSD_CreateLabel} 32% 30u 65% 40u "HackT Runtime requires AI models (~4.5 GB total). Models will be downloaded from GitHub Releases. Internet connection required."
    Pop $2
    SetCtlColors $2 0xFFFFFF transparent

    ${NSD_CreateCheckbox} 35% 80u 60% 15u "📥 Download models during initial setup"
    Pop $DownloadModels
    SetCtlColors $DownloadModels 0xFFFFFF transparent
    ${NSD_Check} $DownloadModels ; Checked by default

    nsDialogs::Show
    
    ${NSD_FreeImage} $BgImageHandle
    ${NSD_FreeImage} $SidebarImageHandle
FunctionEnd

Function SaveFirstRunSetup
    ${NSD_GetState} $DownloadModels $0
    WriteRegStr HKCU "Software\HackT\Runtime" "DownloadModels" $0
FunctionEnd