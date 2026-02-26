# README.md

# DIJON
MIR pipeline for comparative harmonic and formal analysis and visualization.


## Repository:
https://github.com/petermynett/dijon

## Paper:
docs/paper/main.pdf

## Google Colab
https://colab.research.google.com/github/petermynett/dijon/blob/main/notebooks/00_setup.ipynb

## CLI – novelty

Compute novelty functions from raw audio and write `.npy` files to `data/derived/novelty`:

```bash
# Default: spectrum novelty for all .wav in data/datasets/raw/audio (N=1024, H=256, gamma=100, M=10)
dijon novelty

# One type, default params for that type
dijon novelty --type energy
dijon novelty -t phase
dijon novelty -t complex

# Override parameters
dijon novelty --type spectrum --n 2048 --h 128
dijon novelty -t energy --gamma 5.0 --m 0

# Specific file(s) only
dijon novelty path/to/audio.wav
dijon novelty data/datasets/raw/audio/YTB-001.wav data/datasets/raw/audio/YTB-002.wav

# Preview without writing (dry-run)
dijon novelty --dry-run
```

Output filenames: `<track-name>_novelty_<type>_<N>-<H>-<gamma>-<M>.npy`. Same parameters overwrite; different parameters produce different files. All novelty outputs are at **100 Hz** (resampling is done inside the novelty methods).

## CLI – tempogram

Compute tempograms from novelty `.npy` files (assumed 100 Hz) and write to `data/derived/tempogram`:

```bash
# Default: fourier tempogram for all .npy in data/derived/novelty (N=500, H=1, theta 40–320 BPM)
dijon tempogram

# Types: fourier, autocorr, cyclic (cyclic is computed from fourier in the same run)
dijon tempogram --type autocorr
dijon tempogram -t cyclic

# Override N, H, theta range
dijon tempogram --type fourier --n 300 --h 1 --theta-min 60 --theta-max 200

# Specific novelty file(s) only
dijon tempogram data/derived/novelty/YTB-001_novelty_spectrum_1024-256-100.0-10.npy

# Dry-run
dijon tempogram --dry-run
```

Output filenames: `<track_name>_tempogram_<type>_<N>-<H>-<theta_min>-<theta_max>.npy` (track name is parsed from the novelty filename, e.g. `YTB-001_novelty_spectrum_...` → `YTB-001`).

## CLI – beats

Compute beat times from tempogram and novelty `.npy` files and write to `data/derived/beats`:

```bash
# Default: all .npy in data/derived/tempogram (matches novelty by track name)
dijon beats

# Override factor, theta range
dijon beats --factor 1.0 --theta-min 40 --theta-max 320

# Specific tempogram file(s) only
dijon beats data/derived/tempogram/YTB-001_tempogram_fourier_500-1-40-320.npy

# Dry-run
dijon beats --dry-run
```

Output filenames: `<track_name>_beats.npy`. Tracks without matching novelty are skipped.

## CLI – meter

Compute meter labels (bar/beat numbers) from beats `.npy` and write to `data/derived/meter`:

```bash
# Default: all .npy in data/derived/beats (requires HEAD_IN_START marker and raw audio)
dijon meter

# Specific beats file(s) only
dijon meter data/derived/beats/YTB-001_beats.npy

# Dry-run
dijon meter --dry-run
```

Output filenames: `<track_name>_meter.npy`. Tracks without `HEAD_IN_START` marker are skipped.

## CLI – chromagram

Compute metric-aligned chromagrams from raw audio and meter `.npy` files and write to `data/derived/chromagram`:

```bash
# Default: all .wav in data/datasets/raw/audio
dijon chromagram

# Choose chroma backend
dijon chromagram --chroma-type cqt
dijon chromagram --chroma-type stft

# Adaptive subdivision + aggregation controls
dijon chromagram --bpm-threshold 180 --aggregate mean --accent-mode preserve
dijon chromagram --accent-mode normalize
dijon chromagram --accent-mode weighted --weight-source onset --weight-power 1.5

# Frame-bin strictness
dijon chromagram --hop-length 256 --min-frames-per-bin 2

# Specific audio file(s) only
dijon chromagram data/datasets/raw/audio/YTB-005.wav

# Dry-run
dijon chromagram --dry-run
```

Input meter files are expected in `data/derived/meter` as `<track_name>_meter.npy` with columns `[time_sec, bar_number, beat_number]`.  
Output files are metric chromagrams `(12, M)` saved as `.npy`, with parameterized filenames.

## CLI – clean

Remove derived data and logs:

```bash
# Empty data/derived subdirs (novelty, tempogram, beats, meter, chromagram) and delete data/logs/derived
dijon clean derived

# Preview without deleting
dijon clean derived --dry-run
```

## Google Drive (currently set to false)
```python
from google.colab import drive
drive.mount('/content/drive')

