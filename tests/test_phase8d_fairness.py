"""Unit tests for Phase 8D economic fairness and distributional metrics."""

import math
import numpy as np
import pytest

from src.game.fairness_metrics import (
    compute_benefit_range,
    compute_fairness_summary,
    compute_household_benefit_shares,
    compute_max_benefit,
    compute_max_min_benefit,
    compute_nash_social_welfare,
    compute_normalized_gini,
    compute_standard_gini,
    extract_active_payoffs,
)


def test_gini_equal_payoffs_3_participants():
    """Verify that equal distribution yields exactly Gini = 0.0."""
    payoffs = {"H001": 0.05, "H002": 0.05, "H003": 0.05}
    active = ["H001", "H002", "H003"]

    g_std = compute_standard_gini(payoffs, active)
    g_norm = compute_normalized_gini(payoffs, active)

    assert g_std is not None
    assert g_norm is not None
    assert abs(g_std - 0.0) < 1e-12
    assert abs(g_norm - 0.0) < 1e-12


def test_gini_extreme_concentration_3_participants():
    """Verify that 1 participant capturing all surplus yields G_std = 2/3 and G_norm = 1.0."""
    payoffs = {"H001": 0.15, "H002": 0.0, "H003": 0.0}
    active = ["H001", "H002", "H003"]

    g_std = compute_standard_gini(payoffs, active)
    g_norm = compute_normalized_gini(payoffs, active)

    assert g_std is not None
    assert g_norm is not None
    assert pytest.approx(g_std, abs=1e-12) == 2.0 / 3.0
    assert pytest.approx(g_norm, abs=1e-12) == 1.0


def test_gini_2_participants():
    """Verify Gini calculations for 2 active participants."""
    # Equal payoffs: G = 0, G_norm = 0
    p_equal = {"H001": 0.10, "H002": 0.10}
    active_2 = ["H001", "H002"]
    assert pytest.approx(compute_standard_gini(p_equal, active_2), abs=1e-12) == 0.0
    assert pytest.approx(compute_normalized_gini(p_equal, active_2), abs=1e-12) == 0.0

    # Extreme concentration: G_std = 0.5, G_norm = 1.0
    p_monopoly = {"H001": 0.20, "H002": 0.0}
    assert pytest.approx(compute_standard_gini(p_monopoly, active_2), abs=1e-12) == 0.5
    assert pytest.approx(compute_normalized_gini(p_monopoly, active_2), abs=1e-12) == 1.0


def test_gini_zero_total_welfare():
    """Verify that zero-benefit hours safely return None."""
    p_zero = {"H001": 0.0, "H002": 0.0, "H003": 0.0}
    active = ["H001", "H002", "H003"]

    assert compute_standard_gini(p_zero, active) is None
    assert compute_normalized_gini(p_zero, active) is None
    shares = compute_household_benefit_shares(p_zero, active)
    assert all(v is None for v in shares.values())


def test_gini_bounds_and_monotonicity_random_samples():
    """Verify mathematical bounds for random nonnegative payoff distributions."""
    np.random.seed(42)
    active_3 = ["H001", "H002", "H003"]
    active_2 = ["H001", "H002"]

    for _ in range(50):
        # 3 participants
        vals_3 = np.random.uniform(0.01, 1.0, size=3)
        payoffs_3 = {h: v for h, v in zip(active_3, vals_3)}
        g3 = compute_standard_gini(payoffs_3, active_3)
        gnorm3 = compute_normalized_gini(payoffs_3, active_3)

        assert 0.0 <= g3 <= 2.0 / 3.0 + 1e-12
        assert 0.0 <= gnorm3 <= 1.0 + 1e-12

        # 2 participants
        vals_2 = np.random.uniform(0.01, 1.0, size=2)
        payoffs_2 = {h: v for h, v in zip(active_2, vals_2)}
        g2 = compute_standard_gini(payoffs_2, active_2)
        gnorm2 = compute_normalized_gini(payoffs_2, active_2)

        assert 0.0 <= g2 <= 0.5 + 1e-12
        assert 0.0 <= gnorm2 <= 1.0 + 1e-12


def test_active_participant_masking_excludes_inactive():
    """Verify that an inactive participant (U=0) does not artificially zero out Max-Min."""
    # 2 active households trading, H003 inactive
    payoffs = {"H001": 0.02, "H002": 0.04, "H003": 0.0}
    active = ["H001", "H002"]  # H003 is excluded from active

    u_min = compute_max_min_benefit(payoffs, active)
    u_max = compute_max_benefit(payoffs, active)
    u_range = compute_benefit_range(payoffs, active)

    assert pytest.approx(u_min, abs=1e-12) == 0.02
    assert pytest.approx(u_max, abs=1e-12) == 0.04
    assert pytest.approx(u_range, abs=1e-12) == 0.02


def test_benefit_shares_sum_to_one():
    """Verify that participant benefit shares sum identically to 1.0."""
    payoffs = {"H001": 0.015, "H002": 0.045, "H003": 0.040}
    active = ["H001", "H002", "H003"]

    shares = compute_household_benefit_shares(payoffs, active)
    assert pytest.approx(sum(shares.values()), abs=1e-12) == 1.0
    assert pytest.approx(shares["H001"], abs=1e-12) == 0.15
    assert pytest.approx(shares["H002"], abs=1e-12) == 0.45
    assert pytest.approx(shares["H003"], abs=1e-12) == 0.40


def test_nash_social_welfare_handles_zero_payoffs():
    """Verify NSW computes smoothly via epsilon regularization without exception."""
    payoffs = {"H001": 0.05, "H002": 0.0, "H003": 0.05}
    active = ["H001", "H002", "H003"]
    eps = 1e-6

    nsw = compute_nash_social_welfare(payoffs, active, epsilon=eps)
    assert nsw is not None
    expected_nsw = math.log(0.05 + eps) + math.log(0.0 + eps) + math.log(0.05 + eps)
    assert pytest.approx(nsw, abs=1e-10) == expected_nsw


def test_fairness_summary_output_structure():
    """Verify fairness summary dictionary keys and types."""
    payoffs = {"H001": 0.02, "H002": 0.04, "H003": 0.02}
    active = ["H001", "H002", "H003"]

    summary = compute_fairness_summary(payoffs, active)
    assert summary["num_active_participants"] == 3
    assert summary["standard_gini"] is not None
    assert summary["normalized_gini"] is not None
    assert "H001" in summary["benefit_shares"]
    assert summary["max_min_benefit_aud"] == 0.02
    assert summary["max_benefit_aud"] == 0.04
    assert summary["benefit_range_aud"] == 0.02
    assert summary["log_nash_social_welfare"] is not None

