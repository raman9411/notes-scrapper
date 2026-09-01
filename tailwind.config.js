/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0e0d1a",
        card: "#17162a",
        surface: "#1f1e35",
        "border-color": "#2e2c4a",
        accent: "#7c5cbf",
        "accent-lt": "#a78bfa",
      },
    },
  },
  plugins: [],
}
