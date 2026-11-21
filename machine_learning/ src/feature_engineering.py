"""Create transparent, research-only features from the available project summaries."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "tmin_c_season_mean", "tmax_c_season_mean", "diurnal_temp_range_c", "tmean_proxy_c_season_mean",
    "relative_humidity_pct_season_mean", "vpd_proxy_season_kpa", "wind_speed_m_s_season_mean",
    "solar_radiation_mj_m2_day_season_mean", "pressure_kpa_season_mean", "rainfall_season_mm",
    "sand_pct", "silt_pct", "clay_pct", "bulk", "organic_carbon", "ph_water", "latitude", "longitude",
]
FORBIDDEN_PREDICTOR_TOKENS = ("et0", "etc", "water_scenario", "irrigation", "water_values", "gross_", "net_")


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add derived weather/texture summaries; these seasonal inputs are retrospective."""
    out = frame.copy()
    if {"tmax_c_season_mean", "tmin_c_season_mean"}.issubset(out.columns):
        out["diurnal_temp_range_c"] = out["tmax_c_season_mean"] - out["tmin_c_season_mean"]
        out["tmean_proxy_c_season_mean"] = (out["tmax_c_season_mean"] + out["tmin_c_season_mean"]) / 2
    temperature = "tmean_proxy_c_season_mean" if "tmean_proxy_c_season_mean" in out else "tmax_c_season_mean"
    if temperature in out and "relative_humidity_pct_season_mean" in out:
        temp = pd.to_numeric(out[temperature], errors="coerce")
        humidity = pd.to_numeric(out["relative_humidity_pct_season_mean"], errors="coerce") / 100
        es = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
        out["vpd_proxy_season_kpa"] = (es * (1 - humidity)).clip(lower=0)
    if temperature in out and "rainfall_season_mm" in out:
        temp = pd.to_numeric(out[temperature], errors="coerce")
        out["season_aridity_index"] = pd.to_numeric(out["rainfall_season_mm"], errors="coerce") / (temp + 10)
    if {"clay_pct", "sand_pct"}.issubset(out.columns):
        out["clay_to_sand_ratio"] = pd.to_numeric(out["clay_pct"], errors="coerce") / (pd.to_numeric(out["sand_pct"], errors="coerce") + 1)
    if {"awc_smu_mm_per_m", "clay_pct"}.issubset(out.columns):
        out["soil_water_retention_index_mm_per_m"] = pd.to_numeric(out["awc_smu_mm_per_m"], errors="coerce") * pd.to_numeric(out["clay_pct"], errors="coerce") / 100
    return out


def select_candidate_features(frame: pd.DataFrame, configured: list[str]) -> list[str]:
    """Validate an explicitly reviewed feature list; never infer features from all numeric columns."""
    if not configured:
        raise ValueError("No features are configured. Review prediction-time availability and set model.features in config.yaml.")
    missing = [column for column in configured if column not in frame.columns]
    if missing:
        raise ValueError(f"Configured feature(s) are missing from the training data: {missing}")
    forbidden = [column for column in configured if any(token in column.lower() for token in FORBIDDEN_PREDICTOR_TOKENS)]
    if forbidden:
        raise ValueError(f"Potential target-derived or calculated-water leakage feature(s) are forbidden: {forbidden}")
    return configured


def write_feature_reports(ml_root: Path, frame: pd.DataFrame) -> None:
    reports = ml_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    candidates = [column for column in FEATURE_COLUMNS if column in frame.columns]
    descriptions = {
        "diurnal_temp_range_c": ("degC", "Seasonal mean daily max minus min temperature; retrospective."),
        "tmean_proxy_c_season_mean": ("degC", "Proxy: average of seasonal maximum and minimum means."),
        "vpd_proxy_season_kpa": ("kPa", "Vapor-pressure-deficit proxy based on seasonal mean temperature and humidity."),
        "season_aridity_index": ("unitless", "Descriptive seasonal rainfall/temperature index."),
        "clay_to_sand_ratio": ("unitless", "Mapped clay percentage divided by sand percentage plus one."),
    }
    lines = ["# Feature selection report", "", "**Status: descriptive candidate features only. Supervised selection is blocked because no verified field-measured target exists.**", "",
             "No target correlation, model feature importance, or supervised selector was computed.", "",
             "| Candidate feature | Unit | Definition | Availability / limitation |", "|---|---|---|---|"]
    units = {"tmin_c_season_mean": "degC", "tmax_c_season_mean": "degC", "relative_humidity_pct_season_mean": "%",
             "wind_speed_m_s_season_mean": "m/s", "solar_radiation_mj_m2_day_season_mean": "MJ/m2/day",
             "pressure_kpa_season_mean": "kPa", "rainfall_season_mm": "mm/season", "sand_pct": "%",
             "silt_pct": "%", "clay_pct": "%", "bulk": "g/cm3 (source metadata; verify)",
             "organic_carbon": "% (source metadata; verify)", "ph_water": "pH", "latitude": "degrees north", "longitude": "degrees east"}
    for column in candidates:
        unit, definition = descriptions.get(column, (units.get(column, "verify source"), "Source table field; review source metadata."))
        lines.append(f"| `{column}` | {unit} | {definition} | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |")
    lines.extend(["", "Do not use seasonal weather summaries for a prediction made before that season ends. Do not use ET0, ETc, water scenarios, or any quantity derived from the target as a feature."])
    (reports / "feature_selection_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    split = ["# Data splitting strategy", "",
             "## Current data", "",
             f"- Seasonal feature rows available: {len(frame)}.",
             "- Current project snapshots cover 38 grid points and 7 rice seasons (2017-2023); the data quality report identifies only five distinct daily weather series across those points.",
             "- There are no verified field-measured irrigation labels, so no train/validation/test split was created and no model score can be calculated.", "",
             "## Required strategy after field labels arrive", "",
             "1. Define one row as one measured field-season and attach a stable field/farm identifier, season, and measurement provenance.",
             "2. Keep every row from a farm/field/experiment group together. Use a grouped holdout for final testing; if predicting future seasons, reserve later seasons as well.",
             "3. Fit imputation, encoding, and scaling only inside each training fold using a scikit-learn Pipeline.",
             "4. Tune on training groups only. Reserve the grouped test set until one final evaluation.",
             "5. Report group counts, dates, locations, metrics in the verified target unit, and the limitations caused by too few independent groups.", "",
             "A random row split is not acceptable for repeated farm, experiment, point, or season observations."]
    (reports / "data_splitting_strategy.md").write_text("\n".join(split) + "\n", encoding="utf-8")


