from scripts.drift_math import psi


def test_psi_zero_for_matching_distributions():
    assert abs(psi([10, 20, 30], [10, 20, 30])) < 1e-9


def test_psi_increases_for_different_distributions():
    assert psi([90, 10], [10, 90]) > psi([90, 10], [80, 20])
