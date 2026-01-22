/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      animation: {
        'fade-in-dot': 'fadeInDot 1.2s ease-in-out infinite',
      },
      keyframes: {
        fadeInDot: {
          '0%, 20%': { opacity: '0' },
          '40%, 100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
