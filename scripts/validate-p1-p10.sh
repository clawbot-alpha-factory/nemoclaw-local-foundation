#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# NemoClaw Engine Validation Suite — P-1 through P-10
# Tests every new endpoint, edge case, error path, and integration
#
# Run from repo root:
#   cd ~/nemoclaw-local-foundation && bash scripts/validate-p1-p10.sh
# ═══════════════════════════════════════════════════════════════════

set +e  # Don't abort on failure — run all tests and report at end

TOKEN=$(cat ~/.nemoclaw/cc-token)
BASE="http://127.0.0.1:8100"
PASS=0
FAIL=0
WARN=0

# ── Helpers ─────────────────────────────────────────────────────────

ok() { PASS=$((PASS+1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }
warn() { WARN=$((WARN+1)); echo "  ⚠️  $1"; }

# HTTP helper: check status code
check_status() {
  local method="$1" path="$2" expected="$3" label="$4" data="$5"
  local status
  if [ "$method" = "GET" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE$path")
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$data" "$BASE$path")
  fi
  if [ "$status" = "$expected" ]; then
    ok "$label ($status)"
  else
    fail "$label (got $status, expected $expected)"
  fi
}

# HTTP helper: check response contains string
check_contains() {
  local method="$1" path="$2" needle="$3" label="$4" data="$5"
  local body
  if [ "$method" = "GET" ]; then
    body=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE$path")
  else
    body=$(curl -s -X "$method" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$data" "$BASE$path")
  fi
  if echo "$body" | grep -q "$needle"; then
    ok "$label"
  else
    fail "$label (missing: $needle)"
    echo "    Response: $(echo "$body" | head -c 200)"
  fi
}

# HTTP helper: get JSON field
get_field() {
  local method="$1" path="$2" field="$3" data="$4"
  if [ "$method" = "GET" ]; then
    curl -s -H "Authorization: Bearer $TOKEN" "$BASE$path" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d$field)" 2>/dev/null
  else
    curl -s -X "$method" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$data" "$BASE$path" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d$field)" 2>/dev/null
  fi
}

echo "═══════════════════════════════════════════════════════════════"
echo "  NemoClaw P-1→P-10 Validation Suite — $(date +%Y-%m-%d)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ═══════════════════════════════════════════════════════════════════
# P-1: PROJECT SCOPED MEMORY
# ═══════════════════════════════════════════════════════════════════
echo "── P-1: Project Scoped Memory ──"

# Create test project
P1_PROJECT=$(get_field "POST" "/api/projects/" "['id']" '{"name":"P1 Validation Test"}')
if [ -n "$P1_PROJECT" ] && [ "$P1_PROJECT" != "None" ]; then
  ok "Create test project ($P1_PROJECT)"
else
  fail "Create test project"
  P1_PROJECT="none"
fi

# Write operational memory
check_status "POST" "/api/projects/$P1_PROJECT/memory" "201" "Write operational memory" \
  '{"agent_id":"sales_outreach_lead","key":"lead_quality","value":"Enterprise converts 3x","memory_type":"operational","importance":0.9}'

# Write chat memory
check_status "POST" "/api/projects/$P1_PROJECT/memory" "201" "Write chat memory" \
  '{"agent_id":"marketing_campaigns_lead","key":"campaign_note","value":"LinkedIn > cold email","memory_type":"chat","importance":0.7}'

# Read all memory — verify count
P1_TOTAL=$(get_field "GET" "/api/projects/$P1_PROJECT/memory" ".get('total',0)")
if [ "$P1_TOTAL" = "2" ]; then
  ok "Read all memory (total=2)"
else
  fail "Read all memory (total=$P1_TOTAL, expected 2)"
fi

# Filter by type=operational — verify count
P1_OP=$(get_field "GET" "/api/projects/$P1_PROJECT/memory?type=operational" ".get('returned',0)")
if [ "$P1_OP" = "1" ]; then
  ok "Filter operational only (returned=1)"
else
  fail "Filter operational only (returned=$P1_OP, expected 1)"
fi

# Filter by agent — verify count
P1_AG=$(get_field "GET" "/api/projects/$P1_PROJECT/memory?agent=sales_outreach_lead" ".get('returned',0)")
if [ "$P1_AG" = "1" ]; then
  ok "Filter by agent (returned=1)"
else
  fail "Filter by agent (returned=$P1_AG, expected 1)"
fi

# Error: invalid type
check_status "GET" "/api/projects/$P1_PROJECT/memory?type=bogus" "400" "Error: invalid memory type"

# Error: dot in key
check_status "POST" "/api/projects/$P1_PROJECT/memory" "400" "Error: dot in key rejected" \
  '{"agent_id":"sales_outreach_lead","key":"bad.key","value":"test","memory_type":"operational"}'

# Error: empty key
check_status "POST" "/api/projects/$P1_PROJECT/memory" "400" "Error: empty key rejected" \
  '{"agent_id":"sales_outreach_lead","key":"","value":"test","memory_type":"operational"}'

# Cleanup
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/api/projects/$P1_PROJECT" > /dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-2: ACTIVITY EVENT LOG
# ═══════════════════════════════════════════════════════════════════
echo "── P-2: Activity Event Log ──"

# Append execution activity
check_status "POST" "/api/activity/" "201" "Append execution activity" \
  '{"category":"execution","action":"skill_test","actor_type":"agent","actor_id":"sales_outreach_lead","entity_type":"skill","entity_id":"test-skill","summary":"Validation test"}'

# Append bridge activity
check_status "POST" "/api/activity/" "201" "Append bridge activity" \
  '{"category":"bridge","action":"api_call_test","actor_type":"system","actor_id":"system","entity_type":"bridge","entity_id":"resend","summary":"Bridge test"}'

# Query all
check_contains "GET" "/api/activity/" '"total":' "Query all activities"

# Filter by category
check_contains "GET" "/api/activity/?category=execution" '"entries"' "Filter by category=execution"

# Filter by actor
check_contains "GET" "/api/activity/?actor=sales_outreach_lead" '"entries"' "Filter by actor"

# Stats
check_contains "GET" "/api/activity/stats" '"by_category"' "Stats endpoint"

# Categories
check_contains "GET" "/api/activity/categories" '"execution"' "Categories endpoint"

# Error: invalid category in query
check_status "GET" "/api/activity/?category=bogus" "400" "Error: invalid category"

# Error: invalid category in append
check_status "POST" "/api/activity/" "400" "Error: invalid category on append" \
  '{"category":"invalid_cat","action":"test","actor_type":"agent","actor_id":"test"}'

# Error: invalid actor_type
check_status "POST" "/api/activity/" "400" "Error: invalid actor_type" \
  '{"category":"execution","action":"test","actor_type":"robot","actor_id":"test"}'

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-3: WEBHOOK DISPATCH
# ═══════════════════════════════════════════════════════════════════
echo "── P-3: Webhook Dispatch ──"

# Send known webhook
check_contains "POST" "/api/webhooks/instantly" '"status"' "Webhook: instantly/email_reply" \
  '{"event_type":"email_reply","data":{"from":"val@test.com","subject":"Re: Test"}}'

# Send unknown source (should complete, no handler)
check_contains "POST" "/api/webhooks/unknown_val_source" '"status"' "Webhook: unknown source accepted" \
  '{"event_type":"test","data":{}}'

# Dedup: same payload again should return duplicate
DEDUP_RESULT=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"event_type":"email_reply","data":{"from":"val@test.com","subject":"Re: Test"}}' \
  "$BASE/api/webhooks/instantly")
if echo "$DEDUP_RESULT" | grep -q "duplicate"; then
  ok "Dedup: duplicate detected"
else
  fail "Dedup: expected duplicate response"
fi

# History
check_contains "GET" "/api/webhooks/history" '"events"' "Webhook history"

# History filtered by source
check_contains "GET" "/api/webhooks/history?source=instantly" '"events"' "Webhook history filtered"

# Dead-letter (should be empty or have entries)
check_status "GET" "/api/webhooks/dead-letter" "200" "Webhook dead-letter endpoint"

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-4: TASK DEPENDENCIES + BLOCKED STATE
# ═══════════════════════════════════════════════════════════════════
echo "── P-4: Task Dependencies ──"

# Create independent task
TASK_A=$(get_field "POST" "/api/ops/tasks" "['id']" '{"title":"Val Task A","priority":"high"}')
if [ -n "$TASK_A" ] && [ "$TASK_A" != "None" ]; then
  ok "Create task A ($TASK_A)"
else
  fail "Create task A"
  TASK_A="none"
fi

# Create dependent task (should be blocked)
TASK_B_RAW=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"title\":\"Val Task B (depends on A)\",\"depends_on\":[\"$TASK_A\"]}" \
  "$BASE/api/ops/tasks")
TASK_B=$(echo "$TASK_B_RAW" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null)
TASK_B_STATUS=$(echo "$TASK_B_RAW" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)

if [ "$TASK_B_STATUS" = "blocked" ]; then
  ok "Task B is blocked (depends on A)"
else
  fail "Task B should be blocked (got: $TASK_B_STATUS)"
fi

# Complete task A → should auto-unblock B
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"completed"}' "$BASE/api/ops/tasks/$TASK_A" > /dev/null

