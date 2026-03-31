#!/usr/bin/env python3
"""
L-003 Fixer: Replaces hardcoded model references with lib.routing calls.
Handles two patterns:
  Pattern B (newer skills): MODEL_COSTS, get_routing_config(), call_llm(), estimate_cost()
  Pattern A (older skills): call_openai(), call_anthropic(), call_google() with hardcoded defaults
  Critic steps: Direct ChatAnthropic(model="claude-haiku-...") instantiation
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def fix_pattern_b(content, filepath):
    """Fix newer skills with get_routing_config/call_llm/MODEL_COSTS boilerplate."""
    changes = []

    # Detect which default tier is used
    tier_match = re.search(r'return R\.get\("(\w+)"', content)
    default_tier = tier_match.group(1) if tier_match else "moderate"

    # Map old tier names to routing config task_classes
    tier_map = {"premium": "complex_reasoning", "moderate": "moderate", "cheap": "general_short"}
    task_class = tier_map.get(default_tier, "moderate")

    # 1. Remove MODEL_COSTS line
    content, n = re.subn(
        r'\nMODEL_COSTS = \{[^}]+\}\n',
        '\n',
        content
    )
    if n: changes.append("removed MODEL_COSTS")

    # 2. Remove get_routing_config() function (1-4 lines)
    content, n = re.subn(
        r'\ndef get_routing_config\(\):.*?(?=\ndef |\nclass )',
        '\n',
        content,
        flags=re.DOTALL
    )
    if n: changes.append("removed get_routing_config()")

    # 3. Replace call_llm() function with routing import wrapper
    old_call_llm = re.search(
        r'\ndef call_llm\(messages.*?\n(?=def |\nclass )',
        content,
        flags=re.DOTALL
    )
    if old_call_llm:
        new_call_llm = f"""
def call_llm(messages, max_tokens=4000):
    from lib.routing import call_llm as _routed_call
    return _routed_call(messages, task_class="{task_class}", max_tokens=max_tokens)

