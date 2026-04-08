import React, { useState, useEffect, useRef } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { 
  UserPlus, ShieldAlert, CheckCircle, AlertTriangle,
  ArrowLeft, Cpu, Database, Zap, Terminal, 
  Eye, Mic, Code
} from 'lucide-react';

export default function AuthScreen() {
  const { loginLocal, checkSession } = useSystemStore();

  // Auth States
  const [authStep, setAuthStep] = useState<'welcome' | 'identity' | 'booting' | 'complete'>('welcome');
  
  // Form States
  const [operatorName, setOperatorName] = useState('');
  const [avatarPreview, setAvatarPreview] = useState<string>('');
  
  // Boot Sequence States
  const [bootProgress, setBootProgress] = useState(0);
  const [bootStatus, setBootStatus] = useState('Initializing Sovereign Core...');
  const [bootLogs, setBootLogs] = useState<string[]>([]);
  
  // UI States
  const [error, setError] = useState<string | null>(null);
  
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // ======================================================================
  // 1. SESSION CHECK (Silent Bypass for returning users)
  // ======================================================================
  useEffect(() => {
    // If checkSession finds a user in localStorage, it will update Zustand.
    // App.tsx will automatically unmount this screen and jump to Dashboard.
    checkSession();
  }, [checkSession]);

  // Auto-scroll boot logs
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [bootLogs]);

  // ======================================================================
  // 2. LOCAL IDENTITY HANDLERS
  // ======================================================================
  const handleIdentitySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!operatorName.trim()) {
      setError('Operator alias required');
      return;
    }
    
    // Generate cyberpunk avatar
    const finalAvatar = avatarPreview || `https://ui-avatars.com/api/?name=${encodeURIComponent(operatorName)}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`;
    setAvatarPreview(finalAvatar);
    
    // 🔥 FIXED: We DO NOT call loginLocal() here! If we do, the component unmounts.
    // We just start the visual boot sequence.
    setAuthStep('booting');
    simulateBootSequence();
  };

  // 🔥 FIXED: This is called ONLY when the visual sequence is fully complete.
  const handleLaunchDashboard = async () => {
    // THIS triggers Zustand, which triggers App.tsx to unmount AuthScreen and mount Dashboard!
    await loginLocal(operatorName, avatarPreview);
  };

  const handleBack = () => {
    if (authStep === 'identity') setAuthStep('welcome');
  };

  // ======================================================================
  // 3. CYBERPUNK BOOT SEQUENCE SIMULATION
  // ======================================================================
  const simulateBootSequence = async () => {
    const bootSteps = [
      { progress: 10, status: 'Loading VRAM Guard...', log: '[SYSTEM] Initializing memory management...' },
      { progress: 25, status: 'Booting Qwen 3.5 LLM...', log: '[ENGINE] Loading Qwen-3.5-4B (Q4_K_M.gguf)...' },
      { progress: 40, status: 'Initializing Florence-2 Vision...', log: '[VISION] Loading Florence-2-base for OCR...' },
      { progress: 55, status: 'Mounting Knowledge Vault...', log: '[RAG] Connecting to LanceDB vault_chunks.lance...' },
      { progress: 70, status: 'Loading Nomic Embedder...', log: '[EMBED] Loading nomic-embed-text-v1.5 (FP16)...' },
      { progress: 85, status: 'Starting WebSocket Telemetry...', log: '[NETWORK] WebSocket bridge online on ws://127.0.0.1:8000/ws' },
      { progress: 95, status: 'Finalizing Sovereign Core...', log: '[SYSTEM] All systems nominal. Awaiting operator command.' },
      { progress: 100, status: 'Sovereign Core Online', log: '[SUCCESS] HackT Runtime v1.0.0 initialized.' }
    ];

    for (const step of bootSteps) {
      await new Promise(resolve => setTimeout(resolve, 800));
      setBootProgress(step.progress);
      setBootStatus(step.status);
      setBootLogs(prev => [...prev, step.log]);
    }

    await new Promise(resolve => setTimeout(resolve, 600));
    setAuthStep('complete');
  };

  // ======================================================================
  // 4. MAIN RENDER
  // ======================================================================
  return (
    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#030305]/95 backdrop-blur-xl text-[#e0e0e0] font-mono selection:bg-[#00f3ff] selection:text-black overflow-hidden">
      
      {/* Animated Background Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,243,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,243,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] animate-grid-move" />
      
      {/* Floating Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-[#00f3ff]/30 rounded-full animate-float"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${10 + Math.random() * 10}s`
            }}
          />
        ))}
      </div>

      {/* Top Left Branding */}
      <div className="absolute top-8 left-8 z-10">
        <h1 className="text-2xl font-bold tracking-widest text-white drop-shadow-[0_0_10px_rgba(0,243,255,0.5)]">
          HACKT<span className="text-[#00f3ff]">.AI</span>
        </h1>
        <div className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">
          Sovereign Runtime v1.0.0
        </div>
      </div>

      {/* 3D Auth Module */}
      <div className="w-full max-w-md panel-3d rounded-2xl p-8 transform transition-all duration-500 shadow-[0_0_80px_rgba(0,0,0,0.5)] border border-[#1f1f1f] relative z-10 animate-fade-in-up">
        
        {/* Dynamic Header */}
        <div className="text-center mb-8">
          {authStep === 'welcome' && (
            <>
              <div className="relative inline-block mb-4">
                <ShieldAlert className="mx-auto text-[#00f3ff] animate-pulse" size={56} />
                <div className="absolute inset-0 bg-[#00f3ff]/20 blur-xl rounded-full animate-pulse" />
              </div>
              <h2 className="text-2xl font-bold tracking-widest text-white mb-2">
                SOVEREIGN ACCESS
              </h2>
              <p className="text-xs text-gray-400 uppercase tracking-widest">
                Local Identity Verification Required
              </p>
            </>
          )}
          {authStep === 'identity' && (
            <>
              <UserPlus className="mx-auto mb-4 text-[#00f3ff] animate-pulse" size={56} />
              <h2 className="text-2xl font-bold tracking-widest text-white mb-2">
                ESTABLISH IDENTITY
              </h2>
              <p className="text-xs text-gray-400 uppercase tracking-widest">
                Create Your Operator Alias
              </p>
            </>
          )}
          {authStep === 'booting' && (
            <>
              <Terminal className="mx-auto mb-4 text-[#00f3ff] animate-pulse" size={56} />
              <h2 className="text-2xl font-bold tracking-widest text-white mb-2">
                SYSTEM INITIALIZATION
              </h2>
              <p className="text-xs text-gray-400 uppercase tracking-widest">
                Loading AI Subsystems...
              </p>
            </>
          )}
          {authStep === 'complete' && (
            <>
              <CheckCircle className="mx-auto mb-4 text-green-500 animate-bounce" size={56} />
              <h2 className="text-2xl font-bold tracking-widest text-white mb-2">
                ACCESS GRANTED
              </h2>
              <p className="text-xs text-gray-400 uppercase tracking-widest">
                Sovereign Core Operational
              </p>
            </>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-900/20 border border-red-500/30 flex items-center gap-2 text-red-400 text-sm animate-in slide-in-from-bottom-2">
            <AlertTriangle size={16} className="animate-pulse" />
            <span>{error}</span>
          </div>
        )}

        {/* Step Content */}
        {authStep === 'welcome' && (
          <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <button
              onClick={() => setAuthStep('identity')}
              className="w-full py-4 bg-gradient-to-r from-[#00f3ff]/10 to-[#bc13fe]/10 border border-[#00f3ff]/30 text-[#00f3ff] rounded-xl hover:border-[#bc13fe]/50 transition-all font-bold tracking-widest text-sm shadow-[0_0_15px_rgba(0,243,255,0.1)] hover:shadow-[0_0_20px_rgba(188,19,254,0.2)] flex items-center justify-center gap-2 animate-pulse-slow"
            >
              <UserPlus size={16} />
              BEGIN LOCAL AUTHENTICATION
            </button>
            <div className="pt-4 text-center">
              <p className="text-[9px] text-gray-600 uppercase tracking-widest">
                By proceeding, you acknowledge that all processing occurs locally on your hardware.
              </p>
            </div>
          </div>
        )}

        {authStep === 'identity' && (
          <form onSubmit={handleIdentitySubmit} className="space-y-5 animate-in fade-in slide-in-from-right-8 duration-300">
            <div className="text-center">
              <div className="h-16 flex items-center justify-center mb-2">
                {avatarPreview ? (
                  <img 
                    src={avatarPreview} 
                    alt="Preview" 
                    className="w-16 h-16 rounded-full mx-auto border-2 border-[#00f3ff] shadow-[0_0_15px_rgba(0,243,255,0.3)]"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full border border-dashed border-gray-600 mx-auto flex items-center justify-center text-gray-600">
                    ?
                  </div>
                )}
              </div>
            </div>

            <div>
              <label className="block text-[9px] text-gray-500 uppercase tracking-widest mb-2">Alias</label>
              <div className="relative">
                <UserPlus className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-600" size={18} />
                <input 
                  type="text" 
                  required
                  minLength={2}
                  maxLength={20}
                  value={operatorName}
                  onChange={(e) => {
                    setOperatorName(e.target.value);
                    if (e.target.value.trim()) {
                      setAvatarPreview(`https://ui-avatars.com/api/?name=${encodeURIComponent(e.target.value)}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`);
                    } else {
                      setAvatarPreview('');
                    }
                  }}
                  placeholder="e.g., CYBER_GUARDIAN" 
                  className="w-full input-3d rounded-xl py-4 pl-12 pr-4 text-white text-sm font-mono focus:outline-none placeholder-gray-600 tracking-widest border border-[#00f3ff]/30 focus:border-[#00f3ff] bg-[#050505]"
                  autoFocus
                />
              </div>
            </div>

            <button 
              type="submit" 
              disabled={!operatorName.trim()}
              className="w-full py-4 bg-[#00f3ff]/10 text-[#00f3ff] rounded-xl hover:bg-[#00f3ff]/20 transition-all border border-[#00f3ff]/30 hover:shadow-[0_0_25px_rgba(0,243,255,0.3)] text-sm tracking-widest font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <CheckCircle size={16} />
              CONFIRM IDENTITY
            </button>

            <button 
              type="button" 
              onClick={handleBack} 
              className="w-full text-[9px] text-gray-500 hover:text-white tracking-widest mt-2 flex items-center justify-center gap-1 group"
            >
              <ArrowLeft size={12} className="group-hover:-translate-x-1 transition-transform" />
              BACK TO WELCOME
            </button>
          </form>
        )}

        {authStep === 'booting' && (
          <div className="space-y-4 animate-in fade-in duration-300">
            <div className="text-center space-y-2">
              <h3 className="text-sm font-bold text-[#00f3ff] tracking-widest">{bootStatus}</h3>
            </div>

            {/* Progress Bar */}
            <div className="w-full h-2 bg-[#1f1f1f] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] transition-all duration-500 ease-out"
                style={{ width: `${bootProgress}%` }}
              />
            </div>

            {/* Terminal Logs */}
            <div className="w-full h-32 bg-[#030303] border border-[#1f1f1f] rounded-lg p-3 font-mono text-[9px] overflow-y-auto gloomy-scroll">
              {bootLogs.map((log, i) => (
                <div key={i} className={`mb-1 ${
                  log.includes('[SUCCESS]') ? 'text-green-400' : 
                  log.includes('[ERROR]') ? 'text-red-400' : 
                  'text-gray-400'
                }`}>
                  <span className="text-gray-600 mr-2">{'>'}</span>{log}
                </div>
              ))}
              <div ref={terminalEndRef} />
            </div>

            {/* Feature Badges */}
            <div className="grid grid-cols-3 gap-2 mt-4">
              {[
                { icon: Cpu, label: 'Qwen 3.5', color: 'text-[#00f3ff]' },
                { icon: Eye, label: 'Florence-2', color: 'text-[#bc13fe]' },
                { icon: Database, label: 'LanceDB', color: 'text-green-400' }
              ].map((feature, i) => (
                <div key={i} className="flex flex-col items-center p-2 bg-[#050505] border border-[#1f1f1f] rounded-lg">
                  <feature.icon size={16} className={feature.color} />
                  <span className="text-[8px] text-gray-500 mt-1">{feature.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {authStep === 'complete' && (
          <div className="space-y-6 text-center animate-in fade-in zoom-in duration-500">
            <p className="text-gray-400 text-sm animate-fade-in-delayed">
              Welcome, <span className="text-[#00f3ff] font-bold">{operatorName}</span>. Your local AI agent is ready.
            </p>

            {/* System Status Grid */}
            <div className="grid grid-cols-2 gap-3 mt-6 animate-fade-in-delayed">
              {[
                { icon: Cpu, label: 'LLM Engine', status: 'Qwen 3.5 ONLINE', color: 'text-[#00f3ff]' },
                { icon: Eye, label: 'Vision OCR', status: 'Florence-2 ONLINE', color: 'text-[#bc13fe]' },
                { icon: Mic, label: 'Audio Core', status: 'Full-Duplex ONLINE', color: 'text-green-400' },
                { icon: Code, label: 'Code Watcher', status: 'Passive Monitor ACTIVE', color: 'text-yellow-400' }
              ].map((system, i) => (
                <div key={i} className="p-3 bg-[#050505] border border-[#1f1f1f] rounded-lg text-center hover:border-[#00f3ff]/50 transition-colors">
                  <system.icon className={`mx-auto mb-2 ${system.color}`} size={20} />
                  <div className="text-[9px] text-gray-500">{system.label}</div>
                  <div className="text-xs font-bold text-white">{system.status}</div>
                </div>
              ))}
            </div>

            <button
              onClick={handleLaunchDashboard}
              className="w-full mt-6 py-4 bg-[#00f3ff] text-black rounded-xl hover:bg-white transition-all font-bold tracking-widest text-sm shadow-[0_0_20px_rgba(0,243,255,0.4)] hover:shadow-[0_0_30px_rgba(255,255,255,0.6)] flex items-center justify-center gap-2 animate-pulse-slow"
            >
              <Zap size={16} />
              LAUNCH DASHBOARD
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="absolute bottom-8 text-[9px] text-gray-600 uppercase tracking-widest text-center z-10 space-y-1">
        <div className="flex items-center justify-center gap-4">
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
            Local Execution
          </span>
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-[#00f3ff] animate-pulse" />
            End-to-End Encryption
          </span>
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-[#bc13fe] animate-pulse" />
            Sovereign Vault
          </span>
        </div>
        <span className="opacity-50 inline-block mt-2">HackT Runtime • © 2026 HackT Systems</span>
      </div>
    </div>
  );
}