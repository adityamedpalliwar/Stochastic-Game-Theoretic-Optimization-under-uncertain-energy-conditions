"""Household definitions and multi-house aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd


@dataclass
class Household:
    """Represents a single household in the microgrid."""

    house_id: str
    source_customer_id: int
    postcode: int
    generator_capacity_kwp: float
    selection_criteria: str

    def to_dict(self) -> Dict[str, Union[str, int, float]]:
        return {
            "house_id": self.house_id,
            "source_customer_id": self.source_customer_id,
            "postcode": self.postcode,
            "generator_capacity_kwp": self.generator_capacity_kwp,
            "selection_criteria": self.selection_criteria,
        }


def load_households(
    mapping_path: Union[str, Path] = "data/processed/customer_id_mapping.csv",
) -> Dict[str, Household]:
    """Load household metadata from the customer mapping CSV."""
    path = Path(mapping_path)
    if not path.exists():
        raise FileNotFoundError(f"Customer mapping file not found: {path}")

    df = pd.read_csv(path)
    households = {}
    for _, r in df.iterrows():
        h = Household(
            house_id=str(r["house_id"]),
            source_customer_id=int(r["source_customer_id"]),
            postcode=int(r["postcode"]),
            generator_capacity_kwp=float(r["generator_capacity_kwp"]),
            selection_criteria=str(r["selection_criteria"]),
        )
        households[h.house_id] = h
    return households
