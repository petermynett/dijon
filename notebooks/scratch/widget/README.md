# Temporal Widget (Experimental)

Interactive notebook for the novelty → tempogram → beat track → beats & bars pipeline.

## Layout

- **Split widgets** (top): Novelty, Tempogram, Beats — stacked **vertically**. Each has its own controls, plots, audio player, and zoom. Novelty and tempogram params **live update** (cache lookup); beats params also live update.
- **Combined widget** (bottom): Full pipeline in one place, independent of the split widgets.

## Split Widgets (Cascade)

1. **Novelty**: Computes novelty from audio. Recompute updates `_nov_state`. Output feeds Tempogram.
2. **Tempogram**: Reads novelty from Novelty widget. Recompute updates `_temp_state`. Output feeds Beats.
3. **Beats**: Reads novelty + tempogram. Factor, tempo override, beats-per-bar are **live** (fast path). Recompute runs beat tracking + bars.

**Workflow**: Tweak Novelty (live) → Tempogram updates automatically → Tweak Tempogram (live) → Beats updates automatically → Tweak Beats (live params update immediately).

## Usage

1. Open `temporal_widget.ipynb` in Jupyter.
2. Run all cells top to bottom. Eager precompute runs at startup (full 896 novelty grid + tempogram variants; shared-STFT optimization).
3. **Live controls** (precomputed): novelty method, hop, gamma, local avg; tempogram method, window (s), hop (s). Changes hit cache for instant updates.
4. **Tempo range** (40–320 BPM): fixed constants in `temporal_widget_helpers.py` (`DEFAULT_TEMPO_MIN`, `DEFAULT_TEMPO_MAX`); not user-configurable in the notebook.
5. **Live controls** (fast path, Beats widget only): factor, tempo override, beats-per-bar. Changes trigger downstream-only recompute.
6. **Zoom**: Level 1–10 (1 = fully zoomed out, 10 = max zoom in). Enable "Zoom on playhead" so analysis plots center on playback cursor; waveform players stay full-width.
7. **Audio**: Each widget has original waveform + cursor. Beats widget adds optional beat sonification (clicks + accented downbeats). Audio HTML is cached by content hash to avoid regeneration when unchanged.

## Controls

- **Tempo override**: When 0 (or empty), tempo is estimated from the tempogram. Set a nonzero value (e.g. 120) to force that tempo for beat tracking instead of the estimated one. Useful when auto-estimated tempo is wrong.
- **Recompute**: Runs the full pipeline (novelty → tempogram → beat track → bars). Novelty and tempogram params live-update from cache; factor, tempo override, and beats-per-bar use a fast path (beat tracking + bars only).
- **Defaults**: Editable defaults below Zoom. **RESET** applies current defaults to parameters and recomputes. **SET TO DEFAULT** saves current parameter values as the new defaults and recomputes. **Reset to factory** restores original defaults and applies them.

## Scope

- All code lives under `notebooks/scratch/widget/` — no changes to `src/`.
- Default input: `data/datasets/raw/audio/YTB-005.wav`. Set `MARKER` to a segment name (e.g. `HEAD_IN`) or leave blank for full track.
- Requires `HEAD_IN_START` in markers for bar labeling.
