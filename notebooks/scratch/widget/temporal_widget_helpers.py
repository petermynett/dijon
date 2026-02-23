"""Re-exports from widget_common, widget_novelty, widget_tempogram, widget_beats_audio.

Keeps notebook imports working. Implementation lives in the four discrete modules.
"""

from __future__ import annotations

# Ensure common is loaded first (path setup)
from widget_common import (
    DEFAULT_TEMPO_MAX,
    DEFAULT_TEMPO_MIN,
    FS_NOV,
    GAMMA_OPTIONS,
    HOP_OPTIONS,
    HOP_SEC_OPTIONS,
    LOCAL_M_OPTIONS,
    NOVELTY_DEFAULTS,
    WINDOW_SEC_OPTIONS,
    get_head_in_time,
    load_audio_and_markers,
    zoom_level_to_half_sec,
)
from widget_novelty import (
    eager_compute_all,
    eager_compute_novelty,
    get_novelty_for_method,
    novelty_params_key,
    resample_novelty_to_100hz,
)
from widget_tempogram import (
    compute_tempogram,
    eager_compute_tempogram,
    get_tempogram_for_methods,
    tempo_from_tempogram,
)
from widget_beats_audio import (
    build_audio_with_waveform_html,
    build_beat_sonification_audio,
    eager_compute_beats,
    run_beat_tracking,
    run_beats_and_bars,
)

__all__ = [
    "DEFAULT_TEMPO_MAX",
    "DEFAULT_TEMPO_MIN",
    "FS_NOV",
    "GAMMA_OPTIONS",
    "HOP_OPTIONS",
    "HOP_SEC_OPTIONS",
    "LOCAL_M_OPTIONS",
    "NOVELTY_DEFAULTS",
    "WINDOW_SEC_OPTIONS",
    "build_audio_with_waveform_html",
    "build_beat_sonification_audio",
    "compute_tempogram",
    "eager_compute_all",
    "eager_compute_beats",
    "eager_compute_novelty",
    "eager_compute_tempogram",
    "get_head_in_time",
    "get_novelty_for_method",
    "get_tempogram_for_methods",
    "load_audio_and_markers",
    "novelty_params_key",
    "resample_novelty_to_100hz",
    "run_beat_tracking",
    "run_beats_and_bars",
    "tempo_from_tempogram",
    "zoom_level_to_half_sec",
]