# Check B is now pending
TASK_B_NEW_STATUS=$(get_field "GET" "/api/ops/tasks?status=pending" "" "")
if echo "$TASK_B_NEW_STATUS" | python3 -c "import json,sys; tasks=json.load(sys.stdin); found=any(t.get('id')=='$TASK_B' for t in (tasks if isinstance(tasks,list) else [])); print('found' if found else 'not_found')" 2>/dev/null | grep -q "found"; then
  ok "Task B auto-unblocked to pending"
else
  # Check via direct task lookup
  B_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/ops/tasks" | python3 -c "
import json,sys
data = json.load(sys.stdin)
tasks = data if isinstance(data, list) else data.get('tasks', data.get('items', []))
for t in tasks:
    if t.get('id') == '$TASK_B':
        print(t.get('status', 'unknown'))
        break
" 2>/dev/null)
  if [ "$B_CHECK" = "pending" ]; then
    ok "Task B auto-unblocked to pending"
  else
    warn "Task B status after unblock: $B_CHECK (expected pending)"
  fi
fi

# Dependency graph
check_contains "GET" "/api/ops/tasks/dependency-graph" '"nodes"' "Dependency graph endpoint"

# Error: depends on nonexistent task
check_status "POST" "/api/ops/tasks" "400" "Error: nonexistent dependency" \
  '{"title":"Bad dep","depends_on":["nonexistent_id"]}'

