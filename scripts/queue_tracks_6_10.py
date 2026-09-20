#!/usr/bin/env python3
"""Queue Heroic LoFi tracks 6–10 on Venice elevenlabs-music, then poll until saved."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/Users/bobby/Desktop/heroic-lofi")
AUDIO = ROOT / "audio"
STATE = ROOT / "scripts" / "audio_queue_state_06_10.json"
ENV = Path("/Users/bobby/Desktop/GitHub/automate-it/backend/.env")

TRACKS = [
    {
        "id": "06",
        "slug": "the-secret-lair-terminal",
        "title": "The Secret Lair Terminal",
        "duration_seconds": 154,
        "prompt": (
            "Instrumental lo-fi hip hop, 75 BPM, E minor, about 2 minutes 34 seconds. "
            "Deep sub bass, tactile mechanical keyboard clicks woven into a boom-bap pocket, "
            "dark Rhodes electric piano, faint server-fan bed. Intimate subterranean workshop mood. "
            "Start with clicks and vinyl, bass at 0:16, drums at 0:32. No vocals, no lyrics, "
            "tape saturation, loop-friendly ending."
        ),
    },
    {
        "id": "07",
        "slug": "rubber-duck-on-the-ledge",
        "title": "Rubber Duck on the Ledge",
        "duration_seconds": 108,
        "prompt": (
            "Instrumental lo-fi hip hop, 70 BPM, F minor, about 1 minute 48 seconds. "
            "Sparse warm Rhodes, bowed bass, drums whispered in late after 0:40. "
            "Quiet late-night conversation in the chords, vinyl dust, almost nothing extra. "
            "No vocals, no lyrics, no melody pile-up, loop-friendly ending."
        ),
    },
    {
        "id": "08",
        "slug": "rainy-fire-escape-deploy",
        "title": "Rainy Fire Escape Deploy",
        "duration_seconds": 172,
        "prompt": (
            "Instrumental lo-fi hip hop, 73 BPM, C minor, about 2 minutes 52 seconds. "
            "Soft rain-on-tin throughout, melancholy piano, muted trumpet after one minute, "
            "muted bass, dusty drums. Start with rain and a single piano figure, drums at 0:24. "
            "No vocals, no lyrics, vinyl crackle, loop-friendly ending."
        ),
    },
    {
        "id": "09",
        "slug": "keyboard-cathedral",
        "title": "Keyboard Cathedral",
        "duration_seconds": 140,
        "prompt": (
            "Instrumental lo-fi hip hop, 80 BPM, A minor, about 2 minutes 20 seconds. "
            "Close dry Rhodes, tight boom-bap, soft mechanical-keyboard bed on the offbeats, "
            "bone-dry mix except a little tape. Focused late-night coding music. "
            "No vocals, no lyrics, no big fills, loop-friendly ending."
        ),
    },
    {
        "id": "10",
        "slug": "merge-conflict-moonlight",
        "title": "Merge Conflict Moonlight",
        "duration_seconds": 164,
        "prompt": (
            "Instrumental lo-fi hip hop, 76 BPM, D minor, about 2 minutes 44 seconds. "
            "Two interlocking Rhodes figures that eventually agree, walking bass, dusty drums. "
            "Slight tension then settle. No vocals, no lyrics, vinyl, loop-friendly ending."
        ),
    },
]


def load_key() -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith("VENICE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("VENICE_API_KEY missing")


def post(url: str, payload: dict, key: str):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
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
