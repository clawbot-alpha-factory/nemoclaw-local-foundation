# NemoClaw Voice Engine

Self-hosted voice generation for all 11 NemoClaw agents using fish-speech (open source, $0/mo ongoing).

## Quick Start (5 minutes, ~$0.20)

### Prerequisites
```bash
pip install vastai
vastai set api-key YOUR_VAST_AI_API_KEY
```

Get your API key at https://cloud.vast.ai/

### Deploy & Generate All Voices
```bash
bash tools/voice-deploy/deploy.sh
```

This script:
1. Finds the cheapest 24GB GPU on Vast.ai (~$0.20/hr)
2. Launches fish-speech S2 Pro in Docker
3. Uploads all 11 reference audio files
4. Generates voice samples for each agent
5. Downloads results to `assets/voices/generated/`
6. Destroys the GPU instance (stops billing)

**Total cost: ~$0.20 for all 11 voices.**

### Generate Individual Voiceovers (after initial setup)
```bash
# Single agent
python3 tools/voice-deploy/generate_voice.py \
    --agent hassan \
    --text "I'm ready! Pipeline update: 48K total!" \
    --api-url http://VAST_IP:8763

# Weekly promo batch (all 11 agents)
python3 tools/voice-deploy/generate_voice.py \
    --batch weekly_promo \
    --api-url http://VAST_IP:8763
```

## Voice References

Each agent has a 30-second character voice reference in `assets/voices/references/<agent>/`:

| Agent | Character | Reference Style |
|-------|-----------|----------------|
| tariq | Homer Simpson energy | Warm, authoritative, slightly bemused |
| nadia | Velma Dinkley energy | Sharp, analytical, eureka moments |
| khalid | Dexter Morgan energy | Calm, precise, controlled intensity |
| layla | Sandy Cheeks energy | Energetic, can-do, inventive |
| omar | Stewie Griffin energy | Scheming, ambitious, calculated |
| yasmin | Brian Griffin energy | Literary, thoughtful, pretentious |
| faisal | Dexter Lab energy | Focused genius, irritable, protective |
| hassan | SpongeBob energy | Maximum enthusiasm, relentless optimism |
| rania | Daria energy | Deadpan, sarcastic, brutally analytical |
| amira | Dee Dee energy | Bubbly, enthusiastic, caring |
| zara | Rachel Green energy | Dramatic, trendy, storytelling |

## Architecture

```
tools/voice-deploy/
  deploy.sh              # One-click Vast.ai GPU deployment
  generate_voice.py      # Voice generation API client
  README.md              # This file

tools/fish-speech/       # Fish-speech 2.0.0 installation (gitignored)
  checkpoints/s2-pro/    # S2 Pro model weights (11GB)

config/voice/
  fish-speech-config.yaml # Engine configuration

assets/voices/
  references/            # 11 agent voice reference clips (30s each)
  generated/             # Generated voiceovers (output)
```

## Cost Comparison

| Option | Monthly Cost | Quality | Setup |
|--------|-------------|---------|-------|
| Fish-speech self-hosted (Vast.ai) | $0.20 per session | Best | This setup |
| Fish Audio cloud API | $9.99/mo | Excellent | Zero setup |
| ElevenLabs | $22-99/mo | Best | Zero setup |
| OpenAI TTS | ~$0.50/mo | Good | Already have key |
