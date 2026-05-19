/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // "Fraunces": serif moderno con character; ideal para títulos.
        // El stack del sans usa fuentes del sistema para evitar cargas extra.
        display: [
          "Fraunces",
          "ui-serif",
          "Georgia",
          "Cambria",
          "serif",
        ],
        sans: [
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      colors: {
        // Paleta editorial cálida — ver index.css para las variables CSS.
        cream: {
          DEFAULT: "#FAF8F3",
          dark: "#F1ECE0",
        },
        ink: {
          DEFAULT: "#0D1117",
          muted: "#4A4F57",
          subtle: "#6B7280",
        },
        holo: {
          // Acento "holográfico" sutil — referencia a las cartas holo
          // sin caer en el efecto literal de gradiente arcoíris.
          DEFAULT: "#2D6A8F",
          dark: "#1E4F6E",
          light: "#5A92B5",
        },
        danger: "#B83C30",
        success: "#2B7A52",
      },
      letterSpacing: {
        "tight-display": "-0.025em",
      },
      borderRadius: {
        "card": "0.625rem",
      },
    },
  },
  plugins: [],
};
