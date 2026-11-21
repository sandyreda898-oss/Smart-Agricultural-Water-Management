"""Locate and profile the project data without modifying source files."""
from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
EXPORT_RELATIVE = Path("AgriWater/AgriWater_Clean_Data/data/table_exports")

TABLE_DESCRIPTIONS = {
    "weather_daily": "Daily NASA POWER weather observations in long format; gridded estimates, not field station measurements.",
    "point_season_summary": "Seasonal weather and calculated crop-water summaries by grid point and season; water fields are estimates, not observed irrigation.",
    "soil_point": "Mapped soil properties associated with project grid points; not field-specific soil tests.",
    "soil_awc": "Mapped available-water-capacity reference values; verify depth and spatial support before use.",
    "grid_point": "Project weather/soil grid points and geographic coordinates.",
    "water_scenario": "Calculated water scenarios; not measured farm irrigation.",
    "water_scenario_by_variety": "Variety-specific calculated water scenarios; not measured farm irrigation.",
    "water_scenario_by_variety_v3": "A later calculated scenario version; not measured farm irrigation.",
    "water_scenario_by_variety_clay": "Soil-sensitive calculated scenario variants; not measured farm irrigation.",
    "literature_trial_result": "Published research-station trial results; study-specific and not directly linked to project field locations.",
    "literature_trial_observation": "Published trial observations; experimental records, not farmer field-season labels.",
    "literature_environmental_measurement": "Environmental measurements or published summaries with source-specific coverage.",
    "rice_variety": "Rice variety reference records.",
    "rice_variety_reference": "Published/reference information for rice varieties.",
    "crop_calendar": "Regional crop calendar reference information.",
    "season": "Project rice-season date windows.",
}

UNIT_BY_COLUMN = {
    "latitude": "degrees north", "longitude": "degrees east", "obs_date": "date",
    "season_start_date": "date", "season_end_date": "date", "start_date": "date", "end_date": "date",
    "tmin_c_season_mean": "degC", "tmax_c_season_mean": "degC",
    "tmean_c_season_mean": "degC", "relative_humidity_pct_season_mean": "%",
    "wind_speed_m_s_season_mean": "m/s", "solar_radiation_mj_m2_day_season_mean": "MJ/m2/day",
    "pressure_kpa_season_mean": "kPa", "rainfall_season_mm": "mm/season",
    "et0_season_mm": "mm/season (calculated/reference; not irrigation)",
    "estimated_etc_season_mm": "mm/season (calculated; not irrigation)",
    "total_irrigation_m3_per_feddan": "m3/feddan (only when field-measured and verified)",
}


def find_repo_root(start: str | Path | None = None) -> Path | None:
    """Find a checkout containing the AgriWater directory; supports this delivery workspace."""
    here = Path(start or Path.cwd()).expanduser().resolve()
    candidates = [here, *here.parents]
    for candidate in candidates:
        if (candidate / "AgriWater").is_dir():
            return candidate
        # Convenience for the Codex workspace where a read-only source checkout is nested.
        if (candidate / "repo_source" / "AgriWater").is_dir():
            return candidate / "repo_source"
    return None


def find_ml_root(start: str | Path | None = None) -> Path:
    here = Path(start or Path.cwd()).expanduser().resolve()
    if here.name == "machine_learning" and (here / "src").is_dir():
        return here
    for candidate in (here, *here.parents):
        if (candidate / "src" / "data_loader.py").is_file() and (candidate / "config" / "config.yaml").is_file():
            return candidate
    raise FileNotFoundError("Could not find the machine_learning folder. Start from the repository root or pass its path.")


