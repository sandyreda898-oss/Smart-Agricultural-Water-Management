"""Phase 2: conservative, documented cleaning of the project seasonal feature tables."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .data_loader import find_repo_root, read_export


def _trim_strings(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    out = frame.copy()
    changed = 0
    for column in out.select_dtypes(include=["object", "string"]).columns:
        old = out[column].astype("string")
        new = old.str.strip().str.replace(r"\s+", " ", regex=True)
        changed += int((old.ne(new) & old.notna()).sum())
        out[column] = new.where(new.notna(), pd.NA)
    return out, changed


def _count_duplicates(frame: pd.DataFrame, keys: list[str]) -> tuple[int, int]:
    exact = int(frame.duplicated().sum())
    key_duplicates = int(frame.duplicated(keys).sum()) if keys and set(keys).issubset(frame.columns) else 0
    return exact, key_duplicates


def load_seasonal_sources(repo_root: str | Path | None = None, ml_root: str | Path | None = None) -> pd.DataFrame:
    """Join the project's provided seasonal summaries, grid points and mapped soil 1:1."""
    seasonal = read_export("point_season_summary.csv", repo_root=repo_root, ml_root=ml_root)
    grid = read_export("grid_point.csv", repo_root=repo_root, ml_root=ml_root)
    soil = read_export("soil_point.csv", repo_root=repo_root, ml_root=ml_root)
    frames = []
    for name, frame, keys in (
        ("point_season_summary", seasonal, ["point_id", "season_year"]),
        ("grid_point", grid, ["point_id"]),
        ("soil_point", soil, ["point_id"]),
    ):
        if not set(keys).issubset(frame.columns):
            raise ValueError(f"{name} is missing expected join key(s): {keys}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} has duplicate join keys {keys}; investigate before joining.")
        cleaned, _ = _trim_strings(frame)
        frames.append(cleaned)
    seasonal, grid, soil = frames
    seasonal["season_year"] = pd.to_numeric(seasonal["season_year"], errors="coerce").astype("Int64")
    for column in ("season_start_date", "season_end_date"):
        if column in seasonal:
            seasonal[column] = pd.to_datetime(seasonal[column], errors="coerce")
    merged = seasonal.merge(grid, on="point_id", how="left", validate="many_to_one", suffixes=("", "_grid"))
    merged = merged.merge(soil, on="point_id", how="left", validate="many_to_one", suffixes=("", "_soil"))
    for column in merged.select_dtypes(include=["object"]).columns:
        numeric = pd.to_numeric(merged[column], errors="coerce")
        if numeric.notna().sum() and numeric.notna().sum() >= merged[column].notna().sum() * 0.95:
            merged[column] = numeric
    return merged


