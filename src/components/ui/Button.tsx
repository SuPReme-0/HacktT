import { ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  children: React.ReactNode;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'inline-flex items-center justify-center font-mono uppercase tracking-widest transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variantStyles = {
    primary: 'bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] hover:bg-[#00f3ff]/20 hover:border-[#00f3ff]/50 hover:shadow-[0_0_20px_rgba(0,243,255,0.3)]',
    secondary: 'bg-[#bc13fe]/10 border border-[#bc13fe]/30 text-[#bc13fe] hover:bg-[#bc13fe]/20 hover:border-[#bc13fe]/50 hover:shadow-[0_0_20px_rgba(188,19,254,0.3)]',
    danger: 'bg-[#ff003c]/10 border border-[#ff003c]/30 text-[#ff003c] hover:bg-[#ff003c]/20 hover:border-[#ff003c]/50 hover:shadow-[0_0_20px_rgba(255,0,60,0.3)]',
    ghost: 'bg-transparent border border-transparent text-gray-400 hover:text-white hover:bg-white/5',
  };
  
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-[10px]',
    md: 'px-4 py-2 text-xs',
    lg: 'px-6 py-3 text-sm',
  };

  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <span className="animate-spin mr-2">⟳</span>
      )}
      {children}
    </button>
  );
}