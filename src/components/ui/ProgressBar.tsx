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
  // ✅ Prevents division by zero and clamps the value between 0 and 100
  const safeMax = max > 0 ? max : 1; 
  const percentage = Math.max(0, Math.min((value / safeMax) * 100, 100));
  
  const variantColors = {
    cyan: 'bg-[#00f3ff]',
    purple: 'bg-[#bc13fe]',
    red: 'bg-[#ff003c]',
    green: 'bg-[#00ff88]',
  };

  return (
    <div 
      className={`w-full space-y-1 ${className}`}
      // ✅ Added Accessibility (a11y) roles
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={safeMax}
    >
      <div className="h-1 bg-[#1f1f1f] rounded-full overflow-hidden">
        <div
          className={`h-full ${variantColors[variant]} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      
      {showLabel && (
        <div className="flex justify-between text-[9px] text-gray-500 uppercase tracking-wider" aria-hidden="true">
          <span>{value}</span>
          <span>{max}</span>
        </div>
      )}
    </div>
  );
}