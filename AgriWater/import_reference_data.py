"""Backup-first, idempotent import of online ARC and pump reference extracts."""
from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
SOURCE_REGISTRY = ROOT / "source_registry.json"

DDL = """
CREATE TABLE IF NOT EXISTS pump_catalog_series (
    pump_series_id INTEGER PRIMARY KEY,
    manufacturer TEXT NOT NULL, series_name TEXT NOT NULL, pump_type TEXT,
    outlet_diameter_in REAL, min_flow_m3_h REAL, max_flow_m3_h REAL,
    max_head_m REAL, frequency_hz TEXT, power_min_kw REAL, power_max_kw REAL,
    operating_conditions TEXT, source_url TEXT NOT NULL, data_status TEXT NOT NULL,
    UNIQUE (manufacturer, series_name, frequency_hz)
);
CREATE TABLE IF NOT EXISTS machinery_inventory (
    inventory_id INTEGER PRIMARY KEY, survey_year INTEGER NOT NULL,
    source_label TEXT NOT NULL, admin_level_status TEXT NOT NULL,
    mobile_count INTEGER, stationary_count INTEGER, total_count INTEGER,
    source_url TEXT NOT NULL, data_status TEXT NOT NULL, notes TEXT,
    UNIQUE (survey_year, source_label, source_url)
);
CREATE TABLE IF NOT EXISTS rice_variety_field_guide (
    guide_row_id INTEGER PRIMARY KEY, variety_id INTEGER NOT NULL REFERENCES rice_variety(variety_id),
    guide_date TEXT NOT NULL, maturity_days_min REAL, maturity_days_max REAL,
    yield_min_ton_feddan REAL, yield_max_ton_feddan REAL, planting_spacing_cm TEXT,
    hills_per_m2 REAL, plants_per_hill_min REAL, plants_per_hill_max REAL,
    urea_bags_per_feddan REAL, suitability_note TEXT, salinity_response TEXT,
    water_stress_response TEXT, disease_note TEXT, source_url TEXT NOT NULL,
    source_status TEXT NOT NULL, notes TEXT,
    UNIQUE (variety_id, guide_date, source_url)
);
CREATE TABLE IF NOT EXISTS agronomy_recommendation (
    recommendation_id INTEGER PRIMARY KEY, crop TEXT NOT NULL DEFAULT 'rice',
    topic TEXT NOT NULL, recommendation_text TEXT NOT NULL, value_min REAL,
    value_max REAL, unit TEXT, condition_scope TEXT, variety_scope TEXT,
    stage_scope TEXT, geography_scope TEXT, publication_date TEXT,
    source_url TEXT NOT NULL, source_locator TEXT,
    confidence_status TEXT NOT NULL, notes TEXT,
    UNIQUE (topic, recommendation_text, source_url)
);
"""


def rows(filename: str) -> list[dict[str, str]]:
    with (ROOT / "data" / "processed" / filename).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(value: str) -> float | None:
    return float(value) if value.strip() else None


