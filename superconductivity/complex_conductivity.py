import numba
import numpy as np
import scipy.special as sp
import scipy.constants as sc
import scipy.integrate as it

from superconductivity.fermi_functions import fermi
from superconductivity.gap_functions import reduced_delta_bcs


def limit(temp, freq, delta0):
    """
    Calculate the approximate complex conductivity to normal conductivity
    ratio in the limit hf << ∆ and kB T << ∆ given some temperature, frequency
    and transition temperature.
    Parameters
    ----------
    temp : float, numpy.ndarray
        Temperature in units of Kelvin.
    freq : float, numpy.ndarray
        Frequency in units of Hz.
    delta0: float, complex
        Superconducting gap energy at 0 Kelvin in units of Joules. An imaginary
        part signifies finite loss at zero temperature.
    Returns
    -------
    sigma : numpy.ndarray, dtype=numpy.complex128
        The complex conductivity at temp and freq.
    Notes
    -----
    Extension of Mattis-Bardeen theory to a complex gap parameter covered in
        Noguchi T. et al. Physics Proc., 36, 2012.
        Noguchi T. et al. IEEE Trans. Appl. SuperCon., 28, 4, 2018.
    The real part of the gap is assumed to follow the BCS temperature
        dependence expanded at low temperatures. See equation 2.53 in
        Gao J. 2008. CalTech. PhD dissertation.
    No temperature dependence is assumed for the complex portion of the gap
        parameter.
    """
    temp = np.atleast_1d(temp)
    freq = np.atleast_1d(freq)
    delta1 = np.real(delta0)
    delta2 = np.imag(delta1)

    assert (temp > 0).all(), "Temperature must be >= 0."
    if temp.size == 1 and freq.size != 1:
        temp = np.ones(freq.size) * temp
    elif freq.size == 1 and temp.size != 1:
        freq = np.ones(temp.size) * freq
    elif freq.size != temp.size:
        raise ValueError("Incompatible array sizes")

    sigma1 = np.zeros(freq.size)
    sigma2 = np.zeros(freq.size)

    xi = sc.h * freq / (2 * sc.k * temp[temp != 0])
    eta = delta1 / (sc.k * temp[temp != 0])

    sigma1[temp == 0] = np.pi * delta2 / (sc.h * freq[temp == 0])
    sigma2[temp == 0] = np.pi * delta1 / (sc.h * freq[temp == 0])
    sigma1[temp != 0] = (4 * delta1 / (sc.h * freq) * np.exp(-eta) * np.sinh(xi) * sp.k0(xi) +
                         np.pi * delta2 / (sc.h * freq) *
                         (1 + 2 * delta1 / (sc.k * temp) * np.exp(-eta) * np.exp(-xi) * sp.i0(xi)))
    sigma2[temp != 0] = np.pi * delta1 / (sc.h * freq) * (1 - np.sqrt(2 * np.pi / eta) * np.exp(-eta) -
                                                          2 * np.exp(-eta) * np.exp(-xi) * sp.i0(xi))
    return sigma1 + 1j * sigma2


def numeric(temp, freq, delta0, bcs=1.764):
    """
    Numerically calculate the complex conductivity to normal conductivity
    ratio by integrating given some temperature, frequency and transition
    temperature, where hf < ∆ (tones with frequency, f, do not break Cooper
    pairs).
    Parameters
    ----------
    temp : iterable of size N
        Temperature in units of Kelvin.
    freq : float
        Frequency in units of Hz.
    delta0: float
        Superconducting gap energy at 0 Kelvin in units of Joules.
    bcs: float (optional)
        BCS constant that relates the gap to the transition temperature.
        ∆ = bcs * kB * Tc
    Returns
    -------
    sigma : numpy.ndarray, dtype=numpy.complex128
        The complex conductivity at temp and freq.
    """
    # coerce inputs into numpy array
    temp = np.atleast_1d(temp)
    # get the temperature dependent gap
    delta = delta0 * reduced_delta_bcs(bcs * sc.k * temp / delta0, bcs=bcs)
    # calculate unitless reduced temperature and frequency
    t = temp * sc.k / delta
    w = sc.h * freq / delta
    # set the temperature independent bounds for integrals
    a1, b1, b2 = 1, np.inf, 1
    # allocate memory for arrays
    sigma1 = np.zeros(temp.size)
    sigma2 = np.zeros(temp.size)
    # compute the integral by looping over inputs
    for ii in range(temp.size):
        a2 = 1 - w[ii]
        sigma1[ii] = it.quad(sigma1_kernel, a1, b1, args=(t[ii], w[ii]))[0]
        sigma2[ii] = it.quad(sigma2_kernel, a2, b2, args=(t[ii], w[ii]))[0]

    return sigma1 + 1j * sigma2


def sigma1_kernel(e, t, w):
    """
    Calculate the kernel of the integral for the real part of the complex
    conductivity where E = hf < ∆ (tones with frequency, f, do not break Cooper
    pairs).
    Parameters
    ----------
    e: numpy.ndarray
        reduced energy (E / ∆)
    t: float
        reduced temperature (kB T / ∆)
    w: float
        reduced frequency (h f / ∆)
    Returns
    -------
    k: numpy.ndarray
        The kernel for the integral for the real part of the complex conductivity
    """
    k = (2 * (fermi(e, t) - fermi(e + w, t)) * (e**2 + w * e + 1) /
         (w * np.sqrt(e**2 - 1) * np.sqrt((e + w)**2 - 1)))
    return k


def sigma2_kernel(e, t, w):
    """
    Calculate the kernel of the integral for the imaginary part of the complex
    conductivity where E = hf < ∆ (tones with frequency, f, do not break Cooper
    pairs) for arcsin(1 - w) < y < pi / 2. Using e = sin(y) substitution in the
    dimensionless integral.
    Parameters
    ----------
    e: numpy.ndarray
        reduced energy (E / ∆)
    t: float
        reduced temperature (kB T / ∆)
    w: float
        reduced frequency (h f / ∆)
    Returns
    -------
    k: numpy.ndarray
        The kernel for the integral for the imaginary part of the complex
        conductivity
    """
    k = ((1 - 2 * fermi(e + w, t)) * (e**2 + w * e + 1) /
         (w * np.sqrt(1 - e**2) * np.sqrt((e + w)**2 - 1)))
    return k
