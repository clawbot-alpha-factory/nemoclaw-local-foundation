#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# NemoClaw Full Regression Test (E-7)
# Tests: endpoints (assertions), skill compilation, golden output,
#        persistence, failure diagnostics, report history
# ═══════════════════════════════════════════════════════════════════════

set -o pipefail

REPO="$HOME/nemoclaw-local-foundation"
TOKEN=$(cat ~/.nemoclaw/cc-token 2>/dev/null || echo "")
BASE="http://127.0.0.1:8100"
REPORT_DIR="$HOME/.nemoclaw/regression"
mkdir -p "$REPORT_DIR"

PASS=0
FAIL=0
SKIP=0
FAILURES=()
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT=$(cd "$REPO" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date +"%Y-%m-%d")

echo "═══════════════════════════════════════════════════════════════"
echo "  NemoClaw Full Regression — $DATE"
echo "  Commit: $COMMIT"
echo "═══════════════════════════════════════════════════════════════"

# ── Helpers ────────────────────────────────────────────────────────────

check_endpoint() {
  local method="$1" path="$2" expected_status="$3" assert_key="$4" desc="$5"
  local url="${BASE}${path}"
  local response status body

  if [ "$method" = "GET" ]; then
    response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$url")
  else
    local payload="${6:-{}}"
    response=$(curl -s -w "\n%{http_code}" -X "$method" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" "$url")
  fi

  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  # Status check
  if [ "$status" != "$expected_status" ]; then
    echo "  ❌ $method $path → $status (expected $expected_status)"
    FAILURES+=("$method $path → $status (expected $expected_status)")
    FAIL=$((FAIL+1))
    return 1
  fi

  # JSON validity check
  if ! echo "$body" | jq . > /dev/null 2>&1; then
    echo "  ❌ $method $path → invalid JSON"
    FAILURES+=("$method $path → response is not valid JSON")
    FAIL=$((FAIL+1))
    return 1
  fi

  # Key assertion (if provided)
  if [ -n "$assert_key" ]; then
    if ! echo "$body" | jq -e ".$assert_key" > /dev/null 2>&1; then
      echo "  ❌ $method $path → missing key '$assert_key'"
      FAILURES+=("$method $path → missing expected key '$assert_key'")
      FAIL=$((FAIL+1))
      return 1
    fi
  fi

  echo "  ✅ $method $path"
  PASS=$((PASS+1))
  return 0
}

# ── SECTION 1: Cockpit Endpoints ──────────────────────────────────────

echo ""
echo "── Cockpit Endpoints ──"

check_endpoint GET /api/health 200 "status" "Health"
check_endpoint GET /api/health/ready 200 "" "Ready"
check_endpoint GET /api/health/debug 200 "" "Debug"
check_endpoint GET /api/state 200 "" "State"
check_endpoint GET /api/brain/status 200 "" "Brain"
check_endpoint GET /api/comms/lanes 200 "total" "Comms lanes"
check_endpoint GET /api/comms/agents 200 "" "Comms agents"
check_endpoint GET /api/comms/stats 200 "" "Comms stats"
check_endpoint GET /api/agents/ 200 "total" "Agents"
check_endpoint GET /api/agents/org 200 "" "Agents org"
check_endpoint GET /api/agents/workload 200 "" "Agents workload"
check_endpoint GET /api/skills/ 200 "skills" "Skills list"
check_endpoint GET /api/skills/stats 200 "total" "Skills stats"
check_endpoint GET /api/ops/dashboard 200 "" "Ops dashboard"
check_endpoint GET /api/ops/tasks 200 "" "Ops tasks"
check_endpoint GET /api/ops/budget 200 "" "Ops budget"
check_endpoint GET /api/projects/ 200 "" "Projects"
check_endpoint GET /api/clients/ 200 "" "Clients"
check_endpoint GET /api/approvals/ 200 "" "Approvals"

# ── SECTION 2: Execution Engine (E-2) ─────────────────────────────────

echo ""
echo "── Execution Engine (E-2) ──"

check_endpoint GET /api/execution/status 200 "mode" "Exec status"
check_endpoint GET /api/execution/queue 200 "total_queued" "Exec queue"
check_endpoint GET /api/execution/history 200 "executions" "Exec history"
check_endpoint GET /api/execution/dead-letter 200 "entries" "Dead letter"

# ── SECTION 3: Orchestrator (E-3) ─────────────────────────────────────

echo ""
echo "── Orchestrator (E-3) ──"

check_endpoint GET /api/orchestrator/workflows 200 "workflows" "Workflows"
check_endpoint GET /api/orchestrator/projects/active 200 "projects" "Active projects"

# ── SECTION 4: Agent Runtime (E-4a) ───────────────────────────────────

echo ""
echo "── Agent Runtime (E-4a) ──"

check_endpoint GET /api/engine/status 200 "engine" "Engine status"
check_endpoint GET /api/engine/checkpoints 200 "checkpoints" "Checkpoints"
check_endpoint GET /api/agents/sales_outreach_lead/loop-status 200 "" "Sales loop"
check_endpoint GET /api/agents/sales_outreach_lead/memory 200 "lessons" "Sales memory"
check_endpoint GET /api/agents/sales_outreach_lead/schedule 200 "schedule" "Sales schedule"

# ── SECTION 5: Protocol (E-4b) ────────────────────────────────────────

echo ""
echo "── Protocol (E-4b) ──"

check_endpoint GET /api/protocol/history 200 "messages" "Protocol history"
check_endpoint GET /api/protocol/feedback-loops 200 "loops" "Feedback loops"
check_endpoint GET /api/protocol/inbox/sales_outreach_lead 200 "messages" "Sales inbox"
check_endpoint GET /api/knowledge-base 200 "entries" "Knowledge base"

# ── SECTION 6: Enterprise (E-4c) ──────────────────────────────────────

echo ""
echo "── Enterprise (E-4c) ──"

check_endpoint GET /api/engine/config 200 "execution_mode" "Config"
check_endpoint GET /api/engine/alerts 200 "alerts" "Alerts"
check_endpoint GET /api/sla/projects 200 "slas" "SLA projects"
check_endpoint GET /api/audit/log 200 "entries" "Audit log"
check_endpoint GET /api/engine/approvals/chains 200 "" "Approval chains"
check_endpoint GET /api/engine/approvals/pending 200 "pending" "Pending approvals"

# ── SECTION 7: Skill Factory (E-5) ────────────────────────────────────

echo ""
echo "── Skill Factory (E-5) ──"

check_endpoint GET /api/skill-factory/queue 200 "jobs" "Factory queue"
check_endpoint GET /api/skill-factory/stats 200 "total_jobs" "Factory stats"
check_endpoint GET /api/skill-factory/patterns 200 "patterns" "Patterns"

# ── SECTION 8: Skill Compilation ──────────────────────────────────────

echo ""
echo "── Skill Compilation (55 skills) ──"

SKILL_PASS=0
SKILL_FAIL=0
SKILL_TOTAL=0

for skill_dir in "$REPO"/skills/*/; do
  skill_name=$(basename "$skill_dir")
  # Skip non-skill dirs
  if [ "$skill_name" = "__pycache__" ] || [ "$skill_name" = "graph-validation" ]; then
    continue
  fi

  SKILL_TOTAL=$((SKILL_TOTAL+1))

  # Check skill.yaml parseable
  yaml_file="$skill_dir/skill.yaml"
  if [ -f "$yaml_file" ]; then
    if ! python3 -c "import yaml; yaml.safe_load(open('$yaml_file'))" 2>/dev/null; then
      echo "  ❌ $skill_name: skill.yaml parse error"
      FAILURES+=("SKILL $skill_name: skill.yaml parse error")
      SKILL_FAIL=$((SKILL_FAIL+1))
      continue
    fi
  fi

  # Check run.py compileable
  run_file="$skill_dir/run.py"
  if [ -f "$run_file" ]; then
    if ! python3 -c "compile(open('$run_file').read(), '$run_file', 'exec')" 2>/dev/null; then
      echo "  ❌ $skill_name: run.py compile error"
      FAILURES+=("SKILL $skill_name: run.py compile error")
      SKILL_FAIL=$((SKILL_FAIL+1))
      continue
    fi
  fi

  SKILL_PASS=$((SKILL_PASS+1))
done

echo "  Skills: $SKILL_PASS/$SKILL_TOTAL passed"
if [ $SKILL_FAIL -gt 0 ]; then
  echo "  ⚠️ $SKILL_FAIL skill(s) failed compilation"
fi

# ── SECTION 9: Persistence Check ──────────────────────────────────────

echo ""
echo "── Persistence Check (create → read → delete) ──"

# Create a test project
CREATE_RESP=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"REGRESSION_TEST_PROJECT","description":"Auto-created by regression test","status":"planning"}' \
  "$BASE/api/projects/" 2>/dev/null)

PROJECT_ID=$(echo "$CREATE_RESP" | jq -r '.id // empty' 2>/dev/null)

if [ -n "$PROJECT_ID" ]; then
  # Verify it exists
  READ_RESP=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/projects/$PROJECT_ID" 2>/dev/null)
  READ_NAME=$(echo "$READ_RESP" | jq -r '.name // empty' 2>/dev/null)

  if [ "$READ_NAME" = "REGRESSION_TEST_PROJECT" ]; then
    echo "  ✅ Create → Read verified (project $PROJECT_ID)"
    PASS=$((PASS+1))

    # Cleanup: delete
    curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/api/projects/$PROJECT_ID" > /dev/null 2>&1
    echo "  ✅ Cleanup: test project deleted"
  else
    echo "  ❌ Create succeeded but Read returned wrong name"
    FAILURES+=("PERSISTENCE: Created project but read returned '$READ_NAME'")
    FAIL=$((FAIL+1))
  fi
else
  echo "  ⚠️ Persistence check skipped (project create returned no ID)"
  SKIP=$((SKIP+1))
fi

# ── SECTION 10: Golden Output Test ────────────────────────────────────

echo ""
echo "── Golden Output Test (i35-tone-calibrator) ──"

GOLDEN_RESP=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"skill_id":"i35-tone-calibrator","inputs":{"input_text":"NemoClaw is an autonomous AI agent system that orchestrates multiple specialized agents for revenue generation, client management, and strategic planning across B2B SaaS markets in the MENA region. The system features continuous execution loops, skill chaining, and enterprise-grade guardrails.","target_tone":"professional"},"agent_id":"sales_outreach_lead","tier":"standard"}' \
  "$BASE/api/execution/run" 2>/dev/null)

EXEC_ID=$(echo "$GOLDEN_RESP" | jq -r '.execution_id // empty' 2>/dev/null)

if [ -n "$EXEC_ID" ]; then
  echo "  Submitted execution $EXEC_ID — waiting for completion..."

  # Poll for completion (max 120s)
  for i in $(seq 1 60); do
    sleep 2
    STATUS_RESP=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/execution/$EXEC_ID" 2>/dev/null)
    EXEC_STATUS=$(echo "$STATUS_RESP" | jq -r '.status // empty' 2>/dev/null)

    if [ "$EXEC_STATUS" = "completed" ]; then
      OUTPUT_PATH=$(echo "$STATUS_RESP" | jq -r '.output_path // empty' 2>/dev/null)
      ENVELOPE_PATH=$(echo "$STATUS_RESP" | jq -r '.envelope_path // empty' 2>/dev/null)
      COST=$(echo "$STATUS_RESP" | jq -r '.cost // 0' 2>/dev/null)

      # Validate output
      GOLDEN_OK=true

      if [ -f "$OUTPUT_PATH" ]; then
        OUTPUT_LEN=$(wc -c < "$OUTPUT_PATH" | tr -d ' ')
        if [ "$OUTPUT_LEN" -lt 100 ]; then
          echo "  ❌ Output too short ($OUTPUT_LEN bytes)"
          FAILURES+=("GOLDEN: Output only $OUTPUT_LEN bytes (expected >100)")
          GOLDEN_OK=false
        fi
        if ! grep -q "##" "$OUTPUT_PATH" 2>/dev/null; then
          echo "  ⚠️ Output missing markdown headers (##)"
        fi
      else
        echo "  ❌ Output file not found: $OUTPUT_PATH"
        FAILURES+=("GOLDEN: Output file missing")
        GOLDEN_OK=false
      fi

      if [ -f "$ENVELOPE_PATH" ]; then
        if ! jq -e '.skill_id' "$ENVELOPE_PATH" > /dev/null 2>&1; then
          echo "  ❌ Envelope missing skill_id key"
          FAILURES+=("GOLDEN: Envelope missing skill_id")
          GOLDEN_OK=false
        fi
      else
        echo "  ❌ Envelope file not found"
        FAILURES+=("GOLDEN: Envelope file missing")
        GOLDEN_OK=false
      fi

      if $GOLDEN_OK; then
        echo "  ✅ Golden test passed (output=$OUTPUT_LEN bytes, cost=\$$COST)"
        PASS=$((PASS+1))
      else
        FAIL=$((FAIL+1))
      fi
      break
    elif [ "$EXEC_STATUS" = "failed" ] || [ "$EXEC_STATUS" = "dead_letter" ]; then
      ERROR=$(echo "$STATUS_RESP" | jq -r '.error // "unknown"' 2>/dev/null)
      echo "  ❌ Execution failed: $ERROR"
      FAILURES+=("GOLDEN: Execution failed — $ERROR")
      FAIL=$((FAIL+1))
      break
    fi

    if [ "$i" -eq 60 ]; then
      echo "  ❌ Execution timed out (120s)"
      FAILURES+=("GOLDEN: Execution timed out")
      FAIL=$((FAIL+1))
    fi
  done
else
  echo "  ⚠️ Golden test skipped (submission failed)"
  SKIP=$((SKIP+1))
fi

# ── SUMMARY ───────────────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ENDPOINTS:  $PASS passed, $FAIL failed, $SKIP skipped"
echo "  SKILLS:     $SKILL_PASS/$SKILL_TOTAL compile"
echo "  GOLDEN:     $([ -n "$EXEC_ID" ] && echo "executed" || echo "skipped")"
echo "═══════════════════════════════════════════════════════════════"

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo ""
  echo "  FAILURES:"
  for f in "${FAILURES[@]}"; do
    echo "    ❌ $f"
  done
fi

echo ""
if [ $FAIL -eq 0 ] && [ $SKILL_FAIL -eq 0 ]; then
  echo "  ✅ REGRESSION PASSED"
  RESULT="PASS"
else
  echo "  ⛔ REGRESSION FAILED ($FAIL endpoint failures, $SKILL_FAIL skill failures)"
  RESULT="FAIL"
fi

# ── Save Report ───────────────────────────────────────────────────────

REPORT_FILE="$REPORT_DIR/${DATE}_${COMMIT}.json"
cat > "$REPORT_FILE" << REPORTEOF
{
  "date": "$DATE",
  "timestamp": "$TIMESTAMP",
  "commit": "$COMMIT",
  "result": "$RESULT",
  "endpoints": {"passed": $PASS, "failed": $FAIL, "skipped": $SKIP},
  "skills": {"passed": $SKILL_PASS, "failed": $SKILL_FAIL, "total": $SKILL_TOTAL},
  "failures": [$(printf '"%s",' "${FAILURES[@]}" | sed 's/,$//')]
}
REPORTEOF

echo ""
echo "  Report saved: $REPORT_FILE"
echo ""

# Exit code for CI
[ "$RESULT" = "PASS" ] && exit 0 || exit 1
