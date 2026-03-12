"""Tests for tempogram pipeline and CLI behavior."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from dijon.tempogram import (
    compute_cyclic_tempogram,
    compute_tempogram_autocorr,
    compute_tempogram_fourier,
)
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

    def test_resolve_novelty_files_shorthand_track_id(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        nov_dir.mkdir()
        (nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy").touch()
        got = _resolve_novelty_files([Path("YTB-014")], nov_dir)
        assert len(got) == 1
        assert got[0].name == "YTB-014_novelty_spectrum_1024-256-100.0-10.npy"

    def test_resolve_novelty_files_shorthand_ambiguous_raises(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        nov_dir.mkdir()
        (nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy").touch()
        (nov_dir / "YTB-014_novelty_energy_2048-512-10.0-0.npy").touch()
        with pytest.raises(ValueError, match="Ambiguous shorthand"):
            _resolve_novelty_files([Path("YTB-014")], nov_dir)

    def test_resolve_novelty_files_explicit_path_preserved(self, tmp_path: Path) -> None:
        nov_dir = tmp_path / "novelty"
        other_dir = tmp_path / "other"
        nov_dir.mkdir()
        other_dir.mkdir()
        explicit = other_dir / "custom.npy"
        explicit.touch()
        got = _resolve_novelty_files([explicit], nov_dir)
        assert len(got) == 1
        assert got[0].name == "custom.npy"
        assert got[0].parent == other_dir.resolve()


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

    def test_run_tempogram_with_shorthand_track_id(self, tmp_path: Path) -> None:
        """Shorthand YTB-014 resolves to matching novelty in novelty_dir."""
        nov_dir = tmp_path / "novelty"
        out_dir = tmp_path / "tempogram"
        nov_dir.mkdir()
        nov = np.clip(np.random.randn(500).astype(np.float64) * 0.1 + 0.5, 0, 1)
        np.save(nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy", nov)

        result = run_tempogram(
            novelty_files=[Path("YTB-014")],
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
        assert (out_dir / "YTB-014_tempogram_fourier_100-10-60-120.npy").exists()

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

    def test_run_tempogram_skip_if_exists_skips_computation(self, tmp_path: Path) -> None:
        """When skip_if_exists=True and output exists, skip recomputation."""
        nov_dir = tmp_path / "novelty"
        out_dir = tmp_path / "tempogram"
        nov_dir.mkdir()
        out_dir.mkdir()
        nov = np.clip(np.random.randn(500).astype(np.float64) * 0.1 + 0.5, 0, 1)
        np.save(nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy", nov)

        result1 = run_tempogram(
            novelty_files=[nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy"],
            output_dir=out_dir,
            novelty_dir=nov_dir,
            ntype="fourier",
            N=100,
            H=10,
            theta_min=60,
            theta_max=120,
            dry_run=False,
        )
        assert result1["success"] is True
        assert result1["succeeded"] == 1
        assert result1["skipped"] == 0

        result2 = run_tempogram(
            novelty_files=[nov_dir / "YTB-014_novelty_spectrum_1024-256-100.0-10.npy"],
            output_dir=out_dir,
            novelty_dir=nov_dir,
            ntype="fourier",
            N=100,
            H=10,
            theta_min=60,
            theta_max=120,
            dry_run=False,
            skip_if_exists=True,
        )
        assert result2["success"] is True
        assert result2["succeeded"] == 0
        assert result2["skipped"] == 1
        assert result2["items"][0]["status"] == "skipped"
        assert result2["items"][0]["detail"] == "Output exists"

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


class TestTempogramRegression:
    """Numeric regression tests for saved pipeline outputs."""

    def test_autocorr_regression(self) -> None:
        """Autocorr output shape and anchor values on deterministic input."""
        np.random.seed(123)
        x = np.clip(np.random.randn(300).astype(np.float64) * 0.1 + 0.5, 0, 1)
        Fs, N, H = 100.0, 64, 8
        Theta = np.arange(60, 121, dtype=float)

        out, _T, _F = compute_tempogram_autocorr(x, Fs, N, H, Theta=Theta)

        assert out.shape == (61, 38)
        assert out.dtype == np.float64
        np.testing.assert_allclose(out[0, 0], 0.0, atol=1e-10)
        np.testing.assert_allclose(out.min(), -9.818965301039668, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(out.max(), 3.9863013490104655, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(out.mean(), -0.5327567879030604, rtol=1e-9, atol=1e-9)

    def test_cyclic_regression(self) -> None:
        """Cyclic output shape and anchor values on deterministic input."""
        np.random.seed(123)
        x = np.clip(np.random.randn(300).astype(np.float64) * 0.1 + 0.5, 0, 1)
        Fs, N, H = 100.0, 64, 8
        Theta = np.arange(60, 121, dtype=float)

        X, _T, F_coef = compute_tempogram_fourier(x, Fs, N, H, Theta)
        mag = np.abs(X)
        out, _scale = compute_cyclic_tempogram(mag, F_coef)

        assert out.shape == (40, 38)
        assert out.dtype == np.float64
        np.testing.assert_allclose(out[0, 0], 4.3303997198664055, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(out[0, -1], 4.556043689524867, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(out.min(), -16.520550887997505, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(out.max(), 4.677247051965587, rtol=1e-9, atol=1e-9)

    def test_fourier_saved_output_shape_and_stats(self, tmp_path: Path) -> None:
        """Saved fourier magnitude has expected shape and stats on deterministic input."""
        np.random.seed(456)
        nov = np.clip(np.random.randn(200).astype(np.float64) * 0.1 + 0.5, 0, 1)
        nov_dir = tmp_path / "novelty"
        out_dir = tmp_path / "tempogram"
        nov_dir.mkdir()
        np.save(nov_dir / "regress.npy", nov)

        result = run_tempogram(
            novelty_files=[nov_dir / "regress.npy"],
            output_dir=out_dir,
            novelty_dir=nov_dir,
            ntype="fourier",
            N=64,
            H=8,
            theta_min=60,
            theta_max=120,
            dry_run=False,
        )
        assert result["success"] is True
        arr = np.load(out_dir / "regress_tempogram_fourier_64-8-60-120.npy")
        assert arr.ndim == 2
        assert arr.dtype == np.float64
        assert arr.shape[0] == 61
        assert arr.shape[1] == 26
        assert arr.min() >= 0
        np.testing.assert_allclose(arr.mean(), float(result["items"][0]["mean"]), rtol=1e-10)


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


class TestTempogramBenchmark:
    """Lightweight runtime benchmarks for fourier/autocorr/cyclic tempogram."""

    @pytest.mark.slow
    def test_tempogram_runtime_benchmark(self) -> None:
        """Benchmark fourier, autocorr, cyclic on representative novelty lengths."""
        Fs = 100.0
        N = 512
        H = 1
        Theta = np.arange(40, 321, dtype=float)
        np.random.seed(42)

        sizes = [1000, 5000, 15000]
        results: list[dict] = []

        for n_samples in sizes:
            x = np.clip(np.random.randn(n_samples).astype(np.float64) * 0.1 + 0.5, 0, 1)
            row: dict = {"n_samples": n_samples}

            t0 = time.perf_counter()
            compute_tempogram_fourier(x, Fs, N, H, Theta)
            row["fourier_sec"] = time.perf_counter() - t0

            t0 = time.perf_counter()
            compute_tempogram_autocorr(x, Fs, N, H, Theta=Theta)
            row["autocorr_sec"] = time.perf_counter() - t0

            t0 = time.perf_counter()
            X, _T, F_coef = compute_tempogram_fourier(x, Fs, N, H, Theta)
            mag = np.abs(X)
            compute_cyclic_tempogram(mag, F_coef)
            row["cyclic_sec"] = time.perf_counter() - t0

            results.append(row)

        for r in results:
            assert r["fourier_sec"] >= 0 and r["autocorr_sec"] >= 0 and r["cyclic_sec"] >= 0
