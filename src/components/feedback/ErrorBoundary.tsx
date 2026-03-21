import { useEffect, useRef } from 'react';
import { AlertTriangle, RefreshCw, Terminal, XOctagon } from 'lucide-react';
import { useSystemStore } from '../../store/systemStore'; // FIXED: Added missing import

interface ErrorBoundaryProps {
  error: string | null;
  onRetry: () => void;
  threatLevel?: 'safe' | 'medium' | 'high';
}

export default function ErrorBoundary({ error, onRetry }: ErrorBoundaryProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // ======================================================================
  // 1. CANVAS RENDERER: THE CORRUPTED RED BINARY STATIC
  // ======================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Use full screen
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const fontSize = 16;
    const columns = Math.ceil(canvas.width / fontSize);
    const rows = Math.ceil(canvas.height / fontSize);

    const draw = () => {
      // Fill background
      ctx.fillStyle = '#030305'; 
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `bold ${fontSize}px monospace`;

      // Draw Stagnant Binary Static
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
    };

    draw();

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      draw();
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
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
      <div className="absolute inset-0 bg-[#030305]/70 backdrop-blur-[2px]" />

      {/* ==================== FOREGROUND UI MODAL ==================== */}
      <div className="relative z-10 flex flex-col items-center p-8 panel-3d border border-red-500/30 bg-red-950/20 rounded-2xl shadow-[0_0_80px_rgba(255,0,60,0.15)] max-w-lg w-full">
        
        <div className="relative mb-8 flex items-center justify-center">
          <AlertTriangle size={80} className="text-red-500 animate-pulse drop-shadow-[0_0_20px_rgba(255,0,60,1)]" />
          <XOctagon size={40} className="absolute text-[#030305] animate-pulse" />
        </div>
        
        <h1 className="text-sm font-mono tracking-[0.4em] uppercase text-red-400 mb-1 text-center">
          HackT<span className="text-white/80">.OS / SYSTEM PANIC</span>
        </h1>
        
        <h2 className="text-2xl font-bold tracking-[0.2em] text-white mb-2 drop-shadow-lg text-center">
          CRITICAL INITIALIZATION FAILURE
        </h2>
        
        <div className="flex items-center gap-2 text-[10px] text-red-300 uppercase tracking-widest mb-6 font-mono bg-red-500/10 px-3 py-1 rounded border border-red-500/20">
          <Terminal size={10} className="animate-pulse" /> ERR_NEURAL_LINK_SEVERED_PORT_8080
        </div>
        
        {/* ERROR MESSAGE BLOCK */}
        <div className="gloomy-scroll w-full p-4 mb-10 h-32 overflow-y-auto border border-red-500/20 bg-red-950/30 rounded font-mono">
          <div className="flex items-center justify-between text-[8px] text-gray-500 uppercase tracking-widest mb-2 border-b border-red-500/10 pb-1">
            <span>Exception Report</span>
            {/* FIXED: Accessed store safely */}
            <span>VRAM:{useSystemStore.getState().systemVRAM || 'N/A'}MB</span>
          </div>
          <p className="text-xs text-white leading-relaxed break-all whitespace-pre-wrap selection:bg-red-500/30">
            {error || 'Fatal logic error detected in Tauri Core. No specific exception payload was provided. Backend response timed out or returned HTTP/500.'}
          </p>
        </div>
        
        <button 
          onClick={onRetry} 
          className="w-full px-6 py-4 border border-red-500/50 text-red-400 hover:bg-red-500/10 transition-all text-xs tracking-[0.3em] font-bold uppercase rounded-xl flex items-center justify-center gap-3 hover:shadow-[0_0_20px_rgba(255,0,60,0.3)] shadow-[0_0_10px_rgba(0,0,0,0.8)]"
        >
          <RefreshCw size={16} /> Reset OS Bridge & Re-Initialize
        </button>

        <p className="mt-4 text-[9px] text-gray-600 font-mono tracking-wider text-center">
          NOTE: Please ensure the Python Sovereign Core is running on Port 8080.
        </p>
      </div>
      
      <div className="fixed inset-0 z-0 bg-[#ff003c]/5 animate-pulse-slow pointer-events-none"/>
    </div>
  );
}