/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: 'rgb(var(--brand-50) / <alpha-value>)', 100: 'rgb(var(--brand-100) / <alpha-value>)', 300: 'rgb(var(--brand-300) / <alpha-value>)',
          500: 'rgb(var(--brand-500) / <alpha-value>)', 600: 'rgb(var(--brand-600) / <alpha-value>)',
          700: 'rgb(var(--brand-700) / <alpha-value>)', 800: 'rgb(var(--brand-800) / <alpha-value>)',
          900: 'rgb(var(--brand-900) / <alpha-value>)',
        },
        sportblue: { 50: 'rgb(var(--info-soft) / <alpha-value>)', 500: 'rgb(var(--info) / <alpha-value>)', 600: 'rgb(var(--info-strong) / <alpha-value>)' },
        ai: { 50: 'rgb(var(--ai-soft) / <alpha-value>)', 500: 'rgb(var(--ai) / <alpha-value>)', 600: 'rgb(var(--ai-strong) / <alpha-value>)' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      borderRadius: { card: '14px' },
      boxShadow: { card: '0 10px 30px rgba(6, 95, 70, .07)', float: '0 18px 48px rgba(6, 95, 70, .13)' },
      spacing: { 18: '4.5rem' },
    },
  },
  plugins: [],
};
