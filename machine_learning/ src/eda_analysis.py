#!/usr/bin/env python3
"""Phase 3 - Exploratory Data Analysis (EDA) (Smart Agricultural Water Management, ML component).

What this script does
---------------------
1. Loads the cleaned datasets generated in Phase 2 (`data/processed/` and `data/intermediate/`).
2. Computes descriptive statistics across weather, soil, season summaries, and literature trials.
3. Analyzes spatial grouping (`weather_cell_id`), seasonal trends (2017-2023), and feature correlations.
4. Generates publication-ready EDA visualizations in `visualizations/eda/` and a markdown summary in `reports/eda_report.md`.

Principles
----------
* Uses ONLY cleaned Phase 2 outputs (never touches raw SQLite).
* Respects `exclude_from_ml` flags on incomplete soil points (2 of 38 points).
* Never treats calculated water scenarios as measured targets.

Usage
-----
    python src/eda_analysis.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SEED = 42


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_none_"
    d = df.head(max_rows)
    cols = [str(c) for c in d.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in d.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v).replace("|", "/").replace("\n", " ")
                                       for v in r) + " |")
    return "\n".join(out)


def run(root: Path) -> None:
    np.random.seed(SEED)
    proc = root / "data" / "processed"
    inter = root / "data" / "intermediate"
    rep = root / "reports"
    viz = root / "visualizations" / "eda"
    for p in (rep, viz):
        p.mkdir(parents=True, exist_ok=True)

    # Load cleaned datasets from Phase 2
    dataset_path = proc / "cleaned_dataset.csv"
    weather_path = proc / "cleaned_weather_daily.csv"
    soil_path = proc / "cleaned_soil.csv"
    obs_path = inter / "literature_trial_observation_cleaned.csv"

    if not dataset_path.exists():
        raise SystemExit(f"Missing Phase 2 output: {dataset_path}. Run src/data_cleaning.py first.")

    df = pd.read_csv(dataset_path)
    weather = pd.read_csv(weather_path)
    soil = pd.read_csv(soil_path)
    obs = pd.read_csv(obs_path) if obs_path.exists() else pd.DataFrame()

    # Filter usable points for ML analysis
    usable_df = df[~df["exclude_from_ml"].fillna(False)].copy()
    usable_soil = soil[~soil["exclude_from_ml"].fillna(False)].copy()

    # 1. Descriptive Statistics (Season Features)
    num_cols = [c for c in usable_df.select_dtypes(include=[np.number]).columns
                if c not in ("point_id", "season_year", "latitude", "longitude", "weather_day_count")]
    stats = usable_df[num_cols].describe().T[["count", "mean", "std", "min", "50%", "max"]].round(3)
    stats = stats.reset_index().rename(columns={"index": "Feature", "50%": "median"})

    # 2. Seasonal Trends (2017 - 2023)
    season_trends = usable_df.groupby("season_year").agg(
        mean_tmax=("tmax_c_season_mean", "mean"),
        mean_rh=("relative_humidity_pct_season_mean", "mean"),
        total_rain_mm=("rainfall_season_mm", "mean"),
        points_count=("point_id", "nunique")
    ).round(2).reset_index()

    # 3. Literature Benchmark Summary
    lit_summary = pd.DataFrame()
    if not obs.empty:
        irr_metrics = ["seasonal_irrigation_applied", "irrigation_water_applied",
                       "total_water_applied", "total_irrigation_water"]
        lit_irr = obs[obs["metric_name"].isin(irr_metrics) & obs["metric_value"].notna()].copy()
        if not lit_irr.empty:
            lit_summary = lit_irr.groupby("metric_name")["metric_value"].agg(
                count="count", mean="mean", std="std", min="min", median="median", max="max"
            ).round(1).reset_index()

    # 4. Visualizations
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 110})

    # Plot 1: Correlation Heatmap of Season Features
    corr_cols = [c for c in num_cols if usable_df[c].nunique() > 1][:12]
    if len(corr_cols) >= 2:
        corr = usable_df[corr_cols].corr()
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr_cols)))
        ax.set_yticks(range(len(corr_cols)))
        ax.set_xticklabels(corr_cols, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(corr_cols, fontsize=8)
        for i in range(len(corr_cols)):
            for j in range(len(corr_cols)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Feature Correlation Matrix (Usable Rice Seasons 2017-2023)")
        fig.tight_layout()
        fig.savefig(viz / "01_feature_correlations.png")
        plt.close(fig)

    # Plot 2: Inter-annual Weather Variability across Seasons
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    axes[0].plot(season_trends["season_year"], season_trends["mean_tmax"], marker="o", color="#d95f02")
    axes[0].set_title("Season Mean Tmax (C)")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(season_trends["season_year"], season_trends["mean_rh"], marker="s", color="#1b9e77")
    axes[1].set_title("Season Mean RH (%)")
    axes[1].grid(True, alpha=0.3)

    axes[2].bar(season_trends["season_year"], season_trends["total_rain_mm"], color="#7570b3")
    axes[2].set_title("Season Rainfall (mm)")
    axes[2].grid(True, alpha=0.3)

    fig.suptitle("Inter-Annual Climatic Variability (Kafr El Sheikh, 2017-2023)")
    fig.tight_layout()
    fig.savefig(viz / "02_seasonal_trends.png")
    plt.close(fig)

    # Plot 3: Soil Texture Composition across Usable Points
    if {"sand_pct", "silt_pct", "clay_pct"}.issubset(usable_soil.columns):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        idx = np.arange(len(usable_soil))
        ax.bar(idx, usable_soil["clay_pct"], label="Clay %", color="#8c510a")
        ax.bar(idx, usable_soil["silt_pct"], bottom=usable_soil["clay_pct"], label="Silt %", color="#d8b365")
        ax.bar(idx, usable_soil["sand_pct"],
               bottom=usable_soil["clay_pct"] + usable_soil["silt_pct"], label="Sand %", color="#f6e8c3")
        ax.set_xlabel("Usable Grid Points (n=36)")
        ax.set_ylabel("Percentage (%)")
        ax.set_title("Soil Texture Breakdown Across Valid Grid Points")
        ax.legend()
        fig.tight_layout()
        fig.savefig(viz / "03_soil_texture_breakdown.png")
        plt.close(fig)

    # 5. Write EDA Report
    report_lines = [
        "# Exploratory Data Analysis (EDA) Report - Phase 3",
        "",
        "Generated by `src/eda_analysis.py` using cleaned Phase 2 datasets.",
        "",
        "## 1. Dataset Overview",
        f"- **Total rows in `cleaned_dataset.csv`:** {len(df)} (38 points x 7 seasons)",
        f"- **Usable rows for ML (`exclude_from_ml == False`):** {len(usable_df)} (36 points x 7 seasons)",
        f"- **Distinct spatial weather cells (`weather_cell_id`):** {usable_df['weather_cell_id'].nunique()}",
        f"- **Daily weather records analyzed:** {len(weather):,}",
        "",
        "## 2. Descriptive Statistics (Usable Season Features)",
        md_table(stats, max_rows=35),
        "",
        "## 3. Inter-Annual Seasonal Trends (2017-2023)",
        md_table(season_trends),
        "",
        "## 4. Literature Irrigation Benchmarks (m3/feddan)",
        "Reference ranges from published research trials (not used as training labels):",
        md_table(lit_summary),
        "",
        "## 5. Key Takeaways for Phase 4 (Feature Engineering & Splitting)",
        "1. **Group Splitting Mandatory:** All train/validation splits must group by `weather_cell_id` (14 unique cells) to prevent spatial weather leakage.",
        "2. **Soil Exclusions:** 2 grid points lack soil profiles (`exclude_from_ml=True`) and must remain excluded or imputed strictly inside training folds.",
        "3. **No Measured Farm Target:** Supervised model training remains blocked until field survey irrigation labels (`m3/feddan`) are collected.",
        "",
        "## 6. Generated Visuals",
        "- `visualizations/eda/01_feature_correlations.png`",
        "- `visualizations/eda/02_seasonal_trends.png`",
        "- `visualizations/eda/03_soil_texture_breakdown.png`",
    ]
    (rep / "eda_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print("Phase 3 EDA completed successfully. Reports and charts saved.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="machine_learning/ root")
    args = ap.parse_args()
    run(Path(args.root))


if __name__ == "__main__":
    main()
