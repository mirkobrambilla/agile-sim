/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./harness/web/templates/**/*.html",
    "./harness/web/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          app: "var(--color-bg-app)",
          panel: "var(--color-bg-panel)",
        },
        border: { DEFAULT: "var(--color-border)" },
        text: {
          DEFAULT: "var(--color-text)",
          muted: "var(--color-text-muted)",
        },
        accent: {
          DEFAULT: "var(--color-accent)",
          warm: "var(--color-accent-warm)",
          gold: "var(--color-accent-gold)",
        },
        ok: "var(--color-ok)",
        warn: "var(--color-warn)",
        fail: "var(--color-fail)",
      },
      fontFamily: {
        sans: ["var(--font-ui)"],
        mono: ["var(--font-mono)"],
        pixel: ["var(--font-pixel)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
      },
    },
  },
  plugins: [],
};