# Force unblock (create blocked task, then force-unblock)
TASK_C=$(get_field "POST" "/api/ops/tasks" "['id']" '{"title":"Val Task C"}')
TASK_D=$(get_field "POST" "/api/ops/tasks" "['id']" "{\"title\":\"Val Task D (blocked)\",\"depends_on\":[\"$TASK_C\"]}")
check_status "POST" "/api/ops/tasks/$TASK_D/force-unblock" "200" "Force-unblock blocked task"

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-5: APPROVAL RUBRIC SCORES
# ═══════════════════════════════════════════════════════════════════
echo "── P-5: Approval Rubric ──"

# Simulate low-risk (should auto-approve)
LOW_RISK=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"apollo_search","amount":0.01,"factors":{"data_sensitivity":0}}' \
  "$BASE/api/engine/approvals/score")
LOW_DECISION=$(echo "$LOW_RISK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('decision',''))" 2>/dev/null)
if [ "$LOW_DECISION" = "auto_approved" ]; then
  ok "Low-risk score → auto_approved"
else
  fail "Low-risk score (got: $LOW_DECISION, expected: auto_approved)"
fi

# Simulate high-risk (should escalate)
HIGH_RISK=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"cold_email_blast","amount":25.0,"factors":{"data_sensitivity":6}}' \
  "$BASE/api/engine/approvals/score")
HIGH_DECISION=$(echo "$HIGH_RISK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('decision',''))" 2>/dev/null)
if [ "$HIGH_DECISION" = "escalated" ]; then
  ok "High-risk score → escalated"
else
  fail "High-risk score (got: $HIGH_DECISION, expected: escalated)"
fi

# Submit with rubric (low-risk → auto-approved)
check_contains "POST" "/api/engine/approvals/submit-scored" '"auto_approved"' "Submit scored: low-risk auto-approved" \
  '{"action":"apollo_search","amount":0.01,"requested_by":"sales_outreach_lead","factors":{"data_sensitivity":0}}'

# Submit with rubric (high-risk → escalated)
check_contains "POST" "/api/engine/approvals/submit-scored" '"escalated"' "Submit scored: high-risk escalated" \
  '{"action":"cold_email_blast","amount":25.0,"requested_by":"marketing","factors":{"data_sensitivity":6}}'

# Score history (should have entries)
check_contains "GET" "/api/engine/approvals/score-history" '"entries"' "Score history has entries"

# Backward compat: old submit still works
check_contains "POST" "/api/engine/approvals/submit" '"auto_approved"' "Old submit backward compat" \
  '{"action":"test","amount":5.0,"requested_by":"ops"}'

# Verify factor derivation (check that factors are derived, not just passed through)
DERIVED=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"apollo_search","amount":0.01,"factors":{}}' \
  "$BASE/api/engine/approvals/score")
SPEND_SOURCE=$(echo "$DERIVED" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('factors_used',{}).get('spend',{}).get('source',''))" 2>/dev/null)
if [ "$SPEND_SOURCE" = "derived" ]; then
  ok "Factor derivation: spend auto-derived"
