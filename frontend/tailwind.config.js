/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#0066FF', deep: '#1E56A0', soft: '#E1ECFF', ink: '#0050CC' },
        action: { DEFAULT: '#00E6A7', hover: '#00CF96' },
        success: { DEFAULT: '#00C853', soft: '#DDF7EA', ink: '#00703A' },
        hold: { DEFAULT: '#FF9F43', soft: '#FFF1E3', ink: '#A84F00' },
        debt: { DEFAULT: '#FF5252', soft: '#FFE3E3', ink: '#C62828', light: '#FF7A7A' },
        paper: '#F8F9FA',
        ink: {
          DEFAULT: '#121824', 900: '#1A2230', 800: '#232D3D', 700: '#2E3A4D',
          muted: '#5A6472', subtle: '#9AA4B5', line: '#D4D9E0', soft: '#EEF0F3',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: { card: '12px', sheet: '16px' },
      boxShadow: { card: '0px 4px 12px rgba(0,0,0,0.06)' },
      minHeight: { touch: '48px' },
      minWidth: { touch: '48px' },
      keyframes: {
        scan: { from: { top: '14%' }, to: { top: '84%' } },
      },
      animation: { scan: 'scan 2.2s ease-in-out infinite alternate' },
    },
  },
  plugins: [],
};
