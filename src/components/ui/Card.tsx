import React from 'react';

interface CardProps {
  children: React.ReactNode;
  variant?: 'default' | 'cyan' | 'purple' | 'red';
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

export default function Card({
  children,
  variant = 'default',
  className = '',
  onClick,
  hoverable = false,
}: CardProps) {
  const variantClasses = {
    default: '',
    cyan: 'variant-cyan',
    purple: 'variant-purple',
    red: 'variant-red',
  };

  // ✅ Allows keyboard users to trigger the onClick event
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault(); // Prevents page scroll when hitting Space
      onClick();
    }
  };

  // Check if the card is meant to be interactive
  const isInteractive = Boolean(onClick || hoverable);

  return (
    <div
      className={`panel-3d ${variantClasses[variant]} ${
        isInteractive ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
      
      // ✅ Accessibility attributes safely applied only if it's clickable
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? handleKeyDown : undefined}
    >
      {children}
    </div>
  );
}