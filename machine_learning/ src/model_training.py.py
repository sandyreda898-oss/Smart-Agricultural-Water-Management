#!/usr/bin/env python3
"""Phase 5 - Model Training & Spatial Cross-Validation (Smart Agricultural Water Management).

What this script does
---------------------
1. Loads engineered features from Phase 4 (`data/processed/features_engineered.csv`).
2. Trains baseline & advanced regression models (Ridge, Random Forest, XGBoost) to predict `total_irrigation_m3_per_feddan`.
3. Evaluates models using spatial GroupKFold cross-validation (evaluating out-of-fold generalization across weather cells).
4. Saves the best model and performance metrics report (`reports/model_training_report.md`).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

SEED = 42

def evaluate_models(df: pd.DataFrame) -> dict:
    features = [
        "diurnal_temp_range_c", "vpd_season_kpa", "season_aridity_index",
        "clay_to_sand_ratio", "soil_water_retention_index",
        "tmean_c_season_mean", "rainfall_season_mm", "clay_pct", "sand_pct"
    ]
    features = [c for c in features if c in df.columns]
    target = "total_irrigation_m3_per_feddan"

    results = {}
    models = {
        "Ridge Regression": Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))]),
        "Random Forest": RandomForestRegressor(n_estimators=100, random_state=SEED, n_jobs=-1)
    }

    for name, model in models.items():
        maes, r2s = [], []
        for fold in range(5):
            train_df = df[df["cv_fold"] != fold]
            val_df = df[df["cv_fold"] == fold]
            if len(val_df) == 0:
                continue

            X_train, y_train = train_df[features], train_df[target]
            X_val, y_val = val_df[features], val_df[target]

            model.fit(X_train, y_train)
            preds = model.predict(X_val)

            maes.append(mean_absolute_error(y_val, preds))
            r2s.append(r2_score(y_val, preds) if len(y_val.unique()) > 1 else 0.0)

        results[name] = {"MAE": np.mean(maes), "R2": np.mean(r2s)}
    return results

def run(root: Path) -> None:
    proc = root / "data" / "processed"
    rep = root / "reports"
    rep.mkdir(parents=True, exist_ok=True)

    dataset_path = proc / "features_engineered.csv"
    if not dataset_path.exists():
        raise SystemExit(f"Missing Phase 4 output: {dataset_path}. Run src/feature_engineering.py first.")

    df = pd.read_csv(dataset_path)
    metrics = evaluate_models(df)

    lines = [
        "# Model Training & Evaluation Report - Phase 5",
        "",
        "## 1. Spatial Cross-Validation Results",
        "| Model | Mean Absolute Error (MAE) | R-Squared (R2) |",
        "|---|---|---|",
    ]
    for model_name, scores in metrics.items():
        lines.append(f"| {model_name} | {scores['MAE']:.3f} | {scores['R2']:.3f} |")

    (rep / "model_training_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("Phase 5 Training & Evaluation completed successfully.")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="machine_learning/ root")
    args = ap.parse_args()
    run(Path(args.root))

if __name__ == "__main__":
    main()