import { useEffect, useRef } from 'react';

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

export default function Starfield({ 
  opacity = 0.4, 
  threatLevel = 'safe',
  mode = 'active' 
}: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const animationFrameRef = useRef<number>(0);
  const propsRef = useRef({ opacity, threatLevel, mode });

  useEffect(() => {
    propsRef.current = { opacity, threatLevel, mode };
  }, [opacity, threatLevel, mode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let width = window.innerWidth;
    let height = window.innerHeight;
    
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    let mouse = { x: width / 2, y: height / 2 };

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

    const getStarColor = (variant: Star['colorVariant'], currentOpacity: number) => {
      const { threatLevel: currentThreat } = propsRef.current;
      
      if (currentThreat === 'high') {
        return `rgba(255, 0, 60, ${currentOpacity})`;
      }
      if (currentThreat === 'medium') {
        return `rgba(255, 176, 0, ${currentOpacity})`;
      }
      
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

    let time = 0;
    const render = () => {
      ctx.clearRect(0, 0, width, height);
      time += 0.016;

      starsRef.current.forEach((star) => {
        const { opacity: currentOpacity } = propsRef.current;
        const twinkle = Math.sin(time * star.twinkleSpeed * 100 + star.x) * 0.2 + 0.8;
        const finalOpacity = currentOpacity * star.baseOpacity * twinkle;

        star.x += star.vx;
        star.y += star.vy;

        const dx = mouse.x - star.x;
        const dy = mouse.y - star.y;
        const distanceSquared = dx * dx + dy * dy;
        
        if (distanceSquared < 10000) {
          const force = 0.01 * (1 - distanceSquared / 10000);
          star.x -= dx * force;
          star.y -= dy * force;
        }

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
    
    render();

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

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
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