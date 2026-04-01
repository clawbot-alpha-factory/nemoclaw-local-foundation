#!/usr/bin/env python3
"""NemoClaw Caption Styler — Convert SRT to styled ASS captions with TikTok-style animations.

Usage: python3 tools/video-composer/caption_styler.py --input captions.srt --output captions.ass
"""
import argparse, re
from pathlib import Path

# fontname, fontsize, bold, primary, outline_col, shadow_col, outline, shadow, alignment, margin_v
STYLES = {
    "tiktok":  {"fontname": "Arial", "fontsize": 48, "bold": -1, "primary_color": "&H00FFFFFF",
                "outline_color": "&H00000000", "shadow_color": "&H80000000",
                "outline": 3, "shadow": 2, "alignment": 2, "margin_v": 100},
    "youtube": {"fontname": "Arial", "fontsize": 42, "bold": -1, "primary_color": "&H00FFFFFF",
                "outline_color": "&H00000000", "shadow_color": "&H80000000",
                "outline": 2, "shadow": 1, "alignment": 8, "margin_v": 30},
    "minimal": {"fontname": "Helvetica", "fontsize": 36, "bold": 0, "primary_color": "&H00FFFFFF",
                "outline_color": "&H00000000", "shadow_color": "&H00000000",
                "outline": 2, "shadow": 0, "alignment": 2, "margin_v": 80},
}


class CaptionStyler:
    """Convert SRT captions to styled ASS format."""

    @staticmethod
    def _parse_srt(srt_path: str) -> list[dict]:
        """Parse SRT file into list of {index, start, end, text} dicts."""
        text = Path(srt_path).read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", text.strip())
        entries = []
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            ts_match = re.match(
                r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
                r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
                lines[1],
            )
            if not ts_match:
                continue
            g = [int(x) for x in ts_match.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            content = "\n".join(lines[2:]).strip()
            content = re.sub(r"<[^>]+>", "", content)  # strip HTML tags
            entries.append({"start": start, "end": end, "text": content})
        return entries

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def srt_to_ass(
        self,
        srt_path: str,
        output_ass_path: str,
        style: str = "tiktok",
        highlight_color: str = "&H0035B6FF",
    ) -> str:
        """Convert SRT to styled ASS file. Returns output path."""
        cfg = STYLES.get(style, STYLES["tiktok"])
        entries = self._parse_srt(srt_path)

        header = self._ass_header(cfg, highlight_color)
        dialogue = []
        for e in entries:
            start = self._format_ass_time(e["start"])
            end = self._format_ass_time(e["end"])
            text = e["text"].replace("\n", "\\N")
            dialogue.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        content = header + "\n".join(dialogue) + "\n"
        Path(output_ass_path).write_text(content, encoding="utf-8")
        return output_ass_path

    @staticmethod
    def _ass_header(cfg: dict, highlight_color: str) -> str:
        return (
            "[Script Info]\n"
            "Title: NemoClaw Captions\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{cfg['fontname']},{cfg['fontsize']},"
            f"{cfg['primary_color']},{highlight_color},"
            f"{cfg['outline_color']},{cfg['shadow_color']},"
            f"{cfg['bold']},0,0,0,100,100,0,0,1,"
            f"{cfg['outline']},{cfg['shadow']},"
            f"{cfg['alignment']},20,20,{cfg['margin_v']},1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
            "Effect, Text\n"
        )

    def generate_test_ass(self, output_path: str, duration: float = 5.0) -> str:
        """Create a test ASS file with sample captions."""
        cfg = STYLES["tiktok"]
        header = self._ass_header(cfg, "&H0035B6FF")
        lines = [
            (0.0, 1.5, "This is a test caption"),
            (1.5, 3.0, "NemoClaw Video Engine"),
            (3.0, duration, "Building the future"),
        ]
        dialogue = []
        for start, end, text in lines:
            dialogue.append(
                f"Dialogue: 0,{self._format_ass_time(start)},"
                f"{self._format_ass_time(end)},Default,,0,0,0,,{text}"
            )
        content = header + "\n".join(dialogue) + "\n"
        Path(output_path).write_text(content, encoding="utf-8")
        return output_path


def main():
    parser = argparse.ArgumentParser(description="NemoClaw Caption Styler")
    parser.add_argument("--input", help="Input SRT file")
    parser.add_argument("--output", help="Output ASS file")
    parser.add_argument("--style", default="tiktok", choices=list(STYLES.keys()))
    parser.add_argument("--highlight-color", default="&H0035B6FF")
    parser.add_argument("--test", help="Generate test ASS at given path")
    args = parser.parse_args()

    styler = CaptionStyler()

    if args.test:
        styler.generate_test_ass(args.test)
        print(f"Test ASS written to {args.test}")
        return

    if not args.input or not args.output:
        parser.error("--input and --output are required (unless using --test)")

    styler.srt_to_ass(args.input, args.output, style=args.style, highlight_color=args.highlight_color)
    print(f"ASS captions written to {args.output}")


if __name__ == "__main__":
    main()
