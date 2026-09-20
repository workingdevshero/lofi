# Heroic LoFi — production rules

Working Dev's Hero album. Canonical folder: `/Users/bobby/Desktop/heroic-lofi/`.

Preview: `open /Users/bobby/Desktop/heroic-lofi/index.html`

---

## Dual format (do not skip)

**Every track ships two video masters from the same audio.**

| Master | Shape | When | Destination |
|---|---|---|---|
| **9:16 Short** | 1080×1920 | **Now** | YouTube Short via Automate It (`working-devs-hero` workspace). Approve and publish as a Short. |
| **16:9 long-form plate** | 1280×720 | **Later** | Bank in `videos/masters/*-16x9.mp4`. Do **not** publish these as standalone YouTube videos. They stitch into one ~45–60 min compilation at the end. |

Same Venice MP3 under both. Same loop (or a 9:16-native loop of the same scene) under both.

### Why this exists

YouTube Shorts are how the album goes out track-by-track. The 16:9 files are the long-form cut — one night of vibe coding, all twenty tracks in order. Publishing a 16:9 file as its own YouTube video burns the compilation.

### Hard caps

- Audio generation: **≤179 seconds** (YouTube Shorts is 3:00; mux overshoots).
- After mux: `ffprobe` the file. Shorts files must be **≤2:59**. Encode with explicit `-t`.
- Never pad. If Venice hands back 180s, trim audio to 179 before mux.

### Mux

```bash
# 16:9 plate (bank it)
ffmpeg -y -stream_loop -1 -i loop-16x9.mp4 -i track.mp3 \
  -map 0:v:0 -map 1:a:0 -t "$DUR" -shortest \
  -c:v libx264 -pix_fmt yuv420p -preset fast \
  -c:a aac -b:a 192k -movflags +faststart \
  masters/NN-slug-16x9.mp4

# 9:16 Short (this is what goes to Automate It / YouTube now)
ffmpeg -y -stream_loop -1 -i loop-9x16.mp4 -i track.mp3 \
  -map 0:v:0 -map 1:a:0 -t "$DUR" -shortest \
  -c:v libx264 -pix_fmt yuv420p -preset fast \
  -c:a aac -b:a 192k -movflags +faststart \
  masters/NN-slug-9x16.mp4
```

Always `-map 0:v:0 -map 1:a:0`. Imagine loops often carry their own AAC; without the map, ffmpeg will mux the loop's silent/junk audio instead of the track.

If the approved loop is 16:9, crop it to 9:16 **only when both characters still fit**. Crop x is per-scene (track 1 used `x=520`). If they don't fit, generate a **native 9:16** still + loop instead of a skinny crop.

**9:16 cast:** keep both people if they fit cleanly. If the tall frame can only hold one, **Dimitris** — not Hero.

### Automate It

- Workspace: **Working Dev's Hero LLC** (`working-devs-hero`).
- Task title: `YouTube Short: <Track Title> — Heroic LoFi`
- `contentType: youtube`, `publishMode: manual`, `requiresReview: true`
- Attach the **9:16** mp4. Optional 9:16 thumbnail.
- Leave 16:9 masters on disk for the compilation.

---

## What's on disk

| # | Title | Audio | 16:9 master | 9:16 master | Short published |
|---|---|---|---|---|---|
| 1 | Cape On, IDE Open | yes | yes | yes | [0t7yv7dCNvQ](https://www.youtube.com/watch?v=0t7yv7dCNvQ) |
| 2 | Coffee Before the Commit | yes | yes | yes | [Y6q9N-kHysE](https://www.youtube.com/watch?v=Y6q9N-kHysE) |
| 3 | Golden Hour Refactor | yes | yes | yes | [Gk7r2Md_QmE](https://www.youtube.com/watch?v=Gk7r2Md_QmE) |
| 4 | City Lights Boot Sequence | yes | yes (new interior) | yes (native 9:16, 1080×1920) | 16:9 is in Automate It review — do not publish it as a standalone. Short file is on disk, not submitted yet. |
| 5 | Midnight Rooftop Flow | yes | old rooftop loop | old rooftop loop | no |
| 6–20 | (see index.html) | yes | no | no | no |

Tracks 1–3 were done correctly: both masters on disk, **9:16** sent to YouTube Shorts. Track 4 broke the rule (16:9 only, and that file is in Automate It review).

---

## Other rules that bit us

- Empty plates first, then dress. `scenes/empty/` is frozen except when Bobby explicitly throws a scene away (track 4 rooftop → interior).
- Character boards on a flat plum ground. Dimitris: younger sidekick, no mask, brown eyes, green suit, green boots, **normal head**. Use the **cast image** as the insert reference — style-hinting lets the model redraw him with a giant head.
- Laptop is a small prop.
- Loops: locked camera, no zoom, 3–6s trim, no palindrome, no overlays. Typing + looking at the screen.
- Venice `elevenlabs-music`, `force_instrumental: true`. Never name artists (422). 128 kbps, no bitrate knob.
- Visual bible: Working Dev's Hero 2D vector, plum/gold — **not Ghibli**.

Tutorial write-up (open PR): https://github.com/workingdevshero/web/pull/27
