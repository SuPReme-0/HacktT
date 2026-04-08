import { useEffect, useRef, useCallback } from 'react';

interface Star {
  x: number;
  y: number;
  z: number;
  radius: number;
  vx: number;
  vy: number;
  baseOpacity: number;
  twinkleSpeed: number;
  colorVariant: 'cyan' | 'purple' | 'white';
}

interface StarfieldProps {
  opacity?: number;
  threatLevel?: 'safe' | 'medium' | 'high' | 'critical';
  mode?: 'active' | 'passive';
}

export default function Starfield({ 
  opacity = 0.4, 
  threatLevel = 'safe',
  mode = 'active' 
}: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const animationFrameRef = useRef<number>(0);
  const propsRef = useRef({ opacity, threatLevel, mode });
  const isReducedMotionRef = useRef(false);

  // ======================================================================
  // 1. ACCESSIBILITY: Reduced Motion Detection
  // ======================================================================
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    isReducedMotionRef.current = mediaQuery.matches;
    
    const handleChange = (e: MediaQueryListEvent) => {
      isReducedMotionRef.current = e.matches;
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Update props ref
  useEffect(() => {
    propsRef.current = { opacity, threatLevel, mode };
  }, [opacity, threatLevel, mode]);

  // ======================================================================
  // 2. CANVAS RENDERING: OPTIMIZED STARFIELD
  // ======================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      // Graceful degradation if canvas context is unavailable
      console.warn('Starfield: Canvas 2D context not available');
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    let width = window.innerWidth;
    let height = window.innerHeight;
    
    // Set canvas resolution for high-DPI displays
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Initialize mouse far off-screen to prevent "center hole" bug
    let mouse = { x: -9999, y: -9999 };

    // Dynamic star count based on performance hints
    const getStarCount = () => {
      if (isReducedMotionRef.current) return 50;
      if (dpr > 1.5) return 300; // High-DPI displays can handle more
      return 200; // Default
    };

    const stars: Star[] = [];
    const colorVariants: Star['colorVariant'][] = ['cyan', 'cyan', 'cyan', 'purple', 'white'];
    
    for (let i = 0; i < getStarCount(); i++) {
      const z = Math.random() * 2 + 0.1;
      stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        z: z,
        radius: (Math.random() * 1.5 + 0.5) / z,
        vx: ((Math.random() - 0.5) * 0.3) / z,
        vy: ((Math.random() - 0.5) * 0.3) / z,
        baseOpacity: Math.random() * 0.5 + 0.3,
        twinkleSpeed: Math.random() * 0.02 + 0.01,
        colorVariant: colorVariants[Math.floor(Math.random() * colorVariants.length)],
      });
    }
    starsRef.current = stars;

    const getStarColor = useCallback((variant: Star['colorVariant'], currentOpacity: number) => {
      const { threatLevel: currentThreat } = propsRef.current;
      
      // Threat-based color override
      if (currentThreat === 'critical' || currentThreat === 'high') {
        return `rgba(255, 0, 60, ${currentOpacity})`;
      }
      if (currentThreat === 'medium') {
        return `rgba(255, 176, 0, ${currentOpacity})`;
      }
      
      // Normal color variants
      switch (variant) {
        case 'cyan':
          return `rgba(0, 243, 255, ${currentOpacity})`;
        case 'purple':
          return `rgba(188, 19, 254, ${currentOpacity})`;
        case 'white':
          return `rgba(255, 255, 255, ${currentOpacity})`;
        default:
          return `rgba(0, 243, 255, ${currentOpacity})`;
      }
    }, []);

    let time = 0;
    let lastResizeTime = 0;
    
    const render = () => {
      // Skip rendering if reduced motion is preferred
      if (isReducedMotionRef.current) {
        // Draw static stars once
        ctx.clearRect(0, 0, width, height);
        starsRef.current.forEach((star) => {
          const { opacity: currentOpacity } = propsRef.current;
          ctx.beginPath();
          ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
          ctx.fillStyle = getStarColor(star.colorVariant, currentOpacity * star.baseOpacity);
          ctx.fill();
        });
        return;
      }
      
      ctx.clearRect(0, 0, width, height);
      time += 0.016;

      starsRef.current.forEach((star) => {
        const { opacity: currentOpacity, mode: currentMode } = propsRef.current;
        const twinkle = Math.sin(time * star.twinkleSpeed * 100 + star.x) * 0.2 + 0.8;
        const finalOpacity = currentOpacity * star.baseOpacity * twinkle;

        // Utilize the 'mode' prop to slow down stars in passive mode
        const speedMultiplier = currentMode === 'passive' ? 0.3 : 1;
        star.x += (star.vx * speedMultiplier);
        star.y += (star.vy * speedMultiplier);

        // Only calculate mouse repulsion if in 'active' mode
        if (currentMode === 'active') {
          const dx = mouse.x - star.x;
          const dy = mouse.y - star.y;
          const distanceSquared = dx * dx + dy * dy;
          
          if (distanceSquared < 10000) {
            const force = 0.01 * (1 - distanceSquared / 10000);
            star.x -= dx * force;
            star.y -= dy * force;
          }
        }

        // Wrap around screen edges
        if (star.x < 0) star.x = width;
        if (star.x > width) star.x = 0;
        if (star.y < 0) star.y = height;
        if (star.y > height) star.y = 0;

        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = getStarColor(star.colorVariant, finalOpacity);
        ctx.fill();
      });

      animationFrameRef.current = requestAnimationFrame(render);
    };
    
    // Start animation
    render();

    // Debounced resize handler
    const handleResize = () => {
      const now = Date.now();
      if (now - lastResizeTime < 100) return; // Debounce 100ms
      lastResizeTime = now;
      
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.scale(dpr, dpr);
    };
    
    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    // Add touch support for mobile users
    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        mouse.x = e.touches[0].clientX;
        mouse.y = e.touches[0].clientY;
      }
    };

    // Reset mouse when cursor leaves the window
    const handleMouseLeave = () => {
      mouse = { x: -9999, y: -9999 };
    };

    // Reset mouse when touch ends
    const handleTouchEnd = () => {
      mouse = { x: -9999, y: -9999 };
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('touchmove', handleTouchMove, { passive: true });
    window.addEventListener('touchend', handleTouchEnd);
    document.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
      document.removeEventListener('mouseleave', handleMouseLeave);
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden="true"
      role="presentation"
    />
  );
}