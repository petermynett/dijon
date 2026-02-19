"""Novelty signal computation package."""

from .methods import (
    compute_novelty_complex,
    compute_novelty_energy,
    compute_novelty_phase,
    compute_novelty_spectrum,
)
from .normalize import compute_local_average

__all__ = [
    "compute_novelty_energy",
    "compute_novelty_spectrum",
    "compute_novelty_phase",
    "compute_novelty_complex",
    "compute_local_average",
]
