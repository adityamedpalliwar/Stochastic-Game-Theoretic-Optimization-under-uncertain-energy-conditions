"""Dynamic P2P price discovery for N-player energy trading games.

Instead of a fixed mid-market price, the P2P price responds to the
*demand pressure* in the active trading pool:

    demand_pressure = total_trading_deficit / (total_trading_surplus + eps)

When buyers compete for scarce supply (pressure > 1), sellers can push
the price up toward the grid retail price. When supply is abundant
(pressure < 1), buyers have leverage and the price drops toward the
feed-in tariff.

Available Models
----------------
DynamicPricingModel (Default)
    Price scales according to demand pressure clamped between feed-in
    tariff and grid retail price.

ElasticDemandPricing
    Uses a smoothed sigmoid so the price response is gradual near
    the midpoint and sharper at the extremes.

StackelbergDemandPricing
    Seller sets a markup on top of feed-in tariff proportional to the
    square-root of demand pressure (Stackelberg leader model).

MidMarketPricing
    Fixed mid-market price (import + export) / 2 as a baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Union
import math
import numpy as np


# ---------------------------------------------------------------------------
# Base Protocol
# ---------------------------------------------------------------------------

class BasePricingModel(Protocol):
    """Protocol for any pricing model computing a P2P price from pool quantities."""

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        ...

    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _demand_pressure(surplus: float, deficit: float, eps: float = 1e-9) -> float:
    """Demand/supply ratio, safely clamped to [0, ∞)."""
    return deficit / (surplus + eps)


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# DynamicPricingModel (Primary Concrete Dynamic Model)
# ---------------------------------------------------------------------------

@dataclass
class DynamicPricingModel:
    """Dynamic P2P pricing model where price adjusts to aggregate demand.

    Formula
    -------
    demand_pressure = total_trading_deficit / (total_trading_surplus + eps)
    t = clamp(sensitivity * demand_pressure / max_pressure, 0.0, 1.0)
    P_P2P = P_export + t * (P_import - P_export)

    - At t = 0 (abundant solar surplus, low demand): P_P2P = P_export (feed-in tariff)
    - At t = 0.5 (balanced supply and demand): P_P2P = mid-market rate ($0.19)
    - At t = 1.0 (high demand pressure, scarcity): P_P2P = P_import (grid retail ceiling)

    Parameters
    ----------
    max_pressure : float
        Demand/supply ratio that triggers the maximum price (grid import).
        Default 2.0 (price reaches the ceiling when demand is double available supply).
    sensitivity : float
        Multiplier on demand pressure before clamping. Default 1.0.
    """

    max_pressure: float = 2.0
    sensitivity: float = 1.0
    clamp_ceiling: bool = False

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        if total_trading_surplus_kwh <= 1e-9 or total_trading_deficit_kwh <= 1e-9:
            # Fallback to fair mid-market when no trade pool exists
            return (grid_import_price_aud + grid_export_credit_aud) / 2.0

        pressure = _demand_pressure(total_trading_surplus_kwh, total_trading_deficit_kwh)
        if self.clamp_ceiling:
            t = _clamp(self.sensitivity * pressure / self.max_pressure, 0.0, 1.0)
            price = grid_export_credit_aud + t * (grid_import_price_aud - grid_export_credit_aud)
            return _clamp(price, grid_export_credit_aud, grid_import_price_aud)
        else:
            t = max(0.0, self.sensitivity * pressure / self.max_pressure)
            price = grid_export_credit_aud + t * (grid_import_price_aud - grid_export_credit_aud)
            return max(grid_export_credit_aud, price)

    def name(self) -> str:
        ceiling_tag = ", uncapped" if not self.clamp_ceiling else ""
        return f"DynamicPricingModel(max_p={self.max_pressure}, sens={self.sensitivity}{ceiling_tag})"


# Backward-compatible alias
LinearDemandPricing = DynamicPricingModel


# ---------------------------------------------------------------------------
# Alternative Built-in Pricing Models
# ---------------------------------------------------------------------------

@dataclass
class MidMarketPricing:
    """Constant mid-market price — benchmark model.

    Price = (grid_import + grid_export) / 2, regardless of supply/demand.
    """

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        return (grid_import_price_aud + grid_export_credit_aud) / 2.0

    def name(self) -> str:
        return "MidMarket"


@dataclass
class ElasticDemandPricing:
    """Sigmoid-smoothed demand-responsive pricing.

    Formula
    -------
    pressure = deficit / (surplus + eps)
    x = steepness * (pressure - midpoint)
    t = 1 / (1 + exp(-x))
    price = FIT + t * (grid_import - FIT)
    """

    midpoint: float = 1.0
    steepness: float = 4.0

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        if total_trading_surplus_kwh <= 1e-9 or total_trading_deficit_kwh <= 1e-9:
            return (grid_import_price_aud + grid_export_credit_aud) / 2.0

        pressure = _demand_pressure(total_trading_surplus_kwh, total_trading_deficit_kwh)
        x = self.steepness * (pressure - self.midpoint)
        t = 1.0 / (1.0 + math.exp(-x))
        price = grid_export_credit_aud + t * (grid_import_price_aud - grid_export_credit_aud)
        return _clamp(price, grid_export_credit_aud, grid_import_price_aud)

    def name(self) -> str:
        return f"ElasticDemand(mid={self.midpoint}, steep={self.steepness})"


@dataclass
class StackelbergDemandPricing:
    """Seller-leader Stackelberg pricing: markup based on sqrt(pressure)."""

    markup_factor: float = 0.5

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        if total_trading_surplus_kwh <= 1e-9 or total_trading_deficit_kwh <= 1e-9:
            return (grid_import_price_aud + grid_export_credit_aud) / 2.0

        pressure = _demand_pressure(total_trading_surplus_kwh, total_trading_deficit_kwh)
        markup = self.markup_factor * math.sqrt(pressure)
        t = _clamp(markup, 0.0, 1.0)
        price = grid_export_credit_aud + t * (grid_import_price_aud - grid_export_credit_aud)
        return _clamp(price, grid_export_credit_aud, grid_import_price_aud)

    def name(self) -> str:
        return f"Stackelberg(markup={self.markup_factor})"


@dataclass
class CustomDemandPricing:
    """Wrap any user-supplied callable as a pricing model."""

    fn: Callable[[float, float, float, float], float]
    label: str = "Custom"

    def compute_price(
        self,
        total_trading_surplus_kwh: float,
        total_trading_deficit_kwh: float,
        grid_import_price_aud: float,
        grid_export_credit_aud: float,
    ) -> float:
        raw = self.fn(
            total_trading_surplus_kwh,
            total_trading_deficit_kwh,
            grid_import_price_aud,
            grid_export_credit_aud,
        )
        return _clamp(float(raw), grid_export_credit_aud, grid_import_price_aud)

    def name(self) -> str:
        return self.label


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

PRICING_MODELS: dict = {
    "dynamic":      DynamicPricingModel,
    "linear":       DynamicPricingModel,
    "midmarket":    MidMarketPricing,
    "elastic":      ElasticDemandPricing,
    "stackelberg":  StackelbergDemandPricing,
}


def get_pricing_model(name: str, **kwargs) -> DynamicPricingModel:
    """Instantiate a pricing model by name.

    Parameters
    ----------
    name : str
        One of ``'dynamic'``, ``'linear'``, ``'midmarket'``, ``'elastic'``, ``'stackelberg'``.
    **kwargs
        Passed to constructor.
    """
    key = name.lower().strip()
    if key not in PRICING_MODELS:
        raise ValueError(
            f"Unknown pricing model '{name}'. "
            f"Choose from: {list(PRICING_MODELS.keys())}"
        )
    return PRICING_MODELS[key](**kwargs)
