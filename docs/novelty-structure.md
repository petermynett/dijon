# Novelty Module Structure Overview

The novelty implementation should live inside a dedicated subpackage under `src/dijon/novelty/`. Rather than placing everything into a single `novelty.py` file, the functionality should be separated into clearly defined modules. This keeps the codebase clean, scalable, and easy to test as the novelty system grows.

At the center is an **orchestrator module**. This is the only public entry point that notebooks or other parts of the project import and call (e.g., `compute_novelty`). It validates inputs (mono, 22050 Hz), manages configuration, computes shared features, calls one or more novelty methods, applies normalization and resampling, combines results via weighted sum, and returns structured output (combined curve plus optional components and debug metadata).

Feature extraction lives in a separate **features module**. It computes the STFT once per call and packages the results (complex spectrum, magnitude, phase) into a shared feature bundle. All novelty methods reuse this bundle, ensuring consistency and avoiding redundant computation.

Individual novelty algorithms (energy, spectral flux, phase-based, complex-domain) live in a **methods module**. These functions are pure: they take the feature bundle and return a novelty curve at their native frame rate. They do not handle resampling or combination logic.

Normalization utilities (robust scaling, max normalization) live in a **normalize module**, while timebase alignment and interpolation logic live in a **resample module**.

This modular design keeps responsibilities clearly separated: methods compute signals, the orchestrator manages the pipeline, and utilities handle shared operations. It prevents a monolithic file, supports future expansion (e.g., subband methods), and keeps the public API minimal and stable.


__init__.py defines what a package exposes when it is imported. You import internal functions (e.g., from orchestrator.py) into __init__.py and list them in __all__, so users can write from dijon.novelty import compute_novelty instead of importing from deeper modules. Everything not re-exported remains internal to the package structure.


src/
└── dijon/
    ├── __init__.py
    └── novelty/
        ├── __init__.py          # Exposes public API (e.g., compute_novelty)
        ├── orchestrator.py      # Public entry point + pipeline logic
        ├── features.py          # STFT + FeatureBundle definition
        ├── methods.py           # energy, spectral, phase, complex implementations
        ├── normalize.py         # robust_norm, max_norm, etc.
        └── resample.py          # resampling + optional smoothing utilities


