import { useEffect, useState, useRef, useCallback } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { listen } from '@tauri-apps/api/event';
import ModeToggle from '../ui/ModeToggle';
import ChatView from './ChatView';
import { 
  Menu, Terminal, Shield, BookOpen, EyeOff, Activity, 
  ChevronRight, Zap, AlertTriangle, CheckCircle,
  ExternalLink, Clock, FileText,
  Code, Globe, Monitor, X, Wifi, WifiOff
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

interface SecurityDiscovery {
  id: string;
  title: string;
  severity: 'high' | 'medium' | 'low';
  timestamp: string;
  source: string;
  page: number;
}

interface ActiveProject {
  id: string;
  title: string;
  lastActive: string;
  messagesCount: number;
}

// ======================================================================
// COMPONENT
// ======================================================================
export default function DashboardView() {
  const { 
    isSidebarOpen, 
    toggleSidebar, 
    vaultSkills, 
    user, 
    logout,
    mode,
    toggleMode,
    systemVRAM,
    threatLevel,
    permissions,
    messages,
    initSystem,
    checkSession,
    setSystemVRAM
  } = useSystemStore();

  // UI States
  const [bootSequence, setBootSequence] = useState(true);
  const [showPassiveModal, setShowPassiveModal] = useState(false);
  const [activeTab, setActiveTab] = useState<'projects' | 'security' | 'vault'>('projects');
  const [backendConnected, setBackendConnected] = useState(false);
  
  // Telemetry State
  const [telemetryData, setTelemetryData] = useState<TelemetryData>({
    scansCompleted: 0,
    threatsDetected: 0,
    lastScanTime: 'Never',
    activeConnections: 0,
    cpuUsage: 0,
    memoryUsage: 0
  });

  const sidebarRef = useRef<HTMLDivElement>(null);
  const telemetryInterval = useRef<NodeJS.Timeout | null>(null);

  // ======================================================================
  // 1. INITIALIZATION & HARDWARE CHECK
  // ======================================================================
  useEffect(() => {
    const init = async () => {
      try {
        await initSystem();
        await checkSession();
        setSystemVRAM(systemVRAM);
        
        const timer = setTimeout(() => setBootSequence(false), 800);
        return () => clearTimeout(timer);
      } catch (error) {
        console.error('Initialization failed:', error);
        setBootSequence(false);
      }
    };
    
    init();
  }, [initSystem, checkSession, setSystemVRAM, systemVRAM]);

  // ======================================================================
  // 2. BACKEND CONNECTION HEALTH CHECK
  // ======================================================================
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/health', {
          method: 'GET',
          signal: AbortSignal.timeout(2000)
        });
        setBackendConnected(response.ok);
      } catch {
        setBackendConnected(false);
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // ======================================================================
  // 3. TELEMETRY LISTENER (Fixed UnlistenFn Type)
  // ======================================================================
  useEffect(() => {
    const setupTelemetry = async () => {
      try {
        const unlisten = await listen('telemetry_update', (event: any) => {
          const payload = event.payload as Partial<TelemetryData>;
          setTelemetryData(prev => ({
            ...prev,
            ...payload,
            lastScanTime: new Date().toLocaleTimeString()
          }));
        });

        return () => {
          // ✅ FIXED: UnlistenFn is a function, not a Promise
          unlisten();
        };
      } catch (error) {
        console.warn('Telemetry listener setup failed:', error);
      }
    };

    setupTelemetry();

    // Fallback: Simulate telemetry if WebSocket not available
    telemetryInterval.current = setInterval(() => {
      setTelemetryData(prev => ({
        ...prev,
        scansCompleted: prev.scansCompleted + (mode === 'passive' ? Math.floor(Math.random() * 2) : 0),
        lastScanTime: new Date().toLocaleTimeString(),
        activeConnections: 
          (permissions.ideIntegration ? 1 : 0) + 
          (permissions.browserIntegration ? 1 : 0)
      }));
    }, 5000);

    return () => {
      if (telemetryInterval.current) {
        clearInterval(telemetryInterval.current);
      }
    };
  }, [mode, permissions]);

  // ======================================================================
  // 4. THREAT LEVEL LISTENER (Fixed UnlistenFn Type)
  // ======================================================================
  useEffect(() => {
    const setupThreatListener = async () => {
      try {
        const unlisten = await listen('threat_detected', (event: any) => {
          const payload = event.payload as { level: string; source?: string };
          console.log('Threat detected:', payload);
        });

        return () => {
          // ✅ FIXED: UnlistenFn is a function, not a Promise
          unlisten();
        };
      } catch (error) {
        console.warn('Threat listener setup failed:', error);
      }
    };

    setupThreatListener();
  }, []);

  // ======================================================================
  // 5. OPERATOR INFO
  // ======================================================================
  const operatorName = user?.name ? user.name.split(' ')[0].toUpperCase() : 'OPERATOR';
  const isPassiveAvailable = systemVRAM >= 6144;
  const sessionId = user?.email ? user.email.slice(0, 8) + '...' : 'N/A';

  // ======================================================================
  // 6. PASSIVE MODE HANDLERS
  // ======================================================================
  const handleEngagePassive = useCallback(() => {
    if (isPassiveAvailable && !backendConnected) {
      alert('Backend not connected. Please ensure HackT Core is running.');
      return;
    }
    if (isPassiveAvailable) {
      setShowPassiveModal(true);
    }
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
  // 7. DYNAMIC DATA
  // ======================================================================
  const securityDiscoveries: SecurityDiscovery[] = messages
    .filter(m => m.sender === 'system' && m.text.includes('[THREAT]'))
    .slice(-5)
    .map((m, i) => ({
      id: `threat-${i}`,
      title: m.text.slice(0, 50) + '...',
      severity: 'high' as const,
      timestamp: new Date(m.timestamp).toLocaleTimeString(),
      source: 'vault.lance:sec-' + Math.floor(Math.random() * 100),
      page: Math.floor(Math.random() * 100)
    }));

  const displayDiscoveries: SecurityDiscovery[] = securityDiscoveries.length > 0 ? securityDiscoveries : [
    { 
      id: '1', 
      title: 'XSS Payload Intercepted', 
      severity: 'high', 
      timestamp: '2 min ago',
      source: 'vault.lance:sec-004',
      page: 12
    },
    { 
      id: '2', 
      title: 'Suspicious DOM Manipulation', 
      severity: 'medium', 
      timestamp: '15 min ago',
      source: 'vault.lance:sec-017',
      page: 34
    }
  ];

  const activeProjects: ActiveProject[] = messages
    .filter(m => m.sender === 'user')
    .slice(-5)
    .reverse()
    .map((m, i) => ({
      id: `proj-${i}`,
      title: m.text.slice(0, 30) + (m.text.length > 30 ? '...' : ''),
      lastActive: `${i + 1} min ago`,
      messagesCount: Math.floor(Math.random() * 10) + 1
    }));

  // ======================================================================
  // 8. HELP COMMAND SUGGESTIONS
  // ======================================================================
  const helpSuggestions = [
    { icon: <Shield size={12} />, text: 'Scan for vulnerabilities', command: 'Scan my code for security issues' },
    { icon: <BookOpen size={12} />, text: 'Explain vault concepts', command: 'Explain network forensics' },
    { icon: <Code size={12} />, text: 'Analyze current file', command: 'Analyze current file for bugs' },
    { icon: <Globe size={12} />, text: 'Check phishing threats', command: 'Is this website safe?' },
    { icon: <Monitor size={12} />, text: 'Screen analysis', command: 'Scan my screen for threats' },
    { icon: <Terminal size={12} />, text: 'System status', command: 'Show system status' }
  ];

  // ======================================================================
  // 9. RENDER
  // ======================================================================
  return (
    <div className={`relative flex h-screen w-screen bg-[#030305] text-[#e0e0e0] font-mono overflow-hidden transition-opacity duration-700 ${bootSequence ? 'opacity-0' : 'opacity-100'}`}>
      
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
                  <div className="text-xs text-white">IDE Integration (Port 8081)</div>
                  <div className="text-[10px] text-gray-500">Live code stream monitoring</div>
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
                className="flex-1 py-3 rounded-lg border border-[#1f1f1f] text-gray-400 hover:bg-white/5 transition-colors text-xs uppercase tracking-widest"
              >
                Cancel
              </button>
              <button 
                onClick={confirmPassiveMode}
                className="flex-1 py-3 rounded-lg bg-[#bc13fe]/20 border border-[#bc13fe]/50 text-[#bc13fe] hover:bg-[#bc13fe]/30 transition-all text-xs uppercase tracking-widest font-bold shadow-[0_0_15px_rgba(188,19,254,0.2)]"
              >
                Engage Sentinel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== LEFT: 3D Extendable Sidebar ==================== */}
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
            
            {/* ==================== Operator Greeting ==================== */}
            <div className="p-4 rounded-xl border border-[#00f3ff]/30 bg-gradient-to-br from-[#00f3ff]/5 to-transparent relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-[#00f3ff] to-transparent shadow-[0_0_15px_#00f3ff]" />
              <div className="flex items-center gap-3 mb-2">
                <div className="h-2 w-2 rounded-full bg-[#00f3ff] shadow-[0_0_8px_#00f3ff] animate-pulse" />
                <div className="text-[9px] text-[#00f3ff] uppercase tracking-widest">Authenticated Session</div>
              </div>
              <div className="text-sm font-bold text-white tracking-wide mb-1">WELCOME, {operatorName}</div>
              <div className="text-[10px] text-gray-500">
                Session: {sessionId} • {new Date().toLocaleDateString()}
              </div>
            </div>

            {/* ==================== Backend Connection Status ==================== */}
            <div className={`p-3 rounded-lg border flex items-center gap-2 ${
              backendConnected 
                ? 'border-green-500/30 bg-green-500/5' 
                : 'border-red-500/30 bg-red-500/5'
            }`}>
              {backendConnected ? (
                <Wifi size={14} className="text-green-500" />
              ) : (
                <WifiOff size={14} className="text-red-500" />
              )}
              <span className={`text-[9px] uppercase tracking-widest ${
                backendConnected ? 'text-green-400' : 'text-red-400'
              }`}>
                {backendConnected ? 'Core Online' : 'Core Offline'}
              </span>
            </div>

            {/* ==================== Tab Navigation ==================== */}
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

            {/* ==================== Dynamic Content Based on Tab ==================== */}
            {activeTab === 'projects' && (
              <section className="space-y-3 animate-in slide-in-from-left-4 duration-300">
                <div className="flex items-center justify-between">
                  <h2 className="text-[10px] uppercase text-gray-500 flex items-center gap-2 tracking-wider">
                    <Terminal size={12} /> Active Projects
                  </h2>
                  <span className="text-[9px] text-gray-600">{activeProjects.length} total</span>
                </div>
                <div className="space-y-2">
                  {activeProjects.length > 0 ? (
                    activeProjects.map((project) => (
                      <div 
                        key={project.id} 
                        className="group text-xs p-3 rounded-lg bg-gradient-to-r from-[#1f1f1f]/80 to-transparent border-l-2 border-[#00f3ff] cursor-pointer hover:translate-x-1 hover:bg-[#1f1f1f] transition-all duration-300"
                      >
                        <div className="text-white font-medium truncate">{project.title}</div>
                        <div className="flex items-center gap-2 mt-1 text-[9px] text-gray-500">
                          <Clock size={10} />
                          <span>{project.lastActive}</span>
                          <span>•</span>
                          <FileText size={10} />
                          <span>{project.messagesCount} msgs</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-gray-600 text-xs">
                      <Terminal size={24} className="mx-auto mb-2 opacity-50" />
                      <p>No active projects</p>
                      <p className="text-[9px]">Start chatting to create one</p>
                    </div>
                  )}
                </div>
              </section>
            )}

            {activeTab === 'security' && (
              <section className="space-y-3 animate-in slide-in-from-left-4 duration-300">
                <div className="flex items-center justify-between">
                  <h2 className="text-[10px] uppercase text-gray-500 flex items-center gap-2 tracking-wider">
                    <Shield size={12} /> Intel Gathered
                  </h2>
                  <span className={`text-[9px] ${threatLevel === 'high' ? 'text-red-500' : 'text-gray-600'}`}>
                    {displayDiscoveries.length} alerts
                  </span>
                </div>
                <div className="space-y-2">
                  {displayDiscoveries.map((discovery) => (
                    <div 
                      key={discovery.id} 
                      className={`group text-xs p-3 rounded-lg border cursor-pointer hover:shadow-lg transition-all duration-300 ${
                        discovery.severity === 'high' 
                          ? 'border-red-900/50 bg-red-900/10 hover:border-red-500/50' 
                          : 'border-yellow-900/50 bg-yellow-900/10 hover:border-yellow-500/50'
                      }`}
                    >
                      <div className={`font-medium ${
                        discovery.severity === 'high' ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {discovery.title}
                      </div>
                      <div className="flex items-center gap-2 mt-2 text-[9px] text-gray-500">
                        <AlertTriangle size={10} className={
                          discovery.severity === 'high' ? 'text-red-500' : 'text-yellow-500'
                        } />
                        <span>{discovery.timestamp}</span>
                        <span>•</span>
                        <Code size={10} />
                        <span>{discovery.source}</span>
                        <span>•</span>
                        <FileText size={10} />
                        <span>p.{discovery.page}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {activeTab === 'vault' && (
              <section className="space-y-3 animate-in slide-in-from-left-4 duration-300">
                <div className="flex items-center justify-between">
                  <h2 className="text-[10px] uppercase text-gray-500 flex items-center gap-2 tracking-wider">
                    <BookOpen size={12} /> Vault Modules
                  </h2>
                  <span className="text-[9px] text-gray-600">{vaultSkills.length} loaded</span>
                </div>
                <div className="space-y-3">
                  {vaultSkills.map((skill, idx) => (
                    <div 
                      key={idx} 
                      className="text-xs panel-3d p-3 rounded-lg bg-black/40 hover:bg-black/60 transition-all cursor-default group"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[#bc13fe] font-bold drop-shadow-[0_0_5px_rgba(188,19,254,0.3)]">
                          {skill.chapter}
                        </span>
                        <ExternalLink size={12} className="text-gray-600 group-hover:text-[#bc13fe] transition-colors" />
                      </div>
                      <ul className="list-disc list-inside text-gray-400 mt-1 ml-1 opacity-80 space-y-1">
                        {skill.topicsCovered.map((topic, i) => (
                          <li key={i} className="text-[10px]">{topic}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ==================== Telemetry Panel ==================== */}
            <div className="panel-3d p-4 rounded-xl border border-[#1f1f1f]/50 bg-[#0a0a0a]/60 space-y-3">
              <h3 className="text-gray-400 text-[10px] font-bold tracking-widest mb-3 uppercase flex items-center gap-2">
                <Activity size={12} /> System Telemetry
              </h3>
              
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">Scans Completed</span>
                  <span className="text-white text-xs font-mono">{telemetryData.scansCompleted}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">Threats Detected</span>
                  <span className={`text-xs font-mono ${
                    telemetryData.threatsDetected > 0 ? 'text-red-400' : 'text-green-400'
                  }`}>{telemetryData.threatsDetected}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">Last Scan</span>
                  <span className="text-white text-xs font-mono">{telemetryData.lastScanTime}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-[9px]">Active Connections</span>
                  <span className="text-[#00f3ff] text-xs font-mono">{telemetryData.activeConnections}</span>
                </div>
              </div>

              <div className="pt-3 border-t border-[#1f1f1f]">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-500 text-[9px]">Dedicated VRAM</span>
                  <span className={`text-xs font-bold ${
                    systemVRAM >= 6144 ? 'text-green-400' : 'text-yellow-500'
                  }`}>
                    {systemVRAM > 0 ? `${(systemVRAM / 1024).toFixed(1)} GB` : 'Scanning...'}
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

      {/* ==================== CENTER: Main Workspace ==================== */}
      <main className="relative z-10 flex-1 flex flex-col">
        
        {/* Top Header */}
        <header className="h-16 panel-3d flex items-center justify-between px-6 z-20 shadow-xl bg-black/40 backdrop-blur-md border-b border-[#1f1f1f]">
          <div className="flex items-center gap-4">
            <ModeToggle />
            
            {/* Mode Status Indicator */}
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

          {/* User Profile */}
          {user && (
            <div className="flex items-center gap-3">
              <div className="text-right hidden md:block">
                <div className="text-sm text-white font-bold">{user.name}</div>
                <div className="text-[10px] text-[#00f3ff] flex items-center gap-1 justify-end uppercase tracking-widest">
                  <div className="h-1.5 w-1.5 rounded-full bg-[#00f3ff] shadow-[0_0_5px_#00f3ff] animate-pulse"></div>
                  Link Established
                </div>
              </div>
              <button 
                onClick={logout} 
                title="Disconnect Session" 
                className="hover:scale-105 active:scale-95 transition-transform relative group"
                aria-label="Logout"
              >
                <img 
                  src={user.avatarUrl} 
                  alt="Profile" 
                  className="h-10 w-10 rounded-full border-2 border-[#1f1f1f] group-hover:border-red-500/50 object-cover transition-colors"
                />
              </button>
            </div>
          )}
        </header>

        {/* Passive Mode CTA Banner */}
        {mode === 'active' && (
          <div className="w-full bg-gradient-to-r from-red-950/40 via-[#1f1f1f]/80 to-transparent border-b border-red-900/30 p-3 px-6 flex items-center justify-between animate-in slide-in-from-top-2 duration-300">
            <div className="flex items-center gap-3 text-red-400">
              <EyeOff className="animate-pulse" size={18} />
              <div>
                <div className="text-xs font-bold tracking-widest uppercase">Sensory Uplink Offline</div>
                <div className="text-[10px] text-gray-400">
                  Your IDE and Browser are currently unmonitored.
                  {!isPassiveAvailable && (
                    <span className="text-red-500 ml-2">
                      (Requires 6GB+ VRAM)
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button 
              onClick={handleEngagePassive}
              disabled={!isPassiveAvailable || !backendConnected}
              className={`flex items-center gap-2 px-4 py-1.5 rounded border text-xs font-bold tracking-widest uppercase transition-all duration-300 ${
                isPassiveAvailable && backendConnected
                  ? 'border-[#00f3ff]/50 text-[#00f3ff] hover:bg-[#00f3ff]/10 hover:shadow-[0_0_15px_rgba(0,243,255,0.2)] hover:scale-105'
                  : 'border-gray-700 text-gray-600 cursor-not-allowed'
              }`}
            >
              <Zap size={14} />
              Engage Passive Mode
              <ChevronRight size={14} className="opacity-50" />
            </button>
          </div>
        )}

        {/* Help Suggestions Banner (First Time Users) */}
        {messages.length <= 1 && (
          <div className="w-full bg-gradient-to-r from-[#00f3ff]/5 via-[#1f1f1f]/80 to-transparent border-b border-[#00f3ff]/20 p-3 px-6 animate-in slide-in-from-top-2 duration-500">
            <div className="flex items-center gap-2 text-[#00f3ff] mb-2">
              <Terminal size={14} className="animate-pulse" />
              <div className="text-xs font-bold tracking-widest uppercase">Quick Start Commands</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {helpSuggestions.map((suggestion, i) => (
                <button
                  key={i}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#00f3ff]/30 text-[10px] text-[#00f3ff] hover:bg-[#00f3ff]/10 transition-all duration-300 hover:scale-105"
                  title={suggestion.command}
                >
                  {suggestion.icon}
                  <span>{suggestion.text}</span>
                </button>
              ))}
            </div>
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