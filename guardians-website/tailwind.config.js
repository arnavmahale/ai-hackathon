/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#040404',
        shell: '#050505',
        panel: '#0d0d0f',
        panelMuted: '#141417',
        border: '#1f1f22',
        accent: '#0ea5e9',
        accentMuted: '#0891d0',
        text: '#f8fafc',
        textMuted: '#8b8b93',
        success: '#10b981',
        warning: '#f97316',
        critical: '#dc2626',
      },
      fontFamily: {
        inter: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)',
        'card-soft': '0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)',
        lift: '0 12px 16px rgba(0,0,0,0.1), 0 3px 6px rgba(0,0,0,0.08)',
      },
      borderRadius: {
        lg: '0.75rem',
        xl: '1rem',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: 0.4 },
          '50%': { opacity: 1 },
        },
      },
      animation: {
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
