import csv
import json
import logging
import math
import os
import sys
import time
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from typing import Any

import requests
import pandas as pd
from shapely.geometry import shape, Point, mapping
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
OUT = CONFIG["output"]
for key in ("raw_dir", "processed_dir", "metadata_dir", "reports_dir", "logs_dir"):
    (ROOT / OUT[key]).mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("agriwater")
logger.setLevel(logging.INFO)
logger.handlers.clear()
fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
fh = logging.FileHandler(ROOT / OUT["logs_dir"] / "collector.log", encoding="utf-8")
fh.setFormatter(fmt)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(sh)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": CONFIG["runtime"].get("user_agent", "AgriWater-Collector/1.0")})
TIMEOUT = int(CONFIG["runtime"].get("request_timeout_seconds", 60))
MAX_RETRIES = int(CONFIG["runtime"].get("max_retries", 4))
BACKOFF = float(CONFIG["runtime"].get("backoff_seconds", 2))
STATE_PATH = ROOT / OUT["metadata_dir"] / "state.json"
REPORT_PATH = ROOT / OUT["reports_dir"] / "latest_report.json"
REPORT = {"project": CONFIG["project_name"], "started_utc": datetime.now(timezone.utc).isoformat(),
          "sources": {}, "warnings": [], "coverage": {}}

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("State file unreadable; starting fresh: %s", exc)
    return {}

STATE = load_state()

def save_state():
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)

