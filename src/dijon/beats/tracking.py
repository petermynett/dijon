"""Ellis DP beat tracking from novelty (FMP C6S3_BeatTracking)."""

import numpy as np


def compute_penalty(N, beat_ref):
    """Compute penalty array for beat tracking DP (log-squared deviation from reference period)."""
    t = np.arange(1, N) / beat_ref
    penalty = -np.square(np.log2(t))
    return np.concatenate((np.array([0.0]), penalty))


def compute_beat_sequence(novelty, beat_ref, penalty=None, factor=1.0, return_all=False):
    """Dynamic programming beat tracking from novelty curve.

    Returns beat indices (0-based, in novelty frames). With return_all=True,
    returns (B, D, P) where D is accumulated score and P is backpointers.
    """
    N = len(novelty)
    if penalty is None:
        penalty = compute_penalty(N, beat_ref)
    penalty = penalty * factor

    novelty = np.concatenate((np.array([0.0]), novelty))
    D = np.zeros(N + 1)
    P = np.zeros(N + 1, dtype=int)
    D[1] = novelty[1]

    for n in range(2, N + 1):
        m_idx = np.arange(1, n)
        scores = D[m_idx] + penalty[n - m_idx]
        score_max = np.max(scores)
        if score_max <= 0:
            D[n] = novelty[n]
            P[n] = 0
        else:
            D[n] = novelty[n] + score_max
            P[n] = int(np.argmax(scores)) + 1

    B = np.zeros(N, dtype=int)
    k = 0
    B[k] = int(np.argmax(D))
    while P[B[k]] != 0:
        k += 1
        B[k] = P[B[k - 1]]
    B = B[: k + 1][::-1] - 1

    if return_all:
        return B, D, P
    return B


def beat_period_to_tempo(beat, Fs):
    """Convert beat period (frames) to tempo (BPM)."""
    return 60.0 / (beat / Fs)
