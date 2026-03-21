import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, className = '', ...props }, ref) => {
    return (
      <div className="w-full space-y-1">
        {label && (
          <label className="block text-[10px] uppercase tracking-widest text-gray-400">
            {label}
          </label>
        )}
        
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
              {icon}
            </div>
          )}
          
          <input
            ref={ref}
            className={`w-full input-3d px-4 py-2 text-sm font-mono ${
              icon ? 'pl-10' : ''
            } ${error ? 'border-[#ff003c]/50' : ''} ${className}`}
            {...props}
          />
        </div>
        
        {error && (
          <p className="text-[10px] text-[#ff003c] uppercase tracking-wider">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';