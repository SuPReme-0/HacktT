import React, { useState, useEffect } from 'react';
import { useSystemStore } from '../store/systemStore';
import { 
  Mic, Monitor, Code, Globe, Cloud, ShieldAlert, 
  LogOut, User as UserIcon, Lock, RefreshCw, 
  CheckCircle, AlertTriangle, Info, ExternalLink,
  Zap, Download, Shield
} from 'lucide-react';

export default function Settings() {
  const { 
    permissions, 
    togglePermission, 
    user, 
    logout, 
    loginWithGoogle, 
    systemVRAM,
    initSystem,
    checkSession,
    mode,
    toggleMode
  } = useSystemStore();

  // Local UI States
  const [loadingPermissions, setLoadingPermissions] = useState<Record<string, boolean>>({});
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date>(new Date());
  const [toasts, setToasts] = useState<Array<{ id: number; message: string; type: 'success' | 'error' | 'info' }>>([]);
  const [isInitializing, setIsInitializing] = useState(true);

  // Toast notification handler
  const addToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  // Initialize and verify session on mount
  useEffect(() => {
    const init = async () => {
      setIsInitializing(true);
      try {
        await initSystem();
        await checkSession();
      } catch (error) {
        console.error('Initialization failed:', error);
        addToast('Failed to initialize system. Check backend connection.', 'error');
      } finally {
        setIsInitializing(false);
        setLastChecked(new Date());
      }
    };
    init();
  }, [initSystem, checkSession]);

  // Settings configuration
  const settingsConfig = [
    {
      id: 'visionEnabled',
      icon: Monitor,
      title: 'Florence-2 Vision OCR',
      desc: 'Allow HackT to capture screen frames for localized threat detection.',
      color: 'text-[#00f3ff]',
      border: 'border-[#00f3ff]',
      requiresVRAM: 6144,
      lockMessage: 'Insufficient VRAM (6GB Required)',
      tooltip: 'Enables real-time screen analysis for phishing detection and UI element recognition.',
      requiresExtension: false
    },
    {
      id: 'micEnabled',
      icon: Mic,
      title: 'Microphone (Faster-Whisper)',
      desc: 'Enable local STT (Speech-to-Text) for hands-free operator commands.',
      color: 'text-[#00f3ff]',
      border: 'border-[#00f3ff]',
      requiresVRAM: 0,
      tooltip: 'Activates continuous voice listening with local transcription. No audio leaves your device.',
      requiresExtension: false
    },
    {
      id: 'ideIntegration',
      icon: Code,
      title: 'IDE Socket Listener (Port 8081)',
      desc: 'Open local WebSocket to receive live code streams from your editor.',
      color: 'text-[#bc13fe]',
      border: 'border-[#bc13fe]',
      requiresVRAM: 0,
      tooltip: 'Connects to VS Code / JetBrains extensions for real-time code security analysis.',
      requiresExtension: true,
      extensionUrl: 'https://marketplace.visualstudio.com/items?itemName=hackt.ide-extension'
    },
    {
      id: 'browserIntegration',
      icon: Globe,
      title: 'Browser Proxy Listener (Port 8082)',
      desc: 'Allow HackT Chrome Extension to send webpage data for phishing analysis.',
      color: 'text-[#bc13fe]',
      border: 'border-[#bc13fe]',
      requiresVRAM: 0,
      tooltip: 'Monitors browser traffic through local proxy. Requires Chrome extension installation.',
      requiresExtension: true,
      extensionUrl: 'https://chrome.google.com/webstore/detail/hackt-browser-extension'
    },
    {
      id: 'cloudSync',
      icon: Cloud,
      title: 'Supabase Cloud Sync',
      desc: 'Periodically backup your encrypted Knowledge Vault history to the cloud.',
      color: 'text-gray-400',
      border: 'border-gray-600',
      requiresVRAM: 0,
      tooltip: 'Encrypted backup of chat history and security discoveries to your Supabase account.',
      requiresExtension: false
    }
  ];

  const handleTogglePermission = async (key: keyof typeof permissions) => {
    if (loadingPermissions[key] || isInitializing) return;
    
    setLoadingPermissions(prev => ({ ...prev, [key]: true }));
    
    try {
      await togglePermission(key);
      
      const newState = !permissions[key];
      addToast(
        `${key.replace(/([A-Z])/g, ' $1').trim()} ${newState ? 'enabled' : 'disabled'}`,
        newState ? 'success' : 'info'
      );
    } catch (error: any) {
      addToast(`Failed to toggle ${key}. ${error.message || 'Check backend connection.'}`, 'error');
    } finally {
      setLoadingPermissions(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleRefreshHardware = async () => {
    setIsInitializing(true);
    try {
      await initSystem();
      addToast('Hardware telemetry refreshed', 'success');
    } catch (error: any) {
      addToast(`Failed to refresh: ${error.message}`, 'error');
    } finally {
      setIsInitializing(false);
      setLastChecked(new Date());
    }
  };

  const handleLogout = async () => {
    setShowLogoutConfirm(false);
    try {
      await logout();
      addToast('Session terminated. Connection severed.', 'info');
    } catch (error: any) {
      addToast(`Logout failed: ${error.message}`, 'error');
    }
  };

  const handleModeToggle = async () => {
    try {
      await toggleMode();
      addToast(`Switched to ${mode === 'active' ? 'Passive' : 'Active'} Mode`, 'success');
    } catch (error: any) {
      addToast(`Mode switch failed: ${error.message}`, 'error');
    }
  };

  const getVRAMStatus = () => {
    if (systemVRAM === 0) return { text: 'Scanning...', color: 'text-yellow-500', percent: 0 };
    const vramGB = (systemVRAM / 1024).toFixed(1);
    const percent = Math.min((systemVRAM / 8192) * 100, 100);
    if (systemVRAM >= 6144) return { text: `${vramGB} GB`, color: 'text-green-400', percent };
    return { text: `${vramGB} GB (Limited)`, color: 'text-yellow-500', percent };
  };

  const vramStatus = getVRAMStatus();
  const isPassiveAvailable = systemVRAM >= 6144;

  return (
    <div className="h-full flex flex-col p-8 text-[#e0e0e0] font-mono overflow-y-auto gloomy-scroll relative z-10">
      
      {/* ==================== TOAST NOTIFICATIONS ==================== */}
      <div className="fixed top-20 right-8 z-50 space-y-2" role="alert" aria-live="polite">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`panel-3d px-4 py-3 rounded-lg border text-xs tracking-widest flex items-center gap-2 animate-in slide-in-from-right-2 ${
              toast.type === 'success' ? 'border-green-500/50 bg-green-900/20 text-green-400' :
              toast.type === 'error' ? 'border-red-500/50 bg-red-900/20 text-red-400' :
              'border-[#00f3ff]/50 bg-[#00f3ff]/10 text-[#00f3ff]'
            }`}
          >
            {toast.type === 'success' && <CheckCircle size={14} aria-hidden="true" />}
            {toast.type === 'error' && <AlertTriangle size={14} aria-hidden="true" />}
            {toast.type === 'info' && <Info size={14} aria-hidden="true" />}
            {toast.message}
          </div>
        ))}
      </div>

      {/* ==================== HEADER ==================== */}
      <div className="mb-8 border-b border-[#1f1f1f] pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-widest text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.2)]">
            SYSTEM <span className="text-[#00f3ff]">MATRIX</span>
          </h2>
          <p className="text-xs text-gray-500 mt-2 uppercase tracking-widest">
            Manage Hardware, Auth & Network • Last checked: {lastChecked.toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleRefreshHardware}
            disabled={isInitializing}
            className="p-2 rounded-lg border border-[#1f1f1f] hover:border-[#00f3ff]/50 hover:text-[#00f3ff] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh Hardware Telemetry"
            aria-label="Refresh hardware telemetry"
          >
            <RefreshCw size={20} className={isInitializing ? 'animate-spin' : ''} />
          </button>
          <ShieldAlert className="text-[#1f1f1f]" size={48} aria-hidden="true" />
        </div>
      </div>

      <div className="flex flex-col xl:flex-row gap-8 max-w-7xl">
        
        {/* ==================== LEFT COLUMN: OPERATOR IDENTITY ==================== */}
        <div className="w-full xl:w-1/3 flex flex-col gap-6">
          
          {/* Identity Panel */}
          <div className="panel-3d p-6 rounded-xl border border-[#1f1f1f]/50 bg-[#0a0a0a]/60 relative overflow-hidden" role="region" aria-label="Operator Identity">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#00f3ff]/5 rounded-full blur-3xl pointer-events-none" />
            
            <h3 className="text-[#00f3ff] text-sm font-bold tracking-widest mb-6 flex items-center gap-2">
              <UserIcon size={16} aria-hidden="true" /> OPERATOR IDENTITY
            </h3>
            
            {user ? (
              <div className="flex flex-col items-center text-center gap-4">
                <div className="relative group">
                  <img 
                    src={user.avatarUrl} 
                    alt="Operator avatar" 
                    className="w-24 h-24 rounded-full border-2 border-[#bc13fe] shadow-[0_0_15px_rgba(188,19,254,0.4)] p-1 transition-transform duration-300 group-hover:scale-105"
                  />
                  <div className="absolute bottom-1 right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-[#0a0a0a] animate-pulse" />
                  <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[9px] text-green-400 uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
                    Online
                  </div>
                </div>
                <div>
                  <h4 className="text-white font-bold text-lg">{user.name}</h4>
                  <p className="text-xs text-gray-400">{user.email}</p>
                  <div className="mt-2 flex items-center justify-center gap-2 text-[10px] text-[#00f3ff] uppercase tracking-widest">
                    <div className="h-1.5 w-1.5 rounded-full bg-[#00f3ff] shadow-[0_0_5px_#00f3ff] animate-pulse" />
                    Session Active
                  </div>
                </div>
                
                {!showLogoutConfirm ? (
                  <button 
                    onClick={() => setShowLogoutConfirm(true)}
                    className="mt-4 w-full py-2 px-4 rounded bg-[#1f1f1f] hover:bg-red-900/40 hover:text-red-400 text-gray-400 text-xs tracking-widest uppercase transition-all duration-300 flex items-center justify-center gap-2 border border-transparent hover:border-red-900"
                    aria-label="Sever connection and logout"
                  >
                    <LogOut size={14} aria-hidden="true" /> Sever Connection
                  </button>
                ) : (
                  <div className="mt-4 w-full space-y-2" role="alertdialog" aria-labelledby="logout-confirm">
                    <p id="logout-confirm" className="text-[10px] text-red-400 uppercase tracking-widest">Confirm Termination?</p>
                    <div className="flex gap-2">
                      <button 
                        onClick={handleLogout}
                        className="flex-1 py-2 rounded bg-red-900/40 text-red-400 text-xs tracking-widest uppercase hover:bg-red-900/60 transition-colors"
                        aria-label="Confirm logout"
                      >
                        Yes
                      </button>
                      <button 
                        onClick={() => setShowLogoutConfirm(false)}
                        className="flex-1 py-2 rounded bg-[#1f1f1f] text-gray-400 text-xs tracking-widest uppercase hover:bg-[#2a2a2a] transition-colors"
                        aria-label="Cancel logout"
                      >
                        No
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center text-center gap-4 py-4">
                <div className="w-20 h-20 rounded-full bg-[#1f1f1f] flex items-center justify-center text-gray-600">
                  <UserIcon size={32} aria-hidden="true" />
                </div>
                <p className="text-xs text-gray-500">No active operator profile.</p>
                <button 
                  onClick={loginWithGoogle}
                  disabled={isInitializing}
                  className="mt-2 w-full py-3 px-4 rounded bg-[#00f3ff]/10 hover:bg-[#00f3ff]/20 text-[#00f3ff] text-xs font-bold tracking-widest uppercase transition-all duration-300 border border-[#00f3ff]/30 hover:border-[#00f3ff] shadow-[0_0_10px_rgba(0,243,255,0.1)] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Initialize Google OAuth login"
                >
                  <ExternalLink size={14} aria-hidden="true" /> Initialize Google Uplink
                </button>
                <p className="text-[9px] text-gray-600 mt-2">
                  Opens system browser for secure OAuth
                </p>
              </div>
            )}
          </div>

          {/* VRAM Telemetry Panel */}
          <div className="panel-3d p-6 rounded-xl border border-[#1f1f1f]/50 bg-[#0a0a0a]/60" role="region" aria-label="Hardware Telemetry">
            <h3 className="text-gray-400 text-xs font-bold tracking-widest mb-4 uppercase flex items-center gap-2">
              <RefreshCw size={12} aria-hidden="true" /> Hardware Telemetry
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-end">
                <span className="text-gray-500 text-xs">Dedicated VRAM:</span>
                <span className={`text-lg font-bold ${vramStatus.color}`} aria-live="polite">
                  {vramStatus.text}
                </span>
              </div>
              
              {/* VRAM Progress Bar */}
              <div className="relative h-2 bg-[#1f1f1f] rounded-full overflow-hidden" role="progressbar" aria-valuenow={vramStatus.percent} aria-valuemin={0} aria-valuemax={100}>
                <div 
                  className={`absolute top-0 left-0 h-full transition-all duration-500 ${
                    systemVRAM >= 6144 ? 'bg-gradient-to-r from-green-500 to-green-400' :
                    systemVRAM >= 4096 ? 'bg-gradient-to-r from-yellow-500 to-yellow-400' :
                    'bg-gradient-to-r from-red-500 to-red-400'
                  }`}
                  style={{ width: `${vramStatus.percent}%` }}
                />
              </div>
              
              <div className="flex justify-between text-[9px] text-gray-600 uppercase tracking-widest">
                <span>0 GB</span>
                <span>8 GB</span>
              </div>

              {/* Mode Toggle Section */}
              <div className="pt-4 border-t border-[#1f1f1f]">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-gray-500 text-xs">Current Mode:</span>
                  <span className={`text-xs font-bold uppercase tracking-widest ${
                    mode === 'passive' ? 'text-[#bc13fe]' : 'text-[#00f3ff]'
                  }`}>
                    {mode === 'passive' ? '🟣 PASSIVE (Full)' : '🔵 ACTIVE (Basic)'}
                  </span>
                </div>
                <button
                  onClick={handleModeToggle}
                  disabled={isInitializing || (mode === 'active' && !isPassiveAvailable)}
                  className={`w-full py-2 rounded-lg border text-xs font-bold uppercase tracking-widest transition-all duration-300 flex items-center justify-center gap-2 ${
                    mode === 'passive'
                      ? 'border-[#bc13fe]/50 text-[#bc13fe] hover:bg-[#bc13fe]/10'
                      : isPassiveAvailable
                        ? 'border-[#00f3ff]/50 text-[#00f3ff] hover:bg-[#00f3ff]/10'
                        : 'border-gray-700 text-gray-600 cursor-not-allowed'
                  } disabled:opacity-50`}
                  aria-label={`Switch to ${mode === 'active' ? 'Passive' : 'Active'} mode`}
                >
                  <Zap size={14} aria-hidden="true" />
                  {mode === 'passive' ? 'Switch to Active' : 'Switch to Passive'}
                </button>
                {!isPassiveAvailable && mode === 'active' && (
                  <p className="text-[8px] text-red-400 mt-2 text-center">
                    <AlertTriangle size={10} className="inline mr-1" />
                    Requires 6GB+ VRAM
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Quick Tips Panel */}
          <div className="panel-3d p-6 rounded-xl border border-[#1f1f1f]/50 bg-[#0a0a0a]/60" role="region" aria-label="Quick Tips">
            <h3 className="text-gray-400 text-xs font-bold tracking-widest mb-4 uppercase flex items-center gap-2">
              <Info size={12} aria-hidden="true" /> Quick Tips
            </h3>
            <ul className="space-y-2 text-[10px] text-gray-500">
              <li className="flex items-start gap-2">
                <span className="text-[#00f3ff]" aria-hidden="true">•</span>
                Passive Mode requires 6GB+ VRAM for Florence-2 Vision
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#bc13fe]" aria-hidden="true">•</span>
                IDE Integration requires VS Code / JetBrains extension
              </li>
              <li className="flex items-start gap-2">
                <span className="text-gray-400" aria-hidden="true">•</span>
                All processing is 100% local. No data leaves your device.
              </li>
            </ul>
          </div>
        </div>

        {/* ==================== RIGHT COLUMN: PERMISSIONS GRID ==================== */}
        <div className="w-full xl:w-2/3 grid grid-cols-1 md:grid-cols-2 gap-6" role="region" aria-label="Permission Settings">
          {settingsConfig.map((setting) => {
            const Icon = setting.icon;
            const isEnabled = permissions[setting.id as keyof typeof permissions];
            const isLoading = loadingPermissions[setting.id];
            
            const isHardwareLocked = systemVRAM > 0 && systemVRAM < setting.requiresVRAM;
            const isDisabled = isHardwareLocked || isLoading || isInitializing;

            return (
              <div 
                key={setting.id} 
                className={`panel-3d p-6 rounded-xl border transition-all duration-300 flex items-start gap-4 group ${
                  isHardwareLocked 
                    ? 'border-red-900/30 bg-red-950/10 opacity-60 cursor-not-allowed' 
                    : isEnabled 
                      ? `${setting.border}/40 shadow-[0_0_20px_rgba(0,0,0,0.5)] bg-[#0a0a0a]/80` 
                      : 'border-[#1f1f1f]/50 hover:bg-[#0a0a0a]/80 opacity-70 hover:opacity-100'
                }`}
                role="group"
                aria-labelledby={`setting-${setting.id}`}
              >
                {/* Icon Container */}
                <div className={`p-3 rounded-lg bg-[#1f1f1f]/50 transition-all duration-300 ${
                  isHardwareLocked ? 'text-red-500' : isEnabled ? setting.color : 'text-gray-600'
                } ${isLoading ? 'animate-pulse' : ''}`} aria-hidden="true">
                  {isHardwareLocked ? <Lock size={24} /> : isLoading ? <RefreshCw size={24} className="animate-spin" /> : <Icon size={24} />}
                </div>

                {/* Text & Description */}
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 id={`setting-${setting.id}`} className={`font-bold text-sm tracking-wide flex items-center gap-2 ${
                        isHardwareLocked ? 'text-red-400' : 'text-white'
                      }`}>
                        {setting.title}
                        {/* Tooltip Icon */}
                        <div className="group/tooltip relative">
                          <Info size={12} className="text-gray-600 cursor-help" aria-label={`More info about ${setting.title}`} />
                          <div className="absolute left-0 top-6 w-56 max-w-xs p-3 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-[9px] text-gray-400 opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                            {setting.tooltip}
                          </div>
                        </div>
                      </h3>
                      {setting.requiresExtension && (
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[9px] text-[#bc13fe] uppercase tracking-widest">
                            ⚠ Extension Required
                          </span>
                          {setting.extensionUrl && (
                            <a
                              href={setting.extensionUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[9px] text-[#00f3ff] hover:underline flex items-center gap-1"
                              aria-label={`Download ${setting.title} extension`}
                            >
                              <Download size={10} aria-hidden="true" />
                              Install
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                    
                    {/* Custom Cyberpunk Toggle */}
                    <button 
                      onClick={() => handleTogglePermission(setting.id as keyof typeof permissions)}
                      disabled={isDisabled}
                      className={`relative w-12 h-6 rounded-full transition-all duration-300 outline-none ${
                        isHardwareLocked 
                          ? 'bg-red-900/20 cursor-not-allowed' 
                          : isEnabled 
                            ? (setting.id.includes('Integration') ? 'bg-[#bc13fe]/20' : 'bg-[#00f3ff]/20') 
                            : 'bg-[#1f1f1f] cursor-pointer'
                      } ${isLoading ? 'opacity-50' : 'hover:scale-105'} ${isDisabled ? 'opacity-50' : ''}`}
                      role="switch"
                      aria-checked={isEnabled}
                      aria-labelledby={`setting-${setting.id}`}
                      aria-disabled={isDisabled}
                    >
                      <div className={`absolute top-1 left-1 w-4 h-4 rounded-full transition-all duration-300 ${
                        isHardwareLocked
                          ? 'bg-red-900'
                          : isEnabled 
                            ? `translate-x-6 ${setting.id.includes('Integration') ? 'bg-[#bc13fe] shadow-[0_0_10px_#bc13fe]' : 'bg-[#00f3ff] shadow-[0_0_10px_#00f3ff]'}` 
                            : 'bg-gray-500'
                      } ${isLoading ? 'animate-ping' : ''}`} />
                    </button>
                  </div>
                  
                  <p className="text-xs text-gray-400 leading-relaxed min-h-[40px]">
                    {isHardwareLocked ? (
                      <span className="text-red-500 font-bold flex items-center gap-1">
                        <AlertTriangle size={12} aria-hidden="true" /> {setting.lockMessage}
                      </span>
                    ) : (
                      setting.desc
                    )}
                  </p>
                  
                  {/* Status Indicator */}
                  <div className="mt-4 flex items-center gap-2 text-[10px] uppercase tracking-widest">
                    <div className={`w-1.5 h-1.5 rounded-full ${
                      isHardwareLocked ? 'bg-red-700' : isEnabled ? 'bg-green-500 animate-pulse' : 'bg-gray-600'
                    }`} aria-hidden="true" />
                    <span className={isHardwareLocked ? 'text-red-700' : 'text-gray-500'}>
                      {isHardwareLocked ? 'Hardware Locked' : isEnabled ? 'Port/Hardware Active' : 'Offline / Blocked'}
                    </span>
                    {isLoading && (
                      <span className="text-[#00f3ff] animate-pulse ml-2">
                        Processing...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ==================== FOOTER ==================== */}
      <div className="mt-12 text-[10px] text-gray-600 uppercase tracking-widest text-center space-y-1">
        <p>Note: Modifying network listeners executes real-time IPC commands to the Rust Daemon.</p>
        <p className="opacity-50">HackT Runtime v1.0.0 • Build 2024.12 • All Processing Local</p>
        <div className="flex items-center justify-center gap-4 mt-2">
          <span className="flex items-center gap-1">
            <Shield size={10} className="text-[#bc13fe]" aria-hidden="true" />
            Administrator Privileges Required
          </span>
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500" aria-hidden="true" />
            Backend Connected
          </span>
        </div>
      </div>
    </div>
  );
}