#!/usr/bin/env python3
"""Tests for master_album.py. Run: python3 scripts/test_master_album.py"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import master_album as m  # noqa: E402

W = m.WINDOW


def levels(silent_head: float, music: float, silent_tail: float) -> list[float]:
    return [-90.0] * round(silent_head / W) + [-20.0] * round(music / W) + [-90.0] * round(silent_tail / W)


class TrimPoints(unittest.TestCase):
    def test_trims_dead_air_keeping_padding(self):
        start, end = m.trim_points(levels(3.0, 100.0, 7.0), W, 110.0)
        self.assertAlmostEqual(start, 3.0 - m.HEAD_PAD, places=2)
        self.assertAlmostEqual(end, 103.0 + m.TAIL_PAD, places=2)

    def test_leaves_tight_edges_alone(self):
        self.assertEqual(m.trim_points(levels(0.0, 100.0, 0.0), W, 100.0), (0.0, 100.0))

    def test_quiet_intro_counts_as_music(self):
        lv = [-90.0] * 20 + [-50.0] * 200 + [-20.0] * 1000   # soft intro within 40 dB of peak
        start, _ = m.trim_points(lv, W, len(lv) * W)
        self.assertAlmostEqual(start, 20 * W - m.HEAD_PAD, places=2)

    def test_never_exceeds_shorts_cap(self):
        _, end = m.trim_points(levels(0.0, 182.0, 0.0), W, 182.0)
        self.assertEqual(end, m.MAX_DURATION)

    def test_all_silent_returns_whole_file(self):
        self.assertEqual(m.trim_points([-120.0] * 100, W, 5.0), (0.0, 5.0))


class Filters(unittest.TestCase):
    def test_eq_only_on_listed_tracks(self):
        self.assertIn("equalizer", m.shaping_filters("05-cape-on-ide-open", 0.0, 100.0))
        self.assertNotIn("equalizer", m.shaping_filters("02-coffee-before-the-commit", 0.0, 100.0))

    def test_fade_in_only_when_head_trimmed(self):
        self.assertNotIn("t=in", m.shaping_filters("x", 0.0, 100.0))
        self.assertIn("t=in", m.shaping_filters("x", 2.0, 100.0))

    def test_album_files_skip_takes_and_masters(self):
        names = [p.name for p in m.album_files()]
        self.assertEqual(len(names), 20)
        self.assertFalse(any("-v" in n for n in names))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
class EndToEnd(unittest.TestCase):
    def test_masters_quiet_padded_tone_to_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "99-test-tone.mp3"
            # 2s silence, 20s quiet tone, 6s silence
            subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                 "sine=f=220:d=20,volume=-26dB,adelay=2000,apad=pad_dur=6",
                 "-c:a", "libmp3lame", "-b:a", "128k", str(src)],
                check=True,
            )
            out_dir, m.OUT = m.OUT, Path(tmp) / "mastered"
            try:
                m.master(src)
                self.assertEqual(m.check([m.OUT / src.name]), 0)
                self.assertTrue(math.isclose(m.duration_of(m.OUT / src.name), 20 + m.HEAD_PAD + m.TAIL_PAD, abs_tol=0.3))
            finally:
                m.OUT = out_dir


if __name__ == "__main__":
    unittest.main(verbosity=2)
