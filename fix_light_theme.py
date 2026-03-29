#!/usr/bin/env python3
"""
Switch Command Center to light theme.
Usage: cd ~/nemoclaw-local-foundation && python3 fix_light_theme.py
"""

import os, sys

BASE = "command-center/frontend/src"

# ── 1. globals.css ──────────────────────────────────────────────────

globals_css = """\
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --nc-bg: #ffffff;
  --nc-surface: #f8f9fb;
  --nc-surface-2: #f0f1f5;
  --nc-border: #e2e4ea;
  --nc-accent: #6366f1;
  --nc-green: #16a34a;
  --nc-yellow: #ca8a04;
  --nc-red: #dc2626;
  --nc-text: #1a1a2e;
  --nc-text-dim: #6b7280;
}

body {
  background-color: var(--nc-bg);
  color: var(--nc-text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: var(--nc-bg);
}
::-webkit-scrollbar-thumb {
  background: var(--nc-border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--nc-text-dim);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}
"""

# ── 2. tailwind.config.js ──────────────────────────────────────────

tailwind_config = """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'nc-bg': '#ffffff',
        'nc-surface': '#f8f9fb',
        'nc-surface-2': '#f0f1f5',
        'nc-border': '#e2e4ea',
        'nc-accent': '#6366f1',
        'nc-accent-dim': '#4f46e5',
        'nc-green': '#16a34a',
        'nc-yellow': '#ca8a04',
        'nc-red': '#dc2626',
        'nc-text': '#1a1a2e',
        'nc-text-dim': '#6b7280',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
"""

files = {
    f"{BASE}/app/globals.css": globals_css,
    "command-center/frontend/tailwind.config.js": tailwind_config,
}

for path, content in files.items():
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run from ~/nemoclaw-local-foundation/")
        sys.exit(1)
    with open(path, "w") as f:
        f.write(content)
    print(f"  Updated {path}")

print("\nLight theme applied. Frontend will hot-reload automatically.")
