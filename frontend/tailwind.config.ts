import type { Config } from "tailwindcss";

// Tokens ported 1:1 from ui/theme.py (the Gradio CSS) so the Next.js UI
// inherits the editorial legal-tech aesthetic — Fraunces serif headings,
// Inter body, slate-on-canvas cards, blue primary, amber/rose agent accents.
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./styles/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand
        primary:       "#0F52FF",
        "primary-dark": "#0a3fcc",
        // Slates (the design system uses Tailwind's defaults, listed here
        // explicitly so we can reference them in CSS variables / arbitrary
        // values without losing the names).
        slate: {
          50:  "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
        },
        amber: {
          500: "#f59e0b",
          600: "#d97706",
        },
        rose: {
          500: "#f43f5e",
          600: "#e11d48",
        },
        // Semantic
        ink:        "#0f172a",
        "ink-muted":  "#475569",
        "ink-subtle": "#64748b",
        hairline:   "#e2e8f0",
        canvas:     "#f7f9fb",
      },
      fontFamily: {
        display: ["Fraunces", "Source Serif 4", "Georgia", "serif"],
        sans:    ["Inter", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        "elev-sm": "0 1px 2px rgba(15, 23, 42, 0.04)",
        "elev":    "0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 12px rgba(15, 23, 42, 0.04)",
        "elev-lg": "0 1px 2px rgba(15, 23, 42, 0.04), 0 12px 32px rgba(15, 23, 42, 0.08)",
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "10px",
        lg: "14px",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
