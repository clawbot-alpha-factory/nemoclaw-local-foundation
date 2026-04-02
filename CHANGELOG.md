# Changelog

All notable changes to NemoClaw Local Foundation.

Format: [Keep a Changelog](https://keepachangelog.com/)

## [1.0.0] - 2026-04-02

### Added
- 127 skills across 12 domains (100% README coverage)
- 11 autonomous agents with 4-tier authority hierarchy
- 129 capability-registry entries, 0 phantom skills
- Content Factory: 16 cnt-* skills + video composer + HeyGen integration
- Voice engine: fish-speech + 11 agent voices + Vast.ai deployment
- Agent avatars: 11 GPT Image 1 generated PNGs with Jordanian nashmi style
- lib/routing.py: shared LLM routing module (L-003 compliant)
- GamificationEngine: Employee of Month, achievements, rivalry tracking
- SkillRequestService: agent-initiated skill build workflow
- Dashboard spec: 13 views, 72 components (docs/dashboard-spec.md)
- PinchTab browser automation with auth token support
- Makefile, pyproject.toml, CI workflow, Docker support
- Prometheus /metrics endpoint

### Fixed
- L-003: 129 files migrated from hardcoded models to routing config
- Quality thresholds: all 127 skills at 9/10 minimum
- Critic scoring: LLM score replaces heuristic (not averaged)
- 30 legacy skills migrated from direct API keys to lib/routing
- PinchTab auth: auto-reads token from ~/.pinchtab/config.json
- f-string JSON brace escaping in 115 skill run.py files
- SQLite thread safety in 15 k40+ skills
- k40+ arg parsing (nargs=2 + action=append iteration)

### Revenue Coverage
- 12/12 categories fully covered (was 9/12)
- New: k55-k61 (SEO, NDA, contracts, subscriptions, refunds, reports)