def clean_project_data(ml_root: str | Path, repo_root: str | Path | None = None) -> Path:
    """Write a reproducible cleaned seasonal table and quality workbook; never imputes or drops outliers."""
    ml = Path(ml_root).resolve()
    repo = Path(repo_root).resolve() if repo_root else find_repo_root()
    if repo is None:
        raise FileNotFoundError("Could not locate the project checkout. Provide repo_root explicitly.")
    frame = load_seasonal_sources(repo_root=repo, ml_root=ml)
    proc = ml / "data" / "processed"
    reports = ml / "reports"
    proc.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    duplicate_summary = []
    for name, keys in (("joined seasonal dataset", ["point_id", "season_year"]),):
        exact, key_dups = _count_duplicates(frame, keys)
        duplicate_summary.append({"Dataset": name, "Rows": len(frame), "Exact Duplicate Rows": exact,
                                  "Duplicate Join Keys": key_dups, "Key": ", ".join(keys)})
    missing_rows = []
    for column in frame.columns:
        count = int(frame[column].isna().sum())
        missing_rows.append({"Column": column, "Data Type": str(frame[column].dtype), "Rows": len(frame),
                             "Missing": count, "Missing %": round(100 * count / len(frame), 3) if len(frame) else 0})

    checks = []
    if {"latitude", "longitude"}.issubset(frame.columns):
        invalid = (~frame["latitude"].between(-90, 90)) | (~frame["longitude"].between(-180, 180))
        checks.append({"Check": "Coordinates in valid latitude/longitude bounds", "Records checked": len(frame),
                       "Records flagged": int(invalid.sum()), "Action": "Flag only; review source coordinates."})
    for column, low, high in (("relative_humidity_pct_season_mean", 0, 100), ("sand_pct", 0, 100),
                              ("silt_pct", 0, 100), ("clay_pct", 0, 100)):
        if column in frame:
            values = pd.to_numeric(frame[column], errors="coerce")
            flagged = (~values.between(low, high)) & values.notna()
            checks.append({"Check": f"{column} within [{low}, {high}]", "Records checked": int(values.notna().sum()),
                           "Records flagged": int(flagged.sum()), "Action": "Flag only; do not silently correct values."})

    operations = pd.DataFrame([
        {"Operation": "Trim whitespace and normalize spacing in text fields", "Effect": "Recorded below per source table", "Decision": "Applied; values remain semantically unchanged."},
        {"Operation": "Parse seasonal dates and numeric year fields", "Effect": "Dates stored as ISO-compatible values in CSV", "Decision": "Invalid parses remain missing and appear in the missing-value sheet."},
        {"Operation": "Join seasonal summary to grid and soil references", "Effect": f"{len(frame)} rows; 1:1 / many:1 validated", "Decision": "Left joins retain all seasonal rows; duplicate keys cause a hard error."},
        {"Operation": "Imputation / outlier deletion", "Effect": "0 records", "Decision": "Not performed. Preserve missing values and extremes; fit imputers only in training folds."},
        {"Operation": "Ground-truth label creation", "Effect": "0 labels created", "Decision": "Calculated scenario/ETc fields are not accepted as observed irrigation."},
    ])
    out_path = proc / "cleaned_dataset.csv"
    frame.to_csv(out_path, index=False, date_format="%Y-%m-%d")
    workbook_path = reports / "cleaning_report.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame([{"Item": "Rows in joined dataset", "Value": len(frame)},
                      {"Item": "Features", "Value": len(frame.columns)},
                      {"Item": "Training labels created", "Value": 0},
                      {"Item": "Imputation performed", "Value": "No"},
                      {"Item": "Source database modified", "Value": "No"}]).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(missing_rows).to_excel(writer, sheet_name="Missing Values", index=False)
        pd.DataFrame(duplicate_summary).to_excel(writer, sheet_name="Duplicates", index=False)
        pd.DataFrame(checks).to_excel(writer, sheet_name="Validity Checks", index=False)
        operations.to_excel(writer, sheet_name="Cleaning Operations", index=False)
        # Preserve the repository's original all-table quality profile in the same deliverable workbook.
        source_profile = reports / "source_database_cleaning_profile.xlsx"
        if source_profile.is_file():
            for source_sheet in pd.ExcelFile(source_profile).sheet_names:
                source_frame = pd.read_excel(source_profile, sheet_name=source_sheet)
                if source_frame.empty:
                    continue
                clean_name = ("DB " + source_sheet.replace("_", " "))[:31]
                if clean_name not in {"Summary", "Missing Values", "Duplicates", "Validity Checks", "Cleaning Operations"}:
                    source_frame.to_excel(writer, sheet_name=clean_name, index=False)
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill
    workbook = load_workbook(workbook_path)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="176B5B")
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(52, max(12, max(len(str(c.value or "")) for c in col[:150]) + 2))
    workbook.save(workbook_path)
    missing_total = sum(row["Missing"] for row in missing_rows)
    (reports / "cleaning_report.md").write_text(
        "# Data cleaning report\n\n"
        f"- Source: project CSV table exports under `{EXPORT_SOURCE}`.\n"
        f"- Joined seasonal rows: {len(frame)}; columns: {len(frame.columns)}.\n"
        f"- Missing cells: {missing_total} (retained; no imputation).\n"
        f"- Exact duplicate rows: {duplicate_summary[0]['Exact Duplicate Rows']}; duplicate join keys: {duplicate_summary[0]['Duplicate Join Keys']}.\n"
        "- Outliers: flagged for review only; not removed automatically.\n"
        "- Target labels: none created. ET0/ETc and water scenario fields remain calculated quantities, not observed irrigation.\n"
        "- Output: `data/processed/cleaned_dataset.csv`; raw source files are unchanged.\n",
        encoding="utf-8",
    )
    return out_path


EXPORT_SOURCE = "AgriWater/AgriWater_Clean_Data/data/table_exports"


def run(root: str | Path | None = None, repo_root: str | Path | None = None) -> Path:
    ml = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    return clean_project_data(ml, repo_root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="machine_learning folder")
    parser.add_argument("--repo-root", default=None, help="repository root containing AgriWater/")
    args = parser.parse_args()
    output = run(args.root, args.repo_root)
    print(f"Cleaned feature table written to {output}")


if __name__ == "__main__":
    main()
