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

  return (
    <div
      className={`panel-3d ${variantClasses[variant]} ${
        hoverable ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}