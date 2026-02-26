"""Tests for tempogram pipeline and CLI behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dijon.tempogram import compute_tempogram_fourier
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
        item = result["items"][0]
        assert item["input_file"] == "TRACK01_novelty_spectrum_1024-256-100.0-10.npy"
        assert item["output"] == "TRACK01_tempogram_fourier_100-10-60-120.npy"
        assert item["num_features"] == 1000
        assert item["feature_sample_rate_hz"] == pytest.approx(100.0)
        assert item["N"] == 100
        assert item["H"] == 10
        assert item["shape"] == tuple(np.load(out_dir / item["output"]).shape)
        assert item["dtype"] == "float64"
        assert "min" in item and "max" in item and "mean" in item and "std" in item
        assert item["tempo_min_bpm"] == 60
        assert item["tempo_max_bpm"] == 120
        assert item["tempo_bin_count"] == 61
        assert item["tempo_resolution_bpm"] == pytest.approx(1.0)
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
        assert TEMPOGRAM_DEFAULTS["fourier"] == (512, 1)
        assert TEMPOGRAM_DEFAULTS["autocorr"] == (512, 1)
        assert TEMPOGRAM_DEFAULTS["cyclic"] == (512, 1)


def _fourier_tempogram_reference(x: np.ndarray, Fs: float, N: int, H: int, Theta: np.ndarray) -> np.ndarray:
    """Reference implementation (full-length exponential) for numerical equivalence testing."""
    win = np.hanning(N)
    N_left = N // 2
    L_left = N_left
    L_right = N_left
    L_pad = x.shape[0] + L_left + L_right
    x_pad = np.concatenate((np.zeros(L_left), x, np.zeros(L_right)))
    t_pad = np.arange(L_pad)
    M = int(np.floor(L_pad - N) / H) + 1
    K = len(Theta)
    X = np.zeros((K, M), dtype=np.complex128)
    for k in range(K):
        omega = (Theta[k] / 60) / Fs
        exponential = np.exp(-2 * np.pi * 1j * omega * t_pad)
        x_exp = x_pad * exponential
        for n in range(M):
            t_0 = n * H
            t_1 = t_0 + N
            X[k, n] = np.sum(win * x_exp[t_0:t_1])
    return X


class TestComputeTempogramFourier:
    """Unit tests for compute_tempogram_fourier numerical correctness."""

    def test_fourier_matches_reference(self) -> None:
        """Optimized implementation matches reference within tolerance."""
        np.random.seed(42)
        x = np.clip(np.random.randn(200).astype(np.float64) * 0.1 + 0.5, 0, 1)
        Fs = 100.0
        N = 64
        H = 8
        Theta = np.arange(60, 121, dtype=float)

        X_opt, T_coef, F_coef = compute_tempogram_fourier(x, Fs, N, H, Theta)
        X_ref = _fourier_tempogram_reference(x, Fs, N, H, Theta)

        np.testing.assert_allclose(X_opt.real, X_ref.real, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(X_opt.imag, X_ref.imag, rtol=1e-10, atol=1e-10)
