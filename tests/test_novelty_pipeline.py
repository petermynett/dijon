"""Tests for novelty pipeline and CLI behavior."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from dijon.novelty.methods import compute_novelty_spectrum
from dijon.pipeline.novelty import (
    NOVELTY_DEFAULTS,
    NOVELTY_OUTPUT_DIR,
    _output_filename,
    _resolve_audio_files,
    _track_name,
    run_novelty,
)


def _write_minimal_wav(path: Path, sr: int = 22050, duration_sec: float = 0.5) -> None:
    """Write a minimal mono WAV (silence) so librosa can load it."""
    n = int(sr * duration_sec)
    buf = np.zeros(n, dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


class TestNoveltyHelpers:
    """Unit tests for pipeline helpers."""

    def test_track_name_from_path(self) -> None:
        assert _track_name(Path("/foo/bar/YTB-001.wav")) == "YTB-001"
        assert _track_name(Path("a.wav")) == "a"

    def test_output_filename_format(self) -> None:
        name = _output_filename("YTB-001", "spectrum", 1024, 256, 100.0, 10)
        assert name == "YTB-001_novelty_spectrum_1024-256-100.0-10.npy"

    def test_resolve_audio_files_explicit(self, tmp_path: Path) -> None:
        a = tmp_path / "a.wav"
        a.touch()
        b = tmp_path / "b.wav"
        b.touch()
        got = _resolve_audio_files([a, b], tmp_path)
        assert len(got) == 2
        assert got[0].name == "a.wav"
        assert got[1].name == "b.wav"

    def test_resolve_audio_files_default_folder(self, tmp_path: Path) -> None:
        (tmp_path / "one.wav").touch()
        (tmp_path / "two.wav").touch()
        (tmp_path / "manifest.csv").touch()
        got = _resolve_audio_files(None, tmp_path)
        assert len(got) == 2
        names = {p.name for p in got}
        assert names == {"one.wav", "two.wav"}

    def test_resolve_audio_files_empty_folder(self, tmp_path: Path) -> None:
        assert _resolve_audio_files(None, tmp_path) == []

    def test_resolve_audio_files_nonexistent_folder(self, tmp_path: Path) -> None:
        assert _resolve_audio_files(None, tmp_path / "missing") == []


class TestRunNovelty:
    """Integration-style tests for run_novelty (use tmp paths)."""

    def test_run_novelty_writes_npy(self, tmp_path: Path) -> None:
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        out_dir = tmp_path / "novelty"
        _write_minimal_wav(wav_dir / "TRACK01.wav")

        result = run_novelty(
            audio_files=[wav_dir / "TRACK01.wav"],
            output_dir=out_dir,
            raw_audio_dir=wav_dir,
            ntype="spectrum",
            dry_run=False,
        )

        assert result["success"] is True
        assert result["total"] == 1
        assert result["succeeded"] == 1
        assert result["failed"] == 0
        out_file = out_dir / "TRACK01_novelty_spectrum_1024-256-100.0-10.npy"
        assert out_file.exists()
        arr = np.load(out_file)
        assert arr.ndim == 1
        assert arr.dtype == np.float64

    def test_run_novelty_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        out_dir = tmp_path / "novelty"
        _write_minimal_wav(wav_dir / "TRACK02.wav")

        result = run_novelty(
            audio_files=[wav_dir / "TRACK02.wav"],
            output_dir=out_dir,
            raw_audio_dir=wav_dir,
            ntype="spectrum",
            dry_run=True,
        )

        assert result["success"] is True
        assert result["succeeded"] == 1
        assert not out_dir.exists() or not list(out_dir.glob("*.npy"))

    def test_run_novelty_same_params_overwrites(self, tmp_path: Path) -> None:
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        out_dir = tmp_path / "novelty"
        _write_minimal_wav(wav_dir / "TRACK03.wav")

        run_novelty(
            audio_files=[wav_dir / "TRACK03.wav"],
            output_dir=out_dir,
            raw_audio_dir=wav_dir,
            ntype="spectrum",
            dry_run=False,
        )
        out_file = out_dir / "TRACK03_novelty_spectrum_1024-256-100.0-10.npy"
        first_content = np.load(out_file).tobytes()

        run_novelty(
            audio_files=[wav_dir / "TRACK03.wav"],
            output_dir=out_dir,
            raw_audio_dir=wav_dir,
            ntype="spectrum",
            dry_run=False,
        )
        second_content = np.load(out_file).tobytes()
        assert first_content == second_content

    def test_run_novelty_different_params_different_files(self, tmp_path: Path) -> None:
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        out_dir = tmp_path / "novelty"
        _write_minimal_wav(wav_dir / "TRACK04.wav")

        run_novelty(
            audio_files=[wav_dir / "TRACK04.wav"],
            output_dir=out_dir,
            ntype="spectrum",
            N=1024,
            H=256,
            dry_run=False,
        )
        run_novelty(
            audio_files=[wav_dir / "TRACK04.wav"],
            output_dir=out_dir,
            ntype="spectrum",
            N=2048,
            H=512,
            dry_run=False,
        )

        assert (out_dir / "TRACK04_novelty_spectrum_1024-256-100.0-10.npy").exists()
        assert (out_dir / "TRACK04_novelty_spectrum_2048-512-100.0-10.npy").exists()

    def test_run_novelty_unknown_type_fails(self, tmp_path: Path) -> None:
        result = run_novelty(
            audio_files=[],
            output_dir=tmp_path,
            ntype="invalid",
        )
        assert result["success"] is False
        assert "Unknown novelty type" in result["message"]

    def test_run_novelty_no_files_returns_ok_empty_message(self, tmp_path: Path) -> None:
        result = run_novelty(
            audio_files=None,
            output_dir=tmp_path,
            raw_audio_dir=tmp_path,
        )
        assert result["success"] is True
        assert result["total"] == 0
        assert "No audio files" in result["message"]

    def test_defaults_match_spec(self) -> None:
        assert NOVELTY_DEFAULTS["spectrum"] == (1024, 256, 100.0, 10)
        assert NOVELTY_DEFAULTS["energy"] == (2048, 512, 10.0, 0)
        assert NOVELTY_DEFAULTS["phase"] == (1024, 64, 40.0, 10)
        assert NOVELTY_DEFAULTS["complex"] == (1024, 64, 10.0, 40)

    def test_novelty_output_at_100_hz_when_Fs_target_100(self) -> None:
        """With Fs_target=100, output length is duration_sec * 100 (contract)."""
        sr = 22050
        duration_s = 2.0
        x = np.zeros(int(sr * duration_s), dtype=np.float64)
        nov, Fs_out = compute_novelty_spectrum(
            x, Fs=sr, N=1024, H=256, gamma=100.0, M=10, norm=True, Fs_target=100.0
        )
        assert Fs_out == 100.0
        expected_len = int(duration_s * 100)
        assert abs(len(nov) - expected_len) <= 2  # allow small rounding
