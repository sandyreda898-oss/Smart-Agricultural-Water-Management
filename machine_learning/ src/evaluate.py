"""Evaluate a tuned model once on held-out field groups."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .model_training import FEATURES, TARGET, training_readiness


def run(root: Path) -> bool:
    root = root.resolve()
    df, reasons = training_readiness(root)
    models, reports = root / "models", root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    metrics_path = models / "model_metrics.json"
    split_path = root / "data" / "processed" / "model_split.csv"
    if reasons or df is None or not (models / "best_model.joblib").exists() or not split_path.exists():
        (reports / "model_evaluation_report.md").write_text(
            "# Model Evaluation Report\n\n**Status: BLOCKED - no held-out evaluation was run.**\n\n" +
            "\n".join(f"- {item}" for item in (reasons or ["A trained model and reserved grouped test split are required."])) +
            "\n", encoding="utf-8")
        print("Evaluation blocked; no metrics were fabricated.")
        return False

    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if metrics.get("final_test_metrics"):
        (reports / "model_evaluation_report.md").write_text(
            "# Model Evaluation Report\n\n**Status: already evaluated.** The final test set is protected from repeated evaluation.\n",
            encoding="utf-8")
        print("The final test evaluation already exists; it was not repeated.")
        return False

    import joblib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    split_info = pd.read_csv(split_path)
    test_rows = split_info.loc[split_info["split_set"].eq("test"), "row_index"].astype(int).to_numpy()
    if len(test_rows) == 0:
        raise ValueError("Reserved test split is empty.")
    test = df.iloc[test_rows]
    x_test, y_test = test[FEATURES], test[TARGET].astype(float)
    model = joblib.load(models / "best_model.joblib")
    prediction = model.predict(x_test)
    final = {
        "mae": float(mean_absolute_error(y_test, prediction)),
        "mse": float(mean_squared_error(y_test, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, prediction))),
        "r2": float(r2_score(y_test, prediction)) if y_test.nunique() > 1 else None,
        "unit": "m3/feddan",
        "test_rows": int(len(test)),
        "test_groups": int(test["field_group_id"].nunique()),
    }
    metrics["final_test_metrics"] = final
    metrics["training_status"] = "evaluation_complete_pending_reliability_review"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    pred_dir = root / "visualizations" / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y_test, prediction, alpha=0.75)
    lim = [min(float(y_test.min()), float(prediction.min())), max(float(y_test.max()), float(prediction.max()))]
    ax.plot(lim, lim, "--", color="black")
    ax.set_xlabel("Measured irrigation (m3/feddan)")
    ax.set_ylabel("Predicted irrigation (m3/feddan)")
    ax.set_title("Held-out field groups")
    fig.tight_layout()
    fig.savefig(pred_dir / "actual_vs_predicted.png", dpi=150)
    plt.close(fig)
    report = ["# Model Evaluation Report", "", "**Status: held-out evaluation complete; reliability review remains.**", "",
              "| Metric | Result | Unit |", "|---|---:|---|",
              f"| MAE | {final['mae']:.3f} | m3/feddan |",
              f"| MSE | {final['mse']:.3f} | (m3/feddan)^2 |",
              f"| RMSE | {final['rmse']:.3f} | m3/feddan |",
              f"| R2 | {final['r2'] if final['r2'] is not None else 'undefined'} | unitless |",
              "", f"Test rows: {final['test_rows']}; independent test groups: {final['test_groups']}.",
              "The result is not field-ready until limitations, extrapolation, and uncertainty are reviewed."]
    (reports / "model_evaluation_report.md").write_text("\n".join(report), encoding="utf-8")
    print("Final held-out evaluation completed once; reliability review is still required.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    run(Path(args.root))


if __name__ == "__main__":
    main()
