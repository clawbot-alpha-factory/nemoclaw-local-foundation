#!/usr/bin/env python3
"""
NemoClaw Checkpoint Manager
CLI interface for checkpoint operations.
Imports checkpoint_utils shared module.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint_utils as cp

def cmd_create(args):
    steps = args.steps.split(",") if args.steps else []
    data = cp.create(args.workflow_id, args.phase, steps)
    print(f"Created checkpoint: {data['workflow_id']}")
    print(f"Phase: {data['current_phase']}")
    print(f"Steps: {data['pending_steps']}")

def cmd_status(args):
    data = cp.load(args.workflow_id)
    if not data:
        print(f"Checkpoint not found: {args.workflow_id}")
        return
    print(f"\n{'='*55}")
    print(f"  Checkpoint: {data['workflow_id']}")
    print(f"{'='*55}")
    print(f"  Status:     {data['status']}")
    print(f"  Phase:      {data['current_phase']}")
    print(f"  Step:       {data['current_step']}")
    print(f"  Updated:    {data['updated_at']}")
    print(f"  Completed:  {data['completed_steps']}")
    print(f"  Pending:    {data['pending_steps']}")
    print(f"  Files:      {data['files_created']}")
    if data['pause_reason']:
        print(f"  PAUSED:     {data['pause_reason']}")
        print(f"  Resume at:  {data['resume_point']}")
    print(f"{'='*55}\n")

def cmd_complete_step(args):
    files = args.files.split(",") if args.files else []
    data = cp.complete_step(args.workflow_id, args.step, files_created=files)
    print(f"Step '{args.step}' marked complete.")
    print(f"Next step: {data['current_step']}")
    print(f"Status: {data['status']}")

def cmd_pause(args):
    data = cp.pause(args.workflow_id, args.reason, args.instruction or "")
    print(f"Workflow paused: {args.workflow_id}")
    print(f"Reason: {args.reason}")
    if args.reason == "paused_budget_warning":
        print(f"\n{'='*60}")
        print(f"YOU HIT 90% OF YOUR BUDGET")
        print(f"Workflow paused. Explicit approval required to resume.")
        print(f"{'='*60}\n")
    elif args.reason == "paused_budget_exhausted":
        print(f"\n{'='*60}")
        print(f"PROVIDER BUDGET EXHAUSTED — SWITCHED TO FALLBACK")
        print(f"Workflow paused. Switch provider before resuming.")
        print(f"{'='*60}\n")

def cmd_resume(args):
    data, error = cp.resume(args.workflow_id)
    if error:
        print(f"Cannot resume: {error}")
        return
    print(f"\n{'='*55}")
    print(f"  Resume: {data['workflow_id']}")
    print(f"{'='*55}")
    print(f"  Status:      {data['status']}")
    print(f"  Resume step: {data['resume_point']['step']}")
    print(f"  Instruction: {data['resume_point']['instruction']}")
    print(f"  Pending:     {data['pending_steps']}")
    print(f"{'='*55}\n")

def cmd_list(args):
    checkpoints = cp.list_checkpoints()
    if not checkpoints:
        print("No checkpoints found.")
        return
    print(f"\n{'='*70}")
    print(f"  {'WORKFLOW ID':<35} {'STATUS':<25} {'STEP'}")
    print(f"{'='*70}")
    for c in checkpoints:
        print(f"  {c['workflow_id']:<35} {c['status']:<25} {c['step'] or 'complete'}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Checkpoint Manager")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create")
    p_create.add_argument("--workflow-id", required=True)
    p_create.add_argument("--phase", required=True)
    p_create.add_argument("--steps", required=True, help="Comma-separated step names")

    p_status = sub.add_parser("status")
    p_status.add_argument("--workflow-id", required=True)

    p_complete = sub.add_parser("complete-step")
    p_complete.add_argument("--workflow-id", required=True)
    p_complete.add_argument("--step", required=True)
    p_complete.add_argument("--files", default="", help="Comma-separated files created")

    p_pause = sub.add_parser("pause")
    p_pause.add_argument("--workflow-id", required=True)
    p_pause.add_argument("--reason", required=True,
        choices=["paused_budget_warning","paused_budget_exhausted","paused_manual"])
    p_pause.add_argument("--instruction", default="")

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--workflow-id", required=True)

    p_list = sub.add_parser("list")

    args = parser.parse_args()

    if args.command == "create":          cmd_create(args)
    elif args.command == "status":        cmd_status(args)
    elif args.command == "complete-step": cmd_complete_step(args)
    elif args.command == "pause":         cmd_pause(args)
    elif args.command == "resume":        cmd_resume(args)
    elif args.command == "list":          cmd_list(args)
    else:
        parser.print_help()
