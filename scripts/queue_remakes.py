#!/usr/bin/env python3
"""Queue new takes of tracks 07, 12, 16, 17 and 19 on Venice elevenlabs-music.

Takes save next to the originals as NN-slug-vN.mp3. Originals are never touched.
Rerunning resumes queued takes; bump TAKES to queue more.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from queue_tracks_16_20 import AUDIO, load_key, looks_like_audio, post  # noqa: E402

STATE = Path(__file__).parent / "audio_queue_state_remakes.json"
TAKES = 2

TRACKS = [
    {
        "id": "07",
        "slug": "rubber-duck-on-the-ledge",
        "duration_seconds": 108,
        "takes": 3,
        "prompt": (
            "Instrumental lo-fi hip hop, 76 BPM, D minor, about 1 minute 48 seconds. "
            "A warm, muffled electric piano plays slow chords and a simple melody in the low and middle "
            "register, soft and rounded with a gentle tremolo, like it's coming from the next room. "
            "Dusty boom-bap drums and a round upright bass from the first bar. A quiet late-night "
            "conversation on a rooftop ledge, calm and thoughtful. No acoustic piano, no high notes, "
            "no bright attack, no sharp notes, no guitar, no long intro. Even volume the whole way. "
            "Light vinyl crackle and tape warmth. No vocals, no lyrics, loop-friendly ending with no crash."
        ),
    },
    {
        "id": "12",
        "slug": "stack-trace-serenade",
        "duration_seconds": 152,
        "prompt": (
            "Instrumental lo-fi hip hop, 78 BPM, A minor, about 2 minutes 32 seconds. "
            "A clean electric jazz guitar with the tone knob rolled down plays a slow, singing "
            "serenade melody over warm chords, thumb-picked and round. Dusty boom-bap drums and a "
            "round upright bass from the first bar. Thoughtful and steady, like reading a stack trace "
            "until it makes sense. No piano, no Rhodes, no bright attack, no sharp notes, no long intro, "
            "no breakdown. Even volume the whole way. Light tape saturation, faint vinyl dust. "
            "No vocals, no lyrics, loop-friendly ending with no crash."
        ),
    },
    {
        "id": "16",
        "slug": "side-quest-after-hours",
        "duration_seconds": 116,
        "prompt": (
            "Instrumental lo-fi hip hop, 80 BPM, B-flat major, about 1 minute 56 seconds. "
            "Dusty boom-bap drums and a warm round bass from the first bar, the same late-night pocket "
            "as a study beat. Over it, a soft 8-bit quest melody like an old handheld game heard through "
            "a cassette: a mellow, low-passed triangle-wave lead sitting behind the drums, heroic but "
            "gentle, rising and answering itself. A warm pad quietly doubles the melody. No piano, "
            "no Rhodes, no piercing square wave, no fast arpeggios, no bright attack. Light tape "
            "saturation and faint cassette hiss. Medium volume the whole way. No vocals, no lyrics, "
            "loop-friendly ending with no crash."
        ),
    },
    {
        "id": "17",
        "slug": "documentation-rain",
        "duration_seconds": 170,
        "prompt": (
            "Instrumental lo-fi hip hop, 72 BPM, B-flat major, about 2 minutes 50 seconds. "
            "Soft steady rain in the background, brushed drums and round upright bass from the first bar. "
            "A soft-mallet vibraphone plays slow warm chords and a simple melody, a dull electric piano "
            "pad far underneath only. No acoustic piano, no bright notes, no sharp attack, no long intro, "
            "no breakdown. Even volume the whole way, calm and steady. Light tape warmth, no vinyl crackle. "
            "No vocals, no lyrics, loop-friendly ending with no crash."
        ),
    },
    {
        "id": "19",
        "slug": "green-build-glow",
        "duration_seconds": 152,
        "prompt": (
            "Instrumental lo-fi hip hop, 78 BPM, C major, about 2 minutes 32 seconds. "
            "A warm analog synth pad and a soft, low-passed synth lead with a slow attack play a simple "
            "hopeful melody, like a green status light glowing in a dark room. Dusty boom-bap drums and a "
            "round bass from the first bar. Quiet success, laid back, not triumphant. No piano, no Rhodes, "
            "no bright attack, no sharp notes, no arpeggios, no long intro, no drop. Even volume the whole "
            "way. Light tape saturation. No vocals, no lyrics, loop-friendly ending with no crash."
        ),
    },
]


def next_take_path(tid: str, slug: str, claimed: set[str]) -> Path:
    n = 2
    while True:
        p = AUDIO / f"{tid}-{slug}-v{n}.mp3"
        if not p.exists() and str(p) not in claimed:
            return p
        n += 1


def main() -> int:
    key = load_key()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"takes": {}}
    takes = state["takes"]
    claimed = {t["file"] for t in takes.values()}

    for t in TRACKS:
        # A new prompt for a track gets its own takes.
        have = [k for k, v in takes.items() if k.startswith(t["id"] + "-") and v["prompt"] == t["prompt"]]
        for _ in range(t.get("takes", TAKES) - len(have)):
            out = next_take_path(t["id"], t["slug"], claimed)
            raw, _ = post(
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
            name = out.stem
            takes[name] = {"queue_id": qid, "file": str(out), "prompt": t["prompt"], "status": "queued"}
            claimed.add(str(out))
            STATE.write_text(json.dumps(state, indent=2))
            print(f"QUEUED {name} {qid}", flush=True)

    pending = [k for k, v in takes.items() if v["status"] == "queued"]
    while pending:
        time.sleep(20)
        still = []
        for name in pending:
            info = takes[name]
            try:
                raw, ctype = post(
                    "https://api.venice.ai/api/v1/audio/retrieve",
                    {"model": "elevenlabs-music", "queue_id": info["queue_id"]},
                    key,
                )
            except Exception as e:
                print(f"POLL_ERR {name} {e}", flush=True)
                if any(s in str(e) for s in ("HTTP 402", "HTTP 422")):
                    info["status"] = "failed"
                    info["error"] = str(e)[:500]
                    continue
                still.append(name)
                continue
            if looks_like_audio(raw) or "audio" in (ctype or "") or "mpeg" in (ctype or ""):
                Path(info["file"]).write_bytes(raw)
                info["status"] = "saved"
                print(f"SAVED {info['file']} {len(raw)} bytes", flush=True)
            else:
                data = json.loads(raw.decode())
                status = (data.get("status") or "").lower()
                print(f"STATUS {name} {status}", flush=True)
                if status in {"failed", "error"}:
                    info["status"] = "failed"
                    info["error"] = str(data)[:500]
                else:
                    still.append(name)
        STATE.write_text(json.dumps(state, indent=2))
        pending = still

    failed = [k for k, v in takes.items() if v["status"] == "failed"]
    print("FAILED " + " ".join(failed) if failed else "ALL_SAVED", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