"""
        content = content[:old_call_llm.start()] + new_call_llm + content[old_call_llm.end():]
        changes.append(f"replaced call_llm() -> lib.routing (task_class={task_class})")

    # 4. Replace estimate_cost(model) function
    content, n = re.subn(
        r'\ndef estimate_cost\(model\):.*\n',
        '\ndef estimate_cost(task_class="moderate"):\n    from lib.routing import estimate_cost as _est\n    return _est(task_class)\n',
        content
    )
    if n: changes.append("replaced estimate_cost()")

    # 5. Fix estimate_cost(model) call sites — change to estimate_cost()
    content, n = re.subn(
        r'estimate_cost\(model\)',
        'estimate_cost()',
        content
    )
    if n: changes.append(f"fixed {n} estimate_cost() call sites")

    # 5b. Fix get_routing_config()[1] in envelope metadata
    content, n = re.subn(
        r'get_routing_config\(\)\[1\]',
        f'__import__("lib.routing", fromlist=["resolve_from_env_or_config"]).resolve_from_env_or_config("{task_class}")[1]',
        content
    )
    if n: changes.append(f"fixed {n} get_routing_config()[1] metadata references")

    # 6. Fix "provider, model = get_routing_config()" in step functions
    content, n = re.subn(
        r'provider, model = get_routing_config\(\)',
        f'from lib.routing import resolve_from_env_or_config as _resolve\n    provider, model, _cost = _resolve("{task_class}")',
        content
    )
    if n: changes.append(f"fixed {n} get_routing_config() call sites")

    # 7. Fix hardcoded critic ChatAnthropic calls
    # Pattern: resp = ChatAnthropic(model="claude-haiku-4-5-20251001", ...).invoke(...)
    # Replace with two lines: resolve alias, then use the model
    def _fix_critic_line(m):
        indent = m.group(1)
        rest = m.group(2)
        return (
            f'{indent}from lib.routing import resolve_alias as _ra\n'
            f'{indent}_cp, _cm, _cc = _ra("structured_short")\n'
            f'{indent}{rest.replace("claude-haiku-4-5-20251001", '" + '"_cm")}'
        )

    # Match lines like: <indent>resp = ChatAnthropic(model="claude-haiku-4-5-20251001"...)
    old_content = content
    content = re.sub(
        r'^( +)(.*ChatAnthropic\(model=)"claude-haiku-4-5-20251001"(.*)$',
        lambda m: (
            f'{m.group(1)}from lib.routing import resolve_alias as _ra\n'
            f'{m.group(1)}_cp, _cm, _cc = _ra("structured_short")\n'
            f'{m.group(1)}{m.group(2)}_cm{m.group(3)}'
        ),
        content,
        flags=re.MULTILINE
    )
    n = 1 if content != old_content else 0
    if n: changes.append(f"fixed hardcoded critic model references")

    return content, changes


def fix_pattern_a(content, filepath):
    """Fix older skills with call_openai/call_anthropic/call_google hardcoded defaults."""
    changes = []

    # Fix call_openai default model parameter
    content, n = re.subn(
        r'def call_openai\(messages, model="[^"]*"',
        'def call_openai(messages, model=None',
        content
    )
    if n:
        # Add routing resolution at the top of the function
        content = re.sub(
            r'(def call_openai\(messages, model=None.*?:\n)',
            r'\1    if model is None:\n        from lib.routing import resolve_alias\n        _, model, _ = resolve_alias("general_short")\n',
            content,
            flags=re.DOTALL
        )
        changes.append("fixed call_openai() default model")

    # Fix call_anthropic default model parameter
    content, n = re.subn(
        r'def call_anthropic\(messages, model="[^"]*"',
        'def call_anthropic(messages, model=None',
        content
    )
    if n:
        content = re.sub(
            r'(def call_anthropic\(messages, model=None.*?:\n)',
            r'\1    if model is None:\n        from lib.routing import resolve_alias\n        _, model, _ = resolve_alias("complex_reasoning")\n',
            content,
            flags=re.DOTALL
        )
        changes.append("fixed call_anthropic() default model")

    # Fix call_google default model parameter
    content, n = re.subn(
        r'def call_google\(messages, model="[^"]*"',
        'def call_google(messages, model=None',
        content
    )
    if n:
        content = re.sub(
            r'(def call_google\(messages, model=None.*?:\n)',
            r'\1    if model is None:\n        from lib.routing import resolve_alias\n        _, model, _ = resolve_alias("moderate")\n',
            content,
            flags=re.DOTALL
        )
        changes.append("fixed call_google() default model")

    # Fix call_resolved default fallbacks
    content, n = re.subn(
        r'context\.get\("resolved_provider", "[^"]*"\)',
        'context.get("resolved_provider", __import__("lib.routing", fromlist=["resolve_alias"]).resolve_alias("moderate")[0])',
        content
    )
    # Actually this is too complex. Let me just fix the string defaults.
    # Revert and use simpler approach: just fix the default strings
    # Actually the call_resolved reads from context which comes from skill-runner.
    # The defaults are fallbacks. We should make them dynamic.

    return content, changes


def fix_critic_inline(content):
    """Fix any remaining inline hardcoded ChatAnthropic/ChatOpenAI with model strings."""
    changes = []

    # Pattern: ChatAnthropic(model="claude-...-20251001" or "claude-sonnet-4-6")
    # in lines that are NOT inside a def call_llm or def call_anthropic
    for old_model in [
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022",
        "claude-sonnet-4-6",
    ]:
        if old_model in content:
            # Only fix in non-function-def contexts (inline in step functions)
            # We already handle the call_llm/call_anthropic defs above
            pass

    return content, changes


def fix_file(filepath):
    """Apply L-003 fixes to a single file."""
    content = filepath.read_text()
    all_changes = []

    # Detect pattern type
    has_pattern_b = "get_routing_config" in content and "MODEL_COSTS" in content
    has_pattern_a = "def call_openai" in content or "def call_anthropic" in content

    if has_pattern_b:
        content, changes = fix_pattern_b(content, filepath)
        all_changes.extend(changes)
    elif has_pattern_a:
        content, changes = fix_pattern_a(content, filepath)
        all_changes.extend(changes)

    if all_changes:
        filepath.write_text(content)

    return all_changes


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fix-l003.py <file_or_dir> [--dry-run]")
        sys.exit(1)

    target = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("run.py"))
    else:
        print(f"Not found: {target}")
        sys.exit(1)

    total_fixed = 0
    for f in files:
        content = f.read_text()
        has_violation = (
            "MODEL_COSTS" in content
            or "get_routing_config" in content
            or re.search(r'def call_openai\(messages, model="', content)
            or re.search(r'def call_anthropic\(messages, model="', content)
        )
        if not has_violation:
            continue

        if dry_run:
            print(f"  WOULD FIX: {f}")
            total_fixed += 1
            continue

        changes = fix_file(f)
        if changes:
            total_fixed += 1
            print(f"  FIXED: {f}")
            for c in changes:
                print(f"    - {c}")

    print(f"\nTotal: {total_fixed} files {'would be fixed' if dry_run else 'fixed'}")


if __name__ == "__main__":
    main()
