#!/usr/bin/env python3
"""
NemoClaw Agent Messaging System v1.0 (MA-3)

Structured communication layer for multi-agent coordination.

Features:
  - 11 message intents (inform, challenge, propose, critique, decide,
    request, acknowledge, escalate, delegate, withdraw, chat)
  - 5 channel types (topic, decision, adversarial, review, direct)
  - Configurable max turns per channel (default 6)
  - Hybrid blocking (urgent blocks workflow, standard is async)
  - Voting system for multi-agent decisions
  - Multi-approval governance
  - Withdraw intent with reason tracking
  - Chat mode (lightweight, ephemeral)
  - Action triggers (decide→decision_log, delegate→task)
  - Forced synthesis after turn limit
  - Response timeout with escalation
  - Reference validation against memory keys
  - Rule enforcement (no empty, mandatory refs in debates, no self-reply)

Usage:
  from agent_messaging import MessageBus
  bus = MessageBus(workspace_id="my_workflow", memory=memory_system)
  bus.create_channel("pricing-debate", "adversarial", max_turns=6)
  bus.send("strategy_lead", "pricing-debate", "propose", "Target SMB first",
           references=[{"memory_key": "market_segments"}], confidence=0.8)
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".nemoclaw"
CHANNELS_DIR = BASE_DIR / "channels"

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_INTENTS = [
    "inform", "challenge", "propose", "critique", "decide",
    "request", "acknowledge", "escalate", "delegate", "withdraw", "chat",
]

# Intents that can change system state
STATE_AFFECTING_INTENTS = ["decide", "delegate", "escalate", "withdraw"]

VALID_CHANNEL_TYPES = ["topic", "decision", "adversarial", "review", "direct"]

VALID_PRIORITIES = ["urgent", "standard", "low"]

VALID_VOTE_OPTIONS = ["approve", "reject", "abstain"]

DEFAULT_MAX_TURNS = 6
DEFAULT_RESPONSE_TIMEOUT_S = 300  # 5 minutes
MIN_MESSAGE_LENGTH = 20  # chars, except for chat intent
DEFAULT_CHAT_RETENTION = "24h"  # ephemeral | 24h | none


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE
# ═══════════════════════════════════════════════════════════════════════════════

class Message:
    """A structured message between agents."""

    def __init__(self, sender, channel_id, intent, content,
                 recipients=None, references=None, confidence=0.5,
                 requires_response=False, priority="standard",
                 parent_message_id=None, turn_number=None,
                 action_trigger=None, vote=None, withdraw_reason=None,
                 workflow_id=None):

        self.id = f"msg_{uuid.uuid4().hex[:8]}"
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.sender = sender
        self.channel_id = channel_id
        self.intent = intent
        self.content = content
        self.recipients = recipients or []
        self.references = references or []  # [{memory_key: str, source_agent: str}]
        self.confidence = confidence
        self.requires_response = requires_response
        self.priority = priority
        self.parent_message_id = parent_message_id
        self.turn_number = turn_number
        self.action_trigger = action_trigger  # {type: "decision"|"task"|"memory_write", target: str}
        self.vote = vote  # approve | reject | abstain (for decide intent in vote mode)
        self.withdraw_reason = withdraw_reason
        self.workflow_id = workflow_id
        self.status = "active"  # active | withdrawn | superseded
        self.responses = []  # message IDs that respond to this

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "channel_id": self.channel_id,
            "intent": self.intent,
            "content": self.content,
            "recipients": self.recipients,
            "references": self.references,
            "confidence": self.confidence,
            "requires_response": self.requires_response,
            "priority": self.priority,
            "parent_message_id": self.parent_message_id,
            "turn_number": self.turn_number,
            "action_trigger": self.action_trigger,
            "vote": self.vote,
            "withdraw_reason": self.withdraw_reason,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "responses": self.responses,
        }

    @classmethod
    def from_dict(cls, data):
        msg = cls.__new__(cls)
        for k, v in data.items():
            setattr(msg, k, v)
        return msg


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL
# ═══════════════════════════════════════════════════════════════════════════════

class Channel:
    """A communication channel between agents."""

    def __init__(self, channel_id, channel_type="topic", max_turns=DEFAULT_MAX_TURNS,
                 participants=None, decision_mode="single_owner",
                 approval_required=1, chat_mode=False, chat_retention=DEFAULT_CHAT_RETENTION):
        self.channel_id = channel_id
        self.channel_type = channel_type  # topic | decision | adversarial | review | direct
        self.max_turns = max_turns
        self.participants = participants or []  # empty = open to all
        self.decision_mode = decision_mode  # single_owner | vote
        self.approval_required = approval_required  # for vote mode
        self.chat_mode = chat_mode
        self.chat_retention = chat_retention
        self.messages = []
        self.turn_count = 0
        self.decision_closed = False
        self.decision_id = None
        self.votes = {}  # agent_id → approve|reject|abstain
        self.synthesis_requested = False

        self.dir = CHANNELS_DIR / channel_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.messages_path = self.dir / "messages.jsonl"
        self.meta_path = self.dir / "meta.json"

    def add_message(self, msg):
        """Add a message to the channel."""
        self.messages.append(msg)
        if msg.intent != "chat":
            self.turn_count += 1
        msg.turn_number = self.turn_count

        # Persist
        with open(self.messages_path, "a") as f:
            f.write(json.dumps(msg.to_dict()) + "\n")
        self._save_meta()

    def get_messages(self, limit=50, intent_filter=None):
        """Get recent messages, optionally filtered by intent."""
        msgs = self.messages[-limit:]
        if intent_filter:
            msgs = [m for m in msgs if m.intent in intent_filter]
        return msgs

    def get_active_messages(self):
        """Get non-withdrawn messages."""
        return [m for m in self.messages if m.status == "active"]

    def is_turn_limit_reached(self):
        """Check if debate has reached max turns."""
        # Only count non-chat messages
        real_turns = sum(1 for m in self.messages if m.intent != "chat")
        return real_turns >= self.max_turns

    def record_vote(self, agent_id, vote):
        """Record a vote in a decision channel."""
        if vote not in VALID_VOTE_OPTIONS:
            return False, f"Invalid vote: {vote}. Must be: {VALID_VOTE_OPTIONS}"
        self.votes[agent_id] = vote
        self._save_meta()
        return True, "Vote recorded"

    def check_vote_result(self):
        """Check if voting threshold is met.
        
        Returns: (decided, result, details)
        """
        if not self.votes:
            return False, None, "No votes cast"

        approvals = sum(1 for v in self.votes.values() if v == "approve")
        rejections = sum(1 for v in self.votes.values() if v == "reject")
        total = len(self.votes)

        if approvals >= self.approval_required:
            return True, "approved", {
                "approvals": approvals,
                "rejections": rejections,
                "total": total,
                "votes": dict(self.votes),
            }
        elif rejections > (total - self.approval_required):
            # Impossible to reach threshold
            return True, "rejected", {
                "approvals": approvals,
                "rejections": rejections,
                "total": total,
                "votes": dict(self.votes),
            }
        return False, "pending", {
            "approvals": approvals,
            "rejections": rejections,
            "total": total,
            "needed": self.approval_required,
            "votes": dict(self.votes),
        }

    def _save_meta(self):
        meta = {
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "max_turns": self.max_turns,
            "participants": self.participants,
            "decision_mode": self.decision_mode,
            "approval_required": self.approval_required,
            "turn_count": self.turn_count,
            "decision_closed": self.decision_closed,
            "decision_id": self.decision_id,
            "votes": self.votes,
            "synthesis_requested": self.synthesis_requested,
            "message_count": len(self.messages),
        }
        with open(self.meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def load(self):
        """Load channel from disk."""
        if self.messages_path.exists():
            self.messages = []
            with open(self.messages_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.messages.append(Message.from_dict(json.loads(line)))
        if self.meta_path.exists():
            with open(self.meta_path) as f:
                meta = json.load(f)
            self.turn_count = meta.get("turn_count", 0)
            self.decision_closed = meta.get("decision_closed", False)
            self.decision_id = meta.get("decision_id")
            self.votes = meta.get("votes", {})
            self.synthesis_requested = meta.get("synthesis_requested", False)


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE BUS
# ═══════════════════════════════════════════════════════════════════════════════

class MessageBus:
    """Central message routing and rule enforcement.
    
    Validates every message against:
      - Intent validity
      - Channel rules
      - Reference existence (in memory)
      - Authority (from agent registry)
      - Turn limits
      - Content length
      - Self-reply prevention
    """

    def __init__(self, workspace_id, memory=None, registry=None):
        """
        Args:
            workspace_id: current workflow identifier
            memory: MemorySystem instance (for reference validation)
            registry: AgentRegistry instance (for authority checks)
        """
        self.workspace_id = workspace_id
        self.memory = memory
        self.registry = registry
        self.channels = {}
        self.pending_responses = []  # messages awaiting response
        self.action_log = []  # triggered actions

    def create_channel(self, channel_id, channel_type="topic", max_turns=DEFAULT_MAX_TURNS,
                       participants=None, decision_mode="single_owner",
                       approval_required=1, chat_mode=False):
        """Create a new communication channel."""
        if channel_type not in VALID_CHANNEL_TYPES:
            return None, f"Invalid channel type: {channel_type}"

        channel = Channel(
            channel_id, channel_type, max_turns, participants,
            decision_mode, approval_required, chat_mode,
        )
        self.channels[channel_id] = channel
        return channel, "OK"

    def get_or_create_channel(self, channel_id, channel_type="topic", **kwargs):
        """Get existing channel or create new one."""
        if channel_id in self.channels:
            return self.channels[channel_id]
        channel, _ = self.create_channel(channel_id, channel_type, **kwargs)
        return channel

    def send(self, sender, channel_id, intent, content,
             recipients=None, references=None, confidence=0.5,
             requires_response=False, priority="standard",
             parent_message_id=None, action_trigger=None,
             vote=None, withdraw_reason=None):
        """Send a message with full validation.
        
        Returns: (success: bool, message_or_error: Message|str)
        """
        # ── Validate intent ──
        if intent not in VALID_INTENTS:
            return False, f"Invalid intent: {intent}. Must be: {VALID_INTENTS}"

        # ── Validate channel exists ──
        channel = self.channels.get(channel_id)
        if not channel:
            return False, f"Channel not found: {channel_id}"

        # ── Validate priority ──
        if priority not in VALID_PRIORITIES:
            return False, f"Invalid priority: {priority}. Must be: {VALID_PRIORITIES}"

        # ── Validate participants ──
        if channel.participants and sender not in channel.participants:
            return False, f"UNAUTHORIZED: {sender} not in channel {channel_id} participants"

        # ── Rule: No empty messages (except chat) ──
        if intent != "chat" and (not content or len(content.strip()) < MIN_MESSAGE_LENGTH):
            return False, f"Message too short ({len(content.strip())} chars). Minimum {MIN_MESSAGE_LENGTH} for non-chat."

        # ── Rule: Chat mode check ──
        if intent == "chat" and not channel.chat_mode:
            return False, f"Chat mode not enabled on channel {channel_id}"

        # ── Rule: Decision channel closed ──
        if channel.decision_closed and intent in STATE_AFFECTING_INTENTS:
            return False, f"Decision channel {channel_id} is closed. No more state-affecting messages."

        # ── Rule: Turn limit (adversarial channels) ──
        if channel.channel_type == "adversarial" and channel.is_turn_limit_reached():
            if intent != "chat" and intent != "acknowledge":
                if not channel.synthesis_requested:
                    channel.synthesis_requested = True
                    channel._save_meta()
                    return False, (
                        f"TURN LIMIT REACHED ({channel.max_turns}). "
                        f"Synthesis required. Highest-authority participant must synthesize."
                    )
                return False, f"Turn limit reached. Awaiting synthesis."

        # ── Rule: No self-reply ──
        if parent_message_id:
            parent = self._find_message(channel, parent_message_id)
            if parent and parent.sender == sender and intent != "withdraw":
                return False, f"Cannot reply to own message (except withdraw)"

        # ── Rule: Mandatory references in adversarial channels ──
        if channel.channel_type == "adversarial" and intent in ["challenge", "critique"]:
            if not references:
                return False, f"Adversarial {intent} requires at least 1 reference"

        # ── Rule: Validate references exist in memory ──
        if references and self.memory:
            for ref in references:
                mem_key = ref.get("memory_key")
                if mem_key and not self.memory.shared.has(mem_key):
                    # Check long-term too
                    if mem_key not in self.memory.long_term.store:
                        return False, f"Reference key '{mem_key}' not found in memory"

        # ── Rule: Withdraw validation ──
        if intent == "withdraw":
            if not parent_message_id:
                return False, "Withdraw requires parent_message_id"
            if not withdraw_reason:
                return False, "Withdraw requires withdraw_reason"
            parent = self._find_message(channel, parent_message_id)
            if not parent:
                return False, f"Parent message {parent_message_id} not found"
            if parent.sender != sender:
                return False, "Can only withdraw own messages"
            if parent.intent == "decide" and channel.decision_closed:
                return False, "Cannot withdraw a finalized decision"
            # Mark original as withdrawn
            parent.status = "withdrawn"

        # ── Rule: Vote validation ──
        if intent == "decide" and channel.decision_mode == "vote":
            if not vote:
                return False, "Vote required in vote-mode decision channel"
            ok, msg = channel.record_vote(sender, vote)
            if not ok:
                return False, msg

        # ── Rule: Authority for decide intent ──
        if intent == "decide" and channel.decision_mode == "single_owner":
            if self.registry:
                agent = self.registry.get_agent(sender)
                if agent and agent.get("authority_level", 99) > 2:
                    # Check if sender owns the domain
                    domain_owner = False
                    for cap_name, cap in self.registry.capabilities.items():
                        if cap.get("owned_by") == sender:
                            domain_owner = True
                            break
                    if not domain_owner:
                        return False, f"AUTHORITY: {sender} (level {agent.get('authority_level')}) cannot issue decide in single_owner mode"

        # ── Create message ──
        msg = Message(
            sender=sender,
            channel_id=channel_id,
            intent=intent,
            content=content,
            recipients=recipients,
            references=references,
            confidence=confidence,
            requires_response=requires_response,
            priority=priority,
            parent_message_id=parent_message_id,
            action_trigger=action_trigger,
            vote=vote,
            withdraw_reason=withdraw_reason,
            workflow_id=self.workspace_id,
        )

        # Add to channel
        channel.add_message(msg)

        # ── Handle requires_response ──
        if requires_response:
            timeout = DEFAULT_RESPONSE_TIMEOUT_S
            self.pending_responses.append({
                "message_id": msg.id,
                "sender": sender,
                "channel_id": channel_id,
                "priority": priority,
                "timestamp": msg.timestamp,
                "timeout_s": timeout,
                "responded": False,
            })

        # ── Handle action triggers ──
        if action_trigger and intent in STATE_AFFECTING_INTENTS:
            self._execute_action_trigger(msg, action_trigger)

        # ── Handle vote result check ──
        if intent == "decide" and channel.decision_mode == "vote":
            decided, result, details = channel.check_vote_result()
            if decided:
                channel.decision_closed = True
                channel.decision_id = f"dec_{uuid.uuid4().hex[:8]}"
                channel._save_meta()

        # ── Handle decision finalization (single_owner) ──
        if intent == "decide" and channel.decision_mode == "single_owner":
            channel.decision_closed = True
            channel.decision_id = f"dec_{uuid.uuid4().hex[:8]}"
            channel._save_meta()

        return True, msg

    def _find_message(self, channel, message_id):
        """Find a message in a channel by ID."""
        for msg in channel.messages:
            if msg.id == message_id:
                return msg
        return None

    def _execute_action_trigger(self, msg, trigger):
        """Execute an action triggered by a state-affecting message."""
        action = {
            "trigger_type": trigger.get("type"),
            "target": trigger.get("target"),
            "message_id": msg.id,
            "sender": msg.sender,
            "timestamp": msg.timestamp,
            "executed": True,
        }
        self.action_log.append(action)

        # If decision → log to decision log via registry
        if trigger.get("type") == "decision" and self.registry:
            self.registry.log_decision(
                owner=msg.sender,
                context=f"Channel: {msg.channel_id}",
                options=[],
                decision=msg.content,
                rationale=f"Decided via messaging (confidence: {msg.confidence})",
            )

    def get_pending_responses(self, priority_filter=None):
        """Get messages awaiting response."""
        pending = [p for p in self.pending_responses if not p["responded"]]
        if priority_filter:
            pending = [p for p in pending if p["priority"] == priority_filter]
        return pending

    def get_blocking_messages(self):
        """Get urgent messages that block workflow progress."""
        return [p for p in self.pending_responses
                if not p["responded"] and p["priority"] == "urgent"]

    def check_timeouts(self):
        """Check for timed-out response requests.
        
        Returns: list of timed-out messages (should escalate to executive_operator)
        """
        timed_out = []
        now = datetime.now(timezone.utc)
        for p in self.pending_responses:
            if p["responded"]:
                continue
            msg_time = datetime.fromisoformat(p["timestamp"])
            elapsed = (now - msg_time).total_seconds()
            if elapsed > p["timeout_s"]:
                timed_out.append(p)
        return timed_out

    def mark_responded(self, original_message_id, response_message_id):
        """Mark a pending response as fulfilled."""
        for p in self.pending_responses:
            if p["message_id"] == original_message_id:
                p["responded"] = True
                break
        # Link response to original
        for channel in self.channels.values():
            for msg in channel.messages:
                if msg.id == original_message_id:
                    msg.responses.append(response_message_id)
                    break

    def get_channel_summary(self, channel_id):
        """Get a summary of a channel's state."""
        channel = self.channels.get(channel_id)
        if not channel:
            return None
        active = [m for m in channel.messages if m.status == "active"]
        withdrawn = [m for m in channel.messages if m.status == "withdrawn"]
        intents = {}
        for m in active:
            intents[m.intent] = intents.get(m.intent, 0) + 1

        summary = {
            "channel_id": channel_id,
            "type": channel.channel_type,
            "total_messages": len(channel.messages),
            "active_messages": len(active),
            "withdrawn_messages": len(withdrawn),
            "turns": channel.turn_count,
            "max_turns": channel.max_turns,
            "turn_limit_reached": channel.is_turn_limit_reached(),
            "decision_closed": channel.decision_closed,
            "decision_id": channel.decision_id,
            "synthesis_requested": channel.synthesis_requested,
            "intents": intents,
        }
        if channel.decision_mode == "vote":
            summary["votes"] = channel.votes
            decided, result, details = channel.check_vote_result()
            summary["vote_result"] = result
            summary["vote_details"] = details
        return summary

    def list_channels(self):
        """List all channels with basic info."""
        result = []
        for cid, channel in self.channels.items():
            result.append({
                "channel_id": cid,
                "type": channel.channel_type,
                "messages": len(channel.messages),
                "turns": channel.turn_count,
                "closed": channel.decision_closed,
            })
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NemoClaw Agent Messaging System")
    parser.add_argument("--test", action="store_true", help="Run enforcement tests")
    parser.add_argument("--list-channels", action="store_true")
    parser.add_argument("--read-channel", metavar="CHANNEL_ID")
    args = parser.parse_args()

    if args.test:
        print("=" * 60)
        print("  MA-3 Messaging System Enforcement Tests")
        print("=" * 60)
        print()

        bus = MessageBus("test_ma3")

        # Create channels
        bus.create_channel("general", "topic", chat_mode=True)
        bus.create_channel("pricing-debate", "adversarial", max_turns=4,
                          participants=["strategy_lead", "growth_revenue_lead", "product_architect"])
        bus.create_channel("launch-decision", "decision", decision_mode="vote", approval_required=2)
        bus.create_channel("code-review", "review")

        # Test 1: Valid message
        ok, msg = bus.send("strategy_lead", "general", "inform",
                          "Market research shows 40% growth in AI agents sector")
        print(f"  {'✅' if ok else '❌'} Valid inform message: {msg.id if ok else msg}")

        # Test 2: Invalid intent
        ok, msg = bus.send("strategy_lead", "general", "yell", "Hello!")
        print(f"  {'✅' if not ok else '❌'} Invalid intent blocked: {msg[:60]}")

        # Test 3: Too short (non-chat)
        ok, msg = bus.send("strategy_lead", "general", "propose", "Short")
        print(f"  {'✅' if not ok else '❌'} Too-short message blocked: {msg[:60]}")

        # Test 4: Chat allowed short
        ok, msg = bus.send("strategy_lead", "general", "chat", "hmm interesting")
        print(f"  {'✅' if ok else '❌'} Chat allows short messages: {msg.id if ok else msg}")

        # Test 5: Chat blocked on non-chat channel
        ok, msg = bus.send("strategy_lead", "code-review", "chat", "yo")
        print(f"  {'✅' if not ok else '❌'} Chat blocked on non-chat channel: {msg[:60]}")

        # Test 6: Unauthorized participant
        ok, msg = bus.send("engineering_lead", "pricing-debate", "propose",
                          "I think we should price at 29 dollars per user per month")
        print(f"  {'✅' if not ok else '❌'} Unauthorized participant blocked: {msg[:60]}")

        # Test 7: Valid debate message
        ok, msg1 = bus.send("strategy_lead", "pricing-debate", "propose",
                           "SMB segment shows fastest adoption, I propose 19 per user",
                           references=[{"memory_key": "test_key"}])
        # Note: reference validation skipped (no memory system in test)
        print(f"  {'✅' if ok else '❌'} Valid debate proposal: {msg1.id if ok else msg1}")

        # Test 8: Challenge without reference in adversarial
        ok, msg = bus.send("growth_revenue_lead", "pricing-debate", "challenge",
                          "I disagree with the SMB pricing approach strongly")
        print(f"  {'✅' if not ok else '❌'} Challenge without reference blocked: {msg[:60]}")

        # Test 9: Challenge with reference
        ok, msg2 = bus.send("growth_revenue_lead", "pricing-debate", "challenge",
                           "Enterprise has higher LTV, SMB pricing is a race to the bottom",
                           references=[{"memory_key": "revenue_data"}],
                           parent_message_id=msg1.id if isinstance(msg1, Message) else None)
        print(f"  {'✅' if ok else '❌'} Challenge with reference: {msg2.id if ok else msg2}")

        # Test 10: Turn limit enforcement
        bus.send("strategy_lead", "pricing-debate", "propose",
                "Counter-argument: SMB volume compensates for lower price",
                references=[{"memory_key": "market_data"}])
        bus.send("product_architect", "pricing-debate", "propose",
                "Architecture supports both tiers, we can do hybrid pricing",
                references=[{"memory_key": "architecture"}])
        ok, msg = bus.send("strategy_lead", "pricing-debate", "propose",
                          "Final push: SMB first then enterprise expansion later",
                          references=[{"memory_key": "expansion"}])
        print(f"  {'✅' if not ok else '❌'} Turn limit enforced: {msg[:60] if isinstance(msg, str) else 'unexpected'}")

        # Test 11: Voting
        bus.send("strategy_lead", "launch-decision", "decide",
                "I vote to approve the SMB-first strategy", vote="approve")
        bus.send("growth_revenue_lead", "launch-decision", "decide",
                "I vote to reject SMB-first, prefer enterprise", vote="reject")
        ok, msg = bus.send("product_architect", "launch-decision", "decide",
                          "I vote to approve with hybrid pricing caveat", vote="approve")
        summary = bus.get_channel_summary("launch-decision")
        vote_result = summary.get("vote_result")
        print(f"  {'✅' if vote_result == 'approved' else '❌'} Voting: 2 approve + 1 reject = {vote_result}")

        # Test 12: Withdraw
        if isinstance(msg2, Message):
            ok, wmsg = bus.send("growth_revenue_lead", "pricing-debate", "withdraw",
                               "I withdraw my challenge based on new market data",
                               parent_message_id=msg2.id,
                               withdraw_reason="New data invalidates my assumption about enterprise LTV")
            print(f"  {'✅' if ok else '❌'} Withdraw with reason: {wmsg.id if ok else wmsg}")
            print(f"  {'✅' if msg2.status == 'withdrawn' else '❌'} Original marked withdrawn: {msg2.status}")
        else:
            print(f"  ⚠️  Skipped withdraw test (msg2 not created)")

        # Test 13: Cannot withdraw other's message
        if isinstance(msg1, Message):
            ok, wmsg = bus.send("growth_revenue_lead", "pricing-debate", "withdraw",
                               "Trying to withdraw strategy's message",
                               parent_message_id=msg1.id,
                               withdraw_reason="Testing unauthorized withdraw")
            print(f"  {'✅' if not ok else '❌'} Cannot withdraw other's message: {wmsg[:60]}")

        # Test 14: Blocking messages
        bus.send("strategy_lead", "general", "request",
                "Need competitive pricing data from growth team urgently",
                requires_response=True, priority="urgent",
                recipients=["growth_revenue_lead"])
        blocking = bus.get_blocking_messages()
        print(f"  {'✅' if len(blocking) > 0 else '❌'} Blocking messages tracked: {len(blocking)}")

        # Summary
        print()
        channels = bus.list_channels()
        print(f"  Channels: {len(channels)}")
        for ch in channels:
            print(f"    {ch['channel_id']}: {ch['type']}, {ch['messages']} msgs, closed={ch['closed']}")

        print()
        print(f"  Action log: {len(bus.action_log)} entries")
        print(f"  Pending responses: {len(bus.get_pending_responses())}")

    elif args.list_channels:
        # Load channels from disk
        if CHANNELS_DIR.exists():
            for ch_dir in sorted(CHANNELS_DIR.iterdir()):
                if ch_dir.is_dir():
                    meta_path = ch_dir / "meta.json"
                    if meta_path.exists():
                        with open(meta_path) as f:
                            meta = json.load(f)
                        print(f"  {meta['channel_id']}: {meta['channel_type']}, "
                              f"{meta['message_count']} msgs, closed={meta['decision_closed']}")

    elif args.read_channel:
        ch_dir = CHANNELS_DIR / args.read_channel
        msg_path = ch_dir / "messages.jsonl"
        if msg_path.exists():
            with open(msg_path) as f:
                for line in f:
                    msg = json.loads(line.strip())
                    status = " [WITHDRAWN]" if msg.get("status") == "withdrawn" else ""
                    print(f"  [{msg['intent']}] {msg['sender']}: {msg['content'][:80]}{status}")
        else:
            print(f"  Channel {args.read_channel} not found")
