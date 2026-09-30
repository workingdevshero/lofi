#!/usr/bin/env python3
"""Master album audio for the long-form compilation.

Trims dead air at the head and tail, applies per-track EQ, levels every track to
the same integrated loudness under a true-peak ceiling, and writes 320 kbps MP3s
to audio/mastered/. Source files are never modified.

    scripts/master_album.py                 # the 20 album tracks
    scripts/master_album.py audio/17-*.mp3  # specific files (e.g. candidate takes)
    scripts/master_album.py --check         # verify everything in audio/mastered/
"""
from __future__ import annotations

import argparse
import array
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"
OUT = AUDIO / "mastered"

TARGET_LUFS = -14.0
LUFS_TOLERANCE = 0.5
TRUE_PEAK_MAX = -1.0
LIMIT_DB = -1.5            # sample-peak limiter ceiling; leaves room for inter-sample overs
ACTIVE_BELOW_PEAK_DB = 40  # a window is "music" if within this many dB of the loudest window
HEAD_PAD = 0.25            # seconds kept before the first note
TAIL_PAD = 1.5             # seconds kept after the last note
FADE_OUT = 1.0
MAX_DURATION = 179.0       # Shorts cap from PRODUCTION.md

DETECT_SR = 8000
WINDOW = 0.05

# Softens the 2.5–5 kHz attacks measured on the harshest tracks (drum hits, not keys).
# Keyed by file stem, so drop an entry when a new take replaces that file.
PRESENCE_CUT = "equalizer=f=3500:t=q:w=1.0:g=-3"
EQ = {
    "05-cape-on-ide-open": PRESENCE_CUT,
    "17-documentation-rain": PRESENCE_CUT,  # sharp snare/rain transients; the keys themselves are mellow
}

ALBUM = re.compile(r"^\d{2}-[a-z0-9-]+\.mp3$")
TAKE = re.compile(r"-v\d+\.mp3$")


def album_files() -> list[Path]:
    return sorted(p for p in AUDIO.glob("*.mp3") if ALBUM.match(p.name) and not TAKE.search(p.name))


def window_levels_db(path: Path) -> list[float]:
    """RMS level of each 50 ms window, in dBFS, from a mono 8 kHz decode."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(DETECT_SR), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    pcm = array.array("h", raw)
    n = int(DETECT_SR * WINDOW)
    levels = []
    for i in range(0, len(pcm) - n + 1, n):
        chunk = pcm[i:i + n]
        rms = math.sqrt(sum(s * s for s in chunk) / n) / 32768
        levels.append(20 * math.log10(rms) if rms > 0 else -120.0)
    return levels


def trim_points(levels_db: list[float], window: float, duration: float) -> tuple[float, float]:
    """Return (start, end) seconds that keep the music plus a little padding."""
    peak = max(levels_db)
    active = [i for i, db in enumerate(levels_db) if db > peak - ACTIVE_BELOW_PEAK_DB]
    if not active:
        return 0.0, duration
    start = max(0.0, active[0] * window - HEAD_PAD)
    end = min(duration, (active[-1] + 1) * window + TAIL_PAD, MAX_DURATION)
    return round(start, 2), round(end, 2)


def duration_of(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def loudness(path: Path, filters: str | None = None) -> tuple[float, float]:
    """Integrated LUFS and true peak (dBTP), optionally after a filter chain."""
    chain = f"{filters},ebur128=peak=true" if filters else "ebur128=peak=true"
    err = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-af", chain, "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = err[err.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    peak = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary).group(1))
    return lufs, peak


def shaping_filters(stem: str, start: float, end: float) -> str:
    fade = min(FADE_OUT, end - start)
    parts = [f"atrim={start}:{end}", "asetpts=PTS-STARTPTS"]
    if start > 0:
        parts.append("afade=t=in:d=0.05")
    parts.append(f"afade=t=out:st={end - start - fade:.2f}:d={fade:.2f}")
    if stem in EQ:
        parts.append(EQ[stem])
    return ",".join(parts)


def level_filters(gain_db: float) -> str:
    return f"volume={gain_db:.2f}dB,alimiter=limit={10 ** (LIMIT_DB / 20):.4f}:level=0:attack=5:release=80"


def master(src: Path) -> dict:
    duration = duration_of(src)
    start, end = trim_points(window_levels_db(src), WINDOW, duration)
    shape = shaping_filters(src.stem, start, end)

    lufs, _ = loudness(src, shape)
    gain = TARGET_LUFS - lufs
    for _ in range(3):  # the limiter can eat a little loudness; nudge until on target
        got, _ = loudness(src, f"{shape},{level_filters(gain)}")
        if abs(got - TARGET_LUFS) <= LUFS_TOLERANCE / 2:
            break
        gain += TARGET_LUFS - got

    OUT.mkdir(exist_ok=True)
    dst = OUT / src.name
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"{shape},{level_filters(gain)}",
         "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "320k", str(dst)],
        check=True,
    )
    return dict(name=src.name, before=lufs, start=start, cut_tail=max(0.0, duration - end), gain=gain, eq=src.stem in EQ)


def check(paths: list[Path]) -> int:
    failures = 0
    for p in paths:
        lufs, tp = loudness(p)
        dur = duration_of(p)
        start, end = trim_points(window_levels_db(p), WINDOW, dur)
        problems = []
        if abs(lufs - TARGET_LUFS) > LUFS_TOLERANCE:
            problems.append(f"loudness {lufs:.1f} LUFS")
        if tp > TRUE_PEAK_MAX:
            problems.append(f"true peak {tp:.1f} dBTP")
        if dur > MAX_DURATION:
            problems.append(f"duration {dur:.1f}s")
        if start > HEAD_PAD + 0.3 or dur - end > 1.0:  # fade-out drops reverb tails below the threshold
            problems.append(f"dead air head={start:.1f}s tail={dur - end:.1f}s")
        failures += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {p.name:42s} {lufs:6.1f} LUFS {tp:5.1f} dBTP {dur:6.1f}s  {'; '.join(problems)}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--check", action="store_true", help="verify files in audio/mastered/")
    args = ap.parse_args()

    if args.check:
        return check(args.files or sorted(OUT.glob("*.mp3")))

    for src in args.files or album_files():
        r = master(src)
        print(f"{r['name']:42s} {r['before']:6.1f} -> {TARGET_LUFS} LUFS  gain {r['gain']:+5.1f} dB  "
              f"head -{r['start']:.1f}s  tail -{r['cut_tail']:.1f}s{'  EQ' if r['eq'] else ''}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
