---
name: thread-content-factory
description: Session bootstrap for content factory, video production, voice synthesis, and HeyGen avatar pipeline. Invoke when working on cnt-* skills, CapCut, Fish Speech, or Zara's video system.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# Thread: Content Factory & Video Pipeline

You are now in **content-factory mode**. Work scoped to `cnt-*` skills, `tools/`, `config/content-factory/`, and `scripts/content_*.py`.

## Pipeline Architecture
```
Content Request
    ↓
cnt-15-daily-content-factory   ← Orchestrates daily pipeline
    ↓
cnt-01 to cnt-10               ← Text content (hooks, scripts, captions)
    ↓
cnt-11 to cnt-14               ← Visual content (thumbnails, video)
    ↓
cnt-16-screen-capture-video    ← Screen recording wrapper
    ↓
Zara (social_media_lead)       ← Distributes content across platforms
```

## Tools Stack
```
tools/
├── capcut-api/          ← CapCut video editing API wrapper
│   └── Full REST client for programmatic video editing
├── fish-speech/         ← Fish Speech TTS (voice synthesis)
│   └── Generates agent voice audio from text
├── video-composer/      ← Multi-track video orchestration
└── voice-deploy/        ← Voice model deployment & management
```

## Config Files
```
config/content-factory/
├── pipeline-config.yaml       ← Production workflow definition
├── heygen-config.yaml         ← HeyGen avatar setup
├── heygen-avatar-ids.json     ← Avatar library (11 agent avatars)
├── accounts-config.yaml       ← Platform credentials (TikTok, IG, YT, etc.)
└── platform-presets.yaml      ← Output format templates per platform

config/voice/
└── fish-speech-config.yaml    ← Voice model config, quality settings

assets/voices/
├── generated/                 ← 11 cloned agent voices (WAV)
│   └── tariq_voice.wav, nadia_voice.wav ... zara_voice.wav
└── references/                ← Reference audio for voice cloning
```

## Key Skills
| Skill | Purpose |
|-------|---------|
| cnt-01-viral-hook-generator | Viral hooks for social posts |
| cnt-12-video-composer | Multi-track video orchestration |
| cnt-13-thumbnail-generator | Video thumbnail creation |
| cnt-14-caption-generator | Auto-captions for video |
| cnt-15-daily-content-factory | Master daily pipeline orchestrator |
| cnt-16-screen-capture-video | Screen recording + video packaging |

## Zara's Video System
- Script: `scripts/zara_video_production.py`
- Workflow: `workflows/content-factory-daily.yaml`
- Avatar: HeyGen (config/content-factory/heygen-config.yaml)
- Voice: Fish Speech + cloned zara_voice.wav
- Distribution: Multi-platform via accounts-config.yaml

## Architecture Locks (L-400 series — Browser Automation)
- L-400: PinchTab 0.8.6 at localhost:9867 for browser actions
- L-404: POST /action with `kind` field
- L-405: GET /text for content extraction
- L-413: Guard DOWN for development (all domains enabled)

## Test Commands
```bash
python3 scripts/test-content-factory.py
python3 scripts/content_factory_runner.py
python3 skills/skill-runner.py --skill cnt-15-daily-content-factory --input topic "AI agents"
```

## Out of Scope in This Thread
- Agent governance logic → use /thread-agents
- Backend API → use /thread-backend
- Revenue skills → use /thread-skills

## Common Tasks
- Fix video composition pipeline
- Add new platform preset
- Update HeyGen avatar configuration
- Fix Fish Speech voice quality
- Add new content type to daily factory
- Debug Zara's video production workflow
- Improve content hook quality
- Fix caption synchronization
