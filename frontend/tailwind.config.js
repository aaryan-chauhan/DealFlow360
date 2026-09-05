/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        ink: {
          900: '#0b1220',
          800: '#111a2e',
          700: '#1b2740',
        },
      },
    },
  },
  plugins: [],
}
