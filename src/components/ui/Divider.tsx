interface DividerProps {
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

export default function Divider({
  orientation = 'horizontal',
  className = '',
}: DividerProps) {
  return (
    <div
      className={`bg-gradient-to-r from-transparent via-white/10 to-transparent ${
        orientation === 'horizontal'
          ? 'h-[1px] w-full'
          : 'w-[1px] h-full'
      } ${className}`}
    />
  );
}