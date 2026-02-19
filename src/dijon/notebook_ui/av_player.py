"""Audio + playback-cursor widget rendering for notebooks."""

from __future__ import annotations

import base64
import io
import uuid
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import HTML, display
from scipy.io import wavfile


@dataclass(frozen=True)
class AvPlayerHandle:
    """Returned handle for debugging/tests and downstream introspection."""

    widget_id: str
    html: str


def _validate_inputs(
    x: np.ndarray,
    sr: int,
    fig,
    ax,
    max_duration_sec: float,
) -> float:
    """Validate core inputs and return duration in seconds."""
    if sr <= 0:
        raise ValueError("Sample rate must be > 0.")

    if x.ndim != 1:
        raise ValueError("Audio must be mono (1D).")

    if (fig is None) ^ (ax is None):
        raise ValueError("Provide both fig and ax, or neither.")

    duration_s = len(x) / sr
    if duration_s > max_duration_sec:
        raise ValueError(
            f"Audio duration {duration_s:.2f}s exceeds max_duration_sec={max_duration_sec}."
        )

    return duration_s


def _render_plot_png_and_bounds(
    x: np.ndarray,
    sr: int,
    duration_s: float,
    fig,
    ax,
    close_fig: bool,
) -> tuple[str, float, float, float, float]:
    """Render plot image and return base64 PNG plus cursor mapping bounds."""
    created_fig = fig is None and ax is None
    if created_fig:
        fig, ax = plt.subplots(figsize=(12, 3))
        t = np.arange(len(x)) / sr
        ax.plot(t, x, color="#c0c0c0", linewidth=0.7, label="Waveform")
        ax.set_ylabel("Amplitude", color="#c0c0c0")
        ax.set_xlabel("Time (s)")
        ax.set_xlim(0, duration_s)
        ax.tick_params(axis="y", labelcolor="#c0c0c0")
        ax.set_title("Waveform")
        plt.tight_layout()

    fig.canvas.draw()
    bbox = ax.get_position()
    plot_left = bbox.x0
    plot_right = bbox.x1
    plot_top_pct = (1 - bbox.y1) * 100
    plot_bottom_pct = bbox.y0 * 100

    fig_buf = io.BytesIO()
    # Keep default bbox mapping; tight bbox changes cursor coordinates.
    fig.savefig(fig_buf, format="png", dpi=150)
    fig_buf.seek(0)
    fig_b64 = base64.b64encode(fig_buf.read()).decode()

    if created_fig or close_fig:
        plt.close(fig)

    return fig_b64, plot_left, plot_right, plot_top_pct, plot_bottom_pct


def _encode_wav_base64(x: np.ndarray, sr: int) -> str:
    """Encode mono float waveform as base64 WAV."""
    audio_buf = io.BytesIO()
    x_int16 = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    wavfile.write(audio_buf, sr, x_int16)
    audio_buf.seek(0)
    return base64.b64encode(audio_buf.read()).decode()


def _build_html(
    *,
    widget_id: str,
    fig_b64: str,
    audio_b64: str,
    duration_s: float,
    plot_left: float,
    plot_right: float,
    plot_top_pct: float,
    plot_bottom_pct: float,
    cursor_color: str,
) -> str:
    """Build self-contained HTML/JS for audio + synchronized cursor."""
    audio_id = f"{widget_id}-audio"
    cursor_id = f"{widget_id}-cursor"

    return f"""
<audio id="{audio_id}" controls style="width:100%; margin-bottom:12px;">
  <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
</audio>
<div style="position:relative; display:inline-block; width:100%;">
  <img src="data:image/png;base64,{fig_b64}" style="width:100%; display:block; vertical-align:top;">
  <div id="{cursor_id}" style="position:absolute; top:{plot_top_pct}%; left:0; bottom:{plot_bottom_pct}%; width:3px; background:{cursor_color}; pointer-events:none; z-index:10; box-shadow:0 0 4px rgba(0,0,0,0.3);"></div>
</div>
<script>
(function() {{
  var audio = document.getElementById('{audio_id}');
  var cursor = document.getElementById('{cursor_id}');
  var duration = {duration_s};
  var plotLeft = {plot_left};
  var plotRight = {plot_right};
  var rafId;

  audio.addEventListener('loadedmetadata', function() {{
    if (Number.isFinite(audio.duration) && audio.duration > 0) {{
      duration = audio.duration;
    }}
    updateCursor();
  }});

  function updateCursor() {{
    var t = Math.min(duration, Math.max(0, audio.currentTime));
    var frac = duration > 0 ? (t / duration) : 0;
    var pct = (plotLeft + (plotRight - plotLeft) * frac) * 100;
    cursor.style.left = pct + '%';
  }}

  function loop() {{
    updateCursor();
    if (!audio.paused && !audio.ended) rafId = requestAnimationFrame(loop);
  }}

  audio.addEventListener('play', function() {{ loop(); }});
  audio.addEventListener('pause', function() {{
    if (rafId) cancelAnimationFrame(rafId);
    updateCursor();
  }});
  audio.addEventListener('ended', function() {{
    if (rafId) cancelAnimationFrame(rafId);
    updateCursor();
  }});
  audio.addEventListener('seeked', updateCursor);
  updateCursor();
}})();
</script>
"""


def build_audio_with_cursor_html(
    x,
    sr,
    fig=None,
    ax=None,
    *,
    max_duration_sec=60,
    cursor_color="#e74c3c",
    close_fig=False,
) -> AvPlayerHandle:
    """Build HTML for an audio player with synchronized cursor (no display).

    Same contract as display_audio_with_cursor but only returns the handle;
    use this when combining multiple players into one layout (e.g. side by side).
    """
    x_arr = np.asarray(x)
    duration_s = _validate_inputs(x_arr, int(sr), fig, ax, max_duration_sec)
    widget_id = uuid.uuid4().hex[:12]

    fig_b64, plot_left, plot_right, plot_top_pct, plot_bottom_pct = _render_plot_png_and_bounds(
        x_arr, int(sr), duration_s, fig, ax, close_fig
    )
    audio_b64 = _encode_wav_base64(x_arr, int(sr))

    html = _build_html(
        widget_id=widget_id,
        fig_b64=fig_b64,
        audio_b64=audio_b64,
        duration_s=duration_s,
        plot_left=plot_left,
        plot_right=plot_right,
        plot_top_pct=plot_top_pct,
        plot_bottom_pct=plot_bottom_pct,
        cursor_color=cursor_color,
    )
    return AvPlayerHandle(widget_id=widget_id, html=html)


def display_audio_with_cursor(
    x,
    sr,
    fig=None,
    ax=None,
    *,
    max_duration_sec=60,
    cursor_color="#e74c3c",
    close_fig=False,
) -> AvPlayerHandle:
    """Display an audio player with a synchronized vertical playback cursor.

    Args:
        x: Mono waveform samples (1D array-like).
        sr: Sample rate (Hz).
        fig: Optional matplotlib Figure (requires ax as well).
        ax: Optional matplotlib Axes (requires fig as well).
        max_duration_sec: Duration hard limit.
        cursor_color: CSS color string for cursor bar.
        close_fig: Close provided figure after rendering when True.

    Returns:
        AvPlayerHandle containing the widget_id and generated HTML.
    """
    handle = build_audio_with_cursor_html(
        x, sr, fig=fig, ax=ax,
        max_duration_sec=max_duration_sec,
        cursor_color=cursor_color,
        close_fig=close_fig,
    )
    display(HTML(handle.html))
    return handle
