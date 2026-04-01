#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# NemoClaw Voice Engine — Vast.ai One-Click Deployment
# Rents a GPU, clones all 11 agent voices, generates samples, downloads results
#
# Prerequisites:
#   pip install vastai
#   vastai set api-key YOUR_API_KEY
#
# Usage:
#   bash tools/voice-deploy/deploy.sh
#
# Cost: ~$0.20-0.50 (1 hour on RTX 4090)
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REFS_DIR="$REPO_ROOT/assets/voices/references"
OUTPUT_DIR="$REPO_ROOT/assets/voices/generated"
mkdir -p "$OUTPUT_DIR"

echo "═══════════════════════════════════════════════════════"
echo "  NemoClaw Voice Engine — Vast.ai Deployment"
echo "═══════════════════════════════════════════════════════"
echo ""

# Step 1: Check vastai CLI
if ! command -v vastai &>/dev/null; then
    echo "Installing vastai CLI..."
    pip install vastai
fi

# Step 2: Find cheapest RTX 4090 or A10 with 24GB+ VRAM
echo "Finding cheapest GPU with 24GB+ VRAM..."
OFFER=$(vastai search offers \
    --type on-demand \
    --gpu-ram ">=24" \
    --disk ">=50" \
    --inet-up ">=100" \
    --order "dph+" \
    --limit 1 \
    --raw 2>/dev/null | tail -1)

if [ -z "$OFFER" ]; then
    echo "ERROR: No GPU offers found. Check vastai API key."
    echo "  Run: vastai set api-key YOUR_KEY"
    exit 1
fi

OFFER_ID=$(echo "$OFFER" | awk '{print $1}')
GPU_NAME=$(echo "$OFFER" | awk '{print $5}')
PRICE=$(echo "$OFFER" | awk '{print $2}')
echo "  Best offer: $GPU_NAME at \$$PRICE/hr (ID: $OFFER_ID)"

# Step 3: Create the instance
echo ""
echo "Creating instance..."
INSTANCE_ID=$(vastai create instance "$OFFER_ID" \
    --image "fishaudio/fish-speech:latest" \
    --disk 50 \
    --env "FISH_API_SERVER_ARGS=--device cuda --listen 0.0.0.0:8763" \
    --raw 2>/dev/null | grep -o '[0-9]*')

if [ -z "$INSTANCE_ID" ]; then
    echo "ERROR: Failed to create instance"
    exit 1
fi
echo "  Instance ID: $INSTANCE_ID"

# Step 4: Wait for instance to be ready
echo "Waiting for instance to start (may take 1-3 minutes)..."
for i in $(seq 1 60); do
    STATUS=$(vastai show instance "$INSTANCE_ID" --raw 2>/dev/null | grep -o 'running' || true)
    if [ "$STATUS" = "running" ]; then
        echo "  Instance is running!"
        break
    fi
    sleep 5
    echo -n "."
done

# Get the public IP and port
INSTANCE_INFO=$(vastai show instance "$INSTANCE_ID" --raw 2>/dev/null)
PUBLIC_IP=$(echo "$INSTANCE_INFO" | grep -o 'ssh_host=[^ ]*' | cut -d= -f2)
PUBLIC_PORT=$(echo "$INSTANCE_INFO" | grep -o 'ssh_port=[^ ]*' | cut -d= -f2)

echo "  IP: $PUBLIC_IP, SSH Port: $PUBLIC_PORT"

# Step 5: Upload reference audio files
echo ""
echo "Uploading voice references..."
for agent in tariq nadia khalid layla omar yasmin faisal hassan rania amira zara; do
    ref_file=$(ls "$REFS_DIR/$agent/"*reference*.wav 2>/dev/null | head -1)
    if [ -n "$ref_file" ]; then
        vastai copy "$ref_file" "$INSTANCE_ID:/app/references/${agent}_reference.wav" 2>/dev/null
        echo "  Uploaded: $agent"
    fi
