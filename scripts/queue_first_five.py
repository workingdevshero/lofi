#!/usr/bin/env python3
"""Queue the first 5 Heroic LoFi tracks on Venice elevenlabs-music, then poll until saved."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/Users/bobby/Desktop/heroic-lofi")
AUDIO = ROOT / "audio"
STATE = ROOT / "scripts" / "audio_queue_state.json"
ENV = Path("/Users/bobby/Desktop/GitHub/automate-it/backend/.env")

TRACKS = [
    {
        "id": "01",
        "slug": "cape-on-ide-open",
        "title": "Cape On, IDE Open",
        "duration_seconds": 112,
        "prompt": (
            "Instrumental lo-fi hip hop, 74 BPM, F major, about 1 minute 52 seconds. "
            "Dusty vintage Rhodes electric piano, mellow upright bass, soft boom-bap drums, "
            "tape saturation and light vinyl crackle. Start with just Rhodes and vinyl for eight bars, "
            "then bass, then drums. Warm dusk rooftop mood, early-2000s dusty study beat, "
            "no vocals, no lyrics, no fade-out crash, loop-friendly ending."
        ),
    },
    {
        "id": "02",
        "slug": "coffee-before-the-commit",
        "title": "Coffee Before the Commit",
        "duration_seconds": 148,
        "prompt": (
            "Instrumental lo-fi hip hop, 72 BPM, D minor, about 2 minutes 28 seconds. "
            "Warm Rhodes, unhurried brushed drums, round bass, a ceramic mug clink used as a quiet percussion texture. "
            "Cozy night, patient, no vocals, vinyl hiss, early-2000s chillhop, loop-friendly ending."
        ),
    },
    {
        "id": "03",
        "slug": "golden-hour-refactor",
        "title": "Golden Hour Refactor",
        "duration_seconds": 168,
        "prompt": (
            "Instrumental lo-fi hip hop, 76 BPM, G major, about 2 minutes 48 seconds. "
            "Nylon guitar then dusty Rhodes, hopeful but still laid back, soft drums, no drop. "
            "Golden hour warmth, no vocals, tape saturation, 2000s study beat, loop-friendly ending."
        ),
    },
    {
        "id": "04",
        "slug": "city-lights-boot-sequence",
        "title": "City Lights Boot Sequence",
        "duration_seconds": 136,
        "prompt": (
            "Instrumental lo-fi hip hop, 78 BPM, C major, about 2 minutes 16 seconds. "
            "A pad that feels like a machine quietly booting, then Rhodes and muted trumpet after one minute. "
            "Night city windows lighting up, no vocals, dusty drums, vinyl, loop-friendly ending."
        ),
    },
    {
        "id": "05",
        "slug": "midnight-rooftop-flow",
        "title": "Midnight Rooftop Flow",
        "duration_seconds": 176,
        "prompt": (
            "Instrumental lo-fi hip hop, 75 BPM, A minor, about 2 minutes 56 seconds. "
            "Classic early-2000s Rhodes study beat, dusty drums, warm bass, vinyl crackle, tape saturation. "
            "Midnight rooftop flow, album centerpiece, no vocals, no lyrics, loop-friendly ending with no crash."
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
    return raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb" or raw[:2] == b"\xff\xf3" or raw[:4] == b"RIFF" or raw[:4] == b"fLaC" or raw[:8] == b"\x00\x00\x00\x1cftyp"


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
        for tid, info in state["tracks"].items()
        if not (info.get("file") and Path(info["file"]).exists())
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
                if "content policy" in err.lower() or "HTTP 422" in err:
                    info["status"] = "failed"
                    info["error"] = err[:500]
                    STATE.write_text(json.dumps(state, indent=2))
                    print(f"REQUEUE_NEEDED {tid}", flush=True)
                    return 1
                still.append(tid)
                continue
            if looks_like_audio(raw) or "audio" in (ctype or "") or "mpeg" in (ctype or ""):
                slug = info["slug"]
                out = AUDIO / f"{tid}-{slug}.mp3"
                out.write_bytes(raw)
                info["status"] = "saved"
                info["file"] = str(out)
                info["bytes"] = len(raw)
                STATE.write_text(json.dumps(state, indent=2))
                print(f"SAVED {tid} {out} {len(raw)} bytes", flush=True)
                continue
            try:
                data = json.loads(raw.decode())
            except Exception:
                if len(raw) > 8000:
                    slug = info["slug"]
                    out = AUDIO / f"{tid}-{slug}.mp3"
                    out.write_bytes(raw)
                    info["status"] = "saved"
                    info["file"] = str(out)
                    info["bytes"] = len(raw)
                    STATE.write_text(json.dumps(state, indent=2))
                    print(f"SAVED {tid} {out} {len(raw)} bytes (raw)", flush=True)
                    continue
                print(f"STATUS {tid} unknown-bytes {len(raw)} {ctype}", flush=True)
                still.append(tid)
                continue
            status = (data.get("status") or data.get("state") or "").lower()
            print(f"STATUS {tid} {status or list(data)[:8]}", flush=True)
            audio_b64 = None
            if isinstance(data.get("data"), str) and len(data["data"]) > 1000:
                audio_b64 = data["data"]
            elif isinstance(data.get("audio"), str):
                audio_b64 = data["audio"]
            if audio_b64:
                import base64

                slug = info["slug"]
                out = AUDIO / f"{tid}-{slug}.mp3"
                blob = base64.b64decode(audio_b64)
                out.write_bytes(blob)
                info["status"] = "saved"
                info["file"] = str(out)
                info["bytes"] = len(blob)
                STATE.write_text(json.dumps(state, indent=2))
                print(f"SAVED {tid} {out} {len(blob)} bytes", flush=True)
            elif status in {"failed", "error"}:
                info["status"] = "failed"
                info["error"] = str(data)[:500]
                STATE.write_text(json.dumps(state, indent=2))
                print(f"FAILED {tid}", flush=True)
                return 1
            else:
                still.append(tid)
        pending = still

    print("ALL_SAVED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
