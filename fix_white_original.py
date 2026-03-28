#!/usr/bin/env python3
"""
Apply original CC-1 first build design with white background.
Only colors change — layout, components, structure all stay identical.
Usage: cd ~/nemoclaw-local-foundation && python3 fix_white_original.py
"""

import os, sys

BASE = "command-center/frontend/src"
CHECK = f"{BASE}/app/globals.css"

if not os.path.exists(CHECK):
    print(f"ERROR: {CHECK} not found. Run from ~/nemoclaw-local-foundation/")
    sys.exit(1)


def write(path, content):
    with open(path, "w") as f:
        f.write(content)
    print(f"  Updated {path}")


# ═══════════════════════════════════════════════════════════════════
# 1. GLOBALS.CSS — white version of original
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/app/globals.css", """\
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --nc-bg: #ffffff;
  --nc-surface: #f9fafb;
  --nc-surface-2: #f3f4f6;
  --nc-border: #e5e7eb;
  --nc-accent: #6366f1;
  --nc-green: #22c55e;
  --nc-yellow: #eab308;
  --nc-red: #ef4444;
  --nc-text: #111827;
  --nc-text-dim: #6b7280;
}

body {
  background-color: var(--nc-bg);
  color: var(--nc-text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--nc-bg); }
::-webkit-scrollbar-thumb { background: var(--nc-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--nc-text-dim); }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}
""")


# ═══════════════════════════════════════════════════════════════════
# 2. TAILWIND CONFIG — white version
# ═══════════════════════════════════════════════════════════════════

write("command-center/frontend/tailwind.config.js", """\
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
""")

print("\\nWhite background applied to original design. Refresh http://localhost:3000")
