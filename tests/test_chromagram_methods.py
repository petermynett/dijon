"""Tests for chromagram methods (preprocess, tuning, weighted weighting)."""

from __future__ import annotations

import numpy as np
import pytest

from dijon.chromagram import methods


def _simple_meter_map(duration: float) -> np.ndarray:
    return np.asarray(
        [
            [0.0, 1.0, 1.0],
            [duration / 2.0, 1.0, 2.0],
            [duration, 1.0, 3.0],
        ],
        dtype=np.float64,
    )


def test_preprocess_audio_for_chroma_none_passthrough() -> None:
    y = np.asarray([0.1, -0.2, 0.3], dtype=np.float64)
    out = methods._preprocess_audio_for_chroma(y, preprocess="none")
    assert out is y


def test_preprocess_audio_for_chroma_harmonic(monkeypatch: pytest.MonkeyPatch) -> None:
    y = np.asarray([0.1, -0.2, 0.3], dtype=np.float64)
    expected = np.asarray([1.0, 2.0, 3.0], dtype=np.float64)

    calls: list[np.ndarray] = []

    def fake_harmonic(arg: np.ndarray) -> np.ndarray:
        calls.append(arg)
        return expected

    monkeypatch.setattr(methods.librosa.effects, "harmonic", fake_harmonic)

    out = methods._preprocess_audio_for_chroma(y, preprocess="harmonic")

    assert calls and calls[0] is y
    assert np.array_equal(out, expected)


def test_preprocess_audio_for_chroma_invalid_mode() -> None:
    y = np.asarray([0.1, -0.2, 0.3], dtype=np.float64)
    with pytest.raises(ValueError, match='preprocess must be "none" or "harmonic"'):
        methods._preprocess_audio_for_chroma(y, preprocess="invalid")


def test_compute_frame_chroma_cqt_forwards_tuning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    y = np.ones(16, dtype=np.float64)
    captured: dict[str, object] = {}

    def fake_chroma_cqt(
        *,
        y: np.ndarray,
        sr: int,
        hop_length: int,
        tuning: float | None = None,
    ) -> np.ndarray:
        captured["y"] = y
        captured["sr"] = sr
        captured["hop_length"] = hop_length
        captured["tuning"] = tuning
        return np.ones((12, 5), dtype=np.float64)

    monkeypatch.setattr(methods.librosa.feature, "chroma_cqt", fake_chroma_cqt)

    C = methods._compute_frame_chroma(
        y,
        sr=22050,
        hop_length=256,
        chroma_type="cqt",
        tuning=0.25,
    )

    assert C.shape == (12, 5)
    assert captured["y"] is y
    assert captured["sr"] == 22050
    assert captured["hop_length"] == 256
    assert captured["tuning"] == 0.25


def test_compute_frame_chroma_stft_does_not_require_tuning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    y = np.ones(16, dtype=np.float64)
    captured: dict[str, object] = {}

    def fake_chroma_stft(
        *,
        y: np.ndarray,
        sr: int,
        hop_length: int,
    ) -> np.ndarray:
        captured["y"] = y
        captured["sr"] = sr
        captured["hop_length"] = hop_length
        return np.ones((12, 4), dtype=np.float64)

    monkeypatch.setattr(methods.librosa.feature, "chroma_stft", fake_chroma_stft)

    C = methods._compute_frame_chroma(
        y,
        sr=16000,
        hop_length=128,
        chroma_type="stft",
        tuning=0.4,
    )

    assert C.shape == (12, 4)
    assert captured["y"] is y
    assert captured["sr"] == 16000
    assert captured["hop_length"] == 128


def test_metric_chromagram_weighted_uses_original_audio_for_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Use sr=8, hop_length=1, duration=1.0 so subdivision boundaries map to distinct
    # frame indices (9 boundaries -> frames 0..8) and avoid "collapsed boundaries" error.
    n_samples = 8
    y = np.asarray([0.5, -0.25, 0.75, -0.5] * 2, dtype=np.float64)[:n_samples]
    y_harmonic = np.ones(n_samples, dtype=np.float64) * 99.0
    meter_map = _simple_meter_map(duration=n_samples / 8.0)

    preprocess_calls: list[np.ndarray] = []
    chroma_inputs: list[np.ndarray] = []
    weight_inputs: list[np.ndarray] = []

    def fake_preprocess_audio_for_chroma(
        y_in: np.ndarray,
        *,
        preprocess: str,
    ) -> np.ndarray:
        assert preprocess == "harmonic"
        preprocess_calls.append(y_in)
        return y_harmonic

    def fake_compute_frame_chroma(
        y_in: np.ndarray,
        *,
        sr: int,
        hop_length: int,
        chroma_type: str,
        tuning: float | None = None,
    ) -> np.ndarray:
        chroma_inputs.append(y_in)
        return np.ones((12, 9), dtype=np.float64)

    def fake_compute_frame_weights(
        y_in: np.ndarray,
        *,
        sr: int,
        hop_length: int,
        weight_source: str,
        weight_power: float,
        n_frames: int,
    ) -> np.ndarray:
        weight_inputs.append(y_in)
        return np.ones(n_frames, dtype=np.float64)

    monkeypatch.setattr(
        methods,
        "_preprocess_audio_for_chroma",
        fake_preprocess_audio_for_chroma,
    )
    monkeypatch.setattr(methods, "_compute_frame_chroma", fake_compute_frame_chroma)
    monkeypatch.setattr(methods, "_compute_frame_weights", fake_compute_frame_weights)

    C_metric = methods.metric_chromagram(
        y,
        sr=8,
        meter_map=meter_map,
        hop_length=1,
        chroma_type="cqt",
        preprocess="harmonic",
        tuning=0.1,
        accent_mode="weighted",
        aggregate="mean",
        min_frames_per_bin=1,
    )

    assert C_metric.shape[0] == 12
    assert preprocess_calls and np.array_equal(preprocess_calls[0], y)
    assert chroma_inputs and np.array_equal(chroma_inputs[0], y_harmonic)
    assert weight_inputs and np.array_equal(weight_inputs[0], y)
    assert not np.array_equal(weight_inputs[0], y_harmonic)
