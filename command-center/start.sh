#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# NemoClaw Command Center — Launch Script
# Starts both FastAPI backend and Next.js frontend
# ──────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  NemoClaw Command Center — CC-1${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"

# ── Backend ───────────────────────────────────────────────────────────
echo -e "\n${YELLOW}Starting backend...${NC}"

cd "$BACKEND_DIR"

# Check for venv
if [ -d "$HOME/.venv312" ]; then
    source "$HOME/.venv312/bin/activate"
elif [ -d ".venv" ]; then
    source ".venv/bin/activate"
fi

# Install deps if needed
pip install -q -r requirements.txt --break-system-packages 2>/dev/null || \
    pip install -q -r requirements.txt

# Start backend in background
python run.py --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ── Frontend ──────────────────────────────────────────────────────────
echo -e "\n${YELLOW}Starting frontend...${NC}"

cd "$FRONTEND_DIR"

# Install deps if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start frontend
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# ── Summary ───────────────────────────────────────────────────────────
echo -e "\n${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "  Backend:  http://127.0.0.1:8100"
echo -e "  Frontend: http://localhost:3000"
echo -e "  API docs: http://127.0.0.1:8100/docs"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "\nPress Ctrl+C to stop both services"

# Wait and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
