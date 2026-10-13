"""Data preprocessing and feature engineering for solar and demand forecasting.

Includes cyclical time encoding (hour_sin, hour_cos, dow_sin, dow_cos),
half-hour to hourly aggregation, and LSTM sequence creation.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def add_cyclical_features(
    df: pd.DataFrame,
    hour_col: str = "hour",
    dow_col: str = "day_of_week",
) -> pd.DataFrame:
    """Add sine and cosine cyclical encodings for hour of day and day of week.

    Args:
        df: Input DataFrame containing hour and day of week columns.
        hour_col: Name of hour column (values 0-23).
        dow_col: Name of day-of-week column (values 0-6).

    Returns:
        DataFrame with added cyclical features:
        - hour_sin = sin(2 * pi * hour / 24)
        - hour_cos = cos(2 * pi * hour / 24)
        - dow_sin = sin(2 * pi * day_of_week / 7)
        - dow_cos = cos(2 * pi * day_of_week / 7)
    """
    df = df.copy()
    if hour_col in df.columns:
        hours = df[hour_col].to_numpy(dtype=np.float64)
        df["hour_sin"] = np.sin(2.0 * np.pi * hours / 24.0)
        df["hour_cos"] = np.cos(2.0 * np.pi * hours / 24.0)
    elif "timestamp" in df.columns:
        hours = pd.to_datetime(df["timestamp"]).dt.hour.to_numpy(dtype=np.float64)
        df["hour_sin"] = np.sin(2.0 * np.pi * hours / 24.0)
        df["hour_cos"] = np.cos(2.0 * np.pi * hours / 24.0)

    if dow_col in df.columns:
        dows = df[dow_col].to_numpy(dtype=np.float64)
        df["dow_sin"] = np.sin(2.0 * np.pi * dows / 7.0)
        df["dow_cos"] = np.cos(2.0 * np.pi * dows / 7.0)
    elif "timestamp" in df.columns:
        dows = pd.to_datetime(df["timestamp"]).dt.dayofweek.to_numpy(dtype=np.float64)
        df["dow_sin"] = np.sin(2.0 * np.pi * dows / 7.0)
        df["dow_cos"] = np.cos(2.0 * np.pi * dows / 7.0)

    return df


def prepare_hourly_panel(
    raw_csv_path: Path,
    output_hourly_path: Optional[Path] = None,
    output_mapping_path: Optional[Path] = None,
    num_houses: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Parse Ausgrid raw solar home dataset and aggregate to hourly panel with cyclical features.

    Args:
        raw_csv_path: Path to raw 'Solar home 2012-2013.csv'.
        output_hourly_path: Path to save processed hourly CSV (optional).
        output_mapping_path: Path to save customer ID mapping CSV (optional).
        num_houses: Number of eligible full-year households to select.

    Returns:
        Tuple of (hourly DataFrame, house mapping DataFrame).
    """
    raw = pd.read_csv(raw_csv_path, header=1, low_memory=False, keep_default_na=False)
    interval_columns = raw.columns[5:53].tolist()
    if len(interval_columns) != 48 or raw.columns[53] != "Row Quality":
        raise ValueError("Source CSV does not have the documented 48-interval schema.")

    raw["Customer"] = pd.to_numeric(raw["Customer"], errors="coerce")
    raw["Generator Capacity"] = pd.to_numeric(raw["Generator Capacity"], errors="coerce")
    raw["date"] = pd.to_datetime(raw["date"], dayfirst=True, errors="coerce")
    raw[interval_columns] = raw[interval_columns].apply(pd.to_numeric, errors="coerce")

    actual = raw.loc[
        raw["Row Quality"].eq("") & raw[interval_columns].notna().all(axis=1)
    ].copy()

    required_categories = ["GC", "CL", "GG"]
    coverage = (
        actual.groupby(["Customer", "Consumption Category"])["date"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=required_categories, fill_value=0)
    )
    eligible_customers = sorted(
        int(cust)
        for cust in coverage.index[(coverage[required_categories] == 365).all(axis=1)]
    )
    if len(eligible_customers) < num_houses:
        raise ValueError(f"Fewer than {num_houses} houses have full-year actual records.")

    selected_customers = eligible_customers[:num_houses]
    house_ids = {cust: f"H{i:03d}" for i, cust in enumerate(selected_customers, 1)}

    selected = actual.loc[actual["Customer"].isin(selected_customers)]
    capacity_by_customer = (
        selected.drop_duplicates("Customer")
        .set_index("Customer")["Generator Capacity"]
        .to_dict()
    )
    postcode_by_customer = (
        selected.drop_duplicates("Customer")
        .set_index("Customer")["Postcode"]
        .to_dict()
    )
    keyed = selected.set_index(["Customer", "date", "Consumption Category"])
    source_dates = sorted(raw["date"].unique())

    hourly_records = []
    for customer in selected_customers:
        for day in source_dates:
            category_rows = {
                cat: keyed.loc[(customer, day, cat), interval_columns]
                for cat in required_categories
            }
            for hour in range(24):
                first_half, second_half = interval_columns[2 * hour : 2 * hour + 2]
                gc_kwh = float(category_rows["GC"][first_half] + category_rows["GC"][second_half])
                cl_kwh = float(category_rows["CL"][first_half] + category_rows["CL"][second_half])
                gg_kwh = float(category_rows["GG"][first_half] + category_rows["GG"][second_half])
                timestamp = pd.Timestamp(day) + pd.Timedelta(hours=hour)
                hour_val = timestamp.hour
                dow_val = timestamp.dayofweek
                hourly_records.append({
                    "house_id": house_ids[customer],
                    "timestamp": timestamp,
                    "total_demand_kwh": gc_kwh + cl_kwh,
                    "solar_generation_kwh": gg_kwh,
                    "generator_capacity_kwp": float(capacity_by_customer[customer]),
                    "hour": hour_val,
                    "day_of_week": dow_val,
                    "month": timestamp.month,
                    "hour_sin": float(np.sin(2.0 * np.pi * hour_val / 24.0)),
                    "hour_cos": float(np.cos(2.0 * np.pi * hour_val / 24.0)),
                    "dow_sin": float(np.sin(2.0 * np.pi * dow_val / 7.0)),
                    "dow_cos": float(np.cos(2.0 * np.pi * dow_val / 7.0)),
                })

    hourly = pd.DataFrame(hourly_records).sort_values(["house_id", "timestamp"]).reset_index(drop=True)
    house_mapping = pd.DataFrame([
        {
            "house_id": house_ids[customer],
            "source_customer_id": customer,
            "postcode": postcode_by_customer[customer],
            "generator_capacity_kwp": capacity_by_customer[customer],
            "selection_criteria": "365 complete actual days for GC, CL, and GG",
        }
        for customer in selected_customers
    ])

    if output_hourly_path is not None:
        output_hourly_path.parent.mkdir(parents=True, exist_ok=True)
        hourly.to_csv(output_hourly_path, index=False)
    if output_mapping_path is not None:
        output_mapping_path.parent.mkdir(parents=True, exist_ok=True)
        house_mapping.to_csv(output_mapping_path, index=False)

    return hourly, house_mapping