def append_registry(entries: list[dict]) -> None:
    current = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    known = {(item.get("source"), item.get("url")) for item in current}
    for entry in entries:
        key = (entry["source"], entry["url"])
        if key not in known:
            current.append(entry)
            known.add(key)
    SOURCE_REGISTRY.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if not DB.exists():
        raise FileNotFoundError(DB)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB.with_name(f"{DB.stem}_backup_before_reference_import_{stamp}{DB.suffix}")
    shutil.copy2(DB, backup)
    pump_rows = rows("pump_catalog_suteksan.csv")
    census_rows = rows("machinery_inventory_ministry.csv")
    rule_rows = rows("rice_recommendations_arc.csv")
    guide_rows = rows("rice_variety_field_guide_2025.csv")

    conn = sqlite3.connect(DB)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(DDL)
        with conn:
            variety_ids = dict(conn.execute("SELECT name_en,variety_id FROM rice_variety"))
            conn.executemany(
                """INSERT INTO pump_catalog_series
                (manufacturer,series_name,pump_type,outlet_diameter_in,min_flow_m3_h,max_flow_m3_h,
                 max_head_m,frequency_hz,power_min_kw,power_max_kw,operating_conditions,source_url,data_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(manufacturer,series_name,frequency_hz) DO UPDATE SET
                 pump_type=excluded.pump_type,outlet_diameter_in=excluded.outlet_diameter_in,
                 min_flow_m3_h=excluded.min_flow_m3_h,max_flow_m3_h=excluded.max_flow_m3_h,
                 max_head_m=excluded.max_head_m,power_min_kw=excluded.power_min_kw,
                 power_max_kw=excluded.power_max_kw,operating_conditions=excluded.operating_conditions,
                 source_url=excluded.source_url,data_status=excluded.data_status""",
                [(r["manufacturer"],r["series_name"],r["pump_type"],num(r["outlet_diameter_in"]),
                  num(r["min_flow_m3_h"]),num(r["max_flow_m3_h"]),num(r["max_head_m"]),r["frequency_hz"],
                  num(r["power_min_kw"]),num(r["power_max_kw"]),r["operating_conditions"],r["source_url"],r["data_status"])
                 for r in pump_rows],
            )
            conn.executemany(
                """INSERT INTO machinery_inventory
                (survey_year,source_label,admin_level_status,mobile_count,stationary_count,total_count,source_url,data_status,notes)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(survey_year,source_label,source_url) DO UPDATE SET
                 admin_level_status=excluded.admin_level_status,mobile_count=excluded.mobile_count,
                 stationary_count=excluded.stationary_count,total_count=excluded.total_count,
                 data_status=excluded.data_status,notes=excluded.notes""",
                [(int(r["survey_year"]),r["source_label"],r["admin_level_status"],int(r["mobile_count"]),
                  int(r["stationary_count"]),int(r["total_count"]),r["source_url"],r["data_status"],r["notes"])
                 for r in census_rows],
            )
            conn.executemany(
                """INSERT INTO agronomy_recommendation
                (crop,topic,recommendation_text,value_min,value_max,unit,condition_scope,variety_scope,
                 stage_scope,geography_scope,publication_date,source_url,source_locator,confidence_status,notes)
                VALUES ('rice',?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(topic,recommendation_text,source_url) DO UPDATE SET
                 value_min=excluded.value_min,value_max=excluded.value_max,unit=excluded.unit,
                 condition_scope=excluded.condition_scope,variety_scope=excluded.variety_scope,
                 stage_scope=excluded.stage_scope,geography_scope=excluded.geography_scope,
                 publication_date=excluded.publication_date,source_locator=excluded.source_locator,
                 confidence_status=excluded.confidence_status,notes=excluded.notes""",
                [(r["topic"],r["recommendation_text"],num(r["value_min"]),num(r["value_max"]),r["unit"] or None,
                  r["condition_scope"] or None,r["variety_scope"] or None,r["stage_scope"] or None,
                  r["geography_scope"] or None,r["publication_date"],r["source_url"],r["source_locator"],
                  r["confidence_status"],r["notes"]) for r in rule_rows],
            )
            guide_values = []
            unresolved_varieties = []
            for r in guide_rows:
                variety_id = variety_ids.get(r["variety_name"])
                if variety_id is None:
                    unresolved_varieties.append(r["variety_name"])
                    continue
                guide_values.append((
                    variety_id,"2025-05-22",num(r["maturity_days_min"]),num(r["maturity_days_max"]),
                    num(r["yield_min_ton_feddan"]),num(r["yield_max_ton_feddan"]),r["planting_spacing_cm"] or None,
                    num(r["hills_per_m2"]),num(r["plants_per_hill_min"]),num(r["plants_per_hill_max"]),
                    num(r["urea_bags_per_feddan"]),r["suitability_note"] or None,r["salinity_response"] or None,
                    r["water_stress_response"] or None,r["disease_note"] or None,r["source_url"],
                    r["source_status"],r["notes"] or None))
            conn.executemany(
                """INSERT INTO rice_variety_field_guide
                (variety_id,guide_date,maturity_days_min,maturity_days_max,yield_min_ton_feddan,
                 yield_max_ton_feddan,planting_spacing_cm,hills_per_m2,plants_per_hill_min,
                 plants_per_hill_max,urea_bags_per_feddan,suitability_note,salinity_response,
                 water_stress_response,disease_note,source_url,source_status,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(variety_id,guide_date,source_url) DO UPDATE SET
                 maturity_days_min=excluded.maturity_days_min,maturity_days_max=excluded.maturity_days_max,
                 yield_min_ton_feddan=excluded.yield_min_ton_feddan,yield_max_ton_feddan=excluded.yield_max_ton_feddan,
                 planting_spacing_cm=excluded.planting_spacing_cm,hills_per_m2=excluded.hills_per_m2,
                 plants_per_hill_min=excluded.plants_per_hill_min,plants_per_hill_max=excluded.plants_per_hill_max,
                 urea_bags_per_feddan=excluded.urea_bags_per_feddan,suitability_note=excluded.suitability_note,
                 salinity_response=excluded.salinity_response,water_stress_response=excluded.water_stress_response,
                 disease_note=excluded.disease_note,source_status=excluded.source_status,notes=excluded.notes""",
                guide_values,
            )
            for name,url,notes in [
                ("ARC Rice recommendations 2026","https://www.arc.sci.eg/Products/Details/9704","ARC page and indexed PDF attachment excerpts; see row-level provenance and confidence tags."),
                ("Egypt Agricultural Portal - rice recommendations May 2025","https://misrelzraea.com/محصول-الأرز-توصيات-مايو-2025-للمزارعين/","Reposted ministry extension recommendations; row-level date and source status retained."),
                ("Suteksan Egypt SEP pump catalogue","https://www.suteksanegypt.com/index.php/en/product-en/pumps/sep-6-pump-series","Manufacturer product-family specifications; no field duty point inferred."),
                ("Egypt Ministry of Agriculture machinery survey 2023","https://www.agri.gov.eg/uploads/topics/17329953527147.pdf","Official pump census; location label scope needs confirmation."),
            ]:
                conn.execute("INSERT OR IGNORE INTO data_source(name,url,notes) VALUES (?,?,?)",(name,url,notes))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        counts = {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                  for name in ("pump_catalog_series","machinery_inventory","agronomy_recommendation","rice_variety_field_guide")}
        if integrity != "ok" or fk_errors:
            raise RuntimeError(f"Database validation failed: {integrity}; FK errors={fk_errors[:5]}")
    finally:
        conn.close()

    append_registry([
        {"source":"Suteksan Egypt pump catalogue","url":"https://www.suteksanegypt.com/index.php/en/product-en/pumps/sep-6-pump-series","dataset":"SEP 6/7/8-inch submersible pump series family ranges","coverage":"Six frequency-specific catalogue rows transcribed to pump_catalog_suteksan.csv","access":"Public manufacturer pages","limitations":"Published family limits are not matched flow/head duty points; they do not establish farm discharge or run time."},
        {"source":"Egypt Ministry of Agriculture, Economic Affairs Sector (2023)","url":"https://www.agri.gov.eg/uploads/topics/17329953527147.pdf","dataset":"Table 93 stationary/mobile irrigation pump census","coverage":"One row labelled Kafr El Sheikh transcribed to machinery_inventory_ministry.csv","access":"Public official PDF table extract","limitations":"The row's exact administrative level is ambiguous in the extracted table and must be confirmed before joining to district records; aggregate counts are not a farmer machine catalogue."},
        {"source":"Agricultural Research Center - Rice technical recommendation bulletin (2026)","url":"https://www.arc.sci.eg/Products/Details/9704","dataset":"Rice recommendation excerpts from the ARC page and its PDF attachment","coverage":"18 ARC-specific rule rows in rice_recommendations_arc.csv, including climate-adaptation cultivars and dry direct-seeding irrigation/fertilizer rules","access":"Public ARC page and indexed attachment excerpts","limitations":"The full attachment was not downloaded and parsed end-to-end; excerpts remain tagged official_pdf_excerpt. Dry direct-seeding rules must not be applied to transplanted rice; salinity-only rules remain scoped, and fertilizer formulation must be checked before farm use."},
        {"source":"Egypt Agricultural Portal - May 2025 rice recommendations","url":"https://misrelzraea.com/محصول-الأرز-توصيات-مايو-2025-للمزارعين/","dataset":"Variety-specific cultivation guide and nursery recommendations attributed to the Ministry of Agriculture extension sector","coverage":"13 cultivar rows and nursery/seed rules transcribed in the processed CSVs","access":"Public agricultural extension portal; article identifies the Ministry extension sector as issuer","limitations":"A dated repost of Ministry recommendations, not a current seed-availability list. Keep separate from ARC catalogue values; yield is a bulletin claim, not a local guarantee."},
    ])
    print(json.dumps({"backup":str(backup),"imported":{"pump_catalog_rows":len(pump_rows),"machinery_inventory_rows":len(census_rows),"agronomy_rules":len(rule_rows),"variety_guide_rows":len(guide_values),"unresolved_varieties":unresolved_varieties},"database_counts":counts,"integrity":integrity,"foreign_key_violations":len(fk_errors)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
