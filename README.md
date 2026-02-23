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

## Google Drive (currently set to false)
```python
from google.colab import drive
drive.mount('/content/drive')

