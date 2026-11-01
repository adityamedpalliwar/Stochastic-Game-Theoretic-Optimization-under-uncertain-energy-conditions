"""Economic fairness and distributional metrics for peer-to-peer energy markets.

Provides mathematical implementations of:
1. Standard Gini coefficient:
       G = sum_{i,j} |U_i - U_j| / (2 * n * sum U_i)
2. Normalized Gini coefficient:
       G_norm = (n / (n - 1)) * G in [0, 1] for n >= 2
3. Participant benefit shares:
       Share_i = U_i / sum U_j
4. Max-Min payoff (Rawlsian fairness):
       U_min = min_{i in active} U_i
5. Benefit range:
       Range = max_{i in active} U_i - min_{i in active} U_i
6. Nash Social Welfare (proportional fairness):
       log NSW = sum_{i in active} log(U_i + epsilon)

Enforces strict separation between active participant evaluation (U_active)
and community-level household reporting (U_all).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np


DEFAULT_NUMERICAL_TOLERANCE: float = 1e-6
DEFAULT_NSW_EPSILON: float = 1e-6


def extract_active_payoffs(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
) -> Dict[str, float]:
    """Filter payoffs strictly to active participants.

    Parameters
    ----------
    payoffs : Dict[str, float]
        Mapping from household ID to realized P2P benefit (AUD).
    active_households : Sequence[str]
        Households with positive physical net positions (surplus > 0 or deficit > 0).

    Returns
    -------
    Dict[str, float]
        Payoffs of active households, with negative values clamped to 0.0.
    """
    return {
        hid: max(0.0, float(payoffs.get(hid, 0.0)))
        for hid in active_households
    }


def compute_standard_gini(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[float]:
    """Compute the standard Gini coefficient over active participants.

    Formula:
        G = sum_{i=1}^n sum_{j=1}^n |U_i - U_j| / (2 * n * sum_{i=1}^n U_i)

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs per household.
    active_households : Sequence[str]
        Universe of active participants in the trading hour.
    tolerance : float
        Numerical zero threshold.

    Returns
    -------
    Optional[float]
        Standard Gini coefficient in [0, (n-1)/n], or None if inactive / zero total welfare.
    """
    if not active_households:
        return None

    active_u = [max(0.0, float(payoffs.get(h, 0.0))) for h in active_households]
    total_u = sum(active_u)

    # In one-sided or zero-welfare hours, Gini is not applicable
    if total_u <= tolerance:
        return None

    n = len(active_u)
    if n <= 1:
        return 0.0

    diff_sum = sum(abs(u_i - u_j) for u_i in active_u for u_j in active_u)
    gini = diff_sum / (2.0 * n * total_u)
    return float(gini)


def compute_normalized_gini(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Optional[float]:
    """Compute the normalized Gini coefficient scaled to [0, 1].

    For n nonnegative values, standard Gini has theoretical maximum (n - 1) / n.
    Normalized Gini scales this by n / (n - 1):
        G_norm = (n / (n - 1)) * G

    - For n = 3: G_norm = 1.5 * G in [0, 1].
    - For n = 2: G_norm = 2.0 * G in [0, 1].

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs per household.
    active_households : Sequence[str]
        Universe of active participants.
    tolerance : float
        Numerical zero threshold.

    Returns
    -------
    Optional[float]
        Normalized Gini coefficient in [0, 1], or None if not applicable.
    """
    g = compute_standard_gini(payoffs, active_households, tolerance=tolerance)
    if g is None:
        return None

    n = len(active_households)
    if n <= 1:
        return 0.0

    factor = n / (n - 1.0)
    g_norm = g * factor
    return float(min(1.0, max(0.0, g_norm)))


def compute_household_benefit_shares(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
) -> Dict[str, Optional[float]]:
    """Compute individual participant benefit shares relative to active surplus.

    Share_i = U_i / sum_{j in active} U_j

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs per household.
    active_households : Sequence[str]
        Active households in the trading hour.
    tolerance : float
        Numerical zero threshold.

    Returns
    -------
    Dict[str, Optional[float]]
        Mapping of active household to benefit share in [0, 1], or None if total welfare is 0.
    """
    if not active_households:
        return {}

    active_u = {h: max(0.0, float(payoffs.get(h, 0.0))) for h in active_households}
    total_u = sum(active_u.values())

    if total_u <= tolerance:
        return {h: None for h in active_households}

    return {h: float(u / total_u) for h, u in active_u.items()}


def compute_max_min_benefit(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
) -> Optional[float]:
    """Compute the minimum benefit among active participants (Rawlsian egalitarian metric).

    U_min = min_{i in active} U_i

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs.
    active_households : Sequence[str]
        Active households.

    Returns
    -------
    Optional[float]
        Minimum active payoff, or None if no active participants.
    """
    if not active_households:
        return None
    return float(min(max(0.0, float(payoffs.get(h, 0.0))) for h in active_households))


def compute_max_benefit(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
) -> Optional[float]:
    """Compute the maximum benefit among active participants.

    U_max = max_{i in active} U_i
    """
    if not active_households:
        return None
    return float(max(max(0.0, float(payoffs.get(h, 0.0))) for h in active_households))


def compute_benefit_range(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
) -> Optional[float]:
    """Compute the payoff dispersion range across active participants.

    Range = U_max - U_min
    """
    if not active_households:
        return None
    u_min = compute_max_min_benefit(payoffs, active_households)
    u_max = compute_max_benefit(payoffs, active_households)
    if u_min is None or u_max is None:
        return None
    return float(u_max - u_min)


def compute_nash_social_welfare(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
    epsilon: float = DEFAULT_NSW_EPSILON,
) -> Optional[float]:
    """Compute the log Nash Social Welfare over active participants.

    log NSW = sum_{i in active} log(U_i + epsilon)

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs.
    active_households : Sequence[str]
        Active participants.
    epsilon : float
        Small positive regularizer preventing log(0) for active households with 0 payoff.

    Returns
    -------
    Optional[float]
        log NSW scalar, or None if no active households.
    """
    if not active_households:
        return None
    return float(
        sum(
            math.log(max(0.0, float(payoffs.get(h, 0.0))) + epsilon)
            for h in active_households
        )
    )


def compute_fairness_summary(
    payoffs: Dict[str, float],
    active_households: Sequence[str],
    tolerance: float = DEFAULT_NUMERICAL_TOLERANCE,
    epsilon: float = DEFAULT_NSW_EPSILON,
) -> Dict[str, Any]:
    """Compute a complete statistical fairness report for an evaluated hour.

    Parameters
    ----------
    payoffs : Dict[str, float]
        Realized payoffs per household.
    active_households : Sequence[str]
        Active households with positive surplus or deficit.
    tolerance : float
        Numerical zero threshold.
    epsilon : float
        NSW regularization epsilon.

    Returns
    -------
    Dict[str, Any]
        Dictionary of all fairness indicators.
    """
    return {
        "num_active_participants": len(active_households),
        "standard_gini": compute_standard_gini(payoffs, active_households, tolerance),
        "normalized_gini": compute_normalized_gini(payoffs, active_households, tolerance),
        "benefit_shares": compute_household_benefit_shares(payoffs, active_households, tolerance),
        "max_min_benefit_aud": compute_max_min_benefit(payoffs, active_households),
        "max_benefit_aud": compute_max_benefit(payoffs, active_households),
        "benefit_range_aud": compute_benefit_range(payoffs, active_households),
        "log_nash_social_welfare": compute_nash_social_welfare(payoffs, active_households, epsilon),
    }

