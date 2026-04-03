/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        'nc-bg': '#0a0a0f',
        'nc-surface': '#111118',
        'nc-surface-2': '#1a1a24',
        'nc-surface-3': '#222230',
        'nc-border': 'rgba(255, 255, 255, 0.08)',
        'nc-border-bright': 'rgba(255, 255, 255, 0.15)',
        'nc-accent': '#6366f1',
        'nc-accent-dim': '#4f46e5',
        'nc-accent-glow': 'rgba(99, 102, 241, 0.15)',
        'nc-green': '#22c55e',
        'nc-yellow': '#eab308',
        'nc-red': '#ef4444',
        'nc-text': '#e2e8f0',
        'nc-text-dim': '#94a3b8',
        'nc-text-muted': '#64748b',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
