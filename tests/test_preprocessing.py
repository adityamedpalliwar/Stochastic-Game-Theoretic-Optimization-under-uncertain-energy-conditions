"""Unit tests for preprocessing, cyclical feature engineering, and sequence generation."""

from __future__ import annotations

import io
import pathlib
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.data.preprocessing import (
    add_cyclical_features,
    create_lstm_sequences,
    prepare_hourly_panel,
)


def _generate_synthetic_ausgrid_csv(
    customers: list[int] = (101, 102, 103),
    n_days: int = 365,
    gc_val: float = 0.1,
    cl_val: float = 0.2,
    gg_val: float = 0.5,
    capacity: float = 3.5,
    postcode: int = 2000,
    bad_quality_rows: int = 0,
) -> pathlib.Path:
    """Generate a temporary synthetic Ausgrid raw CSV for testing."""
    dates = pd.date_range("2012-07-01", periods=n_days, freq="D").strftime("%d/%m/%Y")
    categories = ["GC", "CL", "GG"]

    idx = (
        pd.MultiIndex.from_product(
            [customers, categories, dates],
            names=["Customer", "Consumption Category", "date"],
        )
        .to_frame()
        .reset_index(drop=True)
    )
    idx["Generator Capacity"] = capacity
    idx["Postcode"] = postcode

    interval_cols = [f"{h:02d}:{m:02d}" for h in range(24) for m in (30, 0)]
    val_map = {"GC": gc_val, "CL": cl_val, "GG": gg_val}
    vals = np.array([val_map[cat] for cat in idx["Consumption Category"]], dtype=np.float64)[:, np.newaxis]
    intervals_arr = np.repeat(vals, 48, axis=1)

    intervals_df = pd.DataFrame(intervals_arr, columns=interval_cols)
    idx["Row Quality"] = ""
    if bad_quality_rows > 0:
        idx.loc[:bad_quality_rows - 1, "Row Quality"] = "Estimate"

    df = pd.concat(
        [
            idx[["Customer", "Generator Capacity", "Postcode", "Consumption Category", "date"]],
            intervals_df,
            idx[["Row Quality"]],
        ],
        axis=1,
    )

    buf = io.StringIO()
    buf.write("Ausgrid local header title row\n")
    df.to_csv(buf, index=False)
    buf.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(buf.getvalue())
        return pathlib.Path(tf.name)


class TestCyclicalFeatures(unittest.TestCase):
    """Unit tests for trigonometric cyclical encodings."""

    def test_cyclical_features_values(self):
        """Verify standard sine and cosine values at key hours of the day."""
        df = pd.DataFrame({
            "hour": [0, 6, 12, 18],
            "day_of_week": [0, 1, 2, 3],
        })
        result = add_cyclical_features(df)

        self.assertIn("hour_sin", result.columns)
        self.assertIn("hour_cos", result.columns)
        self.assertIn("dow_sin", result.columns)
        self.assertIn("dow_cos", result.columns)

        # Hour 0: sin(0) = 0, cos(0) = 1
        self.assertTrue(np.isclose(result.loc[0, "hour_sin"], 0.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[0, "hour_cos"], 1.0, atol=1e-6))

        # Hour 6: sin(pi/2) = 1, cos(pi/2) = 0
        self.assertTrue(np.isclose(result.loc[1, "hour_sin"], 1.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[1, "hour_cos"], 0.0, atol=1e-6))

        # Hour 12: sin(pi) = 0, cos(pi) = -1
        self.assertTrue(np.isclose(result.loc[2, "hour_sin"], 0.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[2, "hour_cos"], -1.0, atol=1e-6))

        # Hour 18: sin(3pi/2) = -1, cos(3pi/2) = 0
        self.assertTrue(np.isclose(result.loc[3, "hour_sin"], -1.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[3, "hour_cos"], 0.0, atol=1e-6))

    def test_cyclical_features_pythagorean_identity(self):
        """Verify that sin^2 + cos^2 == 1 for all hours and days of the week."""
        all_hours = list(range(24))
        all_dows = [h % 7 for h in all_hours]
        df = pd.DataFrame({"hour": all_hours, "day_of_week": all_dows})
        result = add_cyclical_features(df)

        hour_norm = result["hour_sin"] ** 2 + result["hour_cos"] ** 2
        self.assertTrue(np.allclose(hour_norm, 1.0, atol=1e-6))

        dow_norm = result["dow_sin"] ** 2 + result["dow_cos"] ** 2
        self.assertTrue(np.allclose(dow_norm, 1.0, atol=1e-6))

    def test_cyclical_features_smooth_periodicity(self):
        """Verify that hour 23 and hour 0 are close in Euclidean cyclical space."""
        df = pd.DataFrame({"hour": [0, 23], "day_of_week": [0, 0]})
        result = add_cyclical_features(df)

        p0 = np.array([result.loc[0, "hour_sin"], result.loc[0, "hour_cos"]])
        p23 = np.array([result.loc[1, "hour_sin"], result.loc[1, "hour_cos"]])
        p12 = np.array([np.sin(np.pi), np.cos(np.pi)])  # 12 hours away

        dist_adjacent = np.linalg.norm(p0 - p23)
        dist_opposite = np.linalg.norm(p0 - p12)

        self.assertLess(dist_adjacent, 0.3)
        self.assertGreater(dist_opposite, 1.9)


