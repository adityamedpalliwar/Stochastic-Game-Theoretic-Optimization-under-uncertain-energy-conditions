"""Flask REST API and Web Application for 5-Household (N=5) Stochastic Energy Trading Platform.

Serves precomputed Monte Carlo simulation results, customer profiles, diurnal trajectories,
battery dispatches, dynamic pricing discoveries, and publication figures from `dashboard.data_service`.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request, Response, send_from_directory

try:
    from dashboard.data_service import DashboardDataService, get_data_service
except ModuleNotFoundError:
    # When run directly as python dashboard/app.py, add project root to sys.path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dashboard.data_service import DashboardDataService, get_data_service

logger = logging.getLogger(__name__)

VALID_HOUSEHOLDS = {"H001", "H002", "H003", "H004", "H005", "COMMUNITY_TOTAL"}


def success_response(data: Any, status_code: int = 200) -> Tuple[Response, int]:
    """Return uniform success JSON response."""
    return jsonify({"status": "success", "data": data}), status_code


def error_response(message: str, status_code: int = 400) -> Tuple[Response, int]:
    """Return uniform error JSON response."""
    return jsonify({"status": "error", "message": message}), status_code


def create_app(data_service: Optional[DashboardDataService] = None) -> Flask:
    """Application factory for Flask dashboard web prototype."""
    app = Flask(__name__)
    service = data_service or get_data_service()

    # Enable CORS for local cross-origin development
    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,OPTIONS"
        return response

    # -------------------------------------------------------------------------
    # Static Figure Serving Routes
    # -------------------------------------------------------------------------

    @app.route("/figures/<path:filename>", methods=["GET"])
    def serve_figure(filename: str) -> Any:
        """Serve high-resolution publication plots."""
        fig_dir = service.path_figures_monte_carlo
        if not (fig_dir / filename).exists():
            # Check single-day directory as fallback
            alt_dir = service.path_figures_daily
            if (alt_dir / filename).exists():
                return send_from_directory(alt_dir, filename)
            return error_response(f"Figure '{filename}' not found.", 404)
        return send_from_directory(fig_dir, filename)

    @app.route("/figures/daily/<path:filename>", methods=["GET"])
    def serve_daily_figure(filename: str) -> Any:
        """Serve 24-hour single-day simulation figures."""
        fig_dir = service.path_figures_daily
        if not (fig_dir / filename).exists():
            return error_response(f"Daily figure '{filename}' not found.", 404)
        return send_from_directory(fig_dir, filename)

    # -------------------------------------------------------------------------
    # Core Health & HTML Page Routes
    # -------------------------------------------------------------------------

    @app.route("/", methods=["GET"])
    def root() -> Any:
        """Root route delivering interactive research prototype UI."""
        return render_template("index.html")

    @app.route("/dashboard", methods=["GET"])
    def dashboard_ui() -> Any:
        """Interactive research web prototype dashboard UI."""
        return render_template("index.html")

    @app.route("/api/health", methods=["GET"])
    def health_check() -> Tuple[Response, int]:
        """System health and in-memory cache status."""
        return success_response({
            "status": "healthy",
            "system": "5-Household Stochastic Energy Trading Platform",
            "cache_initialized": service._is_loaded,
            "read_only_mode": True,
            "scenarios_evaluated": 1000,
        })

    # -------------------------------------------------------------------------
    # System Overview & Customer Profiles
    # -------------------------------------------------------------------------

    @app.route("/api/system_overview", methods=["GET"])
    def get_system_overview() -> Tuple[Response, int]:
        """Return headline macroeconomic findings from 1,000 Monte Carlo scenarios."""
        data = service.get_system_overview()
        return success_response(data)

    @app.route("/api/customer_profiles", methods=["GET"])
    def get_customer_profiles() -> Tuple[Response, int]:
        """Return specifications, archetypes, and capacities for all 5 households."""
        profiles = service.get_customer_profiles()
        return success_response(profiles)

    # -------------------------------------------------------------------------
    # Diurnal Trajectories & Battery Dispatch
    # -------------------------------------------------------------------------

    @app.route("/api/diurnal_trajectories", methods=["GET"])
    def get_diurnal_trajectories() -> Tuple[Response, int]:
        """Return 24-hour diurnal profile and uncertainty bounds for a household or community."""
        house_id = request.args.get("house_id", "H001").upper()
        if house_id not in VALID_HOUSEHOLDS:
            return error_response(
                f"Invalid house_id '{house_id}'. Valid options: {sorted(VALID_HOUSEHOLDS)}",
                400,
            )
        data = service.get_diurnal_trajectories(house_id=house_id)
        return success_response(data)

    # -------------------------------------------------------------------------
    # Operational Modes & Counterfactual Comparisons
    # -------------------------------------------------------------------------

    @app.route("/api/modes_comparison", methods=["GET"])
    def get_modes_comparison() -> Tuple[Response, int]:
        """Return the 4 counterfactual modes cost comparison table."""
        data = service.get_modes_comparison()
        return success_response(data)

    # -------------------------------------------------------------------------
    # Scenario Generation Demo
    # -------------------------------------------------------------------------

    @app.route("/api/scenario_generation_demo", methods=["GET"])
    def get_scenario_generation_demo() -> Tuple[Response, int]:
        """Demonstrate how Monte Carlo smoothed block bootstrap scenarios are generated."""
        house_id = request.args.get("house_id", "H001").upper()
        if house_id not in {"H001", "H002", "H003", "H004", "H005"}:
            house_id = "H001"

        seed_raw = request.args.get("seed", "42")
        try:
            seed = int(seed_raw)
        except ValueError:
            seed = 42

        data = service.get_scenario_generation_demo(house_id=house_id, seed=seed)
        return success_response(data)

    # -------------------------------------------------------------------------
    # Publication Figures Catalog
    # -------------------------------------------------------------------------

    @app.route("/api/figures_catalog", methods=["GET"])
    def get_figures_catalog() -> Tuple[Response, int]:
        """Return catalog of high-resolution publication plots with academic explanations."""
        catalog = service.get_figures_catalog()
        return success_response(catalog)

    # -------------------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(e: Any) -> Tuple[Response, int]:
        return error_response("Endpoint or resource not found.", 404)

    @app.errorhandler(405)
    def method_not_allowed(e: Any) -> Tuple[Response, int]:
        return error_response("Method not allowed. API is strictly read-only (GET).", 405)

    @app.errorhandler(500)
    def server_error(e: Any) -> Tuple[Response, int]:
        logger.exception("Internal server error: %s", e)
        return error_response("An internal server error occurred while querying simulation data.", 500)

    return app


def main() -> None:
    """CLI runner for Flask dashboard server."""
    parser = argparse.ArgumentParser(description="5-Household Stochastic Energy Trading Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    app = create_app()
    print(f"\n==================================================================")
    print(f"  Flagship 5-Household (N=5) Stochastic Energy Trading Dashboard")
    print(f"  URL: http://{args.host}:{args.port}/")
    print(f"  Monte Carlo Scenarios Evaluated: 1,000 (24,000 game rounds)")
    print(f"  Total Community Profit: $10,559.67 AUD (40.07% Bill Reduction)")
    print(f"  Status: Active and Serving Precomputed Results")
    print(f"==================================================================\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
