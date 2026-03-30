#!/bin/bash
# NemoClaw Regression Test Suite v1.0
# Runs every skill with its reference test input
# Reports pass/fail per skill
#
# Usage: bash scripts/test-all.sh [--dry-run]
# --dry-run: show what would run without executing

set -o pipefail

REPO_BASE=~/nemoclaw-local-foundation
SKILLS_DIR="$REPO_BASE/skills"
RUNNER="$SKILLS_DIR/skill-runner.py"
PYTHON="$REPO_BASE/.venv313/bin/python3"
PASS=0
FAIL=0
SKIP=0
TOTAL_COST=0
DRY_RUN=0

[[ "$1" == "--dry-run" ]] && DRY_RUN=1

echo "========================================"
echo "  NemoClaw Regression Test Suite v1.0"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "========================================"
echo ""

# Backup checkpoint DB before test run
if [[ -f ~/.nemoclaw/checkpoints/langgraph.db ]]; then
    cp ~/.nemoclaw/checkpoints/langgraph.db ~/.nemoclaw/checkpoints/langgraph.db.pre-regression
    echo "  [backup] Checkpoint DB saved to .pre-regression"
fi

RESULTS=()

for skill_dir in "$SKILLS_DIR"/*/; do
    skill_id=$(basename "$skill_dir")
    [[ "$skill_id" == "__pycache__" || "$skill_id" == "graph-validation" ]] && continue

    test_input="$skill_dir/test-input.json"
    if [[ ! -f "$test_input" ]]; then
        echo "  ⏭  $skill_id — no test-input.json (SKIP)"
        ((SKIP++))
        RESULTS+=("SKIP $skill_id")
        continue
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  🔍 $skill_id — would run (DRY RUN)"
        continue
    fi

    echo -n "  🔄 $skill_id..."

    # Delete checkpoint DB to prevent stale cache loops
    rm -f ~/.nemoclaw/checkpoints/langgraph.db

    # Build --input args from JSON
    args=$($PYTHON -c "
import json, sys
try:
    with open('$test_input') as f:
        data = json.load(f)
    parts = []
    for k, v in data.get('inputs', {}).items():
        # Escape double quotes in values
        escaped = str(v).replace('\"', '\\\\\"')
        parts.append(f'--input {k} \"{escaped}\"')
    print(' '.join(parts))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)

    if [[ -z "$args" ]]; then
        echo " ❌ FAIL (could not parse test-input.json)"
        ((FAIL++))
        RESULTS+=("FAIL $skill_id — bad test-input.json")
        continue
    fi

    # Run with timeout (5 min per skill)
    start_time=$(date +%s)
    result=$(eval "$PYTHON $RUNNER --skill $skill_id $args" 2>&1)
    exit_code=$?
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    if echo "$result" | grep -q "Skill complete"; then
        echo " ✅ PASS (${elapsed}s)"
        ((PASS++))
        RESULTS+=("PASS $skill_id (${elapsed}s)")
    elif [[ $exit_code -eq 124 ]]; then
        echo " ❌ TIMEOUT (300s)"
        ((FAIL++))
        RESULTS+=("FAIL $skill_id — TIMEOUT")
    else
        error_line=$(echo "$result" | grep -o '"error": "[^"]*"' | head -1)
        echo " ❌ FAIL (${elapsed}s)"
        echo "    $error_line"
        ((FAIL++))
        RESULTS+=("FAIL $skill_id — $error_line")
    fi
done

# Restore checkpoint DB from pre-regression backup
if [[ -f ~/.nemoclaw/checkpoints/langgraph.db.pre-regression ]]; then
    cp ~/.nemoclaw/checkpoints/langgraph.db.pre-regression ~/.nemoclaw/checkpoints/langgraph.db
    echo ""
    echo "  [restore] Checkpoint DB restored from .pre-regression"
fi

echo ""
echo "========================================"
echo "  Results: $PASS passed  $FAIL failed  $SKIP skipped"
echo "========================================"
echo ""

if [[ ${#RESULTS[@]} -gt 0 ]]; then
    echo "  Detail:"
    for r in "${RESULTS[@]}"; do
        echo "    $r"
    done
fi

exit $([[ $FAIL -eq 0 ]] && echo 0 || echo 1)
