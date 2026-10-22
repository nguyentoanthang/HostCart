/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: "#120e0e",
          900: "#161212",
          850: "#181313",
          800: "#201919",
          700: "#231b1b",
          600: "#2d2323",
        },
        crimson: {
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          900: "#7f1d1d",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
