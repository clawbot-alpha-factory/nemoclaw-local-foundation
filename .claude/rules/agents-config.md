---
paths:
  - "config/agents/**"
  - "scripts/agent_*.py"
---

## Agent System
- 11 agents, 4-tier authority: L1 (Tariq) > L2 (Nadia, Khalid) > L3 (Layla, Omar, Yasmin, Faisal) > L4 (Hassan, Rania, Amira, Zara)
- Definitions: config/agents/agent-schema.yaml
- Skill mapping: config/agents/capability-registry.yaml
- Each agent has: owns/forbidden domains, Jordanian identity, cartoon persona
- Gamification: scripts/agent_performance.py (badges, leaderboard, rivalries)
- Self-promotion system with autonomous self-improvement capability
- Browser profiles via PinchTab at localhost:9867
