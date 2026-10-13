"""Grid electricity cost calculations and tariff scenario management.

Calculates:
- Import cost: C^{buy} = P^{buy} * E^{deficit}
- Export revenue: R^{export} = P^{export} * E^{surplus} (if export permitted)
- Net grid cost: C^{net} = C^{buy} - R^{export}

Tariff scenarios are loaded from `data/processed/energy_price_scenarios.csv`
and are explicitly marked as hypothetical illustrative assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from src.energy.energy_balance import EnergyBalance


@dataclass(frozen=True)
class TariffScenario:
    """Represents an electricity tariff structure."""

    scenario_id: str
    scenario_label: str
    import_price_aud_per_kwh: float
    solar_export_credit_aud_per_kwh: float
    is_observed_tariff: bool = False
    price_source: str = "hypothetical_example_not_Ausgrid_observation"
    notes: str = "Illustrative assumption only. Replace with verified retailer tariff."

    @property
    def allows_export(self) -> bool:
        return self.solar_export_credit_aud_per_kwh > 0.0


@dataclass
class GridCostResult:
    """Financial breakdown of electricity exchange with the grid."""

    house_id: str
    tariff_scenario_id: str
    energy_imported_kwh: float
    energy_exported_kwh: float
    unused_surplus_kwh: float
    import_cost_aud: float
    export_credit_aud: float
    net_cost_aud: float
    is_hypothetical_price: bool = True

    def to_dict(self) -> Dict[str, Union[str, float, bool]]:
        return {
            "house_id": self.house_id,
            "tariff_scenario_id": self.tariff_scenario_id,
            "energy_imported_kwh": round(self.energy_imported_kwh, 4),
            "energy_exported_kwh": round(self.energy_exported_kwh, 4),
            "unused_surplus_kwh": round(self.unused_surplus_kwh, 4),
            "import_cost_aud": round(self.import_cost_aud, 4),
            "export_credit_aud": round(self.export_credit_aud, 4),
            "net_cost_aud": round(self.net_cost_aud, 4),
            "is_hypothetical_price": self.is_hypothetical_price,
        }


class GridCostCalculator:
    """Manages tariffs and calculates grid electricity expenditures."""

    def __init__(
        self,
        scenarios_path: Union[str, Path] = "data/processed/energy_price_scenarios.csv",
    ) -> None:
        self.scenarios_path = Path(scenarios_path)
        self.scenarios: Dict[str, TariffScenario] = {}
        self._load_scenarios()

    def _load_scenarios(self) -> None:
        if not self.scenarios_path.exists():
            # Fallback to default illustrative scenarios
            self.scenarios = {
                "HYPOTHETICAL_BASE": TariffScenario(
                    scenario_id="HYPOTHETICAL_BASE",
                    scenario_label="Illustrative base flat tariff",
                    import_price_aud_per_kwh=0.30,
                    solar_export_credit_aud_per_kwh=0.08,
                )
            }
            return

        df = pd.read_csv(self.scenarios_path)
        for _, row in df.iterrows():
            scenario = TariffScenario(
                scenario_id=str(row["scenario_id"]),
                scenario_label=str(row["scenario_label"]),
                import_price_aud_per_kwh=float(row["import_price_aud_per_kwh"]),
                solar_export_credit_aud_per_kwh=float(row["solar_export_credit_aud_per_kwh"]),
                is_observed_tariff=bool(row.get("is_observed_tariff", False)),
                price_source=str(row.get("price_source", "hypothetical")),
                notes=str(row.get("notes", "")),
            )
            self.scenarios[scenario.scenario_id] = scenario

    def get_scenario(self, scenario_id: str = "HYPOTHETICAL_BASE") -> TariffScenario:
        if scenario_id not in self.scenarios:
            raise KeyError(
                f"Unknown scenario '{scenario_id}'. Available: {list(self.scenarios.keys())}"
            )
        return self.scenarios[scenario_id]

    def list_scenarios(self) -> List[TariffScenario]:
        return list(self.scenarios.values())

    def calculate_cost(
        self,
        balance: EnergyBalance,
        scenario_id: str = "HYPOTHETICAL_BASE",
        allow_export: bool = True,
    ) -> GridCostResult:
        """Calculate grid import cost and export revenue for an energy balance.

        Parameters
        ----------
        balance : EnergyBalance
            Household energy balance with deficit and surplus in kWh.
        scenario_id : str
            Tariff scenario ID.
        allow_export : bool
            Whether surplus can be exported to grid for credit.

        Returns
        -------
        GridCostResult
            Breakdown of costs and revenues in AUD.
        """
        tariff = self.get_scenario(scenario_id)

        energy_imported = balance.deficit_kwh
        import_cost = energy_imported * tariff.import_price_aud_per_kwh

        if allow_export and tariff.allows_export:
            energy_exported = balance.surplus_kwh
            unused_surplus = 0.0
            export_credit = energy_exported * tariff.solar_export_credit_aud_per_kwh
        else:
            energy_exported = 0.0
            unused_surplus = balance.surplus_kwh
            export_credit = 0.0

        net_cost = import_cost - export_credit

        return GridCostResult(
            house_id=balance.house_id,
            tariff_scenario_id=tariff.scenario_id,
            energy_imported_kwh=energy_imported,
            energy_exported_kwh=energy_exported,
            unused_surplus_kwh=unused_surplus,
            import_cost_aud=import_cost,
            export_credit_aud=export_credit,
            net_cost_aud=net_cost,
            is_hypothetical_price=not tariff.is_observed_tariff,
        )
