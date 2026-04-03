#!/usr/bin/env python3
"""
Test Agent Backend Awareness — verifies all 11 agents have correct execution
backend knowledge injected into their system prompts.

Usage:
    python3 scripts/test_agent_backend_awareness.py
    python3 scripts/test_agent_backend_awareness.py --live   # Actually call LLM

Output:
    ~/.nemoclaw/tests/backend-awareness-test.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Resolve repo root and add to path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "command-center" / "backend"))

from app.services.agent_chat_service import AgentChatService

# Expected execution backends per agent (from agent-schema.yaml execution_backends)
EXPECTED = {
    "executive_operator":       {"primary": "claude_code", "model": "opus"},
    "strategy_lead":            {"primary": "claude_code", "model": "opus"},
    "operations_lead":          {"primary": "claude_code", "model": "opus"},
    "product_architect":        {"primary": "claude_code", "model": "opus"},
    "growth_revenue_lead":      {"primary": "claude_code", "model": "sonnet"},
    "narrative_content_lead":   {"primary": "claude_code", "model": "sonnet"},
    "engineering_lead":         {"primary": "codex",       "model": "gpt-5.4"},
    "sales_outreach_lead":      {"primary": "claude_code", "model": "haiku"},
    "marketing_campaigns_lead": {"primary": "claude_code", "model": "haiku"},
    "client_success_lead":      {"primary": "claude_code", "model": "haiku"},
    "social_media_lead":        {"primary": "claude_code", "model": "haiku"},
}


def test_prompt_injection(service: AgentChatService) -> list[dict]:
    """Test that each agent's system prompt contains the correct EXECUTION BACKEND block."""
    results = []
    for agent_id, expected in EXPECTED.items():
        agent = service.get_agent(agent_id)
        if not agent:
            results.append({
                "agent_id": agent_id,
                "status": "FAIL",
                "reason": "Agent not loaded",
            })
            continue

        prompt = agent.build_system_prompt(schema_top=service._schema_top)

        checks = {
            "has_block": "EXECUTION BACKEND:" in prompt,
            "has_backend": expected["primary"] in prompt,
            "has_model": expected["model"] in prompt,
            "has_workspace": f"workspaces/{agent_id}" in prompt,
            "has_heartbeat": "heartbeat" in prompt.lower() or "Asana" in prompt,
            "has_status_md": "STATUS.md" in prompt,
        }

        all_pass = all(checks.values())
        failed = [k for k, v in checks.items() if not v]

        results.append({
            "agent_id": agent_id,
            "status": "PASS" if all_pass else "FAIL",
            "expected_backend": expected["primary"],
            "expected_model": expected["model"],
            "checks": checks,
            "failed": failed,
        })

    return results


async def test_live_responses(service: AgentChatService) -> list[dict]:
    """Send test message to each agent and verify response mentions backend."""
    results = []
    test_message = (
        "What execution backend are you assigned to? "
        "What MCP tools do you have access to? "
        "How would you execute a code generation task vs a research task?"
    )

    for agent_id, expected in EXPECTED.items():
        try:
            response = await service.generate_response(agent_id, test_message)
            if not response:
                results.append({
                    "agent_id": agent_id,
                    "status": "FAIL",
                    "reason": "No response",
                    "response": "",
                })
                continue

            response_lower = response.lower()
            mentions_backend = expected["primary"].replace("_", " ") in response_lower or expected["primary"] in response_lower
            mentions_model = expected["model"] in response_lower

            results.append({
                "agent_id": agent_id,
                "status": "PASS" if mentions_backend else "PARTIAL",
                "mentions_backend": mentions_backend,
                "mentions_model": mentions_model,
                "response": response[:500],
            })
        except Exception as e:
            results.append({
                "agent_id": agent_id,
                "status": "ERROR",
                "reason": str(e)[:200],
                "response": "",
            })

    return results


def write_report(prompt_results: list[dict], live_results: list[dict] | None = None) -> Path:
    """Write test results to markdown report."""
    output_dir = Path.home() / ".nemoclaw" / "tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "backend-awareness-test.md"

    lines = [
        "# Agent Backend Awareness Test",
        f"\nRun: {datetime.now().isoformat()}",
        "",
        "## Prompt Injection Tests",
        "",
        "Verifies each agent's system prompt contains correct EXECUTION BACKEND block.",
        "",
        "| Agent | Status | Backend | Model | Failed Checks |",
        "|-------|--------|---------|-------|---------------|",
    ]

    pass_count = 0
    for r in prompt_results:
        status_icon = "PASS" if r["status"] == "PASS" else "FAIL"
        if r["status"] == "PASS":
            pass_count += 1
        failed = ", ".join(r.get("failed", [r.get("reason", "")])) or "none"
        lines.append(
            f"| {r['agent_id']} | {status_icon} | "
            f"{r.get('expected_backend', 'N/A')} | "
            f"{r.get('expected_model', 'N/A')} | {failed} |"
        )

    lines.append(f"\n**Result: {pass_count}/{len(prompt_results)} agents passed prompt injection test.**")

    if live_results:
        lines.extend([
            "",
            "## Live Response Tests",
            "",
            "Each agent was asked about their execution backend.",
            "",
        ])
        for r in live_results:
            lines.extend([
                f"### {r['agent_id']} ({r['status']})",
                "",
                f"```\n{r.get('response', r.get('reason', 'N/A'))}\n```",
                "",
            ])

    report_path.write_text("\n".join(lines))
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Test agent backend awareness")
    parser.add_argument("--live", action="store_true", help="Run live LLM tests (costs money)")
    args = parser.parse_args()

    print("Loading AgentChatService...")
    service = AgentChatService()
    print(f"Loaded {len(service.agents)} agents")

    if len(service.agents) == 0:
        print("FAIL: No agents loaded. Check agent-schema.yaml path.")
        sys.exit(1)

    # Prompt injection tests (free — no LLM calls)
    print("\nRunning prompt injection tests...")
    prompt_results = test_prompt_injection(service)

    pass_count = sum(1 for r in prompt_results if r["status"] == "PASS")
    fail_count = len(prompt_results) - pass_count
    print(f"Prompt tests: {pass_count} passed, {fail_count} failed")

    for r in prompt_results:
        icon = "OK" if r["status"] == "PASS" else "FAIL"
        detail = f" — failed: {', '.join(r.get('failed', []))}" if r.get("failed") else ""
        print(f"  [{icon}] {r['agent_id']}: {r.get('expected_backend', '?')}/{r.get('expected_model', '?')}{detail}")

    # Live tests (optional — requires API key)
    live_results = None
    if args.live:
        import asyncio
        print("\nRunning live response tests...")
        live_results = asyncio.run(test_live_responses(service))
        for r in live_results:
            print(f"  [{r['status']}] {r['agent_id']}")

    # Write report
    report_path = write_report(prompt_results, live_results)
    print(f"\nReport written to: {report_path}")

    # Exit code
    if fail_count > 0:
        print(f"\nFAILED: {fail_count} agents missing execution backend in prompt")
        sys.exit(1)
    else:
        print(f"\nPASSED: All {pass_count} agents have correct execution backend injection")
        sys.exit(0)


if __name__ == "__main__":
    main()
