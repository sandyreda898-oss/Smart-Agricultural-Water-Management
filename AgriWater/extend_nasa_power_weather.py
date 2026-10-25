"""Extend AgriWater's NASA POWER point weather series from 2024 onward.

Downloads daily agroclimatology JSON in one-year chunks; it never downloads
imagery or vegetation-index products. Raw API responses are kept under data/raw.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
import json
import shutil
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
RAW = ROOT / "data" / "raw" / "nasa_power_daily_extension"
OUT = ROOT / "data" / "processed" / "nasa_power_daily_2024_onward.csv"
ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "RH2M", "PRECTOTCORR", "WS2M", "PS", "ALLSKY_SFC_SW_DWN")
UNITS = {"T2M":"C", "T2M_MAX":"C", "T2M_MIN":"C", "RH2M":"%", "PRECTOTCORR":"mm/day", "WS2M":"m/s", "PS":"kPa", "ALLSKY_SFC_SW_DWN":"MJ/m^2/day"}
START_YEAR = 2024
END_DATE = date.today()

def fetch(point, year):
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), END_DATE)
    params = {
        "parameters": ",".join(PARAMETERS), "community":"AG",
        "longitude":f"{point['longitude']:.6f}", "latitude":f"{point['latitude']:.6f}",
        "start":start.strftime("%Y%m%d"), "end":end.strftime("%Y%m%d"), "format":"JSON",
    }
    url = ENDPOINT + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent":"AgriWater-research-data-collection/1.0"})
    last = None
    for attempt in range(5):
        try:
            with urlopen(req, timeout=90) as response:
                body = response.read()
            payload = json.loads(body)
            return point["point_id"], year, url, payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA request failed for {point['point_id']} {year}: {last}")

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        points = [dict(point_id=r[0], latitude=r[1], longitude=r[2])
                  for r in con.execute("SELECT point_id,latitude,longitude FROM grid_point ORDER BY point_id")]
        source_id = con.execute("SELECT source_id FROM data_source WHERE name='NASA POWER Daily API'").fetchone()[0]
    years = list(range(START_YEAR, END_DATE.year + 1))
    jobs = [(point, year) for point in points for year in years]
    payloads = []
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, point, year):(point["point_id"],year) for point,year in jobs}
        for future in as_completed(futures):
            key = futures[future]
            try:
                payloads.append(future.result())
            except Exception as exc:
                errors.append((key, str(exc)))
    if errors:
        raise RuntimeError("Incomplete fetch; database was not changed: " + repr(errors[:10]))

    payloads.sort(key=lambda x:(x[0],x[1]))
    insert_rows = []
    for point_id, year, url, payload in payloads:
        p = payload.get("properties",{}).get("parameter",{})
        if not all(name in p for name in PARAMETERS):
            raise RuntimeError(f"Missing expected variables in NASA response for {point_id} {year}")
        raw_path = RAW / f"{point_id}_{year}.json"
        raw_path.write_text(json.dumps({"request_url":url,"retrieved_at_utc":datetime.utcnow().isoformat()+"Z","response":payload},ensure_ascii=False),encoding="utf-8")
        for name in PARAMETERS:
            for day_key, value in p[name].items():
                numeric = None if value in (-999, "-999", None) else float(value)
                insert_rows.append((point_id,datetime.strptime(day_key,"%Y%m%d").date().isoformat(),name,numeric,UNITS[name],source_id))

    backup = DB.with_name(f"{DB.stem}_before_weather_extension_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB,backup)
    with sqlite3.connect(DB) as con:
        con.execute("PRAGMA foreign_keys=ON")
        with con:
            con.executemany("""INSERT OR IGNORE INTO weather_daily
                (point_id,obs_date,parameter,value,unit,source_id) VALUES (?,?,?,?,?,?)""",insert_rows)

    import csv
    with OUT.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(["point_id","latitude","longitude","date","parameter","value","unit","source","spatial_support"])
        point_map={p["point_id"]:p for p in points}
        for point_id,day,name,value,unit,_ in insert_rows:
            p=point_map[point_id]
            w.writerow([point_id,p["latitude"],p["longitude"],day,name,value if value is not None else "",unit,"NASA POWER Daily API","gridded estimate"])
    with sqlite3.connect(DB) as con:
        integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
        fk=len(con.execute("PRAGMA foreign_key_check").fetchall())
        date_span=con.execute("SELECT MIN(obs_date),MAX(obs_date),COUNT(*) FROM weather_daily WHERE obs_date>='2024-01-01'").fetchone()
    print(json.dumps({"points":len(points),"years":years,"downloaded_values":len(insert_rows),"extension_span":date_span[:2],"extension_rows_in_db":date_span[2],"integrity":integrity,"foreign_key_violations":fk,"raw_files":len(payloads),"processed_csv":str(OUT),"backup":str(backup)},ensure_ascii=False))

if __name__ == "__main__":
    main()
