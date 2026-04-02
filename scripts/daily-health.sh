#!/bin/bash
# NemoClaw Daily Health Check
# Runs at 9am via launchd — logs to ~/.nemoclaw/logs/health-reports/

PROJECT_DIR="/Users/core88/nemoclaw-local-foundation"
PYTHON="$PROJECT_DIR/.venv313/bin/python3"
LOG_DIR="$HOME/.nemoclaw/logs/health-reports"
DATE=$(date +"%Y-%m-%d")
LOG_FILE="$LOG_DIR/health-$DATE.log"

mkdir -p "$LOG_DIR"

echo "=== NemoClaw Health Report — $DATE $(date +%H:%M) ===" > "$LOG_FILE"
echo "" >> "$LOG_FILE"

cd "$PROJECT_DIR" || exit 1

echo "--- Validation (31 checks) ---" >> "$LOG_FILE"
$PYTHON scripts/validate.py 2>&1 | tail -5 >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

echo "--- System Status ---" >> "$LOG_FILE"
$PYTHON scripts/prod-ops.py status 2>&1 | head -20 >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

echo "--- Budget / Costs ---" >> "$LOG_FILE"
$PYTHON scripts/prod-ops.py costs 2>&1 | head -20 >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "=== End of report ===" >> "$LOG_FILE"

# Keep only last 30 days of reports
find "$LOG_DIR" -name "health-*.log" -mtime +30 -delete
