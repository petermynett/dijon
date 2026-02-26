"""Tests for meter pipeline and CLI behavior."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from dijon.pipeline.meter import (
    _resolve_beats_files,
    _track_name_from_beats_stem,
    run_meter,
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


def _write_markers_with_head_in(
    markers_dir: Path, track_name: str, head_in_sec: float, duration_sec: float = 5.0
) -> None:
    """Write marker JSON with HEAD_IN_START and END."""
    path = markers_dir / f"{track_name}_markers.json"
    markers_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "markers": [
            {"name": "START", "position": 0.0},
            {"name": "HEAD_IN_START", "position": head_in_sec},
            {"name": "END", "position": duration_sec},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class TestMeterHelpers:
    """Unit tests for pipeline helpers."""

    def test_track_name_from_beats_stem(self) -> None:
        assert _track_name_from_beats_stem("YTB-001_beats") == "YTB-001"
        assert _track_name_from_beats_stem("stem") == "stem"

    def test_resolve_beats_files_explicit(self, tmp_path: Path) -> None:
        a = tmp_path / "a.npy"
        a.touch()
        got = _resolve_beats_files([a], tmp_path)
        assert len(got) == 1
        assert got[0].name == "a.npy"

    def test_resolve_beats_files_empty(self, tmp_path: Path) -> None:
        assert _resolve_beats_files(None, tmp_path) == []


class TestRunMeter:
    """Integration-style tests for run_meter (tmp paths)."""

    def test_run_meter_writes_npy_and_enriches_items(
        self, tmp_path: Path
    ) -> None:
        beats_dir = tmp_path / "beats"
        out_dir = tmp_path / "meter"
        audio_dir = tmp_path / "audio"
        markers_dir = tmp_path / "markers"
        beats_dir.mkdir()
        audio_dir.mkdir()
        markers_dir.mkdir()

        head_in = 2.0
        # 5 s audio
        _write_minimal_wav(audio_dir / "TRACK01.wav", duration_sec=5.0)
        _write_markers_with_head_in(markers_dir, "TRACK01", head_in, 5.0)

        # Beat times: 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5 (9 beats)
        beat_times = np.arange(0.5, 5.0, 0.5, dtype=np.float64)
        np.save(beats_dir / "TRACK01_beats.npy", beat_times)

        result = run_meter(
            beats_files=[beats_dir / "TRACK01_beats.npy"],
            output_dir=out_dir,
            beats_dir=beats_dir,
            raw_audio_dir=audio_dir,
            markers_dir=markers_dir,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["succeeded"] == 1
        item = result["items"][0]
        assert item["kind"] == "meter"
        assert item["input_file"] == "TRACK01_beats.npy"
        assert item["output"] == "TRACK01_meter.npy"
        assert item["head_in"] == pytest.approx(head_in)
        assert item["num_beats"] == 9
        assert item["t_first_beat"] == pytest.approx(0.5)
        assert item["t_last_beat"] == pytest.approx(4.5)
        assert isinstance(item["beats_per_bar"], int)
        assert item["beats_per_bar"] >= 1
        assert item["label_shape"] == (9, 3)
        assert isinstance(item["bar_count"], int)
        assert item["bar_count"] >= 1
        assert isinstance(item["beat_counts"], dict)
        assert sum(item["beat_counts"].values()) == 9
        assert "head_in_nearest_beat" in item
        assert "head_in_offset" in item

        out_file = out_dir / "TRACK01_meter.npy"
        assert out_file.exists()
        arr = np.load(out_file)
        assert arr.ndim == 2
        assert arr.shape[1] >= 3