def request(method: str, url: str, *, params=None, json_body=None, data=None, headers=None):
    """Retry transient failures only; permanent 4xx responses fail promptly with body captured."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = SESSION.request(method, url, params=params, json=json_body, data=data,
                                   headers=headers, timeout=TIMEOUT)
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if attempt < MAX_RETRIES:
                    retry_after = resp.headers.get("Retry-After")
                    delay = min(90, float(retry_after)) if retry_after and retry_after.isdigit() else BACKOFF * (2 ** attempt)
                    logger.warning("Temporary HTTP %s from %s; retry in %.1fs", resp.status_code, url, delay)
                    time.sleep(delay)
                    continue
            if not resp.ok:
                body = resp.text[:1500].replace("\n", " ")
                raise RuntimeError(f"HTTP {resp.status_code} {url} :: {body}")
            return resp
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            delay = min(90, BACKOFF * (2 ** attempt))
            logger.warning("Network error for %s; retry %d/%d in %.1fs: %s", url, attempt+1, MAX_RETRIES, delay, exc)
            time.sleep(delay)
    raise RuntimeError(f"Request failed after retries: {url} :: {last_error}")

def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def source_result(name, status, **kwargs):
    REPORT["sources"][name] = {"status": status, "finished_utc": datetime.now(timezone.utc).isoformat(), **kwargs}
    write_json(REPORT_PATH, REPORT)

def save_table(rows, stem, raw_path=None):
    if not rows:
        return None
    df = pd.DataFrame(rows).drop_duplicates()
    csv_path = ROOT / OUT["processed_dir"] / f"{stem}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    parquet_path = ROOT / OUT["processed_dir"] / f"{stem}.parquet"
    if CONFIG["output"].get("save_parquet", True):
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception as exc:
            logger.warning("Parquet write skipped for %s: %s", stem, exc)
    return {"rows": int(len(df)), "csv": str(csv_path.relative_to(ROOT)),
            "parquet": str(parquet_path.relative_to(ROOT)) if parquet_path.exists() else None}

def load_boundary():
    cfg = CONFIG["boundary"]
    raw_dir = ROOT / OUT["raw_dir"] / "boundaries"
    raw_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = raw_dir / "egy_adm1.geojson"
    meta_path = raw_dir / "geoboundaries_metadata.json"
    try:
        meta = json.loads(request("GET", cfg["url"]).text)
        write_json(meta_path, meta)
        download_url = meta.get("gjDownloadURL") or meta.get("gjdownloadURL")
        if not download_url:
            raise RuntimeError(f"geoBoundaries response missing GeoJSON URL; keys={list(meta)[:30]}")
        if not geojson_path.exists():
            resp = request("GET", download_url)
            # Validate JSON before saving as a successful boundary file.
            gj = resp.json()
            if gj.get("type") != "FeatureCollection" or not isinstance(gj.get("features"), list):
                raise RuntimeError("Downloaded boundary is not a GeoJSON FeatureCollection")
            write_json(geojson_path, gj)
        else:
            gj = json.loads(geojson_path.read_text(encoding="utf-8"))
        features = gj.get("features", [])
        candidates = []
        for f in features:
            props = f.get("properties") or {}
            textvals = " ".join(str(v) for v in props.values() if v is not None).lower()
            if "kafr el sheikh" in textvals or "kafr ash shaykh" in textvals or "kafr el-sheikh" in textvals:
                candidates.append(f)
        if len(candidates) != 1:
            names = [f.get("properties", {}) for f in features[:3]]
            raise RuntimeError(f"Expected one Kafr El Sheikh ADM1 feature, found {len(candidates)}. Inspect source metadata/features. Sample={names}")
        feature = candidates[0]
        geom = shape(feature["geometry"])
        if geom.is_empty or not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            raise RuntimeError("Boundary geometry is empty after validity repair")
        selected = {"type": "FeatureCollection", "name": "Kafr El Sheikh - geoBoundaries gbOpen ADM1",
                    "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                    "features": [feature]}
        write_json(raw_dir / "kafr_el_sheikh_adm1.geojson", selected)
        try:
            import geopandas as gpd
            gdf = gpd.GeoDataFrame([feature["properties"]], geometry=[geom], crs="EPSG:4326")
            gdf.to_file(raw_dir / "kafr_el_sheikh_adm1.gpkg", layer="admin_boundary", driver="GPKG")
        except Exception as exc:
            logger.warning("GeoPackage export unavailable; GeoJSON retained: %s", exc)
        area_km2 = float(geom.area) * 111.32 * 111.32 * math.cos(math.radians(geom.centroid.y))
        meta_out = {"source": cfg["url"], "download_metadata": meta,
                    "selected_properties": feature.get("properties", {}),
                    "crs": "EPSG:4326", "geometry_type": geom.geom_type,
                    "area_km2_approx_degree_based": area_km2,
                    "area_note": "Approximate QA metric only; use equal-area projection/geodesic area for authoritative area.",
                    "boundary_type": "administrative boundary, not parcel/cadastral boundary"}
        write_json(ROOT / OUT["metadata_dir"] / "boundary_metadata.json", meta_out)
        source_result("boundary", "success", feature_count=1, geometry_type=geom.geom_type,
                      file=str((raw_dir / "kafr_el_sheikh_adm1.geojson").relative_to(ROOT)),
                      source=cfg["url"], note="Administrative outline only; no legal parcel polygons.")
        return geom
    except Exception as exc:
        logger.exception("Boundary collection failed")
        source_result("boundary", "failed", error=str(exc), source=cfg["url"])
        return None

def make_grid(geom):
    cfg = CONFIG["climate"]
    spacing = float(cfg.get("grid_spacing_degrees", 0.1))
    minx, miny, maxx, maxy = geom.bounds
    prepared = prep(geom)
    points = []
    lat = miny + spacing / 2
    while lat < maxy:
        lon = minx + spacing / 2
        while lon < maxx:
            p = Point(lon, lat)
            if prepared.contains(p):
                points.append({"point_id": f"grid_{len(points)+1:04d}", "longitude": round(lon, 6),
                               "latitude": round(lat, 6), "sampling_method": "regular_grid_inside_admin_polygon"})
            lon += spacing
        lat += spacing
    cap = int(cfg.get("max_points", 250))
    if len(points) > cap:
        # Deterministic spatial thinning; explicitly reported as sampled coverage, not exhaustive.
        step = math.ceil(len(points) / cap)
        points = points[::step][:cap]
    return points

def date_chunks(start_s, end_s, max_days):
    start = date.fromisoformat(start_s)
    end = date.fromisoformat(end_s)
    if end < start:
        raise ValueError("date_range.end must be on/after date_range.start")
    cur = start
    while cur <= end:
        stop = min(end, cur + timedelta(days=max_days - 1))
        yield cur, stop
        cur = stop + timedelta(days=1)

def fetch_power_payload(base_query, parameters):
    """Fetch POWER data; on HTTP 422, bisect parameter lists to isolate unsupported parameters."""
    query = dict(base_query)
    query["parameters"] = ",".join(parameters)
    try:
        resp = request("GET", CONFIG["climate"]["endpoint"], params=query)
        payload = resp.json()
        if not isinstance(payload, dict) or "properties" not in payload:
            raise RuntimeError(f"Unexpected NASA POWER JSON schema: {str(payload)[:600]}")
        return payload
    except Exception as exc:
        if "HTTP 422" in str(exc) and len(parameters) > 1:
            middle = len(parameters) // 2
            left = fetch_power_payload(base_query, parameters[:middle])
            right = fetch_power_payload(base_query, parameters[middle:])
            merged = dict(left)
            merged_props = dict(merged.get("properties") or {})
            left_params = merged_props.get("parameter") or merged_props.get("parameters") or {}
            right_props = right.get("properties") or {}
            right_params = right_props.get("parameter") or right_props.get("parameters") or {}
            merged_props["parameter"] = {**left_params, **right_params}
            merged["properties"] = merged_props
            return merged
        raise

def collect_power(points):
    cfg = CONFIG["climate"]
    if not cfg.get("enabled"):
        source_result("nasa_power", "disabled")
        return
    raw_dir = ROOT / OUT["raw_dir"] / "nasa_power"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    success_chunks, failed_chunks = 0, []
    start, end = CONFIG["date_range"]["start"], CONFIG["date_range"]["end"]
    params_list = cfg["parameters"]
    for point in points:
        for cstart, cend in date_chunks(start, end, int(cfg.get("chunk_days", 365))):
            key = f"{point['point_id']}_{cstart:%Y%m%d}_{cend:%Y%m%d}"
            cache = raw_dir / f"{key}.json"
            if key in STATE.get("power_done", []) and cache.exists():
                try:
                    payload = json.loads(cache.read_text(encoding="utf-8"))
                except Exception:
                    payload = None
            else:
                payload = None
            if payload is None:
                query = {"community": cfg.get("community", "AG"),
                         "longitude": point["longitude"], "latitude": point["latitude"],
                         "start": cstart.strftime("%Y%m%d"), "end": cend.strftime("%Y%m%d"),
                         "format": "JSON", "time-standard": "UTC"}
                try:
                    payload = fetch_power_payload(query, params_list)
                    if payload.get("messages") and any("error" in str(x).lower() for x in payload["messages"]):
                        raise RuntimeError(f"NASA POWER API message: {payload['messages']}")
                    write_json(cache, payload)
                    STATE.setdefault("power_done", []).append(key)
                    save_state()
                    success_chunks += 1
                    time.sleep(float(cfg.get("pause_seconds", 1)))
                except Exception as exc:
                    logger.error("NASA POWER chunk failed %s: %s", key, exc)
                    failed_chunks.append({"chunk": key, "error": str(exc)})
                    continue
            try:
                props = payload["properties"]
                parameter_data = props.get("parameter") or props.get("parameters") or {}
                for par, values in parameter_data.items():
                    if not isinstance(values, dict):
                        continue
                    for day, value in values.items():
                        try:
                            val = float(value)
                            if val < -900:
                                val = None
                        except (ValueError, TypeError):
                            val = None
                        rows.append({"point_id": point["point_id"], "latitude": point["latitude"],
                                     "longitude": point["longitude"], "date": f"{day[:4]}-{day[4:6]}-{day[6:8]}",
                                     "parameter": par, "value": val, "unit": None,
                                     "source": "NASA POWER Daily API", "spatial_support": "gridded estimate"})
            except Exception as exc:
                failed_chunks.append({"chunk": key, "error": f"schema parse: {exc}"})
    summary = save_table(rows, "nasa_power_daily")
    source_result("nasa_power", "partial" if failed_chunks else ("success" if rows else "failed"),
                  points_requested=len(points), successful_new_chunks=success_chunks,
                  failed_chunk_count=len(failed_chunks), failed_chunks=failed_chunks[:200],
                  table=summary, requested_period={"start": start, "end": end},
                  note="Values are gridded estimates; coverage is only the sampling points and successful date chunks.")
    write_json(ROOT / OUT["metadata_dir"] / "nasa_power_parameters.json",
               {"parameters": params_list, "units_note": "NASA POWER units are defined by the API parameter metadata; verify before analysis.",
                "endpoint": cfg["endpoint"], "community": cfg.get("community")})

def collect_soil(points):
    cfg = CONFIG["soilgrids"]
    if not cfg.get("enabled"):
        source_result("soilgrids", "disabled")
        return
    # Respect the published 5 requests/minute fair-use policy. Sampling is intentionally capped.
    raw_dir = ROOT / OUT["raw_dir"] / "soilgrids"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cap = int(cfg.get("max_points", 24))
    selected = points[:cap]
    rows, failures = [], []
    for idx, p in enumerate(selected):
        cache = raw_dir / f"{p['point_id']}.json"
        try:
            if cache.exists():
                data = json.loads(cache.read_text(encoding="utf-8"))
            else:
                # SoilGrids v2 query accepts repeated property/depth selectors.
                params = [("lon", p["longitude"]), ("lat", p["latitude"])]
                for prop in cfg.get("properties", []):
                    params.append(("property", prop))
                for depth in cfg.get("depths", []):
                    params.append(("depth", depth))
                resp = request("GET", cfg["endpoint"], params=params)
                data = resp.json()
                if not isinstance(data, dict):
                    raise RuntimeError("Unexpected SoilGrids response type")
                write_json(cache, data)
                time.sleep(float(cfg.get("pause_seconds", 12.5)))
            rows.append({"point_id": p["point_id"], "latitude": p["latitude"], "longitude": p["longitude"],
                         "response_json": json.dumps(data, ensure_ascii=False), "source": "ISRIC SoilGrids REST API v2.0",
                         "status": "response_received"})
        except Exception as exc:
            logger.error("SoilGrids point failed %s: %s", p["point_id"], exc)
            failures.append({"point_id": p["point_id"], "error": str(exc)})
            # A gateway timeout across many consecutive points usually indicates
            # an upstream service outage. Stop hammering the service, but retain
            # the failures in the report and continue with other data sources.
            if "HTTP 504" in str(exc) or "504 Gateway Time-out" in str(exc):
                logger.warning("SoilGrids returned HTTP 504; stopping point requests for this run.")
                remaining = selected[idx + 1:]
                failures.extend({"point_id": rp["point_id"],
                                 "error": "Not requested because SoilGrids returned HTTP 504; retry in a later run."}
                                for rp in remaining)
                break
    summary = save_table(rows, "soilgrids_point_responses")
    source_result("soilgrids", "partial" if failures else ("success" if rows else "failed"),
                  points_requested=len(selected), response_count=len(rows), failed_points=failures,
                  table=summary, note="Sample points only; no full-area raster generated. See raw JSON for original API schema.")
    write_json(ROOT / OUT["metadata_dir"] / "soilgrids_metadata.json",
               {"endpoint": cfg["endpoint"], "properties_requested": cfg["properties"], "depths_requested": cfg["depths"],
                "coverage": "limited point sample, not exhaustive", "fair_use": "5 API calls/minute per ISRIC REST landing page",
                "limitations": "REST response schema may evolve; raw response retained. Obtain official rasters for complete mapping."})

def collect_sentinel(geom):
    cfg = CONFIG["sentinel2"]
    if not cfg.get("enabled"):
        source_result("sentinel2_catalog", "disabled")
        return
    raw_dir = ROOT / OUT["raw_dir"] / "sentinel2_catalog"
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        body = {"collections": cfg.get("collections", ["sentinel-2-l2a"]),
                "intersects": mapping(geom),
                "datetime": f"{CONFIG['date_range']['start']}T00:00:00Z/{CONFIG['date_range']['end']}T23:59:59Z",
                "limit": int(cfg.get("page_size", 100))}
        url = cfg["catalog_endpoint"]
        method, next_body = "POST", body
        all_features, pages, errors, seen_page_keys = [], 0, [], set()
        while url and pages < int(cfg.get("max_pages", 100)):
            # STAC APIs may reuse the same endpoint URL for POST pagination while
            # changing the request body (for example, a page token). Track the
            # complete request, not the URL alone.
            page_key = (url, method, json.dumps(next_body or {}, sort_keys=True, ensure_ascii=False) if method == "POST" else "")
            if page_key in seen_page_keys:
                errors.append("Pagination stopped because the catalog repeated the same URL/method/body.")
                break
            seen_page_keys.add(page_key)
            try:
                resp = request("GET", url) if method == "GET" else request("POST", url, json_body=next_body)
                payload = resp.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
                    raise RuntimeError(f"Unexpected STAC response schema: {str(payload)[:500]}")
                page_features = payload["features"]
                all_features.extend(page_features)
                write_json(raw_dir / f"page_{pages+1:04d}.json", payload)
                pages += 1
                next_link = next((lnk for lnk in payload.get("links", []) if lnk.get("rel") == "next"), None)
                if not next_link:
                    url = None
                else:
                    url = next_link.get("href")
                    method = (next_link.get("method") or "GET").upper()
                    next_body = next_link.get("body") or {}
                    if method not in ("GET", "POST"):
                        errors.append(f"Unsupported STAC pagination method: {method}")
                        url = None
                if not page_features:
                    break
            except Exception as exc:
                errors.append(str(exc))
                logger.error("Sentinel catalog page failed: %s", exc)
                break
        unique = {f["id"]: f for f in all_features if f.get("id")}
        rows = []
        for item in unique.values():
            props = item.get("properties") or {}
            cloud = props.get("eo:cloud_cover")
            try:
                cloud_num = float(cloud) if cloud is not None else None
            except (ValueError, TypeError):
                cloud_num = None
            if cloud_num is not None and cloud_num > float(cfg.get("cloud_cover_max", 100)):
                continue
            rows.append({"scene_id": item.get("id"), "datetime": props.get("datetime"),
                         "cloud_cover_percent": cloud_num, "collection": item.get("collection"),
                         "geometry_json": json.dumps(item.get("geometry"), ensure_ascii=False),
                         "bbox_json": json.dumps(item.get("bbox"), ensure_ascii=False),
                         "assets_json": json.dumps(item.get("assets", {}), ensure_ascii=False),
                         "source": "Copernicus Data Space STAC"})
        summary = save_table(rows, "sentinel2_scene_catalog")
        source_result("sentinel2_catalog", "partial" if errors else ("success" if rows else "success_empty"),
                      pages=pages, unique_scenes=len(rows), errors=errors, table=summary,
                      requested_period=body["datetime"], cloud_cover_max=cfg.get("cloud_cover_max"),
                      download_products=False, note="Scene metadata only. No raster pixels downloaded by this collector.")
    except Exception as exc:
        logger.exception("Sentinel-2 catalog collection failed")
        source_result("sentinel2_catalog", "failed", error=str(exc), endpoint=cfg["catalog_endpoint"])

def create_field_template():
    path = ROOT / OUT["processed_dir"] / "field_survey_template.csv"
    schema_path = ROOT / OUT["metadata_dir"] / "field_survey_schema.json"
    if not schema_path.exists():
        logger.warning("Canonical field survey schema is missing: %s", schema_path)
        return

    # Keep the importer schema as the single source of truth. Replacing it with
    # a flat list here makes import_field_survey.py fail (it expects column objects).
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    columns = [column["name"] for column in schema["columns"]]
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(columns)
    else:
        with path.open(newline="", encoding="utf-8-sig") as f:
            existing_columns = next(csv.reader(f), [])
        if existing_columns != columns:
            logger.warning(
                "Existing field survey template header differs from the canonical schema; "
                "leaving it untouched to avoid overwriting user data: %s", path)

def coverage_report(points, geom):
    report = {
      "administrative_boundary_available": geom is not None,
      "boundary_is_legal_cadastral_parcels": False,
      "grid_sampling_points": len(points),
      "grid_spacing_degrees": CONFIG["climate"].get("grid_spacing_degrees"),
      "grid_points_are_parcel_boundaries": False,
      "date_range_requested": CONFIG["date_range"],
      "coverage_statement": "Coverage must be assessed per source from successful records, scene footprints, and date chunks. A request window is not proof of complete coverage.",
      "not_collected_automatically": ["official rice area/production by center", "field-level irrigation volumes", "farmer records", "legal cadastral parcels", "full SoilGrids raster", "Sentinel-2 image pixels"]
    }
    write_json(ROOT / OUT["reports_dir"] / "coverage_summary.json", report)
    write_json(ROOT / OUT["metadata_dir"] / "sample_grid.geojson",
               {"type": "FeatureCollection", "features": [
                   {"type": "Feature", "geometry": mapping(Point(p["longitude"], p["latitude"])),
                    "properties": p} for p in points]})

def main():
    logger.info("Starting AgriWater collector; date range %s to %s", CONFIG["date_range"]["start"], CONFIG["date_range"]["end"])
    boundary = load_boundary() if CONFIG["boundary"].get("enabled") else None
    points = make_grid(boundary) if boundary is not None else []
    if boundary is not None:
        logger.info("Created %d sampling points inside retrieved administrative polygon", len(points))
    else:
        logger.error("No trusted administrative boundary available; spatial collectors will be skipped rather than use a guessed rectangle.")
    coverage_report(points, boundary)
    create_field_template()
    # Independent source execution: one failure never blocks subsequent sources.
    if points:
        # Preserve a previously collected climate table by default. Set
        # runtime.force_refresh_climate=true in config.json only if a full refresh is intended.
        existing_climate = ROOT / OUT["processed_dir"] / "nasa_power_daily.csv"
        force_refresh_climate = bool(CONFIG.get("runtime", {}).get("force_refresh_climate", False))
        if existing_climate.exists() and existing_climate.stat().st_size > 0 and not force_refresh_climate:
            try:
                existing_rows = int(pd.read_csv(existing_climate, usecols=["point_id", "date", "parameter", "value"]).shape[0])
                source_result("nasa_power", "reused_existing",
                              table={"rows": existing_rows, "csv": str(existing_climate.relative_to(ROOT)),
                                     "parquet": str((ROOT / OUT["processed_dir"] / "nasa_power_daily.parquet").relative_to(ROOT))
                                     if (ROOT / OUT["processed_dir"] / "nasa_power_daily.parquet").exists() else None},
                              note="Existing climate table preserved; download skipped. Set runtime.force_refresh_climate=true to explicitly refresh.")
                logger.info("Existing NASA POWER table found (%d rows); skipping climate download to preserve it.", existing_rows)
            except Exception as exc:
                logger.warning("Could not validate existing climate table; skipping climate download to avoid overwriting it: %s", exc)
                source_result("nasa_power", "reused_existing_unverified",
                              csv=str(existing_climate.relative_to(ROOT)),
                              note="Existing climate CSV preserved; validation failed and download was skipped to avoid overwrite.")
        else:
            try: collect_power(points)
            except Exception as exc:
                logger.exception("NASA POWER collector crashed")
                source_result("nasa_power", "failed", error=str(exc))
        try: collect_soil(points)
        except Exception as exc:
            logger.exception("SoilGrids collector crashed")
            source_result("soilgrids", "failed", error=str(exc))
        try: collect_sentinel(boundary)
        except Exception as exc:
            logger.exception("Sentinel catalog collector crashed")
            source_result("sentinel2_catalog", "failed", error=str(exc))
    else:
        for name in ("nasa_power", "soilgrids", "sentinel2_catalog"):
            source_result(name, "skipped_no_boundary", note="No trusted boundary; no guessed coordinates used.")
    REPORT["finished_utc"] = datetime.now(timezone.utc).isoformat()
    REPORT["summary"] = {
      "sources_attempted": len(REPORT["sources"]),
      "successful_or_empty": sum(1 for x in REPORT["sources"].values() if x["status"] in ("success", "success_empty", "reused_existing")),
      "partial": sum(1 for x in REPORT["sources"].values() if x["status"] == "partial"),
      "failed_or_skipped": sum(1 for x in REPORT["sources"].values() if x["status"] in ("failed", "skipped_no_boundary"))
    }
    write_json(REPORT_PATH, REPORT)
    logger.info("Run finished. Report: %s", REPORT_PATH)
    logger.info("Summary: %s", REPORT["summary"])
    return 0 if REPORT["summary"]["failed_or_skipped"] == 0 else 2
