"""Import numeric treatment, soil-profile, and seasonal climate values from Darwesh et al. (2016).

All observations are station experiment/reference data, never parcel-level labels.
"""
import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "darwesh_sakha_irrigation_trial_2013_2014.csv"
URL = "https://jssae.journals.ekb.eg/article_39351_2bc01450304a3b34c9f247b4a7d2d871.pdf"
STUDY = "DARWESH_SAKHA_IRRIGATION_DEPTH_INTERVAL_2013_2014"

# Table 3 values: seasonal irrigation applied m3/feddan; ordered P1D1, P1D2, P1D3, P2D1, P2D2, P2D3; variety V1/V2/V3 within each.
water = {
    (2013, 6, 3): [4140,4460,4620], (2014, 6, 3): [3990,4350,4570],
    (2013, 6, 5): [5180,5360,5570], (2014, 6, 5): [5100,5400,5600],
    (2013, 6, 7): [6310,6590,6780], (2014, 6, 7): [6220,6495,6685],
    (2013,12, 3): [2775,2810,3100], (2014,12, 3): [2690,2740,3020],
    (2013,12, 5): [3180,3440,3540], (2014,12, 5): [3010,3510,3595],
    (2013,12, 7): [3795,3965,4250], (2014,12, 7): [3725,3895,4165],
}
# Table 4 values, grain yield kg/feddan, same treatment order and variety order.
yield_ = {
    (2013,6,3): [3193.3,3566.7,3680.0], (2014,6,3): [3163.3,3860.0,4133.3],
    (2013,6,5): [3266.7,4606.7,4866.7], (2014,6,5): [3803.3,4640.0,4740.0],
    (2013,6,7): [3560.0,3993.3,4330.0], (2014,6,7): [3871.3,4100.0,4340.0],
    (2013,12,3): [2386.7,2580.0,2806.7], (2014,12,3): [2433.3,2633.3,2913.0],
    (2013,12,5): [2613.3,2930.0,3140.0], (2014,12,5): [2653.3,2883.3,3063.3],
    (2013,12,7): [2650.0,2896.7,3105.0], (2014,12,7): [2700.0,2830.0,3045.0],
}
wp = {
    (2013,6,3): [.77,.80,.80], (2014,6,3): [.79,.89,.90],
    (2013,6,5): [.63,.86,.87], (2014,6,5): [.75,.86,.85],
    (2013,6,7): [.56,.61,.64], (2014,6,7): [.62,.63,.65],
    (2013,12,3): [.95,.92,.91], (2014,12,3): [.90,.96,.96],
    (2013,12,5): [.82,.85,.89], (2014,12,5): [.88,.82,.85],
    (2013,12,7): [.70,.68,.73], (2014,12,7): [.72,.68,.73],
}
grain1000 = {
    (2013,6,3): [25.03,24.80,24.80], (2014,6,3): [24.70,26.83,26.70],
    (2013,6,5): [28.12,27.83,27.46], (2014,6,5): [26.53,27.30,28.00],
    (2013,6,7): [27.86,27.10,27.20], (2014,6,7): [26.26,27.46,27.53],
    (2013,12,3): [20.36,20.96,17.66], (2014,12,3): [19.40,20.73,19.43],
    (2013,12,5): [21.23,22.86,21.36], (2014,12,5): [20.10,22.83,20.60],
    (2013,12,7): [21.13,22.60,21.00], (2014,12,7): [21.30,20.63,19.66],
}
varieties = ["Giza 177", "Sakha 101", "Orabi 1"]
source_refs = {"seasonal_irrigation_applied":"Table 3", "grain_yield":"Table 4", "water_productivity":"Table 4", "thousand_grain_weight":"Table 4"}

