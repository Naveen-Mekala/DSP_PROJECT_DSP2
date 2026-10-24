import numpy as np


def psi(expected, actual, epsilon=1e-6):
    """Population Stability Index for two non-negative frequency vectors."""
    expected = np.asarray(expected, dtype=float) + epsilon
    actual = np.asarray(actual, dtype=float) + epsilon
    expected = expected / expected.sum()
    actual = actual / actual.sum()
    return float(np.sum((actual - expected) * np.log(actual / expected)))
