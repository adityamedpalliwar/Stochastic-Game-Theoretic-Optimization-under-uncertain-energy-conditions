"""Generic MILP and LP optimization solver interface using scipy.optimize.milp (HiGHS).

Provides a typed, reliable wrapper around the HiGHS branch-and-cut MILP solver
included with SciPy (>= 1.9), ensuring deterministic solving, exact constraint
formulation, runtime profiling, and detailed status reporting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


@dataclass
class MILPResult:
    """Standardized result from MILP optimization."""

    success: bool
    status: int
    message: str
    x: Optional[np.ndarray] = None
    fun: Optional[float] = None
    solve_time_sec: float = 0.0

    @property
    def is_optimal(self) -> bool:
        """Check if solver terminated with global optimal status."""
        # HiGHS status 0 indicates optimal solution found
        return self.success and self.status == 0


def solve_milp(
    c: np.ndarray,
    integrality: Optional[np.ndarray] = None,
    bounds: Optional[Bounds] = None,
    constraints: Optional[Union[LinearConstraint, Sequence[LinearConstraint]]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> MILPResult:
    """Solve a Mixed-Integer Linear Program (MILP) using HiGHS via SciPy.

    Minimizes:
        c^T * x
    Subject to:
        lhs <= A * x <= rhs
        lb <= x <= ub
        x[i] integer if integrality[i] == 1, continuous if integrality[i] == 0

    Parameters
    ----------
    c : np.ndarray
        Objective function coefficients (1D array).
    integrality : Optional[np.ndarray]
        Variable type indicators (0 = continuous, 1 = integer/binary).
        If None, all variables are treated as continuous.
    bounds : Optional[Bounds]
        SciPy Bounds(lb, ub) for variables.
    constraints : Optional[Union[LinearConstraint, Sequence[LinearConstraint]]]
        Linear constraints lhs <= A @ x <= rhs.
    options : Optional[Dict[str, Any]]
        Solver options passed to HiGHS (e.g. time_limit, disp).

    Returns
    -------
    MILPResult
        Outcome of optimization including solution vector, objective, and runtime.
    """
    c = np.asarray(c, dtype=float)
    if c.ndim != 1:
        raise ValueError(f"Objective vector c must be 1D, got shape {c.shape}")

    n_vars = len(c)

    if integrality is not None:
        integrality = np.asarray(integrality, dtype=int)
        if integrality.shape != (n_vars,):
            raise ValueError(
                f"integrality vector must match c length ({n_vars}), got shape {integrality.shape}"
            )
    else:
        integrality = np.zeros(n_vars, dtype=int)

    solver_options = {"disp": False, "presolve": True}
    if options:
        solver_options.update(options)

    start_time = time.perf_counter()
    try:
        res = milp(
            c=c,
            integrality=integrality,
            bounds=bounds,
            constraints=constraints,
            options=solver_options,
        )
        elapsed = time.perf_counter() - start_time

        return MILPResult(
            success=bool(res.success),
            status=int(res.status),
            message=str(res.message),
            x=np.asarray(res.x, dtype=float) if res.x is not None else None,
            fun=float(res.fun) if res.fun is not None else None,
            solve_time_sec=elapsed,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        return MILPResult(
            success=False,
            status=-1,
            message=f"Solver exception: {str(exc)}",
            x=None,
            fun=None,
            solve_time_sec=elapsed,
        )
