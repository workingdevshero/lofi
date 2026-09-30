# Heroic Lofi — production rules

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

Nail the animation in **16:9**, then crop that loop to 9:16. Do not generate a separate portrait animation. Pick the crop x so both characters still fit (track 7 boomerang uses `crop=405:720:410:0` on the 1280×720 loop, then `scale=1080:1920`). The 9:16 Short is that crop, looped under the same MP3.

**Laptop lid:** if a character who already has the `</>` chest emblem is holding the laptop, the lid is a **plain gold circle**. The `</>` on the lid is fine when the laptop is sitting on its own (no one holding it).

**Preview page (`index.html`) has a 16:9 / 9:16 switch.** It swaps each card’s loop. Tracks 1–3 have no separate 9:16 loop, so that mode plays the muxed Short. QuickTime still works:

```bash
open -a "QuickTime Player" videos/loops/NN-slug-loop-9x16.mp4
```

### Automate It

- Workspace: **Working Dev's Hero LLC** (`working-devs-hero`).
- Task title: `YouTube Short: <Track Title> — Heroic Lofi`
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
| 4 | City Lights Boot Sequence | yes | yes (new interior) | yes (native 9:16, 1080×1920) | in review (Short swapped in; 16:9 stays on disk) |
| 5 | Midnight Rooftop Flow | yes | yes (hands-on-laptop take) | yes (native 9:16, 1080×1920) | in review (Short, manual) |
| 6 | The Secret Lair Terminal | yes | yes | yes (1080×1920) | in review (Short, manual) |
| 7 | Rubber Duck on the Ledge | yes | yes (boomerang) | yes (crop of that boomerang, 1080×1920) | in review (Short, manual) |
| 8–20 | first-pass loops | yes | yes | yes | no — review 16:9 on the preview page, 9:16 in QuickTime |

Tracks 1–3 were done correctly: both masters on disk, **9:16** sent to YouTube Shorts. Track 4’s review item was the 16:9 plate; that attachment is now the 9:16 Short. The 16:9 master stays on disk for the compilation.

---

## Mastering (compilation audio)

`python3 scripts/master_album.py` writes `audio/mastered/` (gitignored): -14 LUFS, ≤ -1 dBTP, dead head/tail trimmed, per-track EQ in the script. `--check` verifies; tests in `scripts/test_master_album.py`. Build the long-form compilation from these, not from `audio/`. Rerun after any track swap. Shorts keep the raw track (YouTube levels them).

Take swaps: new takes land as `NN-slug-vN.mp3` (`scripts/queue_remakes.py`); once one is picked, copy it into the slot, remux both masters, update the prompt in `index.html`, replace the Short in Automate It, and delete the leftover takes. Good songs that don't fit go to `audio/next-album/` with a `.txt` prompt beside each.

---

## Other rules that bit us

- Empty plates first, then dress. `scenes/empty/` is frozen except when Bobby explicitly throws a scene away (track 4 rooftop → interior).
- Character boards on a flat plum ground. Dimitris: younger sidekick, no mask, brown eyes, green suit, green boots, **normal head**. Use the **cast image** as the insert reference — style-hinting lets the model redraw him with a giant head.
- Laptop is a small prop.
- Loops: locked camera, no zoom, 3–6s trim, no palindrome, no overlays. Typing + looking at the screen. A “no zoom” line in the prompt is not enough. Pinning the same still as the first frame, the last frame, and interior keyframes locks the framing and also freezes the characters, so do not ship that clip unless the characters actually move. Measure the sky and corners against the first frame before calling the camera locked.
- Venice `elevenlabs-music`, `force_instrumental: true`. Never name artists (422). 128 kbps, no bitrate knob.
- Visual bible: Working Dev's Hero 2D vector, plum/gold — **not Ghibli**.

Tutorial write-up (open PR): https://github.com/workingdevshero/web/pull/27
