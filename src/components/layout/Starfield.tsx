import React, { useEffect, useRef } from 'react';

// ======================================================================
// TYPE DEFINITIONS
// ======================================================================
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
  threatLevel?: 'safe' | 'medium' | 'high';
  mode?: 'active' | 'passive';
}

// ======================================================================
// COMPONENT
// ======================================================================
export default function Starfield({ 
  opacity = 0.4, 
  threatLevel = 'safe',
  mode = 'active' 
}: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const animationFrameRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // ==================================================================
    // DPI/RETINA SUPPORT (Critical for 4K displays)
    // ==================================================================
    const dpr = window.devicePixelRatio || 1;
    let width = window.innerWidth;
    let height = window.innerHeight;
    
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // ==================================================================
    // MOUSE TRACKING
    // ==================================================================
    let mouse = { x: width / 2, y: height / 2 };

    // ==================================================================
    // STAR GENERATION WITH VARIATION
    // ==================================================================
    const stars: Star[] = [];
    const colorVariants: Star['colorVariant'][] = ['cyan', 'cyan', 'cyan', 'purple', 'white'];
    
    for (let i = 0; i < 200; i++) {
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

    // ==================================================================
    // COLOR MAPPING (CSS Variables for consistency)
    // ==================================================================
    const getStarColor = (variant: Star['colorVariant'], currentOpacity: number) => {
      // Threat level affects overall color temperature
      if (threatLevel === 'high') {
        return `rgba(255, 0, 60, ${currentOpacity})`; // Red for danger
      }
      if (threatLevel === 'medium') {
        return `rgba(255, 176, 0, ${currentOpacity})`; // Yellow for warning
      }
      
      // Normal mode colors
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
    };

    // ==================================================================
    // RENDER LOOP
    // ==================================================================
    let time = 0;
    const render = () => {
      ctx.clearRect(0, 0, width, height);
      time += 0.016; // Approx 60fps

      starsRef.current.forEach((star) => {
        // Twinkle effect
        const twinkle = Math.sin(time * star.twinkleSpeed * 100 + star.x) * 0.2 + 0.8;
        const currentOpacity = opacity * star.baseOpacity * twinkle;

        // Parallax Movement
        star.x += star.vx;
        star.y += star.vy;

        // ==================================================================
        // PERFORMANCE OPTIMIZATION: Distance Squared (no Math.sqrt)
        // ==================================================================
        const dx = mouse.x - star.x;
        const dy = mouse.y - star.y;
        const distanceSquared = dx * dx + dy * dy;
        
        // 100px radius = 10000 squared
        if (distanceSquared < 10000) {
          const force = 0.01 * (1 - distanceSquared / 10000);
          star.x -= dx * force;
          star.y -= dy * force;
        }

        // Screen wrap
        if (star.x < 0) star.x = width;
        if (star.x > width) star.x = 0;
        if (star.y < 0) star.y = height;
        if (star.y > height) star.y = 0;

        // Draw
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = getStarColor(star.colorVariant, currentOpacity);
        ctx.fill();
      });

      animationFrameRef.current = requestAnimationFrame(render);
    };
    
    render();

    // ==================================================================
    // EVENT HANDLERS
    // ==================================================================
    const handleResize = () => {
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

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);

    // ==================================================================
    // CLEANUP (Prevent Memory Leaks)
    // ==================================================================
    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, [opacity, threatLevel, mode]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 mix-blend-screen"
      aria-hidden="true"
      role="presentation"
    />
  );
}