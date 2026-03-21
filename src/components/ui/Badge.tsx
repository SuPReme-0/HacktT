interface BadgeProps {
  children: React.ReactNode;
  variant?: 'cyan' | 'purple' | 'red' | 'green' | 'yellow' | 'gray';
  size?: 'sm' | 'md';
  pulse?: boolean;
  className?: string;
}

export default function Badge({
  children,
  variant = 'gray',
  size = 'sm',
  pulse = false,
  className = '',
}: BadgeProps) {
  const variantStyles = {
    cyan: 'bg-[#00f3ff]/10 text-[#00f3ff] border-[#00f3ff]/30',
    purple: 'bg-[#bc13fe]/10 text-[#bc13fe] border-[#bc13fe]/30',
    red: 'bg-[#ff003c]/10 text-[#ff003c] border-[#ff003c]/30',
    green: 'bg-[#00ff88]/10 text-[#00ff88] border-[#00ff88]/30',
    yellow: 'bg-[#ffb000]/10 text-[#ffb000] border-[#ffb000]/30',
    gray: 'bg-white/5 text-gray-400 border-white/10',
  };

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-[9px]',
    md: 'px-3 py-1 text-[10px]',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 border rounded font-mono uppercase tracking-wider ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${pulse ? 'animate-pulse' : ''} ${className}`}
    >
      {pulse && (
        <span className={`w-1.5 h-1.5 rounded-full ${
          variant === 'cyan' ? 'bg-[#00f3ff]' :
          variant === 'purple' ? 'bg-[#bc13fe]' :
          variant === 'red' ? 'bg-[#ff003c]' :
          variant === 'green' ? 'bg-[#00ff88]' :
          variant === 'yellow' ? 'bg-[#ffb000]' :
          'bg-gray-400'
        }`} />
      )}
      {children}
    </span>
  );
}