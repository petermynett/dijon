"""Tempogram computation (FMP Section 6.2)."""

import numpy as np
from numba import jit
from scipy.interpolate import interp1d


def _compute_autocorrelation_local(x, Fs, N, H, norm_sum=True):
    """Compute local autocorrelation [FMP, Section 6.2.3].

    Notebook: C6/C6S2_TempogramAutocorrelation.ipynb
    """
    L_left = round(N / 2)
    L_right = L_left
    x_pad = np.concatenate((np.zeros(L_left), x, np.zeros(L_right)))
    L_pad = len(x_pad)
    M = int(np.floor(L_pad - N) / H) + 1
    A = np.zeros((N, M))
    win = np.ones(N)
    if norm_sum is True:
        lag_summand_num = np.arange(N, 0, -1)
    for n in range(M):
        t_0 = n * H
        t_1 = t_0 + N
        x_local = win * x_pad[t_0:t_1]
        r_xx = np.correlate(x_local, x_local, mode="full")
        r_xx = r_xx[N - 1 :]
        if norm_sum is True:
            r_xx = r_xx / lag_summand_num
        A[:, n] = r_xx
    T_coef = np.arange(A.shape[1]) * H / Fs
    F_coef_lag = np.arange(N) / Fs
    return A, T_coef, F_coef_lag


def compute_tempogram_autocorr(x, Fs, N, H, norm_sum=False, Theta=None):
    """Compute autocorrelation-based tempogram [FMP, Section 6.2.3]."""
    if Theta is None:
        Theta = np.arange(40, 321)
    tempo_min, tempo_max = Theta[0], Theta[-1]
    lag_min = int(np.ceil(Fs * 60 / tempo_max))
    lag_max = int(np.ceil(Fs * 60 / tempo_min))
    A, T_coef, F_coef_lag = _compute_autocorrelation_local(
        x, Fs, N, H, norm_sum=norm_sum
    )
    A_cut = A[lag_min : lag_max + 1, :]
    F_coef_lag_cut = F_coef_lag[lag_min : lag_max + 1]
    F_coef_BPM_cut = 60 / F_coef_lag_cut
    tempogram = interp1d(
        F_coef_BPM_cut, A_cut, kind="linear", axis=0, fill_value="extrapolate"
    )(Theta)
    return tempogram, T_coef, Theta


def compute_cyclic_tempogram(
    tempogram, F_coef_BPM, tempo_ref=40, octave_bin=40, octave_num=4
):
    """Compute cyclic tempogram [FMP, Section 6.2.4].

    Notebook: C6/C6S2_TempogramCyclic.ipynb
    """
    F_coef_BPM_log = tempo_ref * np.power(
        2, np.arange(0, octave_num * octave_bin) / octave_bin
    )
    F_coef_scale = np.power(2, np.arange(0, octave_bin) / octave_bin)
    tempogram_log = interp1d(
        F_coef_BPM, tempogram, kind="linear", axis=0, fill_value="extrapolate"
    )(F_coef_BPM_log)
    K = len(F_coef_BPM_log)
    tempogram_cyclic = np.zeros((octave_bin, tempogram.shape[1]))
    for m in range(octave_bin):
        tempogram_cyclic[m, :] = np.mean(
            tempogram_log[m:K:octave_bin, :], axis=0
        )
    return tempogram_cyclic, F_coef_scale


@jit(nopython=True)
def compute_tempogram_fourier(x, Fs, N, H, Theta):
    """Compute Fourier-based tempogram [FMP, Section 6.2.2].

    Notebook: C6/C6S2_TempogramFourier.ipynb

    Args:
        x (np.ndarray): Input signal (novelty function)
        Fs (scalar): Sampling rate
        N (int): Window length
        H (int): Hop size
        Theta (np.ndarray): Set of tempi (given in BPM)

    Returns:
        X (np.ndarray): Tempogram
        T_coef (np.ndarray): Time axis (seconds)
        F_coef_BPM (np.ndarray): Tempo axis (BPM)
    """
    win = np.hanning(N)
    N_left = N // 2
    L = x.shape[0]
    L_left = N_left
    L_right = N_left
    L_pad = L + L_left + L_right
    x_pad = np.concatenate((np.zeros(L_left), x, np.zeros(L_right)))
    t_pad = np.arange(L_pad)
    M = int(np.floor(L_pad - N) / H) + 1
    K = len(Theta)
    X = np.zeros((K, M), dtype=np.complex128)

    for k in range(K):
        omega = (Theta[k] / 60) / Fs 
        exponential = np.exp(-2 * np.pi * 1j * omega * t_pad)
        x_exp = x_pad * exponential
        for n in range(M):
            t_0 = n * H
            t_1 = t_0 + N
            X[k, n] = np.sum(win * x_exp[t_0:t_1])
    T_coef = np.arange(M) * H / Fs
    F_coef_BPM = Theta
    return X, T_coef, F_coef_BPM
