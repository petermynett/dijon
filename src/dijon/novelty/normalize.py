"""Normalization utilities for novelty signals."""

import numpy as np


def compute_local_average(x, M):
    """Compute local average of signal (FMP C6S1_NoveltySpectral)."""
    L = len(x)
    local_average = np.zeros(L)
    for m in range(L):
        a = max(m - M, 0)
        b = min(m + M + 1, L)
        local_average[m] = (1 / (2 * M + 1)) * np.sum(x[a:b])
    return local_average
