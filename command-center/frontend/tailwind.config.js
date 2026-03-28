/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        'nc-bg': '#ffffff',
        'nc-surface': '#f9fafb',
        'nc-surface-2': '#f3f4f6',
        'nc-border': '#e5e7eb',
        'nc-accent': '#6366f1',
        'nc-accent-dim': '#4f46e5',
        'nc-green': '#22c55e',
        'nc-yellow': '#eab308',
        'nc-red': '#ef4444',
        'nc-text': '#111827',
        'nc-text-dim': '#6b7280',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
