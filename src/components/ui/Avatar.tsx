import { useState, useEffect } from 'react';

interface AvatarProps {
  src?: string;
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function Avatar({
  src,
  name,
  size = 'md',
  className = '',
}: AvatarProps) {
  // ✅ Track if the image fails to load
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
  }, [src]);

  const sizeStyles = {
    sm: 'w-6 h-6 text-[8px]',
    md: 'w-8 h-8 text-[10px]',
    lg: 'w-12 h-12 text-xs',
  };

  // ✅ Added .trim() and .filter(Boolean) to handle extra spaces safely
  const initials = (name || '?')
    .trim()
    .split(' ')
    .filter(Boolean) 
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div
      className={`rounded-full border border-[#00f3ff]/30 overflow-hidden bg-[#0a0a0f] flex items-center justify-center text-[#00f3ff] font-mono font-bold ${sizeStyles[size]} ${className}`}
    >
      {/* ✅ Switch to initials if the image src is provided but fails to load */}
      {src && !imgFailed ? (
        <img 
          src={src} 
          alt={name} 
          className="w-full h-full object-cover" 
          onError={() => setImgFailed(true)}
        />
      ) : (
        initials
      )}
    </div>
  );
}