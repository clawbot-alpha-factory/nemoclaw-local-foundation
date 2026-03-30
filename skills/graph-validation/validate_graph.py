#!/usr/bin/env python3
"""
NemoClaw Graph Validation Harness v1.0.0
Phase 9 — Non-Linear Graph Validation

Tests five LangGraph patterns:
  1. Conditional branching
  2. Error branches
  3. Retry paths
  4. Fallback paths
  5. Parallel nodes

No real API calls. No budget enforcer. Pure graph structure validation.
Run with: .venv313/bin/python skills/graph-validation/validate_graph.py
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, END

RESULTS_FILE = os.path.expanduser(
    "~/nemoclaw-local-foundation/docs/architecture/langgraph-graph-validation-results.json"
)

# ── Shared State ──────────────────────────────────────────────────────────────
class ValidationState(TypedDict):
    test_name:        str
    input_value:      str
    path_taken:       Annotated[list, operator.add]
    retry_count:      int
    parallel_a_done:  bool
    parallel_b_done:  bool
    parallel_a_result: str
    parallel_b_result: str
    error_message:    str
    fallback_used:    bool
    status:           str
    output:           str

# ── Test Results Tracker ──────────────────────────────────────────────────────
results = {}

def record(test_name, passed, detail):
    results[test_name] = {
        "passed": passed,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    icon = "✅" if passed else "❌"
    print(f"  {icon} {test_name}: {detail}")

# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Conditional Branching
# ══════════════════════════════════════════════════════════════════════════════

def test_conditional_branching():
    print("\nTest 1 — Conditional Branching")

    def node_start(state: ValidationState) -> ValidationState:
        return {"path_taken": ["start"], "status": "running"}

    def node_branch(state: ValidationState) -> ValidationState:
        return {"path_taken": ["branch_evaluated"]}

    def node_path_a(state: ValidationState) -> ValidationState:
        return {"path_taken": ["path_a"], "output": "took_path_a", "status": "complete"}

    def node_path_b(state: ValidationState) -> ValidationState:
        return {"path_taken": ["path_b"], "output": "took_path_b", "status": "complete"}

    def route_condition(state: ValidationState) -> str:
        return "path_a" if state["input_value"] == "go_a" else "path_b"

    graph = StateGraph(ValidationState)
    graph.add_node("start", node_start)
    graph.add_node("branch", node_branch)
    graph.add_node("path_a", node_path_a)
    graph.add_node("path_b", node_path_b)
    graph.set_entry_point("start")
    graph.add_edge("start", "branch")
    graph.add_conditional_edges("branch", route_condition, {
        "path_a": "path_a",
        "path_b": "path_b"
    })
    graph.add_edge("path_a", END)
    graph.add_edge("path_b", END)
    app = graph.compile()

    # Test A — input routes to path_a
    initial_a: ValidationState = {
        "test_name": "conditional_branching",
        "input_value": "go_a",
        "path_taken": [], "retry_count": 0,
        "parallel_a_done": False, "parallel_b_done": False,
        "parallel_a_result": "", "parallel_b_result": "",
        "error_message": "", "fallback_used": False,
        "status": "pending", "output": ""
    }
    result_a = app.invoke(initial_a)
    passed_a = result_a["output"] == "took_path_a" and "path_a" in result_a["path_taken"]

    # Test B — input routes to path_b
    initial_b = {**initial_a, "input_value": "go_b"}
    result_b = app.invoke(initial_b)
    passed_b = result_b["output"] == "took_path_b" and "path_b" in result_b["path_taken"]

    passed = passed_a and passed_b
    record("conditional_branching", passed,
           f"path_a routed={'✓' if passed_a else '✗'} path_b routed={'✓' if passed_b else '✗'}")
    return passed

# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Error Branches
# ══════════════════════════════════════════════════════════════════════════════

def test_error_branches():
    print("\nTest 2 — Error Branches")

    def node_start(state: ValidationState) -> ValidationState:
        return {"path_taken": ["start"], "status": "running"}

    def node_risky(state: ValidationState) -> ValidationState:
        if state["input_value"] == "fail":
            return {"path_taken": ["risky_failed"], "status": "error",
                    "error_message": "intentional_failure"}
        return {"path_taken": ["risky_success"], "status": "complete", "output": "success"}

    def node_error_handler(state: ValidationState) -> ValidationState:
        return {"path_taken": ["error_handled"], "status": "recovered",
                "output": f"handled: {state['error_message']}"}

    def route_after_risky(state: ValidationState) -> str:
        return "error_handler" if state["status"] == "error" else END

    graph = StateGraph(ValidationState)
    graph.add_node("start", node_start)
    graph.add_node("risky", node_risky)
    graph.add_node("error_handler", node_error_handler)
    graph.set_entry_point("start")
    graph.add_edge("start", "risky")
    graph.add_conditional_edges("risky", route_after_risky, {
        "error_handler": "error_handler",
        END: END
    })
    graph.add_edge("error_handler", END)
    app = graph.compile()

    initial: ValidationState = {
        "test_name": "error_branches", "input_value": "fail",
        "path_taken": [], "retry_count": 0,
        "parallel_a_done": False, "parallel_b_done": False,
        "parallel_a_result": "", "parallel_b_result": "",
        "error_message": "", "fallback_used": False,
        "status": "pending", "output": ""
    }
    result = app.invoke(initial)
    passed = (result["status"] == "recovered" and
              "error_handled" in result["path_taken"] and
              "intentional_failure" in result["output"])
    record("error_branches", passed,
           f"error routed to handler={'✓' if passed else '✗'} state preserved={'✓' if result['error_message'] else '✗'}")
    return passed

# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Retry Paths
# ══════════════════════════════════════════════════════════════════════════════

def test_retry_paths():
    print("\nTest 3 — Retry Paths")

    MAX_RETRIES = 2

    def node_start(state: ValidationState) -> ValidationState:
        return {"path_taken": ["start"], "retry_count": 0, "status": "running"}

    def node_flaky(state: ValidationState) -> ValidationState:
        count = state["retry_count"]
        if count < MAX_RETRIES:
            return {"path_taken": [f"flaky_attempt_{count+1}"],
                    "retry_count": count + 1, "status": "retry"}
        return {"path_taken": [f"flaky_success_attempt_{count+1}"],
                "retry_count": count + 1,
                "status": "complete", "output": f"succeeded_after_{count+1}_attempts"}

    def node_retry_gate(state: ValidationState) -> str:
        if state["status"] == "retry":
            return "flaky"
        return END

    graph = StateGraph(ValidationState)
    graph.add_node("start", node_start)
    graph.add_node("flaky", node_flaky)
    graph.set_entry_point("start")
    graph.add_edge("start", "flaky")
    graph.add_conditional_edges("flaky", node_retry_gate, {
        "flaky": "flaky",
        END: END
    })
    app = graph.compile()

    initial: ValidationState = {
        "test_name": "retry_paths", "input_value": "test",
        "path_taken": [], "retry_count": 0,
        "parallel_a_done": False, "parallel_b_done": False,
        "parallel_a_result": "", "parallel_b_result": "",
        "error_message": "", "fallback_used": False,
        "status": "pending", "output": ""
    }
    result = app.invoke(initial)
    attempts = result["retry_count"]
    passed = (result["status"] == "complete" and
              attempts == MAX_RETRIES + 1 and
              "succeeded" in result["output"])
    record("retry_paths", passed,
           f"retried {attempts-1} times then succeeded={'YES' if passed else 'NO'} attempts={attempts} final status={result['status']}")
    return passed

# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Fallback Paths
# ══════════════════════════════════════════════════════════════════════════════

def test_fallback_paths():
    print("\nTest 4 — Fallback Paths")

    MAX_RETRIES = 2

    def node_start(state: ValidationState) -> ValidationState:
        return {"path_taken": ["start"], "retry_count": 0, "status": "running"}

    def node_primary(state: ValidationState) -> ValidationState:
        count = state["retry_count"]
        if count <= MAX_RETRIES:
            return {"path_taken": [f"primary_fail_{count+1}"],
                    "retry_count": count + 1, "status": "error"}
        return {"path_taken": ["primary_success"], "status": "complete", "output": "primary_ok"}

    def node_fallback(state: ValidationState) -> ValidationState:
        return {"path_taken": ["fallback_executed"], "fallback_used": True,
                "status": "complete", "output": "fallback_result"}

    def route_primary(state: ValidationState) -> str:
        if state["status"] == "error":
            if state["retry_count"] <= MAX_RETRIES:
                return "primary"
            return "fallback"
        return END

    graph = StateGraph(ValidationState)
    graph.add_node("start", node_start)
    graph.add_node("primary", node_primary)
    graph.add_node("fallback", node_fallback)
    graph.set_entry_point("start")
    graph.add_edge("start", "primary")
    graph.add_conditional_edges("primary", route_primary, {
        "primary": "primary",
        "fallback": "fallback",
        END: END
    })
    graph.add_edge("fallback", END)
    app = graph.compile()

    initial: ValidationState = {
        "test_name": "fallback_paths", "input_value": "test",
        "path_taken": [], "retry_count": 0,
        "parallel_a_done": False, "parallel_b_done": False,
        "parallel_a_result": "", "parallel_b_result": "",
        "error_message": "", "fallback_used": False,
        "status": "pending", "output": ""
    }
    result = app.invoke(initial)
    passed = (result["fallback_used"] is True and
              result["status"] == "complete" and
              result["output"] == "fallback_result" and
              "fallback_executed" in result["path_taken"])
    record("fallback_paths", passed,
           f"fallback triggered={'✓' if result['fallback_used'] else '✗'} output valid={'✓' if result['output']=='fallback_result' else '✗'}")
    return passed

# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — Parallel Nodes
# ══════════════════════════════════════════════════════════════════════════════

def test_parallel_nodes():
    print("\nTest 5 — Parallel Nodes")

    def node_start(state: ValidationState) -> ValidationState:
        return {"path_taken": ["start"], "status": "running"}

    def node_parallel_a(state: ValidationState) -> ValidationState:
        return {"path_taken": ["parallel_a"],
                "parallel_a_result": "result_from_a",
                "parallel_a_done": True}

    def node_parallel_b(state: ValidationState) -> ValidationState:
        return {"path_taken": ["parallel_b"],
                "parallel_b_result": "result_from_b",
                "parallel_b_done": True}

    def node_merge(state: ValidationState) -> ValidationState:
        merged = f"{state['parallel_a_result']}+{state['parallel_b_result']}"
        return {"path_taken": ["merge"], "output": merged, "status": "complete"}

    graph = StateGraph(ValidationState)
    graph.add_node("start", node_start)
    graph.add_node("parallel_a", node_parallel_a)
    graph.add_node("parallel_b", node_parallel_b)
    graph.add_node("merge", node_merge)
    graph.set_entry_point("start")
    graph.add_edge("start", "parallel_a")
    graph.add_edge("start", "parallel_b")
    graph.add_edge("parallel_a", "merge")
    graph.add_edge("parallel_b", "merge")
    graph.add_edge("merge", END)
    app = graph.compile()

    initial: ValidationState = {
        "test_name": "parallel_nodes", "input_value": "test",
        "path_taken": [], "retry_count": 0,
        "parallel_a_done": False, "parallel_b_done": False,
        "parallel_a_result": "", "parallel_b_result": "",
        "error_message": "", "fallback_used": False,
        "status": "pending", "output": ""
    }
    result = app.invoke(initial)
    passed = (result["parallel_a_done"] is True and
              result["parallel_b_done"] is True and
              "parallel_a" in result["path_taken"] and
              "parallel_b" in result["path_taken"] and
              "merge" in result["path_taken"] and
              result["output"] == "result_from_a+result_from_b")
    record("parallel_nodes", passed,
           f"both nodes ran={'✓' if result['parallel_a_done'] and result['parallel_b_done'] else '✗'} merged correctly={'✓' if result['output']=='result_from_a+result_from_b' else '✗'}")
    return passed

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  NemoClaw LangGraph Validation Harness v1.0.0")
    print("  Phase 9 — Non-Linear Graph Validation")
    print("=" * 60)

    p1 = test_conditional_branching()
    p2 = test_error_branches()
    p3 = test_retry_paths()
    p4 = test_fallback_paths()
    p5 = test_parallel_nodes()

    all_passed = all([p1, p2, p3, p4, p5])
    total = sum([p1, p2, p3, p4, p5])

    print(f"\n{'='*60}")
    print(f"  Results: {total}/5 patterns passed")
    print(f"  Graph readiness: {'CONFIRMED' if all_passed else 'NOT YET CONFIRMED'}")
    print(f"{'='*60}\n")

    # Write results to docs
    os.makedirs(os.path.dirname(os.path.expanduser(RESULTS_FILE)), exist_ok=True)
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runner_version": "1.0.0",
        "langgraph_version": __import__("importlib.metadata", fromlist=["metadata"]).metadata("langgraph")["Version"],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "total_passed": total,
        "total_tests": 5,
        "graph_ready": all_passed,
        "patterns": results
    }
    with open(os.path.expanduser(RESULTS_FILE), "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results written to: {RESULTS_FILE}")

    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
