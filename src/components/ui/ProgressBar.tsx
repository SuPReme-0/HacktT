interface ProgressBarProps {
  value: number;
  max?: number;
  variant?: 'cyan' | 'purple' | 'red' | 'green';
  showLabel?: boolean;
  className?: string;
}

export default function ProgressBar({
  value,
  max = 100,
  variant = 'cyan',
  showLabel = false,
  className = '',
}: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100);
  
  const variantColors = {
    cyan: 'bg-[#00f3ff]',
    purple: 'bg-[#bc13fe]',
    red: 'bg-[#ff003c]',
    green: 'bg-[#00ff88]',
  };

  return (
    <div className={`w-full space-y-1 ${className}`}>
      <div className="h-1 bg-[#1f1f1f] rounded-full overflow-hidden">
        <div
          className={`h-full ${variantColors[variant]} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      
      {showLabel && (
        <div className="flex justify-between text-[9px] text-gray-500 uppercase tracking-wider">
          <span>{value}</span>
          <span>{max}</span>
        </div>
      )}
    </div>
  );
}