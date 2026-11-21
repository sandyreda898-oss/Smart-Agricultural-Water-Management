"""Grouped, leakage-safe regression workflow gated on verified field measurements."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, RandomizedSearchCV, cross_validate
from sklearn.tree import DecisionTreeRegressor

from .feature_engineering import select_candidate_features
from .preprocessing import build_model_pipeline

SEED = 42
TARGET_DEFAULT = "total_irrigation_m3_per_feddan"
ACCEPTED_MEASUREMENT_STATUSES = {"FIELD_MEASURED", "VERIFIED_FIELD_MEASUREMENT", "MEASURED"}
FORBIDDEN_LABEL_MARKERS = ("SCENARIO", "MODEL_ESTIMATE", "CALCULATED", "NOT_MEASURED", "RECOMMENDATION")


def load_config(root: str | Path) -> dict:
    path = Path(root).resolve() / "config" / "config.yaml"
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    return config


def training_readiness(root: str | Path) -> tuple[pd.DataFrame | None, list[str], dict]:
    """Return data only if target provenance, unit, groups, and features are explicitly verified."""
    base = Path(root).resolve()
    config = load_config(base)
    data_config = config.get("data", {})
    model_config = config.get("model", {})
    target = data_config.get("target", TARGET_DEFAULT)
    group_column = data_config.get("group_column", "field_group_id")
    status_column = data_config.get("target_status_column", "target_status")
    dataset_path = base / data_config.get("training_dataset", "data/processed/training_dataset.csv")
    reasons: list[str] = []
    if not data_config.get("target_verified", False):
        reasons.append("config.yaml does not mark the target as verified field measurement.")
    if not data_config.get("target_unit_confirmed", False):
        reasons.append("The target unit and measurement definition have not been confirmed by the data owner.")
    if not dataset_path.is_file():
        reasons.append(f"Verified training dataset is not present: {dataset_path.relative_to(base)}.")
        return None, reasons, config
    frame = pd.read_csv(dataset_path, low_memory=False)
    required = [target, group_column, status_column, "measurement_method", "target_source"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        reasons.append(f"Training dataset is missing required provenance column(s): {missing}.")
    if not missing:
        statuses = frame[status_column].astype("string").str.strip().str.upper()
        bad_status = ~statuses.isin(ACCEPTED_MEASUREMENT_STATUSES)
        if bad_status.any():
            reasons.append(f"{int(bad_status.sum())} rows do not have an accepted field-measured target status.")
        sources = frame.get("target_source", pd.Series("", index=frame.index)).astype("string").str.upper()
        if sources.isna().any() or sources.str.strip().eq("").any():
            reasons.append("Each target row needs a documented target_source/provenance record.")
        if sources.map(lambda value: any(marker in value for marker in FORBIDDEN_LABEL_MARKERS)).any():
            reasons.append("A target source is marked as a scenario, calculation, model estimate, or recommendation.")
        y = pd.to_numeric(frame[target], errors="coerce")
        if y.isna().any() or not np.isfinite(y.dropna().to_numpy(dtype=float)).all():
            reasons.append("Target values contain missing or non-finite entries; target values are never imputed.")
        if (y.dropna() < 0).any():
            reasons.append("Negative irrigation target values are invalid and must be resolved at source.")
        method = frame["measurement_method"].astype("string").str.strip()
        if method.isna().any() or method.eq("").any():
            reasons.append("Each target row needs a documented measurement method (for example, calibrated flow-meter reading).")
        groups = frame[group_column].dropna().astype(str).nunique()
        minimum = int(model_config.get("minimum_independent_groups", 10))
        if groups < minimum:
            reasons.append(f"Only {groups} independent {group_column} groups are available; at least {minimum} are required for this grouped workflow.")
    features = list(model_config.get("features", []))
    if not features:
        reasons.append("No prediction-time features are configured. Review and set model.features explicitly.")
    elif not missing:
        try:
            select_candidate_features(frame, features)
        except ValueError as exc:
            reasons.append(str(exc))
    if reasons:
        return None, reasons, config
    return frame, [], config


def _write_blocked_state(root: Path, phase: str, reasons: list[str]) -> None:
    models = root / "models"
    reports = root / "reports"
    models.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    target = load_config(root).get("data", {}).get("target", TARGET_DEFAULT)
    unit = load_config(root).get("data", {}).get("target_unit", "m3/feddan")
    metrics_path = models / "model_metrics.json"
    metrics = {"training_status": "blocked", "target": target, "unit": unit, "rows": 0,
               "independent_groups": 0, "metrics": None, "reasons": reasons}
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    metadata = {"model_version": "not_trained", "training_status": "blocked", "target": target,
                "target_unit": unit, "reason": "No verified field-measured irrigation training dataset is available.",
                "training_dataset": None, "features": [], "seed": SEED}
    (models / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    schema = {"training_status": "blocked", "features": [], "target": target, "target_unit": unit,
              "candidate_features": [], "feature_ranges": {}, "categorical_values": {},
              "note": "Not a deployable prediction schema. Candidate inputs must be reviewed after field target verification."}
    (models / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (models / "model_version.txt").write_text("not_trained\n", encoding="utf-8")
    report_file = {
        "compare": "model_training_report.md", "tune": "hyperparameter_tuning_report.md",
        "evaluate": "model_evaluation_report.md",
    }.get(phase, "model_training_report.md")
    title = {"compare": "Model training and comparison", "tune": "Hyperparameter tuning", "evaluate": "Model evaluation"}.get(phase, "Model workflow")
    text = [f"# {title}", "", "**Status: BLOCKED - no model was trained and no model artifact was created.**", "",
            *[f"- {reason}" for reason in reasons], "",
            "Calculated FAO-based water scenarios, ETc, recommendations, and published trial summaries are not accepted as measured farm-irrigation labels."]
    (reports / report_file).write_text("\n".join(text) + "\n", encoding="utf-8")


def _split_groups(frame: pd.DataFrame, group_column: str, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed)
    train_index, test_index = next(splitter.split(frame, groups=frame[group_column]))
    if frame.iloc[train_index][group_column].nunique() < 2 or frame.iloc[test_index][group_column].nunique() < 1:
        raise ValueError("Grouped train/test split is too small. Collect more independent farms or field groups.")
    return train_index, test_index


def compare_models(root: str | Path) -> bool:
    """Compare baseline and tree/linear candidates on grouped CV within training groups only."""
    base = Path(root).resolve()
    frame, reasons, config = training_readiness(base)
    if reasons or frame is None:
        _write_blocked_state(base, "compare", reasons)
        return False
    data_cfg, model_cfg = config["data"], config["model"]
    target, group_col = data_cfg["target"], data_cfg["group_column"]
    features = list(model_cfg["features"])
    x, y = frame[features], pd.to_numeric(frame[target], errors="raise")
    train_idx, test_idx = _split_groups(frame, group_col, float(model_cfg.get("test_fraction", 0.2)), SEED)
    train = frame.iloc[train_idx].copy()
    split = pd.DataFrame({"row_index": np.arange(len(frame)), "split_set": "train"})
    split.loc[test_idx, "split_set"] = "test"
    split["group"] = frame[group_col].astype(str).to_numpy()
    (base / "data" / "processed").mkdir(parents=True, exist_ok=True)
    split.to_csv(base / "data" / "processed" / "model_split.csv", index=False)
    n_splits = min(int(model_cfg.get("cv_splits", 5)), train[group_col].nunique())
    if n_splits < 2:
        raise ValueError("At least two independent training groups are needed for cross-validation.")
    cv = GroupKFold(n_splits=n_splits)
    candidates = {
        "median_baseline": DummyRegressor(strategy="median"),
        "ridge": Ridge(alpha=1.0),
        "decision_tree": DecisionTreeRegressor(max_depth=5, min_samples_leaf=3, random_state=SEED),
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
        "gradient_boosting": GradientBoostingRegressor(random_state=SEED),
    }
    results = []
    for name, estimator in candidates.items():
        pipeline = build_model_pipeline(train[features], estimator, features)
        start = time.perf_counter()
        scores = cross_validate(pipeline, train[features], train[target].astype(float), groups=train[group_col],
                                cv=cv, scoring={"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"},
                                return_train_score=False, n_jobs=1)
        results.append({"model": name, "cv_mae": float(-scores["test_mae"].mean()),
                        "cv_rmse": float(-scores["test_rmse"].mean()), "cv_r2": float(scores["test_r2"].mean()),
                        "fit_and_cv_seconds": time.perf_counter() - start})
    result_frame = pd.DataFrame(results).sort_values("cv_mae")
    best_name = str(result_frame.iloc[0]["model"])
    estimator = candidates[best_name]
    candidate = build_model_pipeline(train[features], estimator, features).fit(train[features], train[target].astype(float))
    import joblib
    (base / "models").mkdir(parents=True, exist_ok=True)
    joblib.dump(candidate, base / "models" / "candidate_pipeline.joblib")
    results_path = base / "data" / "intermediate" / "model_comparison.csv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    result_frame.to_csv(results_path, index=False)
    report = ["# Model training and comparison", "", "**Status: grouped cross-validation completed; final test set remains untouched.**", "",
              f"- Rows: {len(frame)}; training rows: {len(train_idx)}; reserved test rows: {len(test_idx)}.",
              f"- Independent groups: {frame[group_col].nunique()} total; {train[group_col].nunique()} in training.",
              f"- Target: `{target}` ({data_cfg['target_unit']}).", f"- Selected by grouped CV MAE: `{best_name}`.", "",
              "```text\n" + result_frame.to_string(index=False) + "\n```", "", "No final test metrics were calculated in this phase."]
    (base / "reports" / "model_training_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    state = {"training_status": "candidate_trained_test_reserved", "target": target, "unit": data_cfg["target_unit"],
             "rows": len(frame), "independent_groups": int(frame[group_col].nunique()), "candidate": best_name,
             "cv_results": results}
    (base / "models" / "model_metrics.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return True


def tune_best_model(root: str | Path) -> bool:
    """Tune the selected candidate on training groups only; do not inspect the reserved test set."""
    base = Path(root).resolve()
    frame, reasons, config = training_readiness(base)
    split_path = base / "data" / "processed" / "model_split.csv"
    metrics_path = base / "models" / "model_metrics.json"
    if reasons or frame is None or not split_path.is_file() or not metrics_path.is_file():
        if not reasons:
            reasons = ["Run the grouped training comparison first; a reserved split and candidate results are required."]
        _write_blocked_state(base, "tune", reasons)
        return False
    split = pd.read_csv(split_path)
    train_idx = split.index[split["split_set"].eq("train")].to_numpy()
    train = frame.iloc[train_idx]
    data_cfg, model_cfg = config["data"], config["model"]
    target, group_col = data_cfg["target"], data_cfg["group_column"]
    features = list(model_cfg["features"])
    prior = json.loads(metrics_path.read_text(encoding="utf-8"))
    best = prior.get("candidate")
    if best not in {"random_forest", "gradient_boosting"}:
        # There is no scientifically justified reason to tune a median or linear baseline.
        prior["tuning_status"] = "not_applicable"
        metrics_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
        (base / "reports" / "hyperparameter_tuning_report.md").write_text(
            "# Hyperparameter tuning report\n\n**Status: not applicable.** Grouped validation selected a simple baseline or linear candidate; no tree hyperparameters were tuned. The final test data remain untouched.\n",
            encoding="utf-8")
        return True
    estimator = RandomForestRegressor(random_state=SEED, n_jobs=-1) if best == "random_forest" else GradientBoostingRegressor(random_state=SEED)
    pipeline = build_model_pipeline(train[features], estimator, features)
    if best == "random_forest":
        distributions = {"model__n_estimators": [200, 400, 600], "model__max_depth": [None, 8, 16],
                         "model__min_samples_split": [2, 5, 10], "model__min_samples_leaf": [1, 2, 4],
                         "model__max_features": [1.0, "sqrt", 0.7]}
    else:
        distributions = {"model__n_estimators": [100, 200, 400], "model__learning_rate": [0.03, 0.05, 0.1],
                         "model__max_depth": [2, 3, 4], "model__min_samples_leaf": [2, 4, 8]}
    cv = GroupKFold(n_splits=min(int(model_cfg.get("cv_splits", 5)), train[group_col].nunique()))
    search = RandomizedSearchCV(pipeline, distributions, n_iter=min(20, int(model_cfg.get("tuning_iterations", 12))),
                                scoring="neg_mean_absolute_error", cv=cv, random_state=SEED, n_jobs=1,
                                refit=True, return_train_score=False)
    search.fit(train[features], train[target].astype(float), groups=train[group_col])
    import joblib
    joblib.dump(search.best_estimator_, base / "models" / "candidate_pipeline.joblib")
    untuned = min((item.get("cv_mae", float("inf")) for item in prior.get("cv_results", []) if item.get("model") == best), default=None)
    prior["tuning_status"] = "complete"
    prior["best_params"] = search.best_params_
    prior["best_group_cv_mae"] = float(-search.best_score_)
    prior["untuned_group_cv_mae"] = untuned
    metrics_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
    (base / "reports" / "hyperparameter_tuning_report.md").write_text(
        "# Hyperparameter tuning report\n\n**Status: tuning completed on training groups only; the test groups remain untouched.**\n\n"
        f"- Candidate: `{best}`\n- Best grouped-CV MAE: {-search.best_score_:.4f} {data_cfg['target_unit']}\n"
        f"- Best parameters: `{search.best_params_}`\n"
        f"- Untuned grouped-CV MAE: {untuned if untuned is not None else 'not recorded'} {data_cfg['target_unit']}\n\n"
        "The final test set has not been evaluated.\n", encoding="utf-8")
    return True


def evaluate_final(root: str | Path) -> bool:
    """Evaluate a tuned candidate once on its held-out groups, then keep release disabled for review."""
    base = Path(root).resolve()
    frame, reasons, config = training_readiness(base)
    split_path = base / "data" / "processed" / "model_split.csv"
    candidate_path = base / "models" / "candidate_pipeline.joblib"
    metrics_path = base / "models" / "model_metrics.json"
    if reasons or frame is None or not split_path.is_file() or not candidate_path.is_file():
        if not reasons:
            reasons = ["A grouped training comparison and candidate pipeline are required before final evaluation."]
        _write_blocked_state(base, "evaluate", reasons)
        return False
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if metrics.get("final_test_metrics"):
        (base / "reports" / "model_evaluation_report.md").write_text(
            "# Model evaluation report\n\n**Status: final test metrics already exist.** The protected test set was not evaluated a second time.\n",
            encoding="utf-8")
        return False
    split = pd.read_csv(split_path)
    test_idx = split.index[split["split_set"].eq("test")].to_numpy()
    train_idx = split.index[split["split_set"].eq("train")].to_numpy()
    if len(test_idx) == 0:
        raise ValueError("Reserved test split is empty.")
    data_cfg, model_cfg = config["data"], config["model"]
    target, group_col = data_cfg["target"], data_cfg["group_column"]
    features = list(model_cfg["features"])
    test = frame.iloc[test_idx]
    import joblib
    candidate = joblib.load(candidate_path)
    prediction = candidate.predict(test[features])
    baseline = DummyRegressor(strategy="median")
    train = frame.iloc[train_idx]
    baseline.fit(train[features], train[target].astype(float))
    baseline_prediction = baseline.predict(test[features])
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    mse = float(mean_squared_error(test[target], prediction))
    final = {"mae": float(mean_absolute_error(test[target], prediction)), "mse": mse,
             "rmse": float(np.sqrt(mse)), "r2": float(r2_score(test[target], prediction)) if test[target].nunique() > 1 else None,
             "unit": data_cfg["target_unit"], "test_rows": int(len(test)),
             "test_groups": int(test[group_col].nunique()),
             "baseline_mae": float(mean_absolute_error(test[target], baseline_prediction)),
             "baseline_rmse": float(np.sqrt(mean_squared_error(test[target], baseline_prediction)))}
    metrics["final_test_metrics"] = final
    metrics["training_status"] = "evaluation_complete_pending_reliability_review"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    models_dir = base / "models"
    joblib.dump(candidate, models_dir / "best_model.joblib")
    joblib.dump(candidate.named_steps["preprocessing"], models_dir / "preprocessing_pipeline.joblib")
    numeric_features = [column for column in features if pd.api.types.is_numeric_dtype(train[column])]
    categorical_features = [column for column in features if column not in numeric_features]
    ranges = {}
    for column in numeric_features:
        values = pd.to_numeric(train[column], errors="coerce").dropna()
        ranges[column] = {"min": float(values.min()), "max": float(values.max())} if not values.empty else {"min": None, "max": None}
    categories = {column: sorted(train[column].dropna().astype(str).unique().tolist()) for column in categorical_features}
    release_state = "evaluation_complete_pending_reliability_review"
    schema = {"training_status": release_state, "features": features, "numeric_features": numeric_features,
              "categorical_values": categories, "feature_ranges": ranges, "nullable_features": [],
              "target": target, "target_unit": data_cfg["target_unit"]}
    (models_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    metadata = {"model_version": "1.0.0-candidate", "training_status": release_state,
                "target": target, "target_unit": data_cfg["target_unit"], "features": features,
                "seed": SEED, "training_dataset": data_cfg.get("training_dataset"),
                "group_column": group_col, "test_groups": final["test_groups"],
                "release_note": "Prediction remains disabled until the separate reliability review passes."}
    (models_dir / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (models_dir / "model_version.txt").write_text("1.0.0-candidate\n", encoding="utf-8")
    viz = base / "visualizations" / "predictions"
    viz.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(test[target], prediction, alpha=0.7, label="Model")
    limits = [min(float(test[target].min()), float(np.min(prediction))), max(float(test[target].max()), float(np.max(prediction)))]
    ax.plot(limits, limits, "--", color="black", label="Ideal")
    ax.set_xlabel(f"Measured irrigation ({data_cfg['target_unit']})")
    ax.set_ylabel(f"Predicted irrigation ({data_cfg['target_unit']})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(viz / "actual_vs_predicted.png", dpi=150)
    plt.close(fig)
    residuals = test[target].to_numpy(dtype=float) - np.asarray(prediction, dtype=float)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(prediction, residuals, alpha=0.7)
    ax.axhline(0, color="black", linestyle="--")
    ax.set_xlabel(f"Prediction ({data_cfg['target_unit']})")
    ax.set_ylabel(f"Residual: measured - predicted ({data_cfg['target_unit']})")
    fig.tight_layout()
    fig.savefig(viz / "residuals.png", dpi=150)
    plt.close(fig)
    (base / "reports" / "model_evaluation_report.md").write_text(
        "# Model evaluation report\n\n**Status: held-out evaluation complete; reliability review and release approval are still required.**\n\n"
        f"- Target: `{target}` ({data_cfg['target_unit']})\n- Test rows: {len(test)} across {test[group_col].nunique()} independent groups\n"
        f"- Baseline MAE: {final['baseline_mae']:.4f} {data_cfg['target_unit']}\n"
        f"- Baseline RMSE: {final['baseline_rmse']:.4f} {data_cfg['target_unit']}\n"
        f"- MAE: {final['mae']:.4f} {data_cfg['target_unit']}\n- MSE: {final['mse']:.4f} ({data_cfg['target_unit']})^2\n"
        f"- RMSE: {final['rmse']:.4f} {data_cfg['target_unit']}\n- R2: {final['r2']}\n\n"
        "Review bias, group coverage, uncertainty, and scientific acceptability before setting model release status to `ready`. The prediction loader remains disabled until metadata and schema are marked ready.\n",
        encoding="utf-8")
    return True


def run(root: str | Path, phase: str = "compare") -> bool:
    if phase == "compare":
        return compare_models(root)
    if phase == "tune":
        return tune_best_model(root)
    raise ValueError("Training phase must be 'compare' or 'tune'.")