def export_dir(repo_root: str | Path | None = None, ml_root: str | Path | None = None) -> Path:
    repo = Path(repo_root).resolve() if repo_root else find_repo_root()
    if repo is not None:
        candidate = repo / EXPORT_RELATIVE
        if candidate.is_dir():
            return candidate
    if ml_root is None:
        ml_root = find_ml_root()
    fallback = Path(ml_root).resolve() / "data" / "raw"
    if fallback.is_dir() and any(fallback.glob("*.csv*")):
        return fallback
    raise FileNotFoundError(
        "Project CSV exports were not found. Clone the complete repository and use "
        "AgriWater/AgriWater_Clean_Data/data/table_exports, or place supplied CSVs in machine_learning/data/raw."
    )


def find_export(name: str, repo_root: str | Path | None = None, ml_root: str | Path | None = None) -> Path:
    filename = name if name.endswith((".csv", ".csv.gz")) else f"{name}.csv"
    candidates: list[Path] = []
    if repo_root is None:
        repo_root = find_repo_root()
    if repo_root is not None:
        repo = Path(repo_root).resolve()
        candidates.extend([
            repo / EXPORT_RELATIVE / filename,
            repo / "weather_soil_water_modeling" / "data" / "processed" / filename,
            repo / "AgriWater" / "data" / "processed" / filename,
        ])
    if ml_root is None:
        try:
            ml_root = find_ml_root()
        except FileNotFoundError:
            ml_root = None
    if ml_root is not None:
        candidates.append(Path(ml_root).resolve() / "data" / "raw" / filename)
    for candidate in candidates:
        if candidate.is_file():
            with candidate.open("rb") as stream:
                if stream.read(128).startswith(LFS_HEADER):
                    raise RuntimeError(f"{candidate} is a Git LFS pointer. Run `git lfs pull` or use the CSV table exports.")
            return candidate
    raise FileNotFoundError(f"Could not locate {filename} in the repository exports or machine_learning/data/raw.")


def read_export(name: str, repo_root: str | Path | None = None, ml_root: str | Path | None = None, **kwargs) -> pd.DataFrame:
    path = find_export(name, repo_root=repo_root, ml_root=ml_root)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)


def sqlite_tables(database: str | Path) -> list[dict]:
    """List table names and row/column counts from a real SQLite file, read-only."""
    path = Path(database).expanduser().resolve()
    with path.open("rb") as stream:
        if stream.read(128).startswith(LFS_HEADER):
            raise RuntimeError(f"{path} is a Git LFS pointer, not a SQLite database. Run `git lfs pull` first.")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result = []
        for table in tables:
            quoted = table.replace('"', '""')
            columns = connection.execute(f'PRAGMA table_info("{quoted}")').fetchall()
            rows = connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
            result.append({"Dataset Name": table, "Number of Records": int(rows), "Number of Features": len(columns)})
        return result
    finally:
        connection.close()


def _profile_csv(path: Path, chunksize: int = 100_000) -> tuple[int, dict[str, int], dict[str, str], dict[str, str], dict[str, int]]:
    row_count = 0
    missing: dict[str, int] = {}
    dtypes: dict[str, str] = {}
    examples: dict[str, str] = {}
    uniques: dict[str, int] = {}
    seen: dict[str, set[str]] = {}
    reader = pd.read_csv(path, encoding="utf-8-sig", low_memory=False, chunksize=chunksize)
    for chunk in reader:
        row_count += len(chunk)
        for column in chunk.columns:
            missing[column] = missing.get(column, 0) + int(chunk[column].isna().sum())
            if column not in dtypes:
                dtypes[column] = str(chunk[column].dtype)
                values = chunk[column].dropna().astype(str)
                examples[column] = values.iloc[0][:120] if not values.empty else ""
            if column not in seen:
                seen[column] = set()
            # Bound memory for high-cardinality columns; exact unique counts belong to data-specific profiling.
            for value in chunk[column].dropna().astype(str).unique()[:10_000]:
                if len(seen[column]) < 100_000:
                    seen[column].add(value)
    uniques = {column: len(values) for column, values in seen.items()}
    return row_count, missing, dtypes, examples, uniques


