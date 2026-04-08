import { useEffect, useRef } from 'react';
import { AlertTriangle, RefreshCw, Terminal, XOctagon } from 'lucide-react';
import { useSystemStore } from '../../store/systemStore';

interface ErrorBoundaryProps {
  error: string | null;
  onRetry: () => void;
  threatLevel?: 'safe' | 'medium' | 'high' | 'critical';
}

export default function ErrorBoundary({ error, onRetry, threatLevel = 'safe' }: ErrorBoundaryProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { systemVRAM, backendConnected } = useSystemStore();

  // Get dynamic styling based on threat level
  const getThreatStyles = () => {
    switch (threatLevel) {
      case 'critical':
        return {
          border: 'border-[#ff003c]',
          bg: 'bg-red-950/30',
          text: 'text-[#ff003c]',
          shadow: 'shadow-[0_0_80px_rgba(255,0,60,0.3)]',
          pulse: 'animate-pulse'
        };
      case 'high':
        return {
          border: 'border-[#ff003c]/70',
          bg: 'bg-red-950/20',
          text: 'text-[#ff003c]',
          shadow: 'shadow-[0_0_60px_rgba(255,0,60,0.2)]',
          pulse: 'animate-pulse'
        };
      case 'medium':
        return {
          border: 'border-[#ffb000]',
          bg: 'bg-yellow-950/20',
          text: 'text-[#ffb000]',
          shadow: 'shadow-[0_0_40px_rgba(255,176,0,0.2)]',
          pulse: ''
        };
      case 'safe':
          return {
            border: 'border-[#00ff64]/30',
            bg: 'bg-green-950/10',
            text: 'text-[#00ff64]',
            shadow: 'shadow-[0_0_20px_rgba(0,255,100,0.1)]',
            pulse: ''
          };
      default:
        return {
          border: 'border-red-500/30',
          bg: 'bg-red-950/20',
          text: 'text-red-400',
          shadow: 'shadow-[0_0_80px_rgba(255,0,60,0.15)]',
          pulse: 'animate-pulse'
        };
    }
  };

  const threatStyles = getThreatStyles();

  // ======================================================================
  // 1. CANVAS RENDERER: THE CORRUPTED RED BINARY STATIC
  // ======================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Use full screen
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();

    const fontSize = 16;
    let animationFrameId: number;

    const draw = () => {
      const columns = Math.ceil(canvas.width / fontSize);
      const rows = Math.ceil(canvas.height / fontSize);
      
      // Fill background with subtle fade
      ctx.fillStyle = 'rgba(3, 3, 5, 0.1)'; 
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `bold ${fontSize}px monospace`;

      // Draw Stagnant Binary Static (subtle, faded red)
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < columns; c++) {
          if (Math.random() > 0.15) {
            const staticText = Math.random() > 0.5 ? '1' : '0';
            // SUBDUED, FADED RED (0.15 opacity)
            ctx.fillStyle = 'rgba(255, 0, 60, 0.15)';
            ctx.fillText(staticText, c * fontSize, r * fontSize);
          }
        }
      }
      
      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    const handleResize = () => {
      resizeCanvas();
      draw();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#030305] overflow-hidden">
      {/* ==================== BACKGROUND CORRUPTION LAYER ==================== */}
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
      />

      {/* Overlays for focus */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#030305_100%)] pointer-events-none" />
      <div className={`absolute inset-0 bg-[#030305]/70 backdrop-blur-[2px] ${threatStyles.pulse}`} />

      {/* ==================== FOREGROUND UI MODAL ==================== */}
      <div className={`relative z-10 flex flex-col items-center p-8 panel-3d ${threatStyles.border} ${threatStyles.bg} ${threatStyles.shadow} rounded-2xl max-w-lg w-full transition-all duration-300`}>
        
        <div className="relative mb-8 flex items-center justify-center">
          <AlertTriangle size={80} className={`${threatStyles.text} ${threatStyles.pulse} drop-shadow-[0_0_20px_rgba(255,0,60,1)]`} />
          <XOctagon size={40} className="absolute text-[#030305] animate-pulse" />
        </div>

        <h1 className={`text-sm font-mono tracking-[0.4em] uppercase ${threatStyles.text} mb-1 text-center`}>
          HackT<span className="text-white/80">.OS / SYSTEM PANIC</span>
        </h1>

        <h2 className="text-2xl font-bold tracking-[0.2em] text-white mb-2 drop-shadow-lg text-center">
          CRITICAL INITIALIZATION FAILURE
        </h2>

        <div className={`flex items-center gap-2 text-[10px] ${threatStyles.text} uppercase tracking-widest mb-6 font-mono ${threatStyles.bg} px-3 py-1 rounded ${threatStyles.border}`}>
          <Terminal size={10} className={threatStyles.pulse} /> ERR_NEURAL_LINK_SEVERED_PORT_8000
        </div>

        {/* ERROR MESSAGE BLOCK */}
        <div className={`gloomy-scroll w-full p-4 mb-10 h-32 overflow-y-auto ${threatStyles.border} ${threatStyles.bg} rounded font-mono`}>
          <div className="flex items-center justify-between text-[8px] text-gray-500 uppercase tracking-widest mb-2 border-b border-red-500/10 pb-1">
            <span>Exception Report</span>
            <span>VRAM:{systemVRAM || 'N/A'}MB • {backendConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <p className="text-xs text-white leading-relaxed break-all whitespace-pre-wrap selection:bg-red-500/30">
            {error || 'Fatal logic error detected in Tauri Core. No specific exception payload was provided. Backend response timed out or returned HTTP/500.'}
          </p>
        </div>

        <button 
          onClick={onRetry} 
          className={`w-full px-6 py-4 ${threatStyles.border} ${threatStyles.text} hover:bg-red-500/10 transition-all text-xs tracking-[0.3em] font-bold uppercase rounded-xl flex items-center justify-center gap-3 hover:shadow-[0_0_20px_rgba(255,0,60,0.3)] shadow-[0_0_10px_rgba(0,0,0,0.8)]`}
        >
          <RefreshCw size={16} className={threatStyles.pulse} /> Reset OS Bridge & Re-Initialize
        </button>

        <p className="mt-4 text-[9px] text-gray-600 font-mono tracking-wider text-center">
          NOTE: Please ensure the Python Sovereign Core is running on Port 8000.
        </p>
      </div>

      <div className={`fixed inset-0 z-0 ${threatStyles.bg} ${threatStyles.pulse} pointer-events-none`} />
    </div>
  );
}