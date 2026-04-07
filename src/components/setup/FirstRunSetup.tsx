import { useState, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/tauri';
import { Download, CheckCircle, AlertTriangle, Shield, Cpu, Globe } from 'lucide-react';

interface Model {
  name: string;
  filename: string;
  size_gb: number;
  required: boolean;
  path: string;
  url: string;           // <-- ADDED THIS (Fixes TS Error 2339)
  mirror_url?: string;   // <-- Added optional mirror
  sha256?: string; 
  note?: string;
}

export default function FirstRunSetup() {
  const [currentStep, setCurrentStep] = useState<'permissions' | 'models' | 'downloading' | 'complete'>('permissions');
  const [permissions, setPermissions] = useState({
    mic: true,
    screen: true,
    network: true,
    startup: false
  });
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [currentModel, setCurrentModel] = useState('');
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load models manifest
    fetch('/models-manifest.json')
      .then(res => res.json())
      .then(data => setModels(data.models))
      .catch(err => setError('Failed to load models manifest'));
  }, []);

  const handleDownloadModels = async () => {
    setCurrentStep('downloading');
    setError(null);
    
    try {
      for (let i = 0; i < models.length; i++) {
        const model = models[i];
        setCurrentModel(model.name);
        setDownloadProgress(0); 
        
        // 1. Set up the listener
        const unlisten = await listen<{ loaded: number, total: number }>(
          'download_progress', 
          (event) => {
            if (event.payload.total > 0) {
              const percent = (event.payload.loaded / event.payload.total) * 100;
              setDownloadProgress(percent);
            }
          }
        );

        try {
          // 2. Instruct Rust to download
          await invoke('download_model_rust', { 
            url: model.url, 
            filename: model.filename,
            savePath: model.path 
          });
        } finally {
          // 3. GUARANTEED Cleanup: runs whether invoke succeeds or throws an error
          unlisten();
        }
      }
      
      setCurrentStep('complete');
    } catch (err: any) {
      console.error("Download pipeline failed:", err);
      setError(typeof err === 'string' ? err : err.message || "Model download failed. Check your connection.");
      setCurrentStep('models'); 
    }
  };

  const handleRequestPermissions = async () => {
    // Request Windows permissions via Tauri
    try {
      if (permissions.mic) {
        await invoke('request_microphone_permission');
      }
      if (permissions.screen) {
        await invoke('request_screen_capture_permission');
      }
      setCurrentStep('models');
    } catch (err) { // <-- Removed ': any'
      // ✅ Handle both Tauri string rejections and standard JS Errors
      if (typeof err === 'string') {
        setError(err);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to acquire permissions');
      }
    }
  };

  const handleFinish = async () => {
    try {
      // 1. Tell Rust to create the setup_complete file
      await invoke('mark_setup_complete');
      
      // 2. Navigate to the main dashboard
      window.location.hash = '/'; 
    } catch (err) {
      console.error("Failed to finish setup:", err);
    }
  };

  return (
    <div className="h-screen w-screen bg-[#030305] text-white flex items-center justify-center font-mono">
      <div className="panel-3d w-full max-w-2xl p-8 rounded-2xl border border-[#1f1f1f]">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-widest mb-2">
            HACKT<span className="text-[#00f3ff]">.AI</span> SETUP
          </h1>
          <p className="text-gray-400 text-sm">Welcome to HackT Runtime v1.0.0</p>
        </div>

        {/* Progress Steps */}
        <div className="flex justify-between mb-8">
          {['Permissions', 'Models', 'Download', 'Complete'].map((step, i) => (
            <div key={step} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                currentStep === step.toLowerCase() || 
                (['models', 'downloading', 'complete'].includes(currentStep) && i === 0) ||
                (['downloading', 'complete'].includes(currentStep) && i === 1) ||
                (currentStep === 'complete' && i === 2)
                  ? 'bg-[#00f3ff] text-black'
                  : 'bg-[#1f1f1f] text-gray-500'
              }`}>
                {i + 1}
              </div>
              <span className={`ml-2 text-xs ${
                currentStep === step.toLowerCase() ? 'text-[#00f3ff]' : 'text-gray-500'
              }`}>{step}</span>
              {i < 3 && <div className="w-16 h-0.5 bg-[#1f1f1f] ml-4" />}
            </div>
          ))}
        </div>

        {/* Step Content */}
        {currentStep === 'permissions' && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold mb-4">System Permissions</h2>
            <p className="text-gray-400 text-sm mb-6">
              HackT Runtime requires the following permissions to function. All data processing occurs locally.
            </p>
            
            {[
              { key: 'mic', icon: '🎤', title: 'Microphone Access', desc: 'Voice commands via Faster-Whisper (CPU)' },
              { key: 'screen', icon: '👁️', title: 'Screen Capture', desc: 'OCR & threat detection via Florence-2 (Passive Mode)' },
              { key: 'network', icon: '🌐', title: 'Network Proxy', desc: 'Browser phishing detection (localhost only)' },
              { key: 'startup', icon: '🚀', title: 'Start with Windows', desc: 'Launch automatically on system startup' }
            ].map((perm) => (
              <label key={perm.key} className="flex items-start gap-4 p-4 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f] cursor-pointer hover:border-[#00f3ff]/50 transition-colors">
                <input
                  type="checkbox"
                  checked={permissions[perm.key as keyof typeof permissions]}
                  onChange={(e) => setPermissions({ ...permissions, [perm.key]: e.target.checked })}
                  className="mt-1 w-4 h-4 rounded border-[#1f1f1f] bg-[#0a0a0a] text-[#00f3ff] focus:ring-[#00f3ff]"
                />
                <div>
                  <div className="font-bold text-sm">{perm.icon} {perm.title}</div>
                  <div className="text-gray-500 text-xs mt-1">{perm.desc}</div>
                </div>
              </label>
            ))}

            <button
              onClick={handleRequestPermissions}
              className="w-full py-3 bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] rounded-lg hover:bg-[#00f3ff]/20 transition-all font-bold tracking-widest text-sm"
            >
              CONTINUE
            </button>
          </div>
        )}

        {currentStep === 'models' && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold mb-4">AI Models Download</h2>
            <p className="text-gray-400 text-sm mb-6">
              HackT Runtime requires AI models (~9.6 GB total). Choose your download preference:
            </p>

            <div className="space-y-4">
              {models.map((model) => (
                <div key={model.filename} className="p-4 rounded-lg bg-[#0a0a0a]/50 border border-[#1f1f1f]">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-sm">{model.name}</div>
                      <div className="text-gray-500 text-xs mt-1">
                        {model.size_gb} GB • {model.path}
                        {model.note && <span className="text-[#bc13fe]"> • {model.note}</span>}
                        {model.required && <span className="text-red-400"> • Required</span>}
                      </div>
                    </div>
                    {model.required ? (
                      <Shield size={16} className="text-[#00f3ff]" />
                    ) : (
                      <Cpu size={16} className="text-gray-500" />
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-4">
              <button
                onClick={handleDownloadModels}
                className="flex-1 py-3 bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] rounded-lg hover:bg-[#00f3ff]/20 transition-all font-bold tracking-widest text-sm flex items-center justify-center gap-2"
              >
                <Download size={16} />
                DOWNLOAD NOW
              </button>
              <button
                onClick={() => setCurrentStep('complete')}
                className="flex-1 py-3 bg-[#1f1f1f] border border-[#1f1f1f] text-gray-400 rounded-lg hover:bg-[#2a2a2a] transition-all font-bold tracking-widest text-sm"
              >
                SKIP (DOWNLOAD LATER)
              </button>
            </div>
          </div>
        )}

        {currentStep === 'downloading' && (
          <div className="space-y-6 text-center">
            <h2 className="text-xl font-bold mb-4">Downloading Models</h2>
            <p className="text-gray-400 text-sm">Current: {currentModel}</p>
            
            <div className="w-full h-4 bg-[#1f1f1f] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] transition-all duration-300"
                style={{ width: `${downloadProgress}%` }}
              />
            </div>
            
            <div className="text-[#00f3ff] font-mono">{downloadProgress.toFixed(1)}%</div>
            
            <p className="text-gray-500 text-xs">
              This may take several minutes depending on your internet connection.
            </p>
          </div>
        )}

        {currentStep === 'complete' && (
          <div className="space-y-6 text-center">
            <CheckCircle size={64} className="mx-auto text-green-500" />
            <h2 className="text-xl font-bold mb-4">Setup Complete!</h2>
            <p className="text-gray-400 text-sm mb-6">
              HackT Runtime is ready to launch. Your local AI security agent is now active.
            </p>

            <div className="p-4 rounded-lg bg-green-900/20 border border-green-500/30 text-left">
              <div className="flex items-center gap-2 text-green-400 text-sm mb-2">
                <CheckCircle size={16} />
                <span>Permissions Granted</span>
              </div>
              <div className="flex items-center gap-2 text-green-400 text-sm mb-2">
                <CheckCircle size={16} />
                <span>Models Downloaded</span>
              </div>
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <CheckCircle size={16} />
                <span>Backend Ready</span>
              </div>
            </div>

            <button
              onClick={handleFinish}
              className="w-full py-3 bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] rounded-lg hover:bg-[#00f3ff]/20 transition-all font-bold tracking-widest text-sm"
            >
              LAUNCH HACKT RUNTIME
            </button>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-6 p-4 rounded-lg bg-red-900/20 border border-red-500/30 flex items-center gap-2 text-red-400 text-sm">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-[#1f1f1f] text-center">
          <p className="text-[10px] text-gray-600">
            By continuing, you agree to our{' '}
            <a href="#" className="text-[#00f3ff] hover:underline">Terms of Service</a>
            {' '}and{' '}
            <a href="privacy.html" className="text-[#00f3ff] hover:underline">Privacy Policy</a>
          </p>
          <p className="text-[9px] text-gray-700 mt-2">
            HackT Runtime v1.0.0 • © 2026 HackT Systems
          </p>
        </div>
      </div>
    </div>
  );
}