def build_inventory_reports(ml_root: str | Path, repo_root: str | Path | None = None) -> tuple[Path, Path]:
    """Refresh dataset_inventory.xlsx and data_dictionary.xlsx from available CSV exports."""
    from openpyxl.styles import Alignment, Font, PatternFill

    ml = Path(ml_root).resolve()
    reports = ml / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    folder = export_dir(repo_root, ml)
    files = sorted([*folder.glob("*.csv"), *folder.glob("*.csv.gz")])
    if not files:
        raise FileNotFoundError(f"No CSV exports found in {folder}")

    inventory_rows: list[dict] = []
    dictionary_rows: list[dict] = []
    for path in files:
        dataset = path.name.removesuffix(".gz").removesuffix(".csv")
        rows, missing, dtypes, examples, uniques = _profile_csv(path)
        total_cells = rows * max(1, len(dtypes))
        missing_total = sum(missing.values())
        date_values: list[str] = []
        geo = "See latitude/longitude or point_id fields; verify before spatial joins."
        inventory_rows.append({
            "Dataset Name": dataset,
            "Source": str(path),
            "Number of Records": rows,
            "Number of Features": len(dtypes),
            "Description": TABLE_DESCRIPTIONS.get(dataset, "Project table export; see source metadata and data dictionary."),
            "Units": "See feature-level data dictionary; source units vary by column.",
            "Missing Values": f"{missing_total} missing cells ({(100 * missing_total / total_cells):.3f}% of cells)" if total_cells else "0",
            "Time Coverage": "See date/year columns in the source table.",
            "Geographic Coverage": geo,
            "ML Suitability": (
                "Unsuitable as observed target" if dataset.startswith("water_scenario") or dataset == "point_season_summary"
                else "Uncertain; assess source, grain, joins, and prediction-time availability"
            ),
            "Notes": "No source rows are modified. Calculated scenarios and summary estimates are not field-measured labels.",
        })
        for column, dtype in dtypes.items():
            dictionary_rows.append({
                "Dataset": dataset,
                "Column": column,
                "Data Type": dtype,
                "Missing Values": missing.get(column, 0),
                "Missing %": round(100 * missing.get(column, 0) / rows, 4) if rows else 0,
                "Unique Values (sampled/bounded)": uniques.get(column, 0),
                "Example": examples.get(column, ""),
                "Unit": UNIT_BY_COLUMN.get(column, "Unknown - verify in source documentation"),
                "Meaning": "See source table documentation; verify ambiguous fields before modeling.",
                "Source": str(path),
            })

    inventory_path = reports / "dataset_inventory.xlsx"
    dictionary_path = reports / "data_dictionary.xlsx"
    source_inventory_path = reports / "source_database_inventory.xlsx"
    source_dictionary_path = reports / "source_database_dictionary.xlsx"
    db_inventory = pd.read_excel(source_inventory_path) if source_inventory_path.is_file() else pd.DataFrame()
    db_dictionary = pd.read_excel(source_dictionary_path) if source_dictionary_path.is_file() else pd.DataFrame()
    workbook_specs = [
        (inventory_path, [("CSV Exports", pd.DataFrame(inventory_rows)), ("Database Snapshot", db_inventory)]),
        (dictionary_path, [("CSV Export Fields", pd.DataFrame(dictionary_rows)), ("Database Snapshot", db_dictionary)]),
    ]
    from openpyxl import load_workbook
    for output, sheets in workbook_specs:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet_name, frame in sheets:
                if not frame.empty:
                    frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        workbook = load_workbook(output)
        for sheet in workbook.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="176B5B")
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            for column_cells in sheet.columns:
                letter = column_cells[0].column_letter
                max_width = min(58, max(12, max((len(str(cell.value or "")) for cell in column_cells[:200]), default=12) + 2))
                sheet.column_dimensions[letter].width = max_width
        workbook.save(output)
    return inventory_path, dictionary_path
