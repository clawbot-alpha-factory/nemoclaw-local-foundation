---
name: thread-integrations
description: Session bootstrap for external integrations — bridges, APIs, webhooks, n8n, HubSpot, Meta Ads, etc. Invoke when working on bridge scripts or external service connections.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: External Integrations & Bridges

You are now in **integrations mode**. Work scoped to `scripts/*_bridge.py` and `command-center/backend/app/services/bridges/`.

## Bridge Inventory
```
scripts/
├── n8n_bridge.py           ← n8n workflow automation
├── apollo_bridge.py        ← Apollo.io lead data
├── hubspot_bridge.py       ← HubSpot CRM
├── supabase_bridge.py      ← Supabase database
├── instantly_bridge.py     ← Instantly.ai email outreach
├── lemonsqueezy_bridge.py  ← LemonSqueezy payments/billing
├── meta_ads_bridge.py      ← Meta (Facebook/Instagram) Ads
├── google_ads_bridge.py    ← Google Ads
├── resend_bridge.py        ← Resend transactional email
├── social_publish_bridge.py ← Multi-platform social publishing
├── image_gen_bridge.py     ← Image generation (DALL-E / Midjourney)
└── whisper_bridge.py       ← OpenAI Whisper transcription

command-center/backend/app/services/bridges/
└── (Backend service wrappers for the above)
```

## API Keys Location
All API keys in `config/.env` — never commit keys to git.
```
config/.env:
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
ASANA_TOKEN=...
HUBSPOT_API_KEY=...
META_ACCESS_TOKEN=...
GOOGLE_ADS_CUSTOMER_ID=...
INSTANTLY_API_KEY=...
LEMONSQUEEZY_API_KEY=...
RESEND_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

## Bridge Pattern
All bridges follow the same pattern:
```python
class XBridge:
    def __init__(self):
        self.api_key = os.getenv("X_API_KEY")
        self.base_url = "https://api.x.com/v1"

    def call(self, endpoint: str, data: dict) -> dict:
        # REST call with error handling
        ...
```

## PinchTab Browser Automation
For platforms without APIs:
- Server: `localhost:9867`
- Config: `config/pinchtab-config.yaml`
- Bridge: `scripts/web_browser.py`
- Per-agent profiles, max 4 instances
- Blocked: banking, government, payment processors

## Skills That Use Integrations
- `k40-k61` series: Commercial skills (ads, CRM, outreach)
- `out-01` to `out-08`: Outreach skills (email sequences, social)
- `rev-01` to `rev-25`: Revenue skills (sales, attribution)
- `int-01` to `int-06`: Intelligence skills (data scraping, scoring)

## Out of Scope in This Thread
- Skill YAML content → use /thread-skills
- Agent logic → use /thread-agents
- Content/video → use /thread-content-factory

## Common Tasks
- Fix broken bridge authentication
- Add new external service integration
- Debug webhook delivery failures
- Add new n8n workflow trigger
- Fix HubSpot sync errors
- Connect new social platform
- Debug Meta Ads API rate limiting
- Add Supabase table sync
