"""Beat tracking, bar labeling, sonification, and waveform+audio HTML for temporal widgets."""

from __future__ import annotations

import base64
import hashlib
import io
import time
import uuid
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

from widget_common import FS_NOV

from dijon.beats import (
    compute_beat_energies,
    compute_beat_sequence,
    estimate_beats_per_bar,
    label_bars_and_beats,
)


def run_beat_tracking(
    nov_100: np.ndarray,
    tempo_bpm: float,
    factor: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run DP beat tracking. Returns (B_indices, D, P)."""
    beat_ref = int(np.round(FS_NOV * 60.0 / tempo_bpm))
    B, D, P = compute_beat_sequence(nov_100, beat_ref=beat_ref, factor=factor, return_all=True)
    return B, D, P


def run_beats_and_bars(
    beat_times: np.ndarray,
    head_in_time_sec: float,
    x: np.ndarray,
    sr: int,
    beats_per_bar_override: int | None = None,
) -> tuple[np.ndarray, int, np.ndarray, np.ndarray]:
    """Run meter inference and bar labeling.

    Returns (labels, beats_per_bar, low_energy, high_energy).
    """
    if beats_per_bar_override is not None:
        low_energy, high_energy = compute_beat_energies(beat_times, x, sr)
        labels = label_bars_and_beats(beat_times, head_in_time_sec, beats_per_bar_override)
        return labels, beats_per_bar_override, low_energy, high_energy
    beats_per_bar, low_energy, high_energy = estimate_beats_per_bar(
        beat_times, head_in_time_sec, x, sr
    )
    labels = label_bars_and_beats(beat_times, head_in_time_sec, beats_per_bar)
    return labels, beats_per_bar, low_energy, high_energy


def eager_compute_beats(
    nov_100: np.ndarray,
    tempo_bpm: float,
    head_in_time_sec: float,
    x: np.ndarray,
    sr: int,
    *,
    factor: float = 1.0,
    beats_per_bar_override: int | None = None,
) -> tuple[dict[str, Any], float, dict[str, float]]:
    """Eagerly compute default beat state for one novelty/tempogram input.

    Returns (beat_state, total_time_s, timings).
    """
    t0 = time.perf_counter()
    B, _, _ = run_beat_tracking(nov_100, tempo_bpm, factor=factor)
    beat_times = B / FS_NOV
    labels, beats_per_bar, _, _ = run_beats_and_bars(
        beat_times,
        head_in_time_sec,
        x,
        sr,
        beats_per_bar_override=beats_per_bar_override,
    )
    elapsed = time.perf_counter() - t0
    state = {
        "B": B,
        "beat_times": beat_times,
        "labels": labels,
        "beats_per_bar": beats_per_bar,
        "nov_100": nov_100,
    }
    timings = {"beats_default": elapsed, "total": elapsed}
    return state, elapsed, timings


def build_beat_sonification_audio(
    x: np.ndarray,
    sr: int,
    beat_times: np.ndarray,
    labels: np.ndarray,
    beats_per_bar: int,
    head_in_time_sec: float,
    *,
    click_amp: float = 0.3,
    downbeat_amp: float = 0.6,
    click_duration_ms: float = 10.0,
) -> np.ndarray:
    """Mix original audio with beat clicks (accented downbeats).

    Args:
        x: Mono waveform.
        sr: Sample rate.
        beat_times: Beat onset times in seconds.
        labels: Nx3 array (time_sec, bar_number, beat_number).
        beats_per_bar: Beats per bar.
        head_in_time_sec: Anchor time for bar 1 beat 1.
        click_amp: Amplitude of regular beat clicks.
        downbeat_amp: Amplitude of downbeat clicks.
        click_duration_ms: Click length in ms.

    Returns:
        Mono float array (original + clicks), same length as x.
    """
    out = np.copy(x).astype(np.float64)
    n_samples = len(x)
    click_len = int(sr * click_duration_ms / 1000)
    click_len = max(2, min(click_len, 100))

    is_downbeat = labels[:, 2] == 1
    for i, t_sec in enumerate(beat_times):
        pos = int(t_sec * sr)
        if pos < 0 or pos >= n_samples:
            continue
        amp = downbeat_amp if (i < len(is_downbeat) and is_downbeat[i]) else click_amp
        end = min(pos + click_len, n_samples)
        n_click = end - pos
        if n_click >= 2:
            t_click = np.arange(n_click) / sr
            freq = 1000.0
            click = amp * np.sin(2 * np.pi * freq * t_click) * np.hanning(n_click)
            out[pos:end] = out[pos:end] + click

    return np.clip(out, -1.0, 1.0)


_AUDIO_HTML_CACHE: dict[tuple, str] = {}
_AUDIO_HTML_CACHE_MAX = 8
_PLACEHOLDER_ID = "__WIDGET_ID__"


def _audio_content_key(
    x_waveform: np.ndarray, x_audio: np.ndarray, sr: int, max_duration_sec: float
) -> tuple[Any, ...]:
    wb = x_waveform.data.tobytes()
    ab = x_audio.data.tobytes()
    w_hash = hashlib.md5(wb[: min(65536, len(wb))]).hexdigest()
    a_hash = hashlib.md5(ab[: min(65536, len(ab))]).hexdigest()
    return (w_hash, a_hash, sr, max_duration_sec)


def build_audio_with_waveform_html(
    x_waveform: np.ndarray,
    x_audio: np.ndarray,
    sr: int,
    *,
    max_duration_sec: float = 60,
    cursor_color: str = "#e74c3c",
    widget_id_suffix: str | None = None,
) -> str:
    """Build HTML for audio player + waveform with playback cursor.

    Cursor is positioned after DOM is ready and when duration is valid.
    Deferred init avoids "cursor stuck at left" when script runs before element exists.
    """
    cache_key = _audio_content_key(x_waveform, x_audio, sr, max_duration_sec)
    template = _AUDIO_HTML_CACHE.get(cache_key)
    if template is None:
        duration_s = min(len(x_waveform) / sr, len(x_audio) / sr, max_duration_sec)

        fig, ax = plt.subplots(figsize=(12, 2.5))
        t = np.arange(len(x_waveform)) / sr
        ax.plot(t, x_waveform, color="#888", linewidth=0.6)
        ax.set_ylabel("Amplitude", fontsize=9)
        ax.set_xlabel("Time (s)", fontsize=9)
        ax.set_xlim(0, duration_s)
        ax.tick_params(labelsize=8)
        ax.set_title("Waveform (original)", fontsize=10)
        plt.tight_layout()
        fig.canvas.draw()
        bbox = ax.get_position()
        plot_left, plot_right = bbox.x0, bbox.x1
        plot_top_pct = (1 - bbox.y1) * 100
        plot_bottom_pct = bbox.y0 * 100
        fig_buf = io.BytesIO()
        fig.savefig(fig_buf, format="png", dpi=120)
        fig_buf.seek(0)
        fig_b64 = base64.b64encode(fig_buf.read()).decode()
        plt.close(fig)

        audio_buf = io.BytesIO()
        x_int16 = (np.clip(x_audio, -1, 1) * 32767).astype(np.int16)
        wavfile.write(audio_buf, sr, x_int16)
        audio_buf.seek(0)
        audio_b64 = base64.b64encode(audio_buf.read()).decode()

        # Cursor script: defer setup until wrap exists (notebook may inject HTML async).
        # Only set cursor position when duration is valid so we don't stick at 0.
        template = f"""
<div id="{_PLACEHOLDER_ID}-wrap">
<audio id="{_PLACEHOLDER_ID}-audio" controls style="width:100%; margin-bottom:8px;">
  <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
</audio>
<div style="position:relative; display:inline-block; width:100%;">
  <img src="data:image/png;base64,{fig_b64}" style="width:100%; display:block;">
  <div id="{_PLACEHOLDER_ID}-cursor" style="position:absolute; top:{plot_top_pct}%; left:0; bottom:{plot_bottom_pct}%; width:3px; background:{cursor_color}; pointer-events:none; z-index:10;"></div>
</div>
<script>
(function(){{
  var wrapId = '{_PLACEHOLDER_ID}-wrap';
  var audioId = '{_PLACEHOLDER_ID}-audio';
  var cursorSel = '#{_PLACEHOLDER_ID}-cursor';
  var durationSec = {duration_s};
  var plotLeft = {plot_left};
  var plotRight = {plot_right};
  var rafId;
  function getDuration(audio) {{
    var d = audio.duration;
    return (typeof d === 'number' && Number.isFinite(d) && d > 0) ? d : durationSec;
  }}
  function updateCursor(audio, cursor) {{
    if (!audio || !cursor) return;
    var duration = getDuration(audio);
    var t = Math.min(duration, Math.max(0, audio.currentTime));
    var frac = duration > 0 ? (t / duration) : 0;
    var pct = (plotLeft + (plotRight - plotLeft) * frac) * 100;
    cursor.style.left = pct + '%';
  }}
  function loop(audio, cursor) {{
    updateCursor(audio, cursor);
    if (audio && !audio.paused && !audio.ended) rafId = requestAnimationFrame(function() {{ loop(audio, cursor); }});
  }}
  function init() {{
    var wrap = document.getElementById(wrapId);
    if (!wrap) return false;
    var audio = wrap.querySelector('audio');
    var cursor = wrap.querySelector(cursorSel);
    if (!audio || !cursor) return false;
    audio.addEventListener('loadedmetadata', function() {{ updateCursor(audio, cursor); }});
    audio.addEventListener('play', function() {{ loop(audio, cursor); }});
    audio.addEventListener('pause', function() {{ if (rafId) cancelAnimationFrame(rafId); updateCursor(audio, cursor); }});
    audio.addEventListener('ended', function() {{ if (rafId) cancelAnimationFrame(rafId); updateCursor(audio, cursor); }});
    audio.addEventListener('seeked', function() {{ updateCursor(audio, cursor); }});
    audio.addEventListener('timeupdate', function() {{ updateCursor(audio, cursor); }});
    updateCursor(audio, cursor);
    return true;
  }}
  function tryInit(attempt) {{
    if (init()) return;
    if (attempt < 15) setTimeout(function() {{ tryInit(attempt + 1); }}, attempt * 20);
  }}
  setTimeout(function() {{ tryInit(0); }}, 0);
}})();
</script>
</div>
"""
        if len(_AUDIO_HTML_CACHE) >= _AUDIO_HTML_CACHE_MAX:
            _AUDIO_HTML_CACHE.clear()
        _AUDIO_HTML_CACHE[cache_key] = template

    uid = (widget_id_suffix + "-" if widget_id_suffix else "") + uuid.uuid4().hex[:12]
    return template.replace(_PLACEHOLDER_ID, uid)