class TestPrepareHourlyPanel(unittest.TestCase):
    """Unit tests for prepare_hourly_panel using synthetic data."""

    def test_prepare_hourly_panel_correct_aggregation_and_mapping(self):
        """Verify half-hour aggregation, customer mapping, and chronological ordering."""
        tmp_csv = _generate_synthetic_ausgrid_csv(
            customers=[201, 202, 203],
            n_days=365,
            gc_val=0.15,
            cl_val=0.10,
            gg_val=0.40,
            capacity=4.2,
            postcode=2050,
        )
        try:
            hourly, mapping = prepare_hourly_panel(tmp_csv, num_houses=3)

            # Dimensions: 3 houses * 365 days * 24 hours = 26,280 rows
            self.assertEqual(len(hourly), 3 * 365 * 24)
            self.assertEqual(len(mapping), 3)

            # Check mapping
            self.assertListEqual(mapping["house_id"].tolist(), ["H001", "H002", "H003"])
            self.assertListEqual(mapping["source_customer_id"].tolist(), [201, 202, 203])
            self.assertTrue((mapping["generator_capacity_kwp"] == 4.2).all())
            self.assertTrue((mapping["postcode"] == 2050).all())

            # Check hourly aggregation math:
            # gc_kwh = 0.15 + 0.15 = 0.30
            # cl_kwh = 0.10 + 0.10 = 0.20
            # total_demand = 0.30 + 0.20 = 0.50
            # solar = 0.40 + 0.40 = 0.80
            self.assertTrue(np.allclose(hourly["total_demand_kwh"], 0.50, atol=1e-6))
            self.assertTrue(np.allclose(hourly["solar_generation_kwh"], 0.80, atol=1e-6))

            # Check chronological ordering per house
            for house_id, frame in hourly.groupby("house_id"):
                timestamps = pd.to_datetime(frame["timestamp"])
                self.assertTrue(timestamps.is_monotonic_increasing)
                self.assertEqual(len(timestamps), 8760)

            # Check cyclical features present
            for col in ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]:
                self.assertIn(col, hourly.columns)
        finally:
            if tmp_csv.exists():
                tmp_csv.unlink()

    def test_prepare_hourly_panel_invalid_schema_rejected(self):
        """Verify that CSVs missing documented columns are rejected."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tf:
            tf.write("Header Title\nCustomer,date,Row Quality\n1,01/01/2013,\n")
            bad_csv = pathlib.Path(tf.name)

        try:
            with self.assertRaises(ValueError) as ctx:
                prepare_hourly_panel(bad_csv, num_houses=1)
            self.assertIn("48-interval schema", str(ctx.exception))
        finally:
            if bad_csv.exists():
                bad_csv.unlink()

    def test_prepare_hourly_panel_insufficient_houses_rejected(self):
        """Verify that CSV with fewer complete-year houses than requested raises ValueError."""
        # Only 2 customers generated
        tmp_csv = _generate_synthetic_ausgrid_csv(customers=[101, 102], n_days=365)
        try:
            with self.assertRaises(ValueError) as ctx:
                prepare_hourly_panel(tmp_csv, num_houses=3)
            self.assertIn("Fewer than 3 houses", str(ctx.exception))
        finally:
            if tmp_csv.exists():
                tmp_csv.unlink()

    def test_prepare_hourly_panel_filters_bad_row_quality(self):
        """Verify that records with non-empty Row Quality are excluded from eligibility."""
        # Customer 101 has bad quality on day 1 -> has only 364 complete actual days
        tmp_csv = _generate_synthetic_ausgrid_csv(
            customers=[101, 102, 103],
            n_days=365,
            bad_quality_rows=1,  # Corrupts Customer 101's first row
        )
        try:
            with self.assertRaises(ValueError) as ctx:
                prepare_hourly_panel(tmp_csv, num_houses=3)
            # Since Customer 101 is ineligible, only 2 remain
            self.assertIn("Fewer than 3 houses", str(ctx.exception))
        finally:
            if tmp_csv.exists():
                tmp_csv.unlink()


class TestCreateLSTMSequences(unittest.TestCase):
    """Unit tests for create_lstm_sequences using synthetic data."""

    def setUp(self):
        """Construct a synthetic multi-house panel with known values."""
        n_hours = 120
        ts = pd.date_range("2013-01-01", periods=n_hours, freq="h")
        rows = []
        for house in ["H001", "H002"]:
            for i, t in enumerate(ts):
                rows.append({
                    "house_id": house,
                    "timestamp": t,
                    "total_demand_kwh": float(i + 1.0),
                    "solar_generation_kwh": float((i + 1.0) * 0.5),
                    "hour_sin": float(np.sin(2 * np.pi * t.hour / 24.0)),
                    "hour_cos": float(np.cos(2 * np.pi * t.hour / 24.0)),
                    "dow_sin": float(np.sin(2 * np.pi * t.dayofweek / 7.0)),
                    "dow_cos": float(np.cos(2 * np.pi * t.dayofweek / 7.0)),
                })
        self.df = pd.DataFrame(rows)
        self.feature_cols = [
            "total_demand_kwh", "solar_generation_kwh", "hour_sin", "hour_cos", "dow_sin", "dow_cos"
        ]
        self.target_cols = ["total_demand_kwh", "solar_generation_kwh"]

    def test_create_lstm_sequences_shapes_and_splits(self):
        """Verify train, validation, and test sequence dimensions."""
        lookback = 24
        train_frac = 0.80
        val_frac = 0.10

        seq, feat_scaler, targ_scaler = create_lstm_sequences(
            self.df,
            feature_columns=self.feature_cols,
            target_columns=self.target_cols,
            lookback_hours=lookback,
            train_fraction=train_frac,
            val_fraction_of_train=val_frac,
        )

        n_rows = 120
        split_idx = int(n_rows * train_frac)  # 96
        val_start = int(split_idx * (1.0 - val_frac))  # 86

        expected_train_per_house = val_start - lookback  # 86 - 24 = 62
        expected_val_per_house = split_idx - val_start   # 96 - 86 = 10
        expected_test_per_house = n_rows - split_idx     # 120 - 96 = 24

        n_houses = 2
        self.assertEqual(seq["X_train"].shape, (expected_train_per_house * n_houses, lookback, 6))
        self.assertEqual(seq["y_train"].shape, (expected_train_per_house * n_houses, 2))
        self.assertEqual(seq["X_val"].shape, (expected_val_per_house * n_houses, lookback, 6))
        self.assertEqual(seq["y_val"].shape, (expected_val_per_house * n_houses, 2))
        self.assertEqual(seq["X_test"].shape, (expected_test_per_house * n_houses, lookback, 6))
        self.assertEqual(seq["y_test"].shape, (expected_test_per_house * n_houses, 2))

    def test_create_lstm_sequences_chronological_ordering(self):
        """Verify strict chronological sequence progression without backward time jumps."""
        seq, _, _ = create_lstm_sequences(
            self.df,
            feature_columns=self.feature_cols,
            target_columns=self.target_cols,
            lookback_hours=24,
            train_fraction=0.80,
            val_fraction_of_train=0.10,
        )

        # Timestamps must be monotonic within each partition for each house
        for part in ["train", "val", "test"]:
            house_ids = seq[f"{part}_house_id"]
            timestamps = seq[f"{part}_target_timestamp"]
            for house in np.unique(house_ids):
                h_ts = timestamps[house_ids == house]
                self.assertTrue(np.all(h_ts[:-1] < h_ts[1:]))

        # Check partition chronological boundaries: max(train) < min(val) < min(test)
        for house in ["H001", "H002"]:
            h_train_ts = seq["train_target_timestamp"][seq["train_house_id"] == house]
            h_val_ts = seq["val_target_timestamp"][seq["val_house_id"] == house]
            h_test_ts = seq["test_target_timestamp"][seq["test_house_id"] == house]

            self.assertLess(h_train_ts[-1], h_val_ts[0])
            self.assertLess(h_val_ts[-1], h_test_ts[0])

    def test_create_lstm_sequences_lookback_target_alignment(self):
        """Verify that X[k] strictly spans [t - lookback, t - 1] and y[k] is at t."""
        lookback = 12
        seq, feat_scaler, targ_scaler = create_lstm_sequences(
            self.df,
            feature_columns=self.feature_cols,
            target_columns=self.target_cols,
            lookback_hours=lookback,
            train_fraction=0.80,
            val_fraction_of_train=0.10,
        )

        # Invert scaled X and y to original scale to verify exact value alignment
        # For H001, demand at step i is i + 1.0
        # Target row index for test sequence 0
        test_0_target_idx = seq["test_target_row_index"][0]
        test_0_y_actual = seq["test_actual_raw"][0]

        # Target demand at target_idx should be target_idx + 1.0
        self.assertTrue(np.isclose(test_0_y_actual[0], float(test_0_target_idx + 1.0), atol=1e-4))

        # The last row of lookback input X[0][-1] should be target_idx - 1 + 1.0 = target_idx
        # Invert scaled features
        x0_unscaled = feat_scaler.inverse_transform(seq["X_test"][0])
        self.assertTrue(np.isclose(x0_unscaled[-1, 0], float(test_0_target_idx), atol=1e-4))
        # First row of lookback input X[0][0] should be target_idx - lookback + 1.0
        self.assertTrue(np.isclose(x0_unscaled[0, 0], float(test_0_target_idx - lookback + 1.0), atol=1e-4))

    def test_create_lstm_sequences_scaler_leakage_isolation(self):
        """Verify that scalers are fitted ONLY on training period and test outliers do not leak."""
        # Inject extreme outlier in the test period based on timestamp
        df_corrupt = self.df.copy()
        split_point = int(120 * 0.80)
        test_start_ts = self.df["timestamp"].iloc[split_point]
        df_corrupt.loc[df_corrupt["timestamp"] >= test_start_ts, "total_demand_kwh"] = 99999.0

        _, feat_scaler_corrupt, _ = create_lstm_sequences(
            df_corrupt,
            feature_columns=self.feature_cols,
            target_columns=self.target_cols,
            lookback_hours=24,
            train_fraction=0.80,
            val_fraction_of_train=0.10,
        )

        # Normal scaler fitted on clean data
        _, feat_scaler_clean, _ = create_lstm_sequences(
            self.df,
            feature_columns=self.feature_cols,
            target_columns=self.target_cols,
            lookback_hours=24,
            train_fraction=0.80,
            val_fraction_of_train=0.10,
        )

        # The scaler max for total_demand_kwh MUST be identical despite 99999.0 in test
        self.assertTrue(np.isclose(feat_scaler_corrupt.data_max_[0], feat_scaler_clean.data_max_[0], atol=1e-5))
        self.assertLess(feat_scaler_corrupt.data_max_[0], 100.0)


if __name__ == "__main__":
    unittest.main()
