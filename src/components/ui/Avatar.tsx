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
  const sizeStyles = {
    sm: 'w-6 h-6 text-[8px]',
    md: 'w-8 h-8 text-[10px]',
    lg: 'w-12 h-12 text-xs',
  };

  const initials = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div
      className={`rounded-full border border-[#00f3ff]/30 overflow-hidden bg-[#0a0a0f] flex items-center justify-center text-[#00f3ff] font-mono font-bold ${sizeStyles[size]} ${className}`}
    >
      {src ? (
        <img src={src} alt={name} className="w-full h-full object-cover" />
      ) : (
        initials
      )}
    </div>
  );
}