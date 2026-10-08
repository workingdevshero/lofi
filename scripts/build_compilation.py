#!/usr/bin/env python3
"""Build the long-form 16:9 album video from the mastered audio.

Each track plays over its 16:9 loop (the one index.html shows), in album order,
with a crossfade between tracks on both picture and sound.

    scripts/master_album.py            # first, so audio/mastered/ is current
    scripts/build_compilation.py       # -> videos/heroic-lofi-album-16x9.mp4
    scripts/build_compilation.py -o videos/other-name.mp4
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTERED = ROOT / "audio" / "mastered"
DEFAULT_OUT = ROOT / "videos" / "heroic-lofi-album-16x9.mp4"
CROSSFADE = 1.0
VIDEO_PAD = 1.0  # extra loop footage per segment so every crossfade has frames to blend


def album_tracks(html: str) -> list[tuple[str, str]]:
    """(audio filename, 16:9 loop path) for each track card, in page order."""
    cards = re.findall(r'data-src-16="([^"?]+)[^"]*".*?<audio controls src="audio/([^"?]+)', html, re.S)
    return [(audio, loop) for loop, audio in cards]


def segment_starts(durations: list[float], fade: float) -> list[float]:
    """Output-timeline start of each track once neighbours overlap by `fade` seconds."""
    starts, t = [], 0.0
    for d in durations:
        starts.append(round(t, 3))
        t += d - fade
    return starts


def filtergraph(durations: list[float], fade: float) -> str:
    n = len(durations)
    starts = segment_starts(durations, fade)
    parts = [f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v{i}]" for i in range(n)]
    v, a = "[v0]", f"[{n}:a]"
    for i in range(1, n):
        parts.append(f"{v}[v{i}]xfade=transition=fade:duration={fade}:offset={starts[i]}[x{i}]")
        parts.append(f"{a}[{n + i}:a]acrossfade=d={fade}:c1=qsin:c2=qsin[a{i}]")
        v, a = f"[x{i}]", f"[a{i}]"
    return ";".join(parts) + f";{v}null[vout];{a}anull[aout]"


def duration_of(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    tracks = album_tracks((ROOT / "index.html").read_text())
    audio = [MASTERED / a for a, _ in tracks]
    missing = [p.name for p in audio if not p.exists()]
    if missing:
        raise SystemExit(f"missing mastered audio (run scripts/master_album.py): {missing}")
    durations = [duration_of(p) for p in audio]
    total = sum(durations) - CROSSFADE * (len(durations) - 1)

    cmd = ["ffmpeg", "-v", "error", "-stats", "-y"]
    for (_, loop), d in zip(tracks, durations):
        cmd += ["-stream_loop", "-1", "-t", f"{d + VIDEO_PAD:.3f}", "-i", str(ROOT / loop)]
    for p in audio:
        cmd += ["-i", str(p)]
    cmd += [
        "-filter_complex", filtergraph(durations, CROSSFADE),
        "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(args.out),
    ]
    print(f"{len(tracks)} tracks, {int(total // 60)}:{int(total % 60):02d} -> {args.out}", flush=True)
    subprocess.run(cmd, check=True)

    for start, (a, _) in zip(segment_starts(durations, CROSSFADE), tracks):
        print(f"  {int(start // 60)}:{int(start % 60):02d}  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
