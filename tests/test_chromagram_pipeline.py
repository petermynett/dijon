"""Tests for chromagram pipeline and shorthand resolution."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from dijon.pipeline.chromagram import (
    _resolve_audio_files,
    _track_name,
    run_chromagram,
)


def _write_minimal_wav(path: Path, sr: int = 22050, duration_sec: float = 1.0) -> None:
    """Write a minimal mono WAV (silence) so librosa can load it."""
    n = int(sr * duration_sec)
    buf = np.zeros(n, dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


class TestChromagramHelpers:
    """Unit tests for pipeline helpers."""

    def test_track_name_from_path(self) -> None:
        assert _track_name(Path("/foo/bar/YTB-001.wav")) == "YTB-001"
        assert _track_name(Path("a.wav")) == "a"

    def test_resolve_audio_files_explicit(self, tmp_path: Path) -> None:
        a = tmp_path / "a.wav"
        a.touch()
        got = _resolve_audio_files([a], tmp_path)
        assert len(got) == 1
        assert got[0].name == "a.wav"

    def test_resolve_audio_files_default_folder(self, tmp_path: Path) -> None:
        (tmp_path / "one.wav").touch()
        (tmp_path / "two.wav").touch()
        got = _resolve_audio_files(None, tmp_path)
        assert len(got) == 2
        assert {p.name for p in got} == {"one.wav", "two.wav"}

    def test_resolve_audio_files_shorthand_track_id(self, tmp_path: Path) -> None:
        (tmp_path / "YTB-014.wav").touch()
        got = _resolve_audio_files([Path("YTB-014")], tmp_path)
        assert len(got) == 1
        assert got[0].name == "YTB-014.wav"
        assert got[0].parent == tmp_path.resolve()

    def test_resolve_audio_files_explicit_path_preserved(self, tmp_path: Path) -> None:
        audio_dir = tmp_path / "audio"
        other_dir = tmp_path / "other"
        audio_dir.mkdir()
        other_dir.mkdir()
        explicit = other_dir / "custom.wav"
        explicit.touch()
        got = _resolve_audio_files([explicit], audio_dir)
        assert len(got) == 1
        assert got[0].name == "custom.wav"
        assert got[0].parent == other_dir.resolve()


class TestRunChromagram:
    """Integration-style tests for run_chromagram (tmp paths)."""

    def test_run_chromagram_with_shorthand_track_id(self, tmp_path: Path) -> None:
        """Shorthand YTB-014 resolves to raw_audio_dir/YTB-014.wav."""
        audio_dir = tmp_path / "audio"
        meter_dir = tmp_path / "meter"
        out_dir = tmp_path / "chromagram"
        audio_dir.mkdir()
        meter_dir.mkdir()
        _write_minimal_wav(audio_dir / "YTB-014.wav", duration_sec=2.0)
        # 2 s at 0.5 s intervals: 4 beats, 2 bars
        meter_map = np.array([
            [0.0, 1, 1],
            [0.5, 1, 2],
            [1.0, 2, 1],
            [1.5, 2, 2],
        ], dtype=np.float64)
        np.save(meter_dir / "YTB-014_meter.npy", meter_map)

        result = run_chromagram(
            audio_files=[Path("YTB-014")],
            output_dir=out_dir,
            raw_audio_dir=audio_dir,
            meter_dir=meter_dir,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["succeeded"] == 1
        out_name = "YTB-014_chromagram_metric_cqt_256-180.0-mean-preserve-rms-1.0-2.npy"
        assert (out_dir / out_name).exists()
