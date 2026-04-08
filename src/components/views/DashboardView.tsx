import { useEffect, useState, useRef, useCallback } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { listen } from '@tauri-apps/api/event';
import { writeTextFile } from '@tauri-apps/api/fs';
import ModeToggle from '../ui/ModeToggle';
import ChatView from './ChatView';
import CodeDiffModal from '../views/CodeDiffModal'; // adjust path to your actual location
import {
  Menu, Terminal, Shield, BookOpen, EyeOff, Activity,
  ChevronRight, Zap, CheckCircle,
  ExternalLink, Code, Globe, Monitor,
  X, Wifi, WifiOff
} from 'lucide-react';

// ======================================================================
// TYPE DEFINITIONS
// ======================================================================
interface TelemetryData {
  scansCompleted: number;
  threatsDetected: number;
  lastScanTime: string;
  activeConnections: number;
  cpuUsage: number;
  memoryUsage: number;
}

interface CodeDiffPayload {
  threat_level: string;
  source: string;
  original_code: string;
  suggested_fix: string;
  timestamp: number;
  vulnerability?: string;
}

// ======================================================================
// COMPONENT
// ======================================================================
export default function DashboardView() {
  const {
    isSidebarOpen, toggleSidebar, vaultSkills, user, logout,
    mode, toggleMode, systemVRAM, 
    initSystem, checkSession, backendConnected  } = useSystemStore();

  // UI States
  const [bootSequence, setBootSequence] = useState(true);
  const [showPassiveModal, setShowPassiveModal] = useState(false);
  const [activeTab, setActiveTab] = useState<'projects' | 'security' | 'vault'>('projects');

  // Threat Remediation State
  const [activeDiff, setActiveDiff] = useState<CodeDiffPayload | null>(null);
  const [, setIsApplyingFix] = useState(false);

  // Local Telemetry State (Fallback visualizer)
  const [localTelemetry, setLocalTelemetry] = useState<TelemetryData>({
    scansCompleted: 0, threatsDetected: 0, lastScanTime: 'Never',
    activeConnections: 0, cpuUsage: 0, memoryUsage: 0
  });

  const sidebarRef = useRef<HTMLDivElement>(null);

  // ======================================================================
  // 1. INITIALIZATION
  // ======================================================================
  useEffect(() => {
    const init = async () => {
      try {
        await initSystem();
        await checkSession();
        const timer = setTimeout(() => setBootSequence(false), 800);
        return () => clearTimeout(timer);
      } catch (error) {
        console.error('Initialization failed:', error);
        setBootSequence(false);
      }
    };
    init();
  }, [initSystem, checkSession]);

  // ======================================================================
  // 2. TAURI EVENT LISTENERS (RACE-CONDITION SAFE)
  // ======================================================================
  useEffect(() => {
    // Store the raw promises – they resolve to the actual unlisten functions
    const unlistenPromises = [
      listen('code_diff_available', (event: any) => {
        setActiveDiff(event.payload.data);
      }),
      listen('telemetry_update', (event: any) => {
        setLocalTelemetry(prev => ({
          ...prev,
          ...event.payload,
          lastScanTime: new Date().toLocaleTimeString()
        }));
      })
    ];

    // Cleanup: wait for each promise to resolve, then call the unlisten function
    return () => {
      unlistenPromises.forEach(promise =>
        promise.then(unlisten => unlisten?.())
      );
    };
  }, []);

  // ======================================================================
  // 3. PASSIVE MODE HANDLERS
  // ======================================================================
  const operatorName = user?.name ? user.name.split(' ')[0].toUpperCase() : 'OPERATOR';
  const isPassiveAvailable = systemVRAM >= 6144;
  const sessionId = user?.name ? `AUTH-${Date.now().toString().slice(-6)}` : 'N/A';

  const handleEngagePassive = useCallback(() => {
    if (!backendConnected) {
      console.warn('Backend offline. Core must be active to engage Passive Mode.');
      return;
    }
    if (isPassiveAvailable) setShowPassiveModal(true);
  }, [isPassiveAvailable, backendConnected]);

  const confirmPassiveMode = useCallback(async () => {
    try {
      await toggleMode();
      setShowPassiveModal(false);
    } catch (error) {
      console.error('Failed to engage passive mode:', error);
    }
  }, [toggleMode]);

  // ======================================================================
  // 4. APPLY CODE FIX (WITH PATH SANITIZATION)
  // ======================================================================
  const applyCodeFix = async () => {
    if (!activeDiff) return;

    setIsApplyingFix(true);
    try {
      // Strip 'ide:' or 'browser:' tags sent by the backend telemetry
      const cleanPath = activeDiff.source.replace(/^(ide|browser):/, '');
      await writeTextFile(cleanPath, activeDiff.suggested_fix);

      console.log(`✅ Fix applied to ${cleanPath}`);
      setActiveDiff(null);
    } catch (error) {
      console.error('Failed to write fix to disk:', error);
      // In production, replace with a toast notification
    } finally {
      setIsApplyingFix(false);
    }
  };

  // ======================================================================
  // RENDER HELPERS
  // ======================================================================

  // ======================================================================
  // RENDER
  // ======================================================================
  return (
    <div
      className={`relative flex h-screen w-screen bg-[#030305] text-[#e0e0e0] font-mono overflow-hidden transition-opacity duration-700 ${bootSequence ? 'opacity-0' : 'opacity-100'}`}
      // ✅ DRAG REGION REMOVED FROM ROOT – only header handles dragging
    >
      {activeDiff && (
        <CodeDiffModal
          isOpen={!!activeDiff}
          onClose={() => setActiveDiff(null)}
          onApply={applyCodeFix}
          originalCode={activeDiff.original_code}
          suggestedFix={activeDiff.suggested_fix}
          threatLevel={activeDiff.threat_level as 'safe' | 'medium' | 'high' | 'critical'}
          source={activeDiff.source}
          vulnerability={{
            type: activeDiff.threat_level || 'unknown',
            description: activeDiff.vulnerability || 'Security vulnerability detected',
            mitigation: activeDiff.suggested_fix || 'Apply the suggested patch',
            cwe_id: undefined  // Optionally include CWE ID if available in the payload
          }}
        />
      )}

      {/* ==================== PASSIVE MODE ENGAGEMENT MODAL ==================== */}
      {showPassiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="panel-3d w-full max-w-lg rounded-2xl border border-[#bc13fe]/50 p-8 shadow-[0_0_50px_rgba(188,19,254,0.3)] animate-in fade-in zoom-in duration-300">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-[#bc13fe]/20 border border-[#bc13fe]/50">
                  <Monitor size={24} className="text-[#bc13fe]" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white tracking-widest">ENGAGE PASSIVE MODE</h3>
                  <p className="text-[10px] text-gray-400 uppercase">Full Sentinel Suite Activation</p>
                </div>
              </div>
              <button
                onClick={() => setShowPassiveModal(false)}
                className="p-2 hover:bg-white/5 rounded-lg transition-colors"
                aria-label="Close modal"
              >
                <X size={20} className="text-gray-400" />
              </button>
            </div>

            <div className="space-y-4 mb-6">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
                <EyeOff size={16} className="text-[#00f3ff]" />
                <div className="flex-1">
                  <div className="text-xs text-white">Florence-2 Vision OCR</div>
                  <div className="text-[10px] text-gray-500">Real-time screen analysis</div>
                </div>
                <CheckCircle size={16} className="text-green-500" />
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
                <Code size={16} className="text-[#bc13fe]" />
                <div className="flex-1">
                  <div className="text-xs text-white">IDE Live AST Monitoring</div>
                  <div className="text-[10px] text-gray-500">Port 8081 • Real-time code stream</div>
                </div>
                <CheckCircle size={16} className="text-green-500" />
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
                <Globe size={16} className="text-[#bc13fe]" />
                <div className="flex-1">
                  <div className="text-xs text-white">Browser Proxy (Port 8082)</div>
                  <div className="text-[10px] text-gray-500">Phishing detection active</div>
                </div>
                <CheckCircle size={16} className="text-green-500" />
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
                <Activity size={16} className="text-yellow-500" />
                <div className="flex-1">
                  <div className="text-xs text-white">VRAM Usage Estimate</div>
                  <div className="text-[10px] text-gray-500">~3.5 GB of {(systemVRAM / 1024).toFixed(1)} GB available</div>
                </div>
                <CheckCircle size={16} className="text-green-500" />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowPassiveModal(false)}
                className="flex-1 py-3 rounded-lg border border-[#1f1f1f] text-gray-400 hover:bg-white/5 uppercase tracking-widest text-xs transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmPassiveMode}
                className="flex-1 py-3 rounded-lg bg-[#bc13fe]/20 border border-[#bc13fe]/50 text-[#bc13fe] uppercase tracking-widest font-bold shadow-[0_0_15px_rgba(188,19,254,0.2)] hover:bg-[#bc13fe]/30 transition"
              >
                Engage Sentinel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== LEFT SIDEBAR ==================== */}
      <aside
        ref={sidebarRef}
        className={`relative z-20 flex flex-col panel-3d transition-all duration-500 ease-in-out ${
          isSidebarOpen ? 'w-80' : 'w-16'
        } border-r border-[#1f1f1f] shadow-[5px_0_20px_rgba(0,0,0,0.5)]`}
      >
        {/* Sidebar Header */}
        <div className="p-4 flex items-center justify-between border-b border-[#1f1f1f] bg-black/40">
          {isSidebarOpen && (
            <h1 className="text-xl font-bold tracking-widest text-white drop-shadow-[0_0_8px_rgba(0,243,255,0.5)]">
              HACKT<span className="text-[#00f3ff]">.AI</span>
            </h1>
          )}
          <button
            onClick={toggleSidebar}
            className="p-1 hover:text-[#00f3ff] transition-transform hover:scale-110 active:scale-95"
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>
        </div>

        {isSidebarOpen && (
          <div className="flex-1 overflow-y-auto gloomy-scroll p-4 space-y-6 animate-fade-in">
            {/* Operator Box */}
            <div className="p-4 rounded-xl border border-[#00f3ff]/30 bg-gradient-to-br from-[#00f3ff]/5 to-transparent relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-[#00f3ff] to-transparent shadow-[0_0_15px_#00f3ff]" />
              <div className="flex items-center gap-3 mb-2">
                <div className="h-2 w-2 rounded-full bg-[#00f3ff] shadow-[0_0_8px_#00f3ff] animate-pulse" />
                <div className="text-[9px] text-[#00f3ff] uppercase tracking-widest">Authenticated</div>
              </div>
              <div className="text-sm font-bold text-white tracking-wide mb-1">WELCOME, {operatorName}</div>
              <div className="text-[10px] text-gray-500">ID: {sessionId}</div>
            </div>

            {/* Connection Status */}
            <div className={`p-3 rounded-lg border flex items-center justify-between ${
              backendConnected
                ? 'border-green-500/30 bg-green-500/5'
                : 'border-red-500/30 bg-red-500/5'
            }`}>
              <div className="flex items-center gap-2">
                {backendConnected ? (
                  <Wifi size={14} className="text-green-500" />
                ) : (
                  <WifiOff size={14} className="text-red-500" />
                )}
                <span className={`text-[9px] uppercase tracking-widest font-bold ${
                  backendConnected ? 'text-green-400' : 'text-red-400'
                }`}>
                  {backendConnected ? 'Engine Online' : 'Engine Offline'}
                </span>
              </div>
              <span className="text-[9px] text-gray-600 font-mono">PORT: 8000</span>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 p-1 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
              <button
                onClick={() => setActiveTab('projects')}
                className={`flex-1 py-2 rounded text-[10px] uppercase tracking-widest transition-all ${
                  activeTab === 'projects'
                    ? 'bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/30'
                    : 'text-gray-500 hover:text-white'
                }`}
              >
                <Terminal size={12} className="inline mr-1" />
                Projects
              </button>
              <button
                onClick={() => setActiveTab('security')}
                className={`flex-1 py-2 rounded text-[10px] uppercase tracking-widest transition-all ${
                  activeTab === 'security'
                    ? 'bg-[#ff003c]/20 text-[#ff003c] border border-[#ff003c]/30'
                    : 'text-gray-500 hover:text-white'
                }`}
              >
                <Shield size={12} className="inline mr-1" />
                Security
              </button>
              <button
                onClick={() => setActiveTab('vault')}
                className={`flex-1 py-2 rounded text-[10px] uppercase tracking-widest transition-all ${
                  activeTab === 'vault'
                    ? 'bg-[#bc13fe]/20 text-[#bc13fe] border border-[#bc13fe]/30'
                    : 'text-gray-500 hover:text-white'
                }`}
              >
                <BookOpen size={12} className="inline mr-1" />
                Vault
              </button>
            </div>

            {/* Tab Contents */}
            <div className="min-h-[150px]">
              {activeTab === 'projects' && (
                <div className="text-center py-8 text-gray-600 text-xs">
                  <Terminal size={24} className="mx-auto mb-2 opacity-50" />
                  <p>No active projects</p>
                  <p className="text-[9px]">Start chatting to create one</p>
                </div>
              )}
              {activeTab === 'security' && (
                <div className="text-center py-8 text-gray-600 text-xs">
                  <Shield size={24} className="mx-auto mb-2 opacity-50" />
                  <p>System Secure</p>
                  <p className="text-[9px]">No threats in current session</p>
                </div>
              )}
              {activeTab === 'vault' && (
                <div className="space-y-3">
                  {vaultSkills.map((skill, idx) => (
                    <div
                      key={idx}
                      className="text-xs panel-3d p-3 rounded-lg border border-white/5 bg-black/40 hover:bg-black/60 transition-all cursor-default group"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[#bc13fe] font-bold drop-shadow-[0_0_5px_rgba(188,19,254,0.3)]">
                          {skill.chapter}
                        </span>
                        <ExternalLink size={12} className="text-gray-600 group-hover:text-[#bc13fe] transition-colors" />
                      </div>
                      <div className="text-[9px] text-gray-500">{skill.topicsCovered.length} Topics Loaded</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Telemetry Panel */}
            <div className="panel-3d p-4 rounded-xl border border-[#1f1f1f]/50 bg-[#0a0a0a]/60 space-y-3 mt-auto">
              <h3 className="text-gray-400 text-[10px] font-bold tracking-widest mb-3 uppercase flex items-center gap-2">
                <Activity size={12} /> System Telemetry
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">CPU</span>
                  <span className="text-white text-xs font-mono">{localTelemetry.cpuUsage}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">RAM</span>
                  <span className="text-white text-xs font-mono">{localTelemetry.memoryUsage}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">Sockets</span>
                  <span className="text-[#00f3ff] text-xs font-mono">{localTelemetry.activeConnections}</span>
                </div>
              </div>

              <div className="pt-3 border-t border-[#1f1f1f]">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-500 text-[9px]">Dedicated VRAM</span>
                  <span className={`text-xs font-bold ${
                    systemVRAM >= 6144 ? 'text-green-400' : 'text-yellow-500'
                  }`}>
                    {(systemVRAM / 1024).toFixed(1)} GB
                  </span>
                </div>
                <div className="relative h-1.5 bg-[#1f1f1f] rounded-full overflow-hidden">
                  <div
                    className={`absolute top-0 left-0 h-full transition-all duration-500 ${
                      systemVRAM >= 6144
                        ? 'bg-gradient-to-r from-green-500 to-green-400'
                        : 'bg-gradient-to-r from-yellow-500 to-yellow-400'
                    }`}
                    style={{ width: `${Math.min((systemVRAM / 8192) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* ==================== CENTER WORKSPACE ==================== */}
      <main className="relative z-10 flex-1 flex flex-col bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#0f0f15] to-[#030305]">
        {/* Top Header - Native Drag Region */}
        <header
          className="h-16 flex items-center justify-between px-6 border-b border-[#1f1f1f] bg-black/20 backdrop-blur-md shadow-md z-20"
          data-tauri-drag-region  // ✅ Only here – root has no drag region
        >
          <div className="flex items-center gap-4">
            <ModeToggle />
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[10px] uppercase tracking-widest ${
              mode === 'passive'
                ? 'border-[#bc13fe]/50 bg-[#bc13fe]/10 text-[#bc13fe]'
                : 'border-[#00f3ff]/50 bg-[#00f3ff]/10 text-[#00f3ff]'
            }`}>
              <div className={`h-1.5 w-1.5 rounded-full ${
                mode === 'passive' ? 'bg-[#bc13fe] animate-pulse' : 'bg-[#00f3ff]'
              }`} />
              {mode === 'passive' ? 'Passive Monitor' : 'Active Chat'}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right hidden md:block">
              <div className="text-sm text-white font-bold">{user?.name}</div>
              <div className="text-[9px] text-gray-500 uppercase tracking-widest">Local Admin</div>
            </div>
            <button
              onClick={logout}
              className="hover:scale-105 active:scale-95 transition-transform relative group"
              title="Disconnect Session"
              aria-label="Logout"
            >
              <img
                src={user?.avatarUrl}
                alt="Profile"
                className="h-9 w-9 rounded-full border-2 border-[#1f1f1f] group-hover:border-red-500/50 object-cover transition-colors"
              />
            </button>
          </div>
        </header>

        {/* Passive Mode Engagement Banner (Only visible in active mode) */}
        {mode === 'active' && isPassiveAvailable && (
          <div className="w-full bg-[#1f1f1f]/30 border-b border-[#00f3ff]/20 p-2 flex items-center justify-center gap-4 animate-in slide-in-from-top-2">
            <span className="text-[10px] text-gray-400 uppercase tracking-widest flex items-center gap-2">
              <Activity size={12} className="text-[#00f3ff]" /> System Idle. Sentinel Ready for Deployment.
            </span>
            <button
              onClick={handleEngagePassive}
              className="px-3 py-1 text-[9px] uppercase tracking-widest rounded border border-[#00f3ff]/50 text-[#00f3ff] hover:bg-[#00f3ff]/10 transition-colors flex items-center gap-1"
            >
              <Zap size={12} />
              Engage Passive Mode
              <ChevronRight size={12} className="opacity-50" />
            </button>
          </div>
        )}

        {/* Chat Interface */}
        <div className="flex-1 overflow-hidden relative">
          <ChatView />
        </div>
      </main>
    </div>
  );
}