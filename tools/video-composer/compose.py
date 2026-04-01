#!/usr/bin/env python3
"""NemoClaw Video Composer — ffmpeg-based video assembly pipeline.

Usage:
    python3 tools/video-composer/compose.py \
        --audio voice.wav --images img1.png img2.png \
        --captions captions.ass --agent hassan \
        --platform tiktok --output output.mp4
"""
import argparse, json, logging, os, struct, subprocess, tempfile, wave
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("video-composer")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

PLATFORM_PRESETS = {
    "tiktok":          {"width": 1080, "height": 1920, "max_duration": 60,  "crf": 23},
    "instagram_reel":  {"width": 1080, "height": 1920, "max_duration": 90,  "crf": 23},
    "instagram_feed":  {"width": 1080, "height": 1080, "max_duration": 60,  "crf": 23},
    "youtube_short":   {"width": 1080, "height": 1920, "max_duration": 60,  "crf": 20},
    "youtube":         {"width": 1920, "height": 1080, "max_duration": 600, "crf": 20},
    "linkedin":        {"width": 1080, "height": 1080, "max_duration": 300, "crf": 23},
    "twitter":         {"width": 1280, "height": 720,  "max_duration": 140, "crf": 23},
}


class VideoComposer:
    """FFmpeg-based video composition engine."""

    def __init__(self):
        self.presets = dict(PLATFORM_PRESETS)
        self._load_yaml_presets()

    def _load_yaml_presets(self):
        """Override defaults with config/content-factory/platform-presets.yaml if it exists."""
        yaml_path = REPO_ROOT / "config" / "content-factory" / "platform-presets.yaml"
        if not yaml_path.exists():
            return
        try:
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            for platform, settings in data.items():
                if isinstance(settings, dict):
                    self.presets.setdefault(platform, {})
                    self.presets[platform].update(settings)
            log.info("Loaded platform presets from %s", yaml_path)
        except Exception as exc:
            log.warning("Could not load YAML presets: %s", exc)

    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """Return audio duration in seconds via ffprobe."""
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(json.loads(result.stdout)["format"]["duration"])

    @staticmethod
    def _run(cmd: list[str], desc: str = "ffmpeg"):
        log.info("Running: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.error("%s stderr:\n%s", desc, proc.stderr)
            raise RuntimeError(f"{desc} failed (rc={proc.returncode})")

    def _resolve_preset(self, platform: str) -> dict:
        preset = self.presets.get(platform)
        if not preset:
            raise ValueError(f"Unknown platform '{platform}'. Available: {list(self.presets)}")
        return preset

    @staticmethod
    def _avatar_path(agent_id: str) -> Path | None:
        p = REPO_ROOT / "assets" / "avatars" / f"{agent_id}.png"
        return p if p.exists() else None

    def _build_ffmpeg_cmd(
        self,
        concat_file: str,
        audio_path: str,
        output_path: str,
        preset: dict,
        captions_path: str | None = None,
        agent_id: str | None = None,
        fps: int = 30,
    ) -> list[str]:
        w, h, crf = preset["width"], preset["height"], preset.get("crf", 23)
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-i", audio_path]

        avatar = self._avatar_path(agent_id) if agent_id else None
        if avatar:
            cmd += ["-i", str(avatar)]

        scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        filters = [scale]
        if captions_path:
            escaped = captions_path.replace("\\", "/").replace(":", "\\:")
            tag = "ass" if captions_path.endswith(".ass") else "subtitles"
            filters.append(f"{tag}='{escaped}'")
        vf_chain = ",".join(filters)

        if avatar:
            cf = f"[0:v]{vf_chain}[base];[2:v]scale=80:80[av];[base][av]overlay=W-w-20:H-h-20[out]"
            cmd += ["-filter_complex", cf, "-map", "[out]", "-map", "1:a"]
        else:
            cmd += ["-vf", vf_chain]

        cmd += ["-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "medium",
                "-crf", str(crf), "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", "-shortest", output_path]
        return cmd

    def _write_concat(self, image_paths: list[str], per_image: float) -> str:
        """Write ffmpeg concat demuxer file. Returns temp file path."""
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        for img in image_paths:
            f.write(f"file '{os.path.abspath(img)}'\nduration {per_image:.4f}\n")
        f.write(f"file '{os.path.abspath(image_paths[-1])}'\n")  # avoid cut-off
        f.close()
        return f.name

    def compose(self, audio_path: str, image_paths: list[str], output_path: str,
                agent_id: str | None = None, platform: str = "tiktok",
                captions_path: str | None = None) -> dict:
        """Compose images + audio into a finished video."""
        preset = self._resolve_preset(platform)
        duration = self.get_audio_duration(audio_path)
        per_image = duration / len(image_paths)
        log.info("Composing %d images (%.1fs each) + %.1fs audio → %s [%s]",
                 len(image_paths), per_image, duration, output_path, platform)
        concat_file = self._write_concat(image_paths, per_image)
        try:
            self._run(self._build_ffmpeg_cmd(
                concat_file, audio_path, output_path, preset, captions_path, agent_id), "compose")
        finally:
            os.unlink(concat_file)
        return self._result(output_path, platform, preset)

    def compose_timelapse(self, screenshot_paths: list[str], audio_path: str, output_path: str,
                          fps: int = 10, agent_id: str | None = None, platform: str = "tiktok",
                          captions_path: str | None = None) -> dict:
        """Timelapse-style video for screen recordings (Method 4)."""
        preset = self._resolve_preset(platform)
        duration = self.get_audio_duration(audio_path)
        per_image = duration / len(screenshot_paths)
        log.info("Timelapse: %d screenshots @ %dfps + %.1fs audio → %s",
                 len(screenshot_paths), fps, duration, output_path)
        concat_file = self._write_concat(screenshot_paths, per_image)
        try:
            self._run(self._build_ffmpeg_cmd(
                concat_file, audio_path, output_path, preset, captions_path, agent_id, fps=fps),
                "timelapse")
        finally:
            os.unlink(concat_file)
        return self._result(output_path, platform, preset)

    @staticmethod
    def _result(output_path: str, platform: str, preset: dict) -> dict:
        size_bytes = os.path.getsize(output_path)
        try:
            dur = VideoComposer.get_audio_duration(output_path)
        except Exception:
            dur = 0.0
        return {"output_path": os.path.abspath(output_path), "duration": round(dur, 2),
                "file_size_mb": round(size_bytes / (1024 * 1024), 2), "platform": platform,
                "resolution": f"{preset['width']}x{preset['height']}"}

    @staticmethod
    def generate_test_assets(tmpdir: str) -> tuple[str, list[str]]:
        """Create a 5-second silent WAV and a solid-color PNG for testing."""
        wav_path = os.path.join(tmpdir, "silence.wav")
        n_frames = 44100 * 5
        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(struct.pack(f"<{n_frames}h", *([0] * n_frames)))
        img_path = os.path.join(tmpdir, "test_frame.png")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1080x1920:d=1",
                        "-frames:v", "1", img_path], capture_output=True, check=True)
        return wav_path, [img_path]


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Video Composer")
    parser.add_argument("--audio", help="Path to audio file")
    parser.add_argument("--images", nargs="+", help="Paths to image files")
    parser.add_argument("--captions", help="Path to .ass or .srt captions")
    parser.add_argument("--agent", help="Agent ID for avatar watermark")
    parser.add_argument("--platform", default="tiktok", help="Target platform")
    parser.add_argument("--output", default="output.mp4", help="Output video path")
    parser.add_argument("--timelapse", action="store_true", help="Timelapse mode (screen recordings)")
    parser.add_argument("--fps", type=int, default=10, help="FPS for timelapse mode")
    parser.add_argument("--test", action="store_true", help="Generate 5s test video from synthetic assets")
    args = parser.parse_args()

    composer = VideoComposer()

    if args.test:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav, imgs = VideoComposer.generate_test_assets(tmpdir)
            out = args.output or os.path.join(tmpdir, "test_output.mp4")
            result = composer.compose(wav, imgs, out, platform=args.platform)
            print(json.dumps(result, indent=2))
        return

    if not args.audio or not args.images:
        parser.error("--audio and --images are required (unless using --test)")

    fn = composer.compose_timelapse if args.timelapse else composer.compose
    kw = dict(agent_id=args.agent, platform=args.platform, captions_path=args.captions)
    if args.timelapse:
        result = fn(args.images, args.audio, args.output, fps=args.fps, **kw)
    else:
        result = fn(args.audio, args.images, args.output, **kw)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
