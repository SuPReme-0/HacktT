interface DividerProps {
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

export default function Divider({
  orientation = 'horizontal',
  className = '',
}: DividerProps) {
  const isHorizontal = orientation === 'horizontal';

  return (
    <div
      // ✅ Accessibility tags added
      role="separator"
      aria-orientation={orientation}
      className={`${
        isHorizontal
          ? 'bg-gradient-to-r h-[1px] w-full' // ✅ Left-to-right for horizontal
          : 'bg-gradient-to-b w-[1px] h-full' // ✅ Top-to-bottom for vertical
      } from-transparent via-white/10 to-transparent ${className}`}
    />
  );
}