else
  fail "Factor derivation: spend source=$SPEND_SOURCE (expected derived)"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-6: METRICS TIME-RANGE AGGREGATION
# ═══════════════════════════════════════════════════════════════════
echo "── P-6: Metrics Aggregation ──"

# Take a snapshot first
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE/api/autonomous/self-audit" > /dev/null

# Range query
check_contains "GET" "/api/autonomous/metrics/range?after=2026-01-01&before=2026-12-31" '"count"' "Range query returns count"

# Aggregate with dates
check_contains "GET" "/api/autonomous/metrics/aggregate?after=2026-01-01&before=2026-12-31" '"metrics"' "Aggregate with date range"

# Aggregate with preset
check_contains "GET" "/api/autonomous/metrics/aggregate?preset=30d" '"period_a"' "Aggregate with preset=30d"

# Compare with preset
check_contains "GET" "/api/autonomous/metrics/compare?preset=7d" '"comparison"' "Compare with preset=7d"

# Error: missing params
check_status "GET" "/api/autonomous/metrics/aggregate" "400" "Error: missing aggregate params"

# Error: invalid preset
check_status "GET" "/api/autonomous/metrics/aggregate?preset=999d" "400" "Error: invalid preset"

# Existing dashboard still works
check_contains "GET" "/api/autonomous/dashboard" '"timestamp"' "Existing dashboard intact"

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-7: SECURITY HEADERS
# ═══════════════════════════════════════════════════════════════════
echo "── P-7: Security Headers ──"

HEADERS=$(curl -sI -H "Authorization: Bearer $TOKEN" "$BASE/api/health")

for header in "strict-transport-security" "x-content-type-options" "x-frame-options" "x-xss-protection" "referrer-policy" "content-security-policy" "permissions-policy"; do
  if echo "$HEADERS" | grep -qi "$header"; then
    ok "Header: $header"
  else
    fail "Header missing: $header"
  fi
done

# CORS still works
CORS=$(curl -sI -H "Origin: http://localhost:3000" "$BASE/api/health")
if echo "$CORS" | grep -qi "access-control-allow-origin"; then
  ok "CORS: access-control-allow-origin present"
else
  fail "CORS: access-control-allow-origin missing"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-8: SKILLS MARKETPLACE
# ═══════════════════════════════════════════════════════════════════
echo "── P-8: Skills Marketplace ──"

# Sources (may have entries from earlier)
check_status "GET" "/api/marketplace/sources" "200" "List sources"

# Add source (self repo — may already exist)
check_status "POST" "/api/marketplace/sources" "201" "Add source" \
  '{"url":"https://github.com/clawbot-alpha-factory/nemoclaw-local-foundation","name":"val-test"}'

# Stats
check_contains "GET" "/api/marketplace/stats" '"total_sources"' "Marketplace stats"

# Check updates
check_status "GET" "/api/marketplace/updates" "200" "Check updates endpoint"

# Discover (may take a few seconds — clone repo)
DISCOVER_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/marketplace/discover?force=true" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
if [ "$DISCOVER_COUNT" -gt 0 ] 2>/dev/null; then
  ok "Discover found $DISCOVER_COUNT skills"
else
  warn "Discover returned $DISCOVER_COUNT skills (may need git access)"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-9: MENA ADAPTATION
# ═══════════════════════════════════════════════════════════════════
echo "── P-9: MENA Adaptation ──"

# Bridge manager includes WhatsApp
BRIDGES=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/bridges/status" | python3 -c "import json,sys; print(list(json.load(sys.stdin).get('bridges',{}).keys()))" 2>/dev/null)
if echo "$BRIDGES" | grep -q "whatsapp"; then
  ok "WhatsApp bridge registered"
else
  fail "WhatsApp bridge not in bridge list"
fi

# WhatsApp status (should be disabled — no keys)
WA_ENABLED=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/bridges/whatsapp/status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('enabled',''))" 2>/dev/null)
if [ "$WA_ENABLED" = "False" ]; then
  ok "WhatsApp bridge disabled (no keys — expected)"
else
  warn "WhatsApp bridge enabled=$WA_ENABLED"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# P-10: PAYMENT BRIDGE (LEMON SQUEEZY)
# ═══════════════════════════════════════════════════════════════════
echo "── P-10: Payment Bridge ──"

# Bridge manager includes lemonsqueezy
if echo "$BRIDGES" | grep -q "lemonsqueezy"; then
  ok "LemonSqueezy bridge registered"
else
  fail "LemonSqueezy bridge not in bridge list"
fi

# LemonSqueezy status
check_contains "GET" "/api/bridges/lemonsqueezy/status" '"name"' "LemonSqueezy status endpoint"

# Webhook: order_created
check_contains "POST" "/api/webhooks/lemonsqueezy" '"status"' "Webhook: order_created" \
  '{"event_type":"order_created","data":{"customer_email":"val@test.com","order_id":"val_ord_1","total":99}}'

# Webhook: subscription_cancelled
check_contains "POST" "/api/webhooks/lemonsqueezy" '"status"' "Webhook: subscription_cancelled" \
  '{"event_type":"subscription_cancelled","data":{"subscription_id":"val_sub_1"}}'

# Webhook history for lemonsqueezy
check_contains "GET" "/api/webhooks/history?source=lemonsqueezy" '"events"' "Webhook history: lemonsqueezy"

echo ""

# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════
echo "── Integration Tests ──"

# Webhook → Activity Log integration (P-3 → P-2)
ACTIVITY_BRIDGE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/activity/?category=bridge" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null)
if [ "$ACTIVITY_BRIDGE" -gt 0 ] 2>/dev/null; then
  ok "Webhook→ActivityLog integration ($ACTIVITY_BRIDGE bridge activities)"
else
  warn "No bridge activities in activity log"
fi

# Approval scoring → Activity Log integration (P-5 → P-2)
ACTIVITY_SYSTEM=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/activity/?category=system" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null)
if [ "$ACTIVITY_SYSTEM" -gt 0 ] 2>/dev/null; then
  ok "System activities logged ($ACTIVITY_SYSTEM entries)"
else
  warn "No system activities in activity log"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# RUN ORIGINAL REGRESSION (cockpit safety)
# ═══════════════════════════════════════════════════════════════════
echo "── Original Cockpit Regression ──"

COCKPIT_ENDPOINTS=(
  "/api/health" "/api/health/ready" "/api/health/debug" "/api/state"
  "/api/brain/status" "/api/comms/lanes" "/api/comms/agents" "/api/comms/stats"
  "/api/agents/" "/api/agents/org" "/api/agents/workload"
  "/api/skills/" "/api/skills/stats"
  "/api/ops/dashboard" "/api/ops/tasks" "/api/ops/budget"
  "/api/projects/" "/api/clients/" "/api/approvals/"
  "/api/execution/status" "/api/execution/queue" "/api/execution/history" "/api/execution/dead-letter"
  "/api/orchestrator/workflows" "/api/orchestrator/projects/active"
  "/api/engine/status" "/api/engine/checkpoints"
  "/api/agents/sales_outreach_lead/loop-status" "/api/agents/sales_outreach_lead/memory" "/api/agents/sales_outreach_lead/schedule"
  "/api/protocol/history" "/api/protocol/feedback-loops" "/api/protocol/inbox/sales_outreach_lead" "/api/knowledge-base"
  "/api/engine/config" "/api/engine/alerts" "/api/sla/projects" "/api/audit/log"
  "/api/engine/approvals/chains" "/api/engine/approvals/pending"
  "/api/skill-factory/queue" "/api/skill-factory/stats" "/api/skill-factory/patterns"
)

COCKPIT_FAIL=0
for ep in "${COCKPIT_ENDPOINTS[@]}"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE$ep")
  if [ "$STATUS" = "200" ]; then
    PASS=$((PASS+1))
  else
    COCKPIT_FAIL=$((COCKPIT_FAIL+1))
    FAIL=$((FAIL+1))
    echo "  ❌ GET $ep ($STATUS)"
  fi
done

if [ "$COCKPIT_FAIL" -eq 0 ]; then
  echo "  ✅ All ${#COCKPIT_ENDPOINTS[@]} cockpit endpoints pass"
else
  echo "  ❌ $COCKPIT_FAIL cockpit endpoints FAILED"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed, $WARN warnings"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "  ✅ ALL TESTS PASSED"
else
  echo "  ⛔ $FAIL FAILURES — FIX BEFORE CONTINUING"
fi

if [ "$WARN" -gt 0 ]; then
  echo "  ⚠️  $WARN warnings (non-blocking)"
fi

echo ""
echo "  Report: P-1 memory, P-2 activity, P-3 webhook, P-4 deps,"
echo "          P-5 rubric, P-6 metrics, P-7 headers, P-8 marketplace,"
echo "          P-9 MENA, P-10 payment + ${#COCKPIT_ENDPOINTS[@]} cockpit endpoints"
echo ""
