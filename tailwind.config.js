/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: {
          900: '#030305',
          800: '#0a0a0f',
          700: '#15151a',
        },
        neon: {
          cyan: '#00f3ff',
          purple: '#bc13fe',
          red: '#ff003c',
          yellow: '#ffb000',
          green: '#00ff88',
        },
        glass: 'rgba(255, 255, 255, 0.05)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'spin-slow': 'spin 8s linear infinite',
        'spin-fast': 'spin 2s linear infinite',
        'thunder': 'thunder-strike 0.5s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px #00f3ff' },
          '100%': { boxShadow: '0 0 20px #00f3ff, 0 0 10px #00f3ff' },
        },
        'thunder-strike': {
          '0%': { boxShadow: '0 0 0px transparent', filter: 'brightness(1)' },
          '10%': { boxShadow: '0 0 40px #fff, inset 0 0 20px #00f3ff', filter: 'brightness(2)' },
          '20%': { boxShadow: '0 0 10px #00f3ff', filter: 'brightness(1)' },
          '30%': { boxShadow: '0 0 30px #fff, inset 0 0 15px #bc13fe', filter: 'brightness(1.8)' },
          '100%': { boxShadow: '0 0 15px var(--current-color)', filter: 'brightness(1)' },
        },
      },
    },
  },
  plugins: [],
};