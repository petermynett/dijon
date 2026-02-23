"""Tests for tempogram pipeline and CLI behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dijon.pipeline.tempogram import (
    FS_NOVELTY,
    TEMPOGRAM_DEFAULTS,
    _output_filename,
    _resolve_novelty_files,
    _track_name_from_novelty_stem,
    run_tempogram,
)


class TestTempogramHelpers:
    """Unit tests for pipeline helpers."""

    def test_track_name_from_novelty_stem(self) -> None:
        assert _track_name_from_novelty_stem("YTB-001_novelty_spectrum_1024-256-100.0-10") == "YTB-001"
        assert _track_name_from_novelty_stem("stem") == "stem"

    def test_output_filename_format(self) -> None:
        name = _output_filename("YTB-001", "fourier", 500, 1, 40, 320)
        assert name == "YTB-001_tempogram_fourier_500-1-40-320.npy"

    def test_resolve_novelty_files_explicit(self, tmp_path: Path) -> None:
        a = tmp_path / "a.npy"
        a.touch()
        got = _resolve_novelty_files([a], tmp_path)
        assert len(got) == 1
        assert got[0].name == "a.npy"

    def test_resolve_novelty_files_default_folder(self, tmp_path: Path) -> None:
        (tmp_path / "one.npy").touch()
        (tmp_path / "two.npy").touch()
        got = _resolve_novelty_files(None, tmp_path)
        assert len(got) == 2
        assert {p.name for p in got} == {"one.npy", "two.npy"}

    def test_resolve_novelty_files_empty(self, tmp_path: Path) -> None:
        assert _resolve_novelty_files(None, tmp_path) == []


class TestRunTempogram:
    """Integration-style tests for run_tempogram (tmp paths)."""

    def test_run_tempogram_fourier_writes_npy(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        nov_dir.mkdir()
        out_dir = tmp_path / "tempogram"
        # 10 s of novelty at 100 Hz
        nov = np.random.randn(1000).astype(np.float64) * 0.1 + 0.5
        nov = np.clip(nov, 0, 1)
        np.save(nov_dir / "TRACK01_novelty_spectrum_1024-256-100.0-10.npy", nov)

        result = run_tempogram(
            novelty_files=[nov_dir / "TRACK01_novelty_spectrum_1024-256-100.0-10.npy"],
            output_dir=out_dir,
            novelty_dir=nov_dir,
            ntype="fourier",
            N=100,
            H=10,
            theta_min=60,
            theta_max=120,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["succeeded"] == 1
        out_file = out_dir / "TRACK01_tempogram_fourier_100-10-60-120.npy"
        assert out_file.exists()
        arr = np.load(out_file)
        assert arr.ndim == 2
        assert arr.dtype == np.float64

    def test_run_tempogram_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        nov_dir.mkdir()
        np.save(nov_dir / "x.npy", np.zeros(500))
        result = run_tempogram(
            novelty_files=[nov_dir / "x.npy"],
            output_dir=tmp_path / "out",
            novelty_dir=nov_dir,
            ntype="autocorr",
            dry_run=True,
        )
        assert result["success"] is True
        assert result["succeeded"] == 1
        assert not (tmp_path / "out").exists()

    def test_run_tempogram_cyclic_chains_from_fourier(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        nov_dir.mkdir()
        nov = np.clip(np.random.randn(500).astype(np.float64) * 0.1 + 0.5, 0, 1)
        np.save(nov_dir / "stem.npy", nov)
        result = run_tempogram(
            novelty_files=[nov_dir / "stem.npy"],
            output_dir=tmp_path / "out",
            novelty_dir=nov_dir,
            ntype="cyclic",
            N=100,
            H=10,
            dry_run=False,
        )
        assert result["success"] is True
        out_file = tmp_path / "out" / "stem_tempogram_cyclic_100-10-40-320.npy"
        assert out_file.exists()
        arr = np.load(out_file)
        assert arr.ndim == 2

    def test_run_tempogram_unknown_type_fails(self, tmp_path: Path) -> None:
        result = run_tempogram(
            novelty_files=[],
            output_dir=tmp_path,
            ntype="invalid",
        )
        assert result["success"] is False
        assert "Unknown tempogram type" in result["message"]

    def test_defaults_match_spec(self) -> None:
        assert FS_NOVELTY == 100.0
        assert TEMPOGRAM_DEFAULTS["fourier"] == (500, 1)
        assert TEMPOGRAM_DEFAULTS["autocorr"] == (500, 1)
        assert TEMPOGRAM_DEFAULTS["cyclic"] == (500, 1)
