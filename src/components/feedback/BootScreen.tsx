import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal, Cpu, CheckCircle} from 'lucide-react';

interface BootScreenProps {
  progress: number;
  threatLevel?: 'safe' | 'medium' | 'high' | 'critical';
  onBootComplete?: () => void;
}

interface BootLog {
  timestamp: number;
  message: string;
  level: 'info' | 'warning' | 'error' | 'success';
}

export default function BootScreen({ progress, threatLevel = 'safe', onBootComplete }: BootScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loadingText, setLoadingText] = useState('INITIALIZING NEURAL LINK...');
  const [bootLogs, setBootLogs] = useState<BootLog[]>([]);
  const [isReducedMotion, setIsReducedMotion] = useState(false);
  
  const progressRef = useRef(progress);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // ======================================================================
  // 1. ACCESSIBILITY: Reduced Motion Detection
  // ======================================================================
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setIsReducedMotion(mediaQuery.matches);
    
    const handleChange = (e: MediaQueryListEvent) => setIsReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // ======================================================================
  // 2. BOOT LOG MANAGEMENT
  // ======================================================================
  const addBootLog = useCallback((message: string, level: BootLog['level'] = 'info') => {
    setBootLogs(prev => {
      const newLog: BootLog = {
        timestamp: Date.now(),
        message,
        level
      };
      const updated = [...prev, newLog].slice(-8); // Keep last 8 logs
      return updated;
    });
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [bootLogs]);

  // Randomized fallback logs (if WebSocket isn't connected)
  useEffect(() => {
    if (progress < 100) {
      const fallbackLogs = [
        { msg: 'MOUNTING LOCAL KNOWLEDGE VAULT...', level: 'info' as const },
        { msg: 'BYPASSING OS TELEMETRY...', level: 'info' as const },
        { msg: 'ALLOCATING VRAM FOR FLORENCE-2...', level: 'info' as const },
        { msg: 'ESTABLISHING IPC BRIDGE...', level: 'info' as const },
        { msg: 'WAKING QWEN 3.5 CORE...', level: 'info' as const },
        { msg: 'ENCRYPTING LOCAL SOCKETS...', level: 'info' as const },
        { msg: 'LOADING NOMIC EMBEDDER (FP16)...', level: 'info' as const },
        { msg: 'INITIALIZING LANCEDB HYBRID SEARCH...', level: 'info' as const },
      ];
      
      const interval = setInterval(() => {
        if (progressRef.current < 100) {
          const random = fallbackLogs[Math.floor(Math.random() * fallbackLogs.length)];
          addBootLog(random.msg, random.level);
        }
      }, isReducedMotion ? 2000 : 400);
      
      return () => clearInterval(interval);
    }
  }, [progress, isReducedMotion, addBootLog]);

  // Update progress ref
  useEffect(() => {
    progressRef.current = progress;
    if (progress >= 100) {
      setLoadingText('SYSTEM SECURE. READY.');
      addBootLog('Boot sequence complete. Sovereign Core online.', 'success');
      // Notify parent that boot is complete
      setTimeout(() => onBootComplete?.(), 1500);
    }
  }, [progress, onBootComplete, addBootLog]);

  // ======================================================================
  // 3. CANVAS RENDERING: STARS & BINARY RAIN (Optimized)
  // ======================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Skip heavy animations if reduced motion is preferred
    if (isReducedMotion) {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      return;
    }

    let animationFrameId: number;

    // Make canvas full screen
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();

    // Starfield Setup
    const stars = Array.from({ length: 150 }).map(() => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.2,
      speed: Math.random() * 0.5 + 0.1,
      opacity: Math.random()
    }));

    // Binary Rain Setup
    const fontSize = 14;
    let columns = Math.floor(canvas.width / fontSize);
    const drops = Array.from({ length: columns }).map(() => Math.random() * -100);
    const chars = '01';

    const draw = () => {
      // Semi-transparent black to create the trail effect
      ctx.fillStyle = 'rgba(3, 3, 5, 0.2)'; 
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // 1. Draw Distant Stars
      stars.forEach(star => {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`;
        ctx.fill();

        // Move stars slowly upwards
        star.y -= star.speed;
        if (star.y < 0) {
          star.y = canvas.height;
          star.x = Math.random() * canvas.width;
        }
      });

      // 2. Draw Binary Rain
      ctx.font = `${fontSize}px monospace`;
      for (let i = 0; i < drops.length; i++) {
        const text = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillStyle = '#00f3ff'; 
        ctx.shadowBlur = 5;
        ctx.shadowColor = '#00f3ff';
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        ctx.shadowBlur = 0;

        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i] += 0.5; 
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    // Debounced resize handler
    let resizeTimeout: number;
    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = window.setTimeout(() => {
        resizeCanvas();
        columns = Math.floor(canvas.width / fontSize);
        if (columns > drops.length) {
          const extra = Array.from({ length: columns - drops.length }).map(() => Math.random() * -100);
          drops.push(...extra);
        }
      }, 100);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      clearTimeout(resizeTimeout);
      window.removeEventListener('resize', handleResize);
    };
  }, [isReducedMotion]);

  // ======================================================================
  // 4. KEYBOARD NAVIGATION & ACCESSIBILITY
  // ======================================================================
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow Escape to skip boot screen (for testing)
      if (e.key === 'Escape' && import.meta.env.DEV) {
        onBootComplete?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onBootComplete]);

  // ======================================================================
  // 5. RENDER HELPERS
  // ======================================================================
  const getLogColor = (level: BootLog['level']) => {
    switch (level) {
      case 'error': return 'text-[#ff003c]';
      case 'warning': return 'text-[#ffb000]';
      case 'success': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  const getThreatColor = () => {
    switch (threatLevel) {
      case 'critical': return 'border-[#ff003c] text-[#ff003c] animate-pulse';
      case 'high': return 'border-[#ff003c]/70 text-[#ff003c]';
      case 'medium': return 'border-[#ffb000] text-[#ffb000]';
      default: return 'border-[#00f3ff]/30 text-[#00f3ff]';
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#030305] overflow-hidden selection:bg-transparent"
      role="status"
      aria-live="polite"
      aria-label={`System booting: ${Math.floor(progress)}% complete`}
    >
      {/* Background Canvas */}
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 pointer-events-none opacity-60"
        aria-hidden="true"
      />

      {/* Radial Gradient Overlay for depth */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#030305_100%)] pointer-events-none" />

      {/* Scanline Overlay (Cyberpunk Effect) */}
      {!isReducedMotion && (
        <div 
          className="absolute inset-0 pointer-events-none opacity-10"
          style={{
            backgroundImage: 'linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px)',
            backgroundSize: '100% 4px',
            animation: 'scanline 8s linear infinite'
          }}
        />
      )}

      {/* ==================== FOREGROUND UI ==================== */}
      <div className="relative z-10 flex flex-col items-center w-full max-w-md px-8">

        {/* Logo / Icon with Glow */}
        <div className="relative mb-8 group">
          <div className="absolute inset-0 bg-[#00f3ff] blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-700 rounded-full" />
          <div className="relative p-6 border border-[#1f1f1f] bg-[#0a0a0a]/80 backdrop-blur-sm rounded-2xl shadow-[0_0_30px_rgba(0,0,0,0.8)]">
            {progress >= 100 ? (
              <CheckCircle size={48} className="text-green-400" strokeWidth={1} />
            ) : (
              <Cpu size={48} className="text-[#00f3ff]" strokeWidth={1} />
            )}
          </div>
        </div>

        <h1 className="text-2xl font-bold tracking-[0.3em] text-white mb-2 drop-shadow-lg">
          HACKT<span className="text-[#00f3ff]">.OS</span>
        </h1>

        {/* Simulated Command Line Output */}
        <div className="flex items-center gap-2 mb-6 text-[10px] text-[#00f3ff] font-mono tracking-widest uppercase h-4">
          <Terminal size={10} className={isReducedMotion ? '' : 'animate-pulse'} />
          <span className="sr-only">Boot status:</span>
          {loadingText}
        </div>

        {/* Progress Bar Container */}
        <div className="w-full space-y-2">
          <div className="flex justify-between text-[10px] text-gray-500 font-mono tracking-widest uppercase">
            <span>Boot Sequence</span>
            <span className="text-[#00f3ff]">{Math.floor(progress)}%</span>
          </div>

          <div 
            className="h-1.5 w-full bg-[#1f1f1f] rounded-full overflow-hidden shadow-inner relative"
            role="progressbar"
            aria-valuenow={Math.floor(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            {/* The actual progress fill */}
            <div 
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] transition-all duration-300 ease-out relative"
              style={{ width: `${Math.min(progress, 100)}%` }}
            >
              {/* Hot glowing tip on the progress bar */}
              {!isReducedMotion && (
                <div className="absolute right-0 top-0 bottom-0 w-4 bg-white blur-[2px] animate-pulse" />
              )}
            </div>
          </div>
        </div>

        {/* Boot Logs Terminal */}
        <div 
          ref={logContainerRef}
          className="w-full mt-6 h-32 bg-[#030303]/80 border border-[#1f1f1f] rounded-lg p-3 font-mono text-[9px] overflow-y-auto gloomy-scroll"
          aria-label="System boot logs"
        >
          {bootLogs.length === 0 ? (
            <div className="text-gray-600 italic">Waiting for telemetry...</div>
          ) : (
            bootLogs.map((log, i) => (
              <div key={i} className={`mb-1 ${getLogColor(log.level)}`}>
                <span className="text-gray-600 mr-2">[{new Date(log.timestamp).toLocaleTimeString().split(' ')[0]}]</span>
                {log.message}
              </div>
            ))
          )}
        </div>

        {/* Threat Warning (If initializing during an alert) */}
        {threatLevel !== 'safe' && (
          <div className={`mt-6 text-[9px] tracking-[0.2em] px-4 py-2 rounded-full border ${getThreatColor()}`}>
            ⚠ {threatLevel.toUpperCase()} THREAT DETECTED
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="absolute bottom-8 text-[9px] text-gray-600 uppercase tracking-widest text-center z-10">
        <span className="opacity-50">HackT Runtime v1.0.0 • © 2026 HackT Systems</span>
      </div>
    </div>
  );
}