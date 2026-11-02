"""Main entry point for project execution and simulation.

Default execution runs the flagship 5-Household (N=5) Monte Carlo Game Simulation
with battery storage, dynamic pricing, and publication plot generation:
    python main.py
    python main.py --scenarios 1000 --seed 42

To run the legacy initial 2-player prototype (kept aside for historical reference):
    python main.py --legacy-2player
"""

import argparse
import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stochastic Game-Theoretic Optimization under Uncertain Energy Conditions (N=5 Household Simulation)"
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=1000,
        help="Number of Monte Carlo daily scenarios to simulate (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible Monte Carlo scenario generation (default: 42)",
    )
    parser.add_argument(
        "--legacy-2player",
        action="store_true",
        help="Run the initial 2-player pedagogical prototype (kept aside as legacy baseline)",
    )
    parser.add_argument(
        "--step-by-step",
        action="store_true",
        help="Interactive step-by-step mode for legacy 2-player demo",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.legacy_2player or args.step_by_step:
        print("\n[NOTE] Running legacy initial 2-player toy prototype (kept aside for reference)...\n")
        from demo_prototype import main as run_legacy_2player
        run_legacy_2player()
        return

    # Primary Flagship System: 5-Household Monte Carlo Game Simulation
    from simulate_five_house_monte_carlo import run_simulation, print_results
    from generate_monte_carlo_plots import plot_comparisons

    print("=" * 80)
    print("FLAGSHIP SYSTEM: 5-HOUSEHOLD STOCHASTIC P2P ENERGY TRADING GAME")
    print("=" * 80)

    df_scenarios, df_summary, df_hourly = run_simulation(
        num_scenarios=args.scenarios,
        random_seed=args.seed,
        data_path_str="data/processed/five_house_hourly_demand.csv",
    )
    print_results(df_summary, df_hourly, num_scenarios=args.scenarios)

    # Save summary tables
    output_dir = ROOT / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / "monte_carlo_1000_scenarios_summary.csv"
    summary_tables_csv = tables_dir / "monte_carlo_1000_scenarios_summary.csv"
    df_summary.to_csv(summary_csv, index=False)
    df_summary.to_csv(summary_tables_csv, index=False)
    print(f"\n[+] Summary tables saved to: {summary_tables_csv}")

    # Generate and save comparison plots into results/figures/simulate_five_house_monte_carlo/
    fig_dir = output_dir / "figures" / "simulate_five_house_monte_carlo"
    saved_plots = plot_comparisons(df_scenarios, df_summary, df_hourly, fig_dir)
    print(f"[+] Generated {len(saved_plots)} comparison plots in: {fig_dir}\n")


if __name__ == "__main__":
    main()