done

# Step 6: Wait for fish-speech server to be ready inside the container
echo ""
echo "Waiting for fish-speech API server..."
API_URL="http://$PUBLIC_IP:8763"
for i in $(seq 1 60); do
    if curl -s "$API_URL/openapi.json" >/dev/null 2>&1; then
        echo "  Fish-speech API is ready!"
        break
    fi
    sleep 5
    echo -n "."
done

# Step 7: Generate voice samples for each agent
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Generating Agent Voices"
echo "═══════════════════════════════════════════════════════"

AGENTS=(
    "tariq|Hello, I am Tariq, CEO of NemoClaw. My eleven agents are building a million dollar business. D'oh... I mean, strategically."
    "nadia|Jinkies! The market data is fascinating. I've identified three viable segments with strong unit economics. Recommending GO on segment B."
    "khalid|Tonight's the night. I optimized three workflows, eliminated two bottlenecks, and the system is running at 99.7 percent efficiency. Perfect."
    "layla|Y'all, I just redesigned the entire API surface in one sitting. Twelve endpoints, zero breaking changes. Who needs sleep when you have blueprints?"
    "omar|Excellent. My revenue plan is coming together perfectly. We hit fifteen thousand monthly recurring revenue. Soon the entire market will kneel before our pricing model."
    "yasmin|I've been crafting this brand narrative all morning. It's a masterpiece of storytelling. Every word earns its place. You wouldn't understand. It's very literary."
    "faisal|Do not touch my deployment pipeline. I calibrated it to perfection. Build time went from three minutes to forty-seven seconds. Now leave my laboratory."
    "hassan|I'm ready! I'm ready! Forty-seven leads enriched before lunch! Eight meetings booked! The pipeline is beautiful! Who wants to see my conversion numbers?"
    "rania|That campaign had a zero point two percent click-through rate. I killed it. You're welcome. The one that survived? Four point two X return on ad spend. I don't do sentiment."
    "amira|Oooh! Guess what? Acme Corp just renewed AND upgraded! Client health score is ninety-two percent across the board. Zero churn this month. I sent them a thank you!"
    "zara|Oh my God. Hassan just closed a deal and I got the perfect behind the scenes content. This is going viral. This week on NemoClaw, everything changed."
)

for entry in "${AGENTS[@]}"; do
    agent="${entry%%|*}"
    text="${entry##*|}"
    ref_file="/app/references/${agent}_reference.wav"

    echo -n "  Generating $agent... "

    # Call fish-speech API with reference voice
    response=$(curl -s -X POST "$API_URL/v1/tts" \
        -H "Content-Type: application/json" \
        -d "{
            \"text\": \"$text\",
            \"reference_audio\": \"$ref_file\",
            \"format\": \"wav\"
        }" \
        -o "$OUTPUT_DIR/${agent}_sample.wav" \
        -w "%{http_code}")

    if [ "$response" = "200" ] && [ -s "$OUTPUT_DIR/${agent}_sample.wav" ]; then
        size=$(stat -f%z "$OUTPUT_DIR/${agent}_sample.wav" 2>/dev/null || echo "?")
        echo "OK ($size bytes)"
    else
        echo "FAIL (HTTP $response)"
    fi
done

# Step 8: Summary
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Voice Generation Complete"
echo "═══════════════════════════════════════════════════════"
generated=$(ls "$OUTPUT_DIR/"*.wav 2>/dev/null | wc -l | tr -d ' ')
echo "  Generated: $generated/11 voice samples"
echo "  Output: $OUTPUT_DIR/"
echo ""

# Step 9: Destroy instance to stop billing
echo "Destroying GPU instance to stop billing..."
vastai destroy instance "$INSTANCE_ID" 2>/dev/null
echo "  Instance destroyed. Billing stopped."
echo ""
echo "Done! Total estimated cost: ~\$0.20"