def records():
    rows=[]
    for key, vals in water.items():
        year, interval, depth=key
        for i,variety in enumerate(varieties):
            for metric, value, unit in [
                ("seasonal_irrigation_applied", vals[i], "m3/feddan"),
                ("grain_yield", yield_[key][i], "kg/feddan"),
                ("water_productivity", wp[key][i], "kg/m3"),
                ("thousand_grain_weight", grain1000[key][i], "g"),
            ]:
                rows.append(dict(study_id=STUDY, study_year=year, observation_period="rice_growing_season",
                    preceding_crop="not_reported", puddling="puddled_transplanting", depth_top_cm=None, depth_bottom_cm=None,
                    metric_name=metric, metric_value=value, unit=unit,
                    aggregation_level=f"treatment_mean; irrigation_every_{interval}_days; ponding_depth_{depth}_cm; variety_{variety}",
                    replicate_count=3, source_locator=source_refs[metric],
                    data_status="PUBLISHED_SAKHA_STATION_TREATMENT_MEAN_NOT_FARM_FIELD_LABEL", source_url=URL))
    # Site soil profile from Table 2 (mean of 2013 and 2014 seasons).
    soil = {
      "sand":([11.20,15.80,17.50,18.11],"%"), "silt":([29.30,29.60,29.90,31.40],"%"),
      "clay":([59.50,54.60,52.60,50.49],"%"), "bulk_density":([1.16,1.17,1.18,1.21],"kg/m3_as_printed_scale_ambiguous"),
      "field_capacity":([44.50,43.00,42.60,41.50],"%_weight"), "permanent_wilting_point":([23.50,22.60,22.10,21.30],"%_weight"),
      "available_water":([21.00,20.40,20.50,20.20],"%_weight"), "ph":([7.87,8.00,8.10,8.16],"pH"),
      "ec":([2.48,2.60,3.10,2.76],"dS/m"), "calcium":([4.50,4.10,3.88,5.10],"meq/L"),
      "magnesium":([5.12,6.50,5.90,7.60],"meq/L"), "sodium":([14.30,15.00,20.80,14.60],"meq/L"),
      "potassium":([0.61,0.38,0.36,0.41],"meq/L"), "bicarbonate":([9.30,8.90,11.40,10.12],"meq/L"),
      "chloride":([4.23,9.20,12.60,13.30],"meq/L"), "sulfate":([11.00,7.88,6.94,4.29],"meq/L")}
    depths=[(0,15),(15,30),(30,45),(45,60)]
    for metric,(values,unit) in soil.items():
        for (top,bottom),value in zip(depths,values):
            rows.append(dict(study_id=STUDY,study_year=2013,observation_period="experimental_site_soil_profile_mean_2013_2014",
              preceding_crop="not_reported",puddling="",depth_top_cm=top,depth_bottom_cm=bottom,metric_name=metric,
              metric_value=value,unit=unit,aggregation_level="Sakha station experimental site; seasonal mean",
              replicate_count=None,source_locator="Table 2",data_status="PUBLISHED_SAKHA_STATION_BASELINE_NOT_FIELD_ESTIMATE",source_url=URL))
    # Monthly station climate means from Table 1. Relative humidity columns are monthly max/min/mean; T is likewise.
    climate={
      2013:{"May":[31.43,21.85,26.64,75.03,45.78,60.41,1.20,6.35],"June":[32.44,23.97,28.21,74.63,51.27,62.95,1.34,6.61],"July":[32.32,24.31,28.32,79.57,54.70,67.14,1.28,6.11],"August":[33.79,24.72,29.29,83.63,60.52,72.08,1.04,5.13],"September":[32.50,22.93,27.72,81.00,56.60,68.80,1.01,3.82]},
      2014:{"May":[30.47,19.57,25.02,77.20,48.60,62.90,1.14,5.87],"June":[32.65,20.60,26.63,86.23,52.30,69.27,.95,6.56],"July":[33.15,23.64,28.40,83.19,55.11,69.15,1.13,7.73],"August":[34.10,21.80,27.95,92.40,53.50,72.95,1.15,8.14],"September":[32.49,20.76,26.63,87.57,52.20,69.89,1.03,6.65]}}
    names=[("temperature_max","degC"),("temperature_min","degC"),("temperature_mean","degC"),("relative_humidity_max","%"),("relative_humidity_min","%"),("relative_humidity_mean","%"),("wind_speed_2m","m/s"),("pan_evaporation","mm/day")]
    for year, months in climate.items():
      for month,vals in months.items():
       for (metric,unit),value in zip(names,vals):
        rows.append(dict(study_id=STUDY,study_year=year,observation_period=f"monthly_{month.lower()}_station_mean",preceding_crop=None,puddling=None,depth_top_cm=None,depth_bottom_cm=None,metric_name=metric,metric_value=value,unit=unit,aggregation_level="Sakha agrometeorological station monthly summary",replicate_count=None,source_locator="Table 1",data_status="PUBLISHED_STATION_MONTHLY_SUMMARY_NOT_DAILY_FIELD_WEATHER",source_url=URL))
    return rows

def main():
    rows=records()
    with OUT.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    backup=DB.with_name(f"{DB.stem}_before_darwesh_trial_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB,backup)
    con=sqlite3.connect(DB);con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO data_source(name,url,notes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,notes=excluded.notes",
          ("Darwesh et al. 2016 Sakha irrigation, yield, soil and climate trial",URL,"Tables 1-4 transcribed from published 2013-2014 Sakha research station experiment; station/treatment means, not parcel predictions."))
        con.execute("INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,methods_summary=excluded.methods_summary,limitations=excluded.limitations,data_status=excluded.data_status",
          (STUDY,"Rice varieties as affected with different irrigation periods and submerged depths in the North Nile Delta region","R. Kh. Darwesh; A. A. Abdelkhalek; M. A. M. Ibrahim",2016,None,URL,"Sakha Agricultural Research Station Farm, Kafr El-Sheikh",31.1167,30.95,"Two seasons (2013, 2014); intervals 6/12 days; ponding depths 3/5/7 cm; Giza 177, Sakha 101, Orabi 1; water measured by rectangular weir; 3 replications; treatment means transcribed from Tables 1-4.","Single research-station site and historical seasons. No parcel-specific prediction. Seasonal applied water includes nursery, land preparation, and establishment water. Irrigation depths/intervals are experimental treatments, not prescriptions for every farm.","PUBLISHED_PRIMARY_RESEARCH_STATION_TRIAL"))
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?",(STUDY,))
        con.executemany("INSERT INTO literature_trial_observation(study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,source_locator,data_status,source_url) VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,:depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,:replicate_count,:source_locator,:data_status,:source_url)",rows)
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)",("darwesh_sakha_trial_2013_2014",f"Imported {len(rows)} transcribed table values: irrigation/yield/water productivity (Tables 3-4), soil profile (Table 2), monthly climate (Table 1). Station experiment only; source {URL}"))
        assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
    except Exception:
        con.rollback();raise
    finally: con.close()
    print(f"Imported {len(rows)} observations; backup: {backup}")

if __name__=="__main__": main()
