/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F5F1", surface: "#FFFFFF", ink: "#0F1B2D", muted: "#5B6677", line: "#E3E1DA",
        wind: { DEFAULT: "#2F7D5B", dark: "#235E44", soft: "#E6F1EB" },
        forecast: "#2A5C9E", warn: "#9A5B00", warnsoft: "#FFF4DF", danger: "#B3261E",
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        serif: ['"Source Serif 4"', "Georgia", "Cambria", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
