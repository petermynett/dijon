"""Tests for beats pipeline and CLI behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dijon.pipeline.beats import (
    _resolve_tempogram_files,
    _track_name_from_tempogram_stem,
    run_beats,
)


class TestBeatsHelpers:
    """Unit tests for pipeline helpers."""

    def test_track_name_from_tempogram_stem(self) -> None:
        assert (
            _track_name_from_tempogram_stem("YTB-001_tempogram_fourier_500-1-40-320")
            == "YTB-001"
        )
        assert _track_name_from_tempogram_stem("stem") == "stem"

    def test_resolve_tempogram_files_explicit(self, tmp_path: Path) -> None:
        a = tmp_path / "a.npy"
        a.touch()
        got = _resolve_tempogram_files([a], tmp_path)
        assert len(got) == 1
        assert got[0].name == "a.npy"

    def test_resolve_tempogram_files_empty(self, tmp_path: Path) -> None:
        assert _resolve_tempogram_files(None, tmp_path) == []


class TestRunBeats:
    """Integration-style tests for run_beats (tmp paths)."""

    def test_run_beats_writes_npy_and_enriches_items(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        tempo_dir = tmp_path / "tempogram"
        out_dir = tmp_path / "beats"
        nov_dir.mkdir()
        tempo_dir.mkdir()

        # 10 s novelty at 100 Hz
        nov = np.random.randn(1000).astype(np.float64) * 0.1 + 0.5
        nov = np.clip(nov, 0, 1)
        np.save(nov_dir / "TRACK01_novelty_spectrum_1024-256-100.0-10.npy", nov)

        # Minimal 2D tempogram (K=61 tempo bins, M=101 time frames)
        tempo_arr = np.random.rand(61, 101).astype(np.float64) * 0.5
        np.save(
            tempo_dir / "TRACK01_tempogram_fourier_100-10-60-120.npy",
            tempo_arr,
        )

        result = run_beats(
            tempogram_files=[
                tempo_dir / "TRACK01_tempogram_fourier_100-10-60-120.npy"
            ],
            output_dir=out_dir,
            tempogram_dir=tempo_dir,
            novelty_dir=nov_dir,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["succeeded"] == 1
        item = result["items"][0]
        assert item["input_tempogram"] == "TRACK01_tempogram_fourier_100-10-60-120.npy"
        assert item["input_novelty"] == "TRACK01_novelty_spectrum_1024-256-100.0-10.npy"
        assert item["output"] == "TRACK01_beats.npy"
        assert item["num_beats"] > 0
        assert 40 <= item["implied_bpm"] <= 320
        assert item["shape"] == (item["num_beats"],)
        assert item["dtype"] == "float64"
        assert "ibi_min" in item and "ibi_max" in item
        assert "ibi_mean" in item and "ibi_std" in item
        assert item["t_first"] >= 0
        assert item["t_last"] <= 10.0
        assert item["duration"] == pytest.approx(10.0)
        assert 0 <= item["coverage_ratio"] <= 1.0

        out_file = out_dir / "TRACK01_beats.npy"
        assert out_file.exists()
        arr = np.load(out_file)
        assert arr.ndim == 1
        assert arr.dtype == np.float64