def create_lstm_sequences(
    hourly_df: pd.DataFrame,
    feature_columns: List[str],
    target_columns: List[str],
    lookback_hours: int = 24,
    train_fraction: float = 0.80,
    val_fraction_of_train: float = 0.10,
) -> Tuple[Dict[str, np.ndarray], MinMaxScaler, MinMaxScaler]:
    """Generate sequential train/val/test matrices with chronological splits and feature scaling.

    Args:
        hourly_df: Prepared hourly panel.
        feature_columns: List of input feature names (e.g. demand, solar, cyclical features).
        target_columns: List of target column names to predict (e.g. demand, solar).
        lookback_hours: Sequence window length in hours (default 24).
        train_fraction: Proportion of time series for train+val.
        val_fraction_of_train: Proportion of train period used for validation.

    Returns:
        Tuple of (sequence dictionary, feature_scaler, target_scaler).
    """
    houses = {
        house_id: frame.sort_values("timestamp").reset_index(drop=True)
        for house_id, frame in hourly_df.groupby("house_id", sort=True)
    }
    n_rows = len(next(iter(houses.values())))
    split_index = int(n_rows * train_fraction)
    validation_start = int(split_index * (1.0 - val_fraction_of_train))

    feat_fit_values = np.concatenate([
        frame.loc[: validation_start - 1, feature_columns].to_numpy(dtype=np.float64)
        for frame in houses.values()
    ], axis=0)
    target_fit_values = np.concatenate([
        frame.loc[: validation_start - 1, target_columns].to_numpy(dtype=np.float64)
        for frame in houses.values()
    ], axis=0)

    feature_scaler = MinMaxScaler(feature_range=(0, 1))
    feature_scaler.fit(feat_fit_values)

    target_scaler = MinMaxScaler(feature_range=(0, 1))
    target_scaler.fit(target_fit_values)

    sequence_lists = {
        name: [] for name in ["X_train", "y_train", "X_val", "y_val", "X_test", "y_test", "baseline_test"]
    }
    sequence_meta = {
        name: [] for name in [
            "train_house_id", "train_target_timestamp", "train_target_row_index",
            "val_house_id", "val_target_timestamp", "val_target_row_index",
            "test_house_id", "test_target_timestamp", "test_target_row_index", "test_actual_raw",
        ]
    }

    for house_id, frame in houses.items():
        raw_feats = frame[feature_columns].to_numpy(dtype=np.float64)
        scaled_feats = feature_scaler.transform(raw_feats)
        raw_targets = frame[target_columns].to_numpy(dtype=np.float64)
        scaled_targets = target_scaler.transform(raw_targets)
        timestamps = frame["timestamp"].to_numpy(dtype="datetime64[ns]")

        for target_idx in range(lookback_hours, n_rows):
            x_raw = raw_feats[target_idx - lookback_hours : target_idx]
            x_scaled = scaled_feats[target_idx - lookback_hours : target_idx]
            y_raw = raw_targets[target_idx]
            y_scaled = scaled_targets[target_idx]

            if target_idx < validation_start:
                part = "train"
            elif target_idx < split_index:
                part = "val"
            else:
                part = "test"

            sequence_lists[f"X_{part}"].append(x_scaled.astype(np.float32))
            sequence_lists[f"y_{part}"].append(y_scaled.astype(np.float32))
            sequence_meta[f"{part}_house_id"].append(house_id)
            sequence_meta[f"{part}_target_timestamp"].append(timestamps[target_idx])
            sequence_meta[f"{part}_target_row_index"].append(target_idx)
            if part == "test":
                sequence_lists["baseline_test"].append(x_raw[-1, : len(target_columns)].astype(np.float32))
                sequence_meta["test_actual_raw"].append(y_raw.astype(np.float32))

    seq = {name: np.asarray(values, dtype=np.float32) for name, values in sequence_lists.items()}
    for key, values in sequence_meta.items():
        if key.endswith("_timestamp"):
            seq[key] = np.asarray(values, dtype="datetime64[ns]")
        elif key.endswith("_house_id"):
            seq[key] = np.asarray(values, dtype="U4")
        else:
            seq[key] = np.asarray(values)

    seq["feature_columns"] = np.asarray(feature_columns, dtype="U32")
    seq["target_columns"] = np.asarray(target_columns, dtype="U32")
    seq["lookback_hours"] = np.asarray(lookback_hours)
    seq["house_train_test_split_index"] = np.asarray(split_index)
    seq["scaler_fit_end_index"] = np.asarray(validation_start - 1)

    return seq, feature_scaler, target_scaler
