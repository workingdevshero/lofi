#!/usr/bin/env python3
"""Queue Heroic LoFi tracks 16–20 on Venice elevenlabs-music, then poll until saved."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/Users/bobby/Desktop/heroic-lofi")
AUDIO = ROOT / "audio"
STATE = ROOT / "scripts" / "audio_queue_state_16_20.json"
ENV = Path("/Users/bobby/Desktop/GitHub/automate-it/backend/.env")

TRACKS = [
    {
        "id": "16",
        "slug": "side-quest-after-hours",
        "title": "Side Quest After Hours",
        "duration_seconds": 116,
        "prompt": (
            "Instrumental lo-fi hip hop, 82 BPM, A major, about 1 minute 56 seconds. "
            "Slightly brighter dusty Rhodes, bouncing bass, light boom-bap, vinyl crackle. "
            "After-hours side quest mood, still laid back, a little extra bounce. "
            "No vocals, no lyrics, no big fills, loop-friendly ending."
        ),
    },
    {
        "id": "17",
        "slug": "documentation-rain",
        "title": "Documentation Rain",
        "duration_seconds": 170,
        "prompt": (
            "Instrumental lo-fi hip hop, 72 BPM, B-flat minor, about 2 minutes 50 seconds. "
            "Soft rain throughout, melancholy Rhodes, muted bass, dusty drums. "
            "Start with rain and a single piano figure, drums at 0:24. "
            "Quiet documentation night, tape saturation, vinyl, no vocals, no lyrics, "
            "loop-friendly ending."
        ),
    },
    {
        "id": "18",
        "slug": "the-last-todo",
        "title": "The Last TODO",
        "duration_seconds": 104,
        "prompt": (
            "Instrumental lo-fi hip hop, 70 BPM, D major, about 1 minute 44 seconds. "
            "Warm short Rhodes lullaby, round bass, drums whispered in late. "
            "Winding down, one last checkbox, vinyl dust. "
            "No vocals, no lyrics, no melody pile-up, loop-friendly ending."
        ),
    },
    {
        "id": "19",
        "slug": "green-build-glow",
        "title": "Green Build Glow",
        "duration_seconds": 152,
        "prompt": (
            "Instrumental lo-fi hip hop, 78 BPM, C major, about 2 minutes 32 seconds. "
            "Hopeful dusty Rhodes, mellow upright bass, soft boom-bap, light vinyl. "
            "Quiet green success glow, still laid back, tape saturation. "
            "Start with Rhodes, then bass, then drums. No vocals, no lyrics, loop-friendly ending."
        ),
    },
    {
        "id": "20",
        "slug": "dawn-over-the-skyline",
        "title": "Dawn Over the Skyline",
        "duration_seconds": 174,
        "prompt": (
            "Instrumental lo-fi hip hop, 76 BPM, F major, about 2 minutes 54 seconds. "
            "Album closer: warm Rhodes, sunrise pads, mellow bass, dusty drums, vinyl crackle. "
            "Dawn over the city, hopeful and tired, tape saturation. "
            "Start sparse, drums at 0:32, no vocals, no lyrics, loop-friendly ending with no crash."
        ),
    },
]


def load_key() -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith("VENICE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("VENICE_API_KEY missing")


def post(url: str, payload: dict, key: str, attempts: int = 6):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last: Exception | None = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                return raw, ctype
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                text = body.decode()[:800]
            except Exception:
                text = f"<binary {len(body)} bytes>"
            raise RuntimeError(f"HTTP {e.code} {url}: {text}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            wait = min(2 ** i, 20)
            print(f"NET_RETRY {i+1}/{attempts} {e} sleep={wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"network failed after {attempts} attempts: {last}") from last


def looks_like_audio(raw: bytes) -> bool:
    return (
        raw[:3] == b"ID3"
        or raw[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}
        or raw[:4] == b"RIFF"
        or raw[:4] == b"fLaC"
    )


def save_track(info: dict, raw: bytes) -> None:
    out = AUDIO / f"{info['id']}-{info['slug']}.mp3"
    out.write_bytes(raw)
    info["status"] = "saved"
    info["file"] = str(out)
    info["bytes"] = len(raw)
    print(f"SAVED {info['id']} {out} {len(raw)} bytes", flush=True)


def main() -> int:
    AUDIO.mkdir(parents=True, exist_ok=True)
    key = load_key()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"tracks": {}}

    for t in TRACKS:
        tid = t["id"]
        existing = state["tracks"].get(tid, {})
        if existing.get("file") and Path(existing["file"]).exists():
            print(f"SKIP {tid} already saved {existing['file']}", flush=True)
            continue
        if existing.get("queue_id") and existing.get("status") not in {"failed"}:
            print(f"RESUME {tid} queue_id={existing['queue_id']}", flush=True)
            continue
        print(f"QUEUE {tid} {t['title']} {t['duration_seconds']}s", flush=True)
        raw, _ctype = post(
            "https://api.venice.ai/api/v1/audio/queue",
            {
                "model": "elevenlabs-music",
                "prompt": t["prompt"],
                "duration_seconds": t["duration_seconds"],
                "force_instrumental": True,
            },
            key,
        )
        data = json.loads(raw.decode())
        qid = data.get("queue_id") or data.get("id")
        if not qid:
            raise RuntimeError(f"No queue_id in {data}")
        state["tracks"][tid] = {
            "id": tid,
            "title": t["title"],
            "slug": t["slug"],
            "queue_id": qid,
            "duration_seconds": t["duration_seconds"],
            "status": "queued",
        }
        STATE.write_text(json.dumps(state, indent=2))
        print(f"QUEUED {tid} {qid}", flush=True)

    pending = [
        tid
        for tid in (t["id"] for t in TRACKS)
        if not (
            state["tracks"].get(tid, {}).get("file")
            and Path(state["tracks"][tid]["file"]).exists()
        )
    ]
    print(f"POLL {len(pending)} tracks", flush=True)
    while pending:
        time.sleep(20)
        still = []
        for tid in pending:
            info = state["tracks"][tid]
            qid = info["queue_id"]
            try:
                raw, ctype = post(
                    "https://api.venice.ai/api/v1/audio/retrieve",
                    {"model": "elevenlabs-music", "queue_id": qid},
                    key,
                )
            except Exception as e:
                err = str(e)
                print(f"POLL_ERR {tid} {err}", flush=True)
                if "HTTP 402" in err or "insufficient" in err.lower():
                    info["status"] = "failed"
                    info["error"] = err[:500]
                    STATE.write_text(json.dumps(state, indent=2))
                    print(f"LIMIT {tid}", flush=True)
                    return 1
                if "content policy" in err.lower() or "HTTP 422" in err:
                    info["status"] = "failed"
                    info["error"] = err[:500]
                    STATE.write_text(json.dumps(state, indent=2))
                    print(f"REQUEUE_NEEDED {tid}", flush=True)
                    return 1
                still.append(tid)
                continue
            if looks_like_audio(raw) or "audio" in (ctype or "") or "mpeg" in (ctype or ""):
                save_track(info, raw)
                STATE.write_text(json.dumps(state, indent=2))
                continue
            try:
                data = json.loads(raw.decode())
            except Exception:
                if len(raw) > 8000:
                    save_track(info, raw)
                    STATE.write_text(json.dumps(state, indent=2))
                    continue
                print(f"STATUS {tid} unknown-bytes {len(raw)} {ctype}", flush=True)
                still.append(tid)
                continue
            status = (data.get("status") or data.get("state") or "").lower()
            print(f"STATUS {tid} {status or list(data)[:8]}", flush=True)
            if status in {"failed", "error"}:
                info["status"] = "failed"
                info["error"] = str(data)[:500]
                STATE.write_text(json.dumps(state, indent=2))
                print(f"FAILED {tid}", flush=True)
                return 1
            still.append(tid)
        pending = still

    print("ALL_SAVED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
