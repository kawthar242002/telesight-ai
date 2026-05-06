/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        brand: {
          50:  '#e0f2fe',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
        surface: {
          900: '#0b1120',
          800: '#111827',
          700: '#1e293b',
          600: '#334155',
          500: '#475569',
        },
      },
      animation: {
        'pulse-slow':   'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'slide-in':     'slideIn 0.3s ease-out',
        'fade-in':      'fadeIn 0.4s ease-out',
        'glow':         'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        slideIn: { from: { transform: 'translateX(20px)', opacity: 0 }, to: { transform: 'translateX(0)', opacity: 1 } },
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        glow:    { from: { boxShadow: '0 0 5px #6366f150' }, to: { boxShadow: '0 0 20px #6366f180, 0 0 40px #6366f130' } },
      },
      backdropBlur: { xs: '2px' },
    },
  },
  plugins: [],
}
