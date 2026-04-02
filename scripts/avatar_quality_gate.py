#!/usr/bin/env python3
"""
Phase 2: Quality gate for generated avatar poses.
CLIP similarity scoring + structural checks. Runs locally on CPU.

    python3 scripts/avatar_quality_gate.py --ref assets/avatars/tariq.png --img assets/avatars/poses/tariq/01_standing_neutral.png
"""

import json, os, sys
from pathlib import Path
from typing import Optional

REPO = Path(os.path.expanduser("~/nemoclaw-local-foundation"))

# Thresholds
CLIP_PASS_THRESHOLD = 0.65
COMPOSITE_PASS_THRESHOLD = 0.70
MIN_FILE_SIZE = 30_000       # 30KB
MAX_FILE_SIZE = 3_000_000    # 3MB
EXPECTED_SIZE = (1024, 1024)

# Lazy-loaded CLIP model
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None


def _load_clip():
    """Lazy-load CLIP model (CPU). Returns (model, preprocess, tokenizer) or None."""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_tokenizer
    try:
        import open_clip
        import torch
        model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
        model.eval()
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        _clip_model = model
        _clip_preprocess = preprocess
        _clip_tokenizer = tokenizer
        return model, preprocess, tokenizer
    except ImportError:
        return None, None, None
    except Exception:
        return None, None, None


def clip_similarity(ref_path: str, gen_path: str) -> Optional[float]:
    """Compute CLIP cosine similarity between two images. Returns 0.0-1.0 or None on failure."""
    model, preprocess, _ = _load_clip()
    if model is None:
        return None

    try:
        import torch
        from PIL import Image

        ref_img = preprocess(Image.open(ref_path).convert("RGB")).unsqueeze(0)
        gen_img = preprocess(Image.open(gen_path).convert("RGB")).unsqueeze(0)

        with torch.no_grad():
            ref_feat = model.encode_image(ref_img)
            gen_feat = model.encode_image(gen_img)
            ref_feat = ref_feat / ref_feat.norm(dim=-1, keepdim=True)
            gen_feat = gen_feat / gen_feat.norm(dim=-1, keepdim=True)
            similarity = (ref_feat @ gen_feat.T).item()

        return max(0.0, min(1.0, similarity))
    except Exception:
        return None


def structural_checks(image_path: str, expected_bg_hex: str = None) -> dict:
    """Run structural validation on a generated image. Returns dict with pass/fail details."""
    result = {"passed": True, "checks": {}}
    path = Path(image_path)

    # File exists
    result["checks"]["exists"] = path.exists()
    if not path.exists():
        result["passed"] = False
        return result

    # File format
    result["checks"]["is_png"] = path.suffix.lower() == ".png"

    # File size
    size = path.stat().st_size
    result["checks"]["file_size_ok"] = MIN_FILE_SIZE <= size <= MAX_FILE_SIZE
    result["checks"]["file_size_bytes"] = size

    # Dimensions
    try:
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        result["checks"]["dimensions"] = f"{w}x{h}"
        result["checks"]["dimensions_ok"] = (w, h) == EXPECTED_SIZE

        # Not blank (check pixel variance)
        import numpy as np
        arr = np.array(img)
        variance = float(arr.std())
        result["checks"]["pixel_variance"] = round(variance, 2)
        result["checks"]["not_blank"] = variance > 10.0

        # Background color check (sample corners)
        if expected_bg_hex:
            corners = [arr[5, 5], arr[5, -5], arr[-5, 5], arr[-5, -5]]
            avg_corner = [int(c) for c in sum(corners) / 4]
            expected_rgb = tuple(int(expected_bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            color_dist = sum(abs(a - b) for a, b in zip(avg_corner[:3], expected_rgb)) / 3
            result["checks"]["bg_color_distance"] = round(color_dist, 1)
            result["checks"]["bg_color_ok"] = color_dist < 60  # generous tolerance

    except ImportError:
        result["checks"]["pillow_available"] = False
    except Exception as e:
        result["checks"]["image_read_error"] = str(e)[:100]

    # Aggregate
    critical = ["exists", "is_png", "file_size_ok", "dimensions_ok", "not_blank"]
    for check in critical:
        if check in result["checks"] and not result["checks"][check]:
            result["passed"] = False
            break

    return result


def score_image(ref_path: str, gen_path: str, expected_bg_hex: str = None) -> dict:
    """Full quality assessment. Returns composite score and pass/fail."""
    struct = structural_checks(gen_path, expected_bg_hex)
    clip_score = clip_similarity(ref_path, gen_path)

    struct_pass_rate = sum(1 for k, v in struct["checks"].items()
                          if isinstance(v, bool) and v) / max(1, sum(1 for k, v in struct["checks"].items()
                                                                      if isinstance(v, bool)))

    if clip_score is not None:
        composite = 0.7 * clip_score + 0.3 * struct_pass_rate
    else:
        composite = struct_pass_rate  # CLIP unavailable, use structural only

    passed = composite >= COMPOSITE_PASS_THRESHOLD
    if clip_score is not None and clip_score < CLIP_PASS_THRESHOLD:
        passed = False  # CLIP hard floor

    return {
        "clip_similarity": round(clip_score, 4) if clip_score is not None else None,
        "structural": struct,
        "struct_pass_rate": round(struct_pass_rate, 4),
        "composite_score": round(composite, 4),
        "passed": passed,
        "clip_available": clip_score is not None
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Quality gate for avatar poses")
    p.add_argument("--ref", required=True, help="Reference avatar image path")
    p.add_argument("--img", required=True, help="Generated pose image path")
    p.add_argument("--bg-hex", help="Expected background color hex")
    args = p.parse_args()

    result = score_image(args.ref, args.img, args.bg_hex)
    print(json.dumps(result, indent=2))
    status = "✅ PASS" if result["passed"] else "❌ FAIL"
    print(f"\n  {status} — composite: {result['composite_score']}, CLIP: {result['clip_similarity']}")