def run_eda(ml_root: str | Path) -> tuple[Path, Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    root = Path(ml_root).resolve()
    data_path = root / "data" / "processed" / "cleaned_dataset.csv"
    if not data_path.exists():
        raise FileNotFoundError(f"Run notebook 02 first; missing {data_path}")
    frame = pd.read_csv(data_path, low_memory=False)
    feature_frame = engineer_features(frame)
    safe = [column for column in FEATURE_COLUMNS if column in feature_frame.columns]
    numeric = feature_frame[safe].apply(pd.to_numeric, errors="coerce")
    summary = numeric.describe().T
    reports = root / "reports"
    viz_dist = root / "visualizations" / "distributions"
    viz_corr = root / "visualizations" / "correlations"
    reports.mkdir(parents=True, exist_ok=True)
    viz_dist.mkdir(parents=True, exist_ok=True)
    viz_corr.mkdir(parents=True, exist_ok=True)
    if safe:
        n = min(12, len(safe))
        axes = numeric[safe[:n]].hist(bins=20, figsize=(12, max(4, 2.6 * ((n + 2) // 3))), layout=((n + 2) // 3, 3))
        plt.tight_layout()
        plt.savefig(viz_dist / "feature_distributions.png", dpi=150)
        plt.close("all")
        corr = numeric.corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(11, 8))
        sns.heatmap(corr, cmap="vlag", center=0, ax=ax, cbar_kws={"label": "Pearson correlation"})
        ax.set_title("Descriptive correlations among available non-target features")
        fig.tight_layout()
        fig.savefig(viz_corr / "feature_correlations.png", dpi=150)
        plt.close(fig)
    lines = ["# Exploratory data analysis report", "", "## Scope", "",
             f"- Rows in joined seasonal feature table: {len(frame)}.",
             f"- Numeric feature columns summarized: {len(safe)}.",
             "- Target-related correlations and target plots were not produced: current water values are calculated estimates, not verified measured irrigation.",
             "- Input features are seasonal summaries and therefore retrospective; they are not available at planting time.", "",
             "## Numeric summary", "", "```text\n" + summary.round(4).to_string() + "\n```", "",
             "## Interpretation and modeling implications", "",
             "The seasonal summary joins NASA POWER gridded weather to mapped soil and project points. Nearby points may share the same weather series. Any future evaluation must hold out field/farm/experiment groups and account for seasons; random-row splitting would overstate generalization.",
             "No causal interpretation should be made from correlations. Soil profiles are mapped proxies, not individual-field tests.", "",
             "## Figures", "", "- `visualizations/distributions/feature_distributions.png`", "- `visualizations/correlations/feature_correlations.png`"]
    report_path = reports / "eda_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, viz_corr / "feature_correlations.png"


def run_feature_engineering(ml_root: str | Path) -> Path:
    root = Path(ml_root).resolve()
    source = root / "data" / "processed" / "cleaned_dataset.csv"
    if not source.exists():
        raise FileNotFoundError(f"Run notebook 02 first; missing {source}")
    frame = pd.read_csv(source, low_memory=False)
    engineered = engineer_features(frame)
    output = root / "data" / "processed" / "features_engineered.csv"
    engineered.to_csv(output, index=False)
    write_feature_reports(root, engineered)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    print(run_feature_engineering(args.root))


if __name__ == "__main__":
    main()
