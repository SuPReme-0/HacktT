import { useState, useEffect, useRef } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/tauri';
import { 
  Download, 
  CheckCircle, 
  AlertTriangle, 
  Shield, 
  Cpu, 
  Terminal,
  Eye,
  Mic,
  Loader2,
  Play
} from 'lucide-react';

export default function FirstRunSetup() {
  const [currentStep, setCurrentStep] = useState<'permissions' | 'downloading' | 'complete'>('permissions');
  
  const [permissions, setPermissions] = useState({
    mic: true,
    screen: true,
    network: true,
  });
  
  // Terminal Logs State
  const [logs, setLogs] = useState<string[]>(["[SYSTEM]: Initializing Sovereign Bootstrapper..."]);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the terminal when new logs arrive
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleRequestPermissions = async () => {
    try {
      // 1. Request Windows permissions via our Rust `permissions.rs` module
      if (permissions.mic) {
        await invoke('request_microphone_permission').catch(console.warn);
      }
      if (permissions.screen) {
        await invoke('request_screen_capture_permission').catch(console.warn);
      }
      
      // Move to download phase
      handleStartBootstrap();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleStartBootstrap = async () => {
    setCurrentStep('downloading');
    setError(null);
    setIsDownloading(true);
    setLogs(["[SYSTEM]: Launching Python Bootstrap Subsystem...", "[INFO]: Connecting to HuggingFace & Google Drive mirrors..."]);
    
    let unlisten: UnlistenFn | undefined;
    
    try {
      // 1. Listen for the Python terminal output being piped through Rust
      unlisten = await listen<string>('bootstrapper_log', (event) => {
        setLogs(prev => {
          // Keep terminal from overflowing memory (max 100 lines)
          const newLogs = [...prev, event.payload];
          return newLogs.length > 100 ? newLogs.slice(newLogs.length - 100) : newLogs;
        });
      });

      // 2. Instruct Rust to spawn `python main.py --bootstrap`
      // This will freeze here until the Python script finishes downloading everything!
      await invoke('run_model_bootstrapper');
      
      // 3. Cleanup listener and finish
      if (unlisten) unlisten();
      setIsDownloading(false);
      setCurrentStep('complete');
      
    } catch (err: any) {
      console.error("Bootstrap pipeline failed:", err);
      setError(typeof err === 'string' ? err : err.message || "Model download failed. Check your connection.");
      // Add error to terminal
      setLogs(prev => [...prev, `[FATAL ERROR]: ${err.message || err}`]);
      setIsDownloading(false);
    }
  };

  const handleFinish = async () => {
    try {
      // 1. Tell Rust to create the setup_complete file in %AppData%
      await invoke('mark_setup_complete');
      
      // 2. Hard reload the frontend to trigger the App.tsx Boot Sequence
      window.location.reload(); 
    } catch (err) {
      console.error("Failed to finish setup:", err);
      setError("Failed to finalize setup. Please try again.");
    }
  };

  return (
    <div className="h-screen w-screen bg-[#030305] text-white flex items-center justify-center font-mono select-none overflow-hidden">
      {/* Animated Background Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,243,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,243,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] animate-grid-move" />
      
      <div className="panel-3d w-full max-w-3xl p-8 rounded-2xl border border-[#1f1f1f] bg-[#0a0a0a]/90 backdrop-blur-md shadow-2xl relative z-10 animate-fade-in-up">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-widest mb-2 drop-shadow-[0_0_10px_rgba(0,243,255,0.5)] animate-pulse-slow">
            HACKT<span className="text-[#00f3ff]">.AI</span> SOVEREIGN CORE
          </h1>
          <p className="text-gray-400 text-sm">Initialization & Neural Matrix Download</p>
        </div>

        {/* Step Content */}
        {currentStep === 'permissions' && (
          <div className="space-y-6 animate-in fade-in zoom-in duration-300">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Shield className="text-[#00f3ff] animate-pulse" /> OS Access Requirements
            </h2>
            <p className="text-gray-400 text-sm mb-6 border-l-2 border-[#00f3ff] pl-3">
              To operate as a Sovereign agent, HackT requires low-level OS permissions. 
              <span className="text-white font-bold ml-1">No data ever leaves your machine.</span>
            </p>
            
            <div className="space-y-3">
              {[
                { key: 'mic', icon: '🎤', title: 'Microphone Intercept', desc: 'Required for Full-Duplex Voice Commands (Faster-Whisper)' },
                { key: 'screen', icon: '👁️', title: 'Screen Capture', desc: 'Required for Passive OCR Threat Detection (Florence-2)' },
                { key: 'network', icon: '🌐', title: 'Local Proxy Binding', desc: 'Required for active browser phishing interception' }
              ].map((perm) => (
                <label key={perm.key} className="flex items-start gap-4 p-4 rounded-lg bg-[#050505] border border-[#1f1f1f] cursor-pointer hover:border-[#00f3ff]/50 transition-colors group animate-fade-in">
                  <input
                    type="checkbox"
                    checked={permissions[perm.key as keyof typeof permissions]}
                    onChange={(e) => setPermissions({ ...permissions, [perm.key]: e.target.checked })}
                    className="mt-1 w-4 h-4 rounded border-[#1f1f1f] bg-[#0a0a0a] text-[#00f3ff] focus:ring-[#00f3ff] animate-pulse-slow"
                  />
                  <div>
                    <div className="font-bold text-sm text-gray-200 group-hover:text-[#00f3ff] transition-colors">
                      {perm.icon} {perm.title}
                    </div>
                    <div className="text-gray-500 text-xs mt-1">{perm.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            <button
              onClick={handleRequestPermissions}
              className="w-full mt-4 py-3 bg-gradient-to-r from-[#00f3ff]/10 to-[#bc13fe]/10 border border-[#00f3ff]/30 text-[#00f3ff] rounded-lg hover:border-[#bc13fe]/50 transition-all font-bold tracking-widest text-sm shadow-[0_0_15px_rgba(0,243,255,0.1)] hover:shadow-[0_0_20px_rgba(188,19,254,0.2)] flex items-center justify-center gap-2 animate-pulse-slow"
            >
              <Play size={16} />
              GRANT ACCESS & BEGIN SECURE DOWNLOAD
            </button>
          </div>
        )}

        {currentStep === 'downloading' && (
          <div className="space-y-4 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Download className="text-[#00f3ff] animate-bounce" /> Matrix Synchronization
              </h2>
              <div className="flex items-center gap-2 text-xs text-[#00f3ff] animate-pulse">
                <Cpu size={14} /> Neural Weights Downloading (~9.6 GB)
              </div>
            </div>
            
            <p className="text-gray-400 text-xs">
              Do not close this window. The Python subsystem is establishing the Sovereign Core.
            </p>
            
            {/* The "Hacker Terminal" for Python Logs */}
            <div className="w-full h-64 bg-[#030303] border border-[#1f1f1f] rounded-lg p-4 font-mono text-[10px] overflow-y-auto gloomy-scroll relative">
              <div className="absolute top-2 right-2 text-gray-600 animate-pulse">
                <Terminal size={14} />
              </div>
              {logs.map((log, i) => (
                <div key={i} className={`mb-1 ${
                  log.includes('ERROR') || log.includes('Failed') ? 'text-[#ff003c] animate-pulse' : 
                  log.includes('✅') ? 'text-green-400' : 
                  log.includes('Downloading') ? 'text-[#00f3ff]' : 
                  'text-gray-400'
                }`}>
                  <span className="text-gray-600 mr-2">{'>'}</span>{log}
                </div>
              ))}
              <div ref={terminalEndRef} />
            </div>

            {/* Loading Indicator */}
            {isDownloading && (
              <div className="flex items-center justify-center gap-2 text-[#00f3ff] text-xs animate-pulse">
                <Loader2 size={14} className="animate-spin" />
                <span>Python subsystem active... awaiting model sync</span>
              </div>
            )}

            {error && (
               <button 
                 onClick={handleStartBootstrap} 
                 className="w-full py-2 bg-red-900/20 border border-red-500/30 text-red-400 rounded hover:bg-red-900/40 text-xs font-bold animate-pulse"
               >
                 RETRY DOWNLOAD
               </button>
            )}
          </div>
        )}

        {currentStep === 'complete' && (
          <div className="space-y-6 text-center animate-in fade-in zoom-in duration-500">
            <div className="relative inline-block">
              <div className="absolute inset-0 bg-green-500/20 blur-xl rounded-full animate-pulse" />
              <CheckCircle size={80} className="relative text-green-500 mx-auto animate-bounce" />
            </div>
            
            <h2 className="text-2xl font-bold text-white animate-fade-in">System Fully Armed</h2>
            <p className="text-gray-400 text-sm animate-fade-in-delayed">
              The HackT Sovereign Core has been successfully compiled and installed.
            </p>

            <div className="grid grid-cols-3 gap-4 mt-6 animate-fade-in-delayed">
              <div className="p-3 bg-[#050505] border border-[#1f1f1f] rounded-lg text-center hover:border-[#00f3ff]/50 transition-colors animate-fade-in-stagger-1">
                <Shield className="mx-auto text-[#00f3ff] mb-2 animate-pulse" size={20} />
                <div className="text-[10px] text-gray-500">LLM Engine</div>
                <div className="text-xs font-bold text-white">Qwen 3.5 ONLINE</div>
              </div>
              <div className="p-3 bg-[#050505] border border-[#1f1f1f] rounded-lg text-center hover:border-[#bc13fe]/50 transition-colors animate-fade-in-stagger-2">
                <Eye className="mx-auto text-[#bc13fe] mb-2 animate-pulse" size={20} />
                <div className="text-[10px] text-gray-500">Vision OCR</div>
                <div className="text-xs font-bold text-white">Florence-2 ONLINE</div>
              </div>
              <div className="p-3 bg-[#050505] border border-[#1f1f1f] rounded-lg text-center hover:border-green-400/50 transition-colors animate-fade-in-stagger-3">
                <Mic className="mx-auto text-green-400 mb-2 animate-pulse" size={20} />
                <div className="text-[10px] text-gray-500">Audio Core</div>
                <div className="text-xs font-bold text-white">Full-Duplex ONLINE</div>
              </div>
            </div>

            <button
              onClick={handleFinish}
              className="w-full mt-6 py-4 bg-[#00f3ff] text-black rounded-lg hover:bg-white transition-all font-bold tracking-widest text-sm shadow-[0_0_20px_rgba(0,243,255,0.4)] hover:shadow-[0_0_30px_rgba(255,255,255,0.6)] flex items-center justify-center gap-2 animate-pulse-slow"
            >
              <Play size={16} />
              INITIALIZE AGENT
            </button>
          </div>
        )}

        {/* Global Error Display */}
        {error && currentStep !== 'downloading' && (
          <div className="mt-6 p-4 rounded-lg bg-red-900/20 border border-[#ff003c]/30 flex items-center gap-3 text-[#ff003c] text-sm animate-in slide-in-from-bottom-2">
            <AlertTriangle size={18} className="animate-pulse" />
            <span className="font-medium">{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}