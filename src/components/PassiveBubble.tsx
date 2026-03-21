import React, { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { invoke, listen } from '@tauri-apps/api/tauri';
import { getCurrentWindow, appWindow } from '@tauri-apps/api/window';
import { useSystemStore } from '../store/systemStore';
import { 
  Shield, ShieldAlert, Mic, Volume2, Code, 
  Eye, Zap, Activity, Wifi, WifiOff, Settings,
  X, Check, AlertTriangle, Cpu, RefreshCw,
  Terminal, Globe, LogOut, Maximize2
} from 'lucide-react';

export default function PassiveBubble() {
  const { 
    isProcessing, 
    isSpeaking, 
    mode, 
    threatLevel, 
    systemVRAM,
    permissions,
    togglePermission,
    user,
    logout
  } = useSystemStore();
  
  // UI States
  const [isClicked, setIsClicked] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('connected');
  const [particleCount, setParticleCount] = useState(8);
  const [isDragging, setIsDragging] = useState(false);
  const [backendHealth, setBackendHealth] = useState<{
    cpuUsage: number;
    memoryUsage: number;
    activeScans: number;
  }>({ cpuUsage: 0, memoryUsage: 0, activeScans: 0 });
  
  // Refs
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);
  const healthCheckInterval = useRef<NodeJS.Timeout | null>(null);
  const threatListener = useRef<(() => void) | null>(null);

  // If we are in Active mode, the bubble hides so the Dashboard can take over
  if (mode !== 'passive') return null;

  // ======================================================================
  // 1. CONNECTION HEALTH CHECK (Ping Python Backend)
  // ======================================================================
  const checkConnection = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/health', { 
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      
      if (response.ok) {
        const health = await response.json();
        setConnectionStatus('connected');
        setBackendHealth({
          cpuUsage: health.cpu_usage || 0,
          memoryUsage: health.memory_usage || 0,
          activeScans: health.active_scans || 0
        });
      } else {
        setConnectionStatus('reconnecting');
      }
    } catch {
      setConnectionStatus('disconnected');
    }
  }, []);

  useEffect(() => {
    checkConnection();
    healthCheckInterval.current = setInterval(checkConnection, 5000);
    return () => {
      if (healthCheckInterval.current) {
        clearInterval(healthCheckInterval.current);
      }
    };
  }, [checkConnection]);

  // ======================================================================
  // 2. LISTEN FOR THREAT ALERTS FROM BACKEND
  // ======================================================================
  useEffect(() => {
    const setupThreatListener = async () => {
      try {
        threatListener.current = await listen('threat_detected', (event) => {
          const payload = event.payload as { level: string; source?: string };
          
          // Visual feedback on threat
          if (payload.level === 'high') {
            setParticleCount(16);
            setTimeout(() => setParticleCount(8), 3000);
          } else if (payload.level === 'medium') {
            setParticleCount(12);
            setTimeout(() => setParticleCount(8), 2000);
          }
        });
      } catch (error) {
        console.warn('Threat listener setup failed:', error);
      }
    };

    setupThreatListener();

    return () => {
      if (threatListener.current) {
        threatListener.current();
      }
    };
  }, []);

  // ======================================================================
  // 3. LISTEN FOR STT RESULTS (Voice Commands)
  // ======================================================================
  useEffect(() => {
    const setupSTTListener = async () => {
      try {
        const unlisten = await listen('stt_result', (event) => {
          const payload = event.payload as { text: string };
          console.log('Voice command received:', payload.text);
          // Handle voice command
        });

        return () => {
          unlisten.then(fn => fn());
        };
      } catch (error) {
        console.warn('STT listener setup failed:', error);
      }
    };

    setupSTTListener();
  }, []);

  // ======================================================================
  // 4. CLOSE CONTEXT MENU ON CLICK OUTSIDE
  // ======================================================================
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        setShowContextMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ======================================================================
  // 5. WINDOW DRAG FUNCTIONALITY (Tauri API)
  // ======================================================================
  const handleDragStart = useCallback(async () => {
    setIsDragging(true);
    try {
      await getCurrentWindow().startDragging();
    } catch (error) {
      console.warn('Drag failed:', error);
    } finally {
      setIsDragging(false);
    }
  }, []);

  // ======================================================================
  // 6. DYNAMIC STATE LOGIC (Color, Text & HUD Mapping)
  // ======================================================================
  const visualState = useMemo(() => {
    // Default: Safe Monitoring (Cyan / Deep Blue)
    let coreColor = 'bg-gradient-to-br from-[#00f3ff] to-[#0066ff] shadow-[0_0_25px_rgba(0,243,255,0.6)]';
    let ringColor = 'border-[#00f3ff] opacity-30';
    let hudAnimation = 'animate-spin-slow';
    let statusText = 'SYSTEM SECURE';
    let isAlert = false;
    let pulseSpeed = '3s';
    let icon = <Shield size={20} className="text-white/80" />;

    // Connection Status Override
    if (connectionStatus === 'disconnected') {
      coreColor = 'bg-gradient-to-br from-[#4a4a4a] to-[#2a2a2a] shadow-[0_0_15px_rgba(100,100,100,0.4)]';
      ringColor = 'border-gray-600 opacity-40';
      statusText = 'OFFLINE';
      hudAnimation = 'animate-pulse';
      icon = <WifiOff size={20} className="text-gray-400" />;
    } else if (connectionStatus === 'reconnecting') {
      coreColor = 'bg-gradient-to-br from-[#ffb000] to-[#cc5500] shadow-[0_0_20px_rgba(255,176,0,0.5)]';
      ringColor = 'border-[#ffb000] opacity-60';
      statusText = 'RECONNECTING...';
      hudAnimation = 'animate-ping';
      icon = <RefreshCw size={20} className="text-white animate-spin" />;
    }
    // Threat Overrides (Yellow / Red)
    else if (threatLevel === 'high') {
      coreColor = 'bg-gradient-to-br from-[#ff003c] to-[#990000] shadow-[0_0_40px_rgba(255,0,60,0.8)] animate-pulse';
      ringColor = 'border-[#ff003c] opacity-90 scale-110 border-dashed';
      hudAnimation = 'animate-spin-fast';
      statusText = 'CRITICAL THREAT';
      isAlert = true;
      pulseSpeed = '0.5s';
      icon = <ShieldAlert size={20} className="text-white drop-shadow-lg" />;
    } else if (threatLevel === 'medium') {
      coreColor = 'bg-gradient-to-br from-[#ffb000] to-[#cc5500] shadow-[0_0_30px_rgba(255,176,0,0.7)]';
      ringColor = 'border-[#ffb000] opacity-70 scale-105';
      hudAnimation = 'animate-spin';
      statusText = 'WARNING DETECTED';
      isAlert = true;
      pulseSpeed = '1.5s';
      icon = <AlertTriangle size={20} className="text-white" />;
    }

    // Action Overrides (Processing / Speaking)
    if (isProcessing) {
      coreColor = 'bg-gradient-to-br from-[#ffffff] to-[#cccccc] shadow-[0_0_35px_rgba(255,255,255,0.9)]';
      ringColor = 'border-white opacity-50 scale-105 animate-ping';
      hudAnimation = 'animate-pulse';
      statusText = 'ANALYZING...';
      pulseSpeed = '0.3s';
      icon = <Activity size={20} className="text-[#0a0a0a] animate-pulse" />;
    } else if (isSpeaking) {
      coreColor = 'bg-gradient-to-br from-[#bc13fe] to-[#5e00b3] shadow-[0_0_30px_rgba(188,19,254,0.7)]';
      ringColor = 'border-[#bc13fe] opacity-80 scale-125';
      hudAnimation = 'animate-bounce';
      statusText = 'TRANSMITTING';
      pulseSpeed = '0.8s';
      icon = <Volume2 size={20} className="text-white" />;
    }

    return { coreColor, ringColor, hudAnimation, statusText, isAlert, pulseSpeed, icon };
  }, [isProcessing, isSpeaking, threatLevel, connectionStatus]);

  // ======================================================================
  // 7. INTERACTION HANDLERS
  // ======================================================================
  const handleBubbleClick = useCallback(async (e: React.MouseEvent) => {
    if (isProcessing || isSpeaking) return;
    if (e.button === 2) return; // Right-click handled separately

    // Tactile animation trigger
    setIsClicked(true);
    setTimeout(() => setIsClicked(false), 150);

    try {
      if (visualState.isAlert) {
        // Send the fix command down to Rust/Python
        await invoke('trigger_ide_fix_action', { 
          sessionId: user?.email || 'active-operator-session',
          instruction: "Surgically patch the detected vulnerability." 
        });
      } else {
        // Toggle voice listening
        await togglePermission('micEnabled');
      }
    } catch (error) {
      console.error("Failed to execute bubble command:", error);
    }
  }, [isProcessing, isSpeaking, visualState.isAlert, user?.email, togglePermission]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setShowContextMenu(prev => !prev);
  }, []);

  const handleQuickAction = useCallback(async (action: string) => {
    setShowContextMenu(false);
    try {
      switch (action) {
        case 'toggle-vision':
          await togglePermission('visionEnabled');
          break;
        case 'toggle-mic':
          await togglePermission('micEnabled');
          break;
        case 'toggle-ide':
          await togglePermission('ideIntegration');
          break;
        case 'toggle-browser':
          await togglePermission('browserIntegration');
          break;
        case 'scan-screen':
          await invoke('trigger_screen_scan');
          break;
        case 'open-dashboard':
          await appWindow.show();
          await appWindow.setFocus();
          break;
        case 'logout':
          await logout();
          break;
      }
    } catch (error) {
      console.error(`Failed to execute ${action}:`, error);
    }
  }, [togglePermission, logout]);

  // ======================================================================
  // 8. PARTICLE RENDERER (Orbital Effects)
  // ======================================================================
  const renderParticles = useMemo(() => {
    return Array.from({ length: particleCount }).map((_, i) => {
      const angle = (i / particleCount) * Math.PI * 2;
      const radius = 50 + Math.random() * 10;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      const delay = i * 0.1;
      
      return (
        <div
          key={i}
          className={`absolute w-1 h-1 rounded-full ${
            visualState.isAlert ? 'bg-[#ff003c]' : 'bg-[#00f3ff]'
          } animate-ping`}
          style={{
            left: `calc(50% + ${x}px)`,
            top: `calc(50% + ${y}px)`,
            animationDelay: `${delay}s`,
            opacity: 0.6
          }}
          aria-hidden="true"
        />
      );
    });
  }, [particleCount, visualState.isAlert]);

  // ======================================================================
  // 9. VRAM TELEMETRY BADGE
  // ======================================================================
  const vramBadge = useMemo(() => {
    if (systemVRAM === 0) return { text: 'N/A', color: 'text-gray-500' };
    const vramGB = (systemVRAM / 1024).toFixed(1);
    if (systemVRAM >= 6144) return { text: `${vramGB}GB`, color: 'text-green-400' };
    return { text: `${vramGB}GB`, color: 'text-yellow-500' };
  }, [systemVRAM]);

  // ======================================================================
  // 10. RENDER
  // ======================================================================
  return (
    <div 
      className="fixed inset-0 w-full h-full flex items-center justify-center z-50 overflow-hidden"
      onPointerDown={handleDragStart}
      role="application"
      aria-label="HackT Passive Monitor Bubble"
    >
      {/* ==================== CONTEXT MENU ==================== */}
      {showContextMenu && (
        <div 
          ref={contextMenuRef}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 panel-3d rounded-xl border border-[#1f1f1f] bg-[#0a0a0a]/95 backdrop-blur-xl z-50 overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200"
          role="menu"
          aria-label="Quick Actions Menu"
        >
          {/* Header */}
          <div className="p-3 border-b border-[#1f1f1f] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu size={14} className="text-[#00f3ff]" />
              <span className="text-[10px] text-gray-400 uppercase tracking-widest">Quick Actions</span>
            </div>
            <button 
              onClick={() => setShowContextMenu(false)} 
              className="text-gray-500 hover:text-white transition-colors"
              aria-label="Close menu"
            >
              <X size={14} />
            </button>
          </div>

          {/* Menu Items */}
          <div className="p-2 space-y-1 max-h-80 overflow-y-auto gloomy-scroll">
            {/* Permission Toggles */}
            <button 
              onClick={() => handleQuickAction('toggle-vision')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs hover:bg-[#1f1f1f] transition-colors ${
                permissions.visionEnabled ? 'text-[#00f3ff]' : 'text-gray-400'
              }`}
              role="menuitem"
            >
              <div className="flex items-center gap-3">
                <Eye size={14} />
                <span>Vision OCR</span>
              </div>
              {permissions.visionEnabled && <Check size={12} className="text-green-500" />}
            </button>

            <button 
              onClick={() => handleQuickAction('toggle-mic')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs hover:bg-[#1f1f1f] transition-colors ${
                permissions.micEnabled ? 'text-[#00f3ff]' : 'text-gray-400'
              }`}
              role="menuitem"
            >
              <div className="flex items-center gap-3">
                <Mic size={14} />
                <span>Voice Control</span>
              </div>
              {permissions.micEnabled && <Check size={12} className="text-green-500" />}
            </button>

            <button 
              onClick={() => handleQuickAction('toggle-ide')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs hover:bg-[#1f1f1f] transition-colors ${
                permissions.ideIntegration ? 'text-[#bc13fe]' : 'text-gray-400'
              }`}
              role="menuitem"
            >
              <div className="flex items-center gap-3">
                <Code size={14} />
                <span>IDE Integration</span>
              </div>
              {permissions.ideIntegration && <Check size={12} className="text-green-500" />}
            </button>

            <button 
              onClick={() => handleQuickAction('toggle-browser')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs hover:bg-[#1f1f1f] transition-colors ${
                permissions.browserIntegration ? 'text-[#bc13fe]' : 'text-gray-400'
              }`}
              role="menuitem"
            >
              <div className="flex items-center gap-3">
                <Globe size={14} />
                <span>Browser Proxy</span>
              </div>
              {permissions.browserIntegration && <Check size={12} className="text-green-500" />}
            </button>

            {/* Divider */}
            <div className="border-t border-[#1f1f1f] my-2" />

            {/* Actions */}
            <button 
              onClick={() => handleQuickAction('scan-screen')}
              className="w-full flex items-center gap-3 px-3 py-2 rounded text-xs text-[#00f3ff] hover:bg-[#1f1f1f] transition-colors"
              role="menuitem"
            >
              <Zap size={14} />
              <span>Scan Screen Now</span>
            </button>

            <button 
              onClick={() => handleQuickAction('open-dashboard')}
              className="w-full flex items-center gap-3 px-3 py-2 rounded text-xs text-gray-400 hover:bg-[#1f1f1f] transition-colors"
              role="menuitem"
            >
              <Maximize2 size={14} />
              <span>Open Dashboard</span>
            </button>

            {/* User Section */}
            {user && (
              <>
                <div className="border-t border-[#1f1f1f] my-2" />
                <div className="px-3 py-2">
                  <div className="text-[9px] text-gray-500 uppercase tracking-widest mb-1">Operator</div>
                  <div className="text-xs text-white font-medium truncate">{user.name}</div>
                </div>
                <button 
                  onClick={() => handleQuickAction('logout')}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded text-xs text-red-400 hover:bg-red-900/20 transition-colors"
                  role="menuitem"
                >
                  <LogOut size={14} />
                  <span>Sever Connection</span>
                </button>
              </>
            )}
          </div>

          {/* Backend Health Footer */}
          <div className="p-3 border-t border-[#1f1f1f] bg-[#050505]/50">
            <div className="flex items-center justify-between text-[8px] text-gray-500 uppercase tracking-widest">
              <div className="flex items-center gap-1">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' :
                  connectionStatus === 'reconnecting' ? 'bg-yellow-500' : 'bg-red-500'
                }`} />
                <span>{connectionStatus}</span>
              </div>
              <span>CPU: {backendHealth.cpuUsage}%</span>
            </div>
          </div>
        </div>
      )}

      {/* ==================== MAIN BUBBLE ==================== */}
      <div 
        ref={bubbleRef}
        onClick={handleBubbleClick}
        onContextMenu={handleContextMenu}
        className={`relative flex items-center justify-center w-24 h-24 cursor-pointer group transition-all duration-150 ${
          isClicked ? 'scale-90' : 'hover:scale-105'
        } ${connectionStatus === 'disconnected' ? 'opacity-50' : ''} ${
          isDragging ? 'cursor-grabbing' : 'cursor-grab'
        }`}
        title={visualState.statusText}
        tabIndex={0}
        role="button"
        aria-label={`HackT Bubble - ${visualState.statusText}`}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            handleBubbleClick(e as any);
          }
        }}
      >
        {/* Particle Effects */}
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          {renderParticles}
        </div>

        {/* Outer HUD Ring (Counter-Rotating) */}
        <div 
          className={`absolute inset-0 rounded-full border-2 transition-all duration-700 pointer-events-none ${visualState.ringColor}`} 
          style={{ animationDuration: visualState.pulseSpeed }}
          aria-hidden="true"
        />
        <div 
          className={`absolute inset-[-4px] rounded-full border border-t-transparent border-b-transparent transition-all duration-700 pointer-events-none opacity-40 border-white ${visualState.hudAnimation}`} 
          style={{ animationDirection: 'reverse', animationDuration: visualState.pulseSpeed }}
          aria-hidden="true"
        />

        {/* Connection Status Indicator */}
        <div 
          className={`absolute -top-2 -right-2 w-4 h-4 rounded-full border-2 border-[#0a0a0a] ${
            connectionStatus === 'connected' ? 'bg-green-500' :
            connectionStatus === 'reconnecting' ? 'bg-yellow-500 animate-pulse' :
            'bg-red-500'
          }`} 
          title={`Backend: ${connectionStatus}`}
          aria-label={`Backend connection: ${connectionStatus}`}
        />

        {/* The Core Neural Orb */}
        <div 
          className={`relative w-16 h-16 rounded-full transition-all duration-500 overflow-hidden pointer-events-none ${visualState.coreColor}`}
          aria-hidden="true"
        >
          {/* Internal Plasma/Glass Effect */}
          <div className="absolute inset-0 bg-white/10 mix-blend-overlay backdrop-blur-sm" />
          <div 
            className={`absolute inset-[-10px] bg-gradient-to-tr from-transparent via-white/30 to-transparent mix-blend-overlay ${visualState.hudAnimation}`} 
            style={{ animationDuration: visualState.pulseSpeed }}
          />
          
          {/* Inner Core Highlight (3D sphere look) */}
          <div className="absolute top-1 left-2 w-5 h-3 rounded-full bg-white/60 blur-[1px] transform -rotate-45" />
          <div className="absolute bottom-2 right-2 w-3 h-3 rounded-full bg-black/40 blur-[2px]" />
          
          {/* Center Icon (Changes based on state) */}
          <div className="absolute inset-0 flex items-center justify-center">
            {visualState.icon}
          </div>
        </div>

        {/* Hover Action Tooltip */}
        <div 
          className="absolute -top-12 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-300 text-[9px] text-[#00f3ff] bg-[#0a0a0a]/90 px-3 py-1.5 rounded-sm border border-[#00f3ff]/30 font-mono tracking-widest uppercase shadow-lg pointer-events-none z-50"
          aria-hidden="true"
        >
          {visualState.isAlert ? 'Left-Click: Auto-Patch' : 'Left-Click: Voice'}
          <span className="text-gray-500 mx-1">|</span>
          Right-Click: Menu
        </div>

        {/* VRAM Telemetry Badge (Bottom Left) */}
        <div 
          className="absolute -bottom-1 -left-2 flex items-center gap-1 bg-[#0a0a0a]/80 px-2 py-0.5 rounded border border-[#1f1f1f]"
          title={`Available VRAM: ${vramBadge.text}`}
        >
          <Cpu size={8} className={vramBadge.color} />
          <span className={`text-[8px] font-mono ${vramBadge.color}`}>{vramBadge.text}</span>
        </div>
      </div>

      {/* ==================== STATUS TEXT ==================== */}
      <div 
        className={`absolute bottom-2 text-[9px] font-bold tracking-[0.2em] font-mono transition-colors duration-300 pointer-events-none drop-shadow-md ${
          visualState.isAlert ? 'text-[#ff003c]' : 
          connectionStatus === 'disconnected' ? 'text-gray-500' :
          'text-[#00f3ff]/70'
        }`}
        aria-live="polite"
        aria-atomic="true"
      >
        {visualState.statusText}
      </div>

      {/* ==================== THREAT PULSE OVERLAY ==================== */}
      {visualState.isAlert && (
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          <div className="absolute inset-0 bg-[#ff003c]/5 animate-pulse" />
        </div>
      )}
    </div>
  );
}