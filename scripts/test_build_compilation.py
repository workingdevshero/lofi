#!/usr/bin/env python3
"""Tests for build_compilation.py. Run: python3 scripts/test_build_compilation.py"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_compilation as b  # noqa: E402


class AlbumTracks(unittest.TestCase):
    def test_reads_every_card_in_order_with_its_loop(self):
        tracks = b.album_tracks((b.ROOT / "index.html").read_text())
        self.assertEqual(len(tracks), 20)
        self.assertEqual([a[:2] for a, _ in tracks], [f"{i:02d}" for i in range(1, 21)])
        for audio, loop in tracks:
            self.assertTrue((b.ROOT / loop).exists(), loop)
            self.assertTrue((b.ROOT / "audio" / audio).exists(), audio)

    def test_strips_cache_busting(self):
        html = ('<video data-src-16="videos/loops/x.mp4?v=5"></video>'
                '<audio controls src="audio/01-x.mp3?v=2"></audio>')
        self.assertEqual(b.album_tracks(html), [("01-x.mp3", "videos/loops/x.mp4")])


class Timeline(unittest.TestCase):
    def test_each_track_starts_one_fade_early(self):
        self.assertEqual(b.segment_starts([10.0, 20.0, 5.0], 1.0), [0.0, 9.0, 28.0])

    def test_filtergraph_chains_every_track(self):
        g = b.filtergraph([10.0, 20.0, 5.0], 1.0)
        self.assertEqual(g.count("xfade="), 2)
        self.assertEqual(g.count("acrossfade="), 2)
        self.assertIn("offset=9.0", g)
        self.assertIn("offset=28.0", g)
        self.assertTrue(g.endswith("[x2]null[vout];[a2]anull[aout]"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
