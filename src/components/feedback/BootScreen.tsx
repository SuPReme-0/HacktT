import { useEffect, useRef, useState } from 'react';
import { Terminal, Cpu } from 'lucide-react';

interface BootScreenProps {
  progress: number;
  threatLevel?: string;
}

export default function BootScreen({ progress, threatLevel }: BootScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loadingText, setLoadingText] = useState('INITIALIZING NEURAL LINK...');

  // ======================================================================
  // 1. RANDOMIZED SYSTEM LOGS
  // ======================================================================
  const progressRef = useRef(progress);

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  useEffect(() => {
    const logs = [
      'MOUNTING LOCAL KNOWLEDGE VAULT...',
      'BYPASSING OS TELEMETRY...',
      'ALLOCATING VRAM FOR FLORENCE-2...',
      'ESTABLISHING IPC BRIDGE...',
      'WAKING QWEN 3.5 CORE...',
      'ENCRYPTING LOCAL SOCKETS...',
    ];
    
    const interval = setInterval(() => {
      // Check the ref instead of the prop
      if (progressRef.current < 100) {
        setLoadingText(logs[Math.floor(Math.random() * logs.length)]);
      } else {
        setLoadingText('SYSTEM SECURE. READY.');
      }
    }, 400);

    // Empty dependency array ensures this interval is never interrupted
    return () => clearInterval(interval);
  }, []);

  // ======================================================================
  // 2. CANVAS RENDERING: STARS & BINARY RAIN
  // ======================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    // Make canvas full screen
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Starfield Setup
    const stars = Array.from({ length: 150 }).map(() => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.2, // Tiny stars
      speed: Math.random() * 0.5 + 0.1,
      opacity: Math.random()
    }));

    // Binary Rain Setup
    const fontSize = 14;
    const columns = canvas.width / fontSize;
    const drops = Array.from({ length: columns }).map(() => (Math.random() * -100));
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
        // Randomly pick 0 or 1
        const text = chars[Math.floor(Math.random() * chars.length)];
        
        // Glow effect for binary
        ctx.fillStyle = '#00f3ff'; 
        ctx.shadowBlur = 5;
        ctx.shadowColor = '#00f3ff';
        
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        
        // Reset shadow for stars
        ctx.shadowBlur = 0;

        // Reset drop to top randomly to create flow
        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        // Slower binary fall speed
        drops[i] += 0.5; 
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    // Handle Resize
    const handleResize = () => {
      // ✅ ADD THESE BACK: Update the actual canvas internal resolution
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;

      // Recalculate how many columns we need based on the new width
      const newColumns = Math.floor(canvas.width / fontSize);
      
      // If the screen got wider, add more drops to fill the empty space on the right
      if (newColumns > drops.length) {
        const extraDrops = Array.from({ length: newColumns - drops.length }).map(() => (Math.random() * -100));
        drops.push(...extraDrops);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#030305] overflow-hidden selection:bg-transparent">
      
      {/* Background Canvas */}
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 pointer-events-none opacity-60"
        aria-hidden="true"
      />

      {/* Radial Gradient Overlay for depth */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#030305_100%)] pointer-events-none" />

      {/* ==================== FOREGROUND UI ==================== */}
      <div className="relative z-10 flex flex-col items-center w-full max-w-md px-8">
        
        {/* Logo / Icon */}
        <div className="relative mb-8 group">
          <div className="absolute inset-0 bg-[#00f3ff] blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-700 rounded-full" />
          <div className="relative p-6 border border-[#1f1f1f] bg-[#0a0a0a]/80 backdrop-blur-sm rounded-2xl shadow-[0_0_30px_rgba(0,0,0,0.8)]">
            <Cpu size={48} className="text-[#00f3ff]" strokeWidth={1} />
          </div>
        </div>

        <h1 className="text-2xl font-bold tracking-[0.3em] text-white mb-2 drop-shadow-lg">
          HACKT<span className="text-[#00f3ff]">.OS</span>
        </h1>
        
        {/* Simulated Command Line Output */}
        <div className="flex items-center gap-2 mb-8 text-[10px] text-[#00f3ff] font-mono tracking-widest uppercase h-4">
          <Terminal size={10} className="animate-pulse" />
          {loadingText}
        </div>

        {/* Progress Bar Container */}
        <div className="w-full space-y-2">
          <div className="flex justify-between text-[10px] text-gray-500 font-mono tracking-widest uppercase">
            <span>Boot Sequence</span>
            <span className="text-[#00f3ff]">{Math.floor(progress)}%</span>
          </div>
          
          <div className="h-1.5 w-full bg-[#1f1f1f] rounded-full overflow-hidden shadow-inner relative">
            {/* The actual progress fill */}
            <div 
              className="absolute top-0 left-0 h-full bg-[#00f3ff] transition-all duration-300 ease-out relative"
              style={{ width: `${Math.min(progress, 100)}%` }}
            >
              {/* Hot glowing tip on the progress bar */}
              <div className="absolute right-0 top-0 bottom-0 w-4 bg-white blur-[2px]" />
            </div>
          </div>
        </div>

        {/* Threat Warning (If initializing during an alert) */}
        {threatLevel === 'high' && (
          <div className="mt-8 text-[9px] text-red-500 tracking-[0.2em] animate-pulse border border-red-500/30 bg-red-500/10 px-4 py-2 rounded-full">
            ⚠ WARNING: BOOTING UNDER CRITICAL THREAT CONDITION
          </div>
        )}
      </div>
    </div>
  );
}