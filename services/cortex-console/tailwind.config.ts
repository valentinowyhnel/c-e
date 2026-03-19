import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#07111f",
        panel: "#0f1b2d",
        border: "#1d3557",
        signal: "#4cc9f0",
        success: "#059669",
        warning: "#d97706",
        danger: "#dc2626",
        ink: "#e8eef7",
        muted: "#8ba3c0"
      },
      boxShadow: {
        panel: "0 24px 80px rgba(1, 10, 24, 0.35)"
      }
    }
  },
  plugins: []
};

export default config;
