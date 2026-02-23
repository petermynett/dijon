"""Normalization utilities for novelty signals."""

import numpy as np


def compute_local_average(x, M):
    """Compute local average of signal. Vectorized via convolution."""
    L = len(x)
    kernel = np.ones(2 * M + 1) / (2 * M + 1)
    padded = np.pad(x, M, mode="constant", constant_values=0)
    return np.convolve(padded, kernel, mode="valid")[:L]
