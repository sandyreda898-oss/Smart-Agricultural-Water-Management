"""Import published Sakha rice water-budget, ET, and weather summaries (Moursi & Abdelkhalek, 2015)."""
import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/"database"/"agriwater_v2.sqlite"
OUT=ROOT/"data"/"processed"/"moursi_sakha_water_requirements_2012_2013.csv"
URL="https://asejaiqjsae.journals.ekb.eg/article_2859_6ce5a0229c306dd687cba488da0d80a1.pdf"
STUDY="MOURSI_SAKHA_RICE_WATER_COMPONENTS_2012_2013"
VARIETIES=["Giza 178","Sakha 102","Sakha 104"]

def make_rows():
    rows=[]
    def add(year,period,variety,metric,value,unit,locator,status="PUBLISHED_SAKHA_STATION_RESULT_NOT_FARM_LABEL"):
        rows.append(dict(study_id=STUDY,study_year=year,observation_period=period,preceding_crop=None,puddling="puddled_transplanting",
          depth_top_cm=None,depth_bottom_cm=None,metric_name=metric,metric_value=value,unit=unit,
          aggregation_level=(f"cultivar={variety}; two-season study mean" if variety else "Sakha station summary"),replicate_count=None,
          source_locator=locator,data_status=status,source_url=URL))
    # Table 3 and study summary. Preserve direct values; no normalization of paper-specific ambiguities.
    seasonal={
      "Giza 178":{"evaporation_mm_season":439.5,"evaporation_pct":39.8,"transpiration_mm_season":232.0,"transpiration_pct":21.0,
        "percolation_mm_season":384.8,"percolation_pct":39.2,"et_actual_mean_mm_day":6.1,"irrigation_after_transplant_mm":1104.9,
        "nursery_water_mm":104.0,"irrigation_applied_mm_season":1208.9,"grain_yield_kg_m2":1.029,"irrigation_water_productivity_kg_m3":0.85,"crop_water_use_efficiency_kg_m3":1.53},
      "Sakha 102":{"evaporation_mm_season":411.3,"evaporation_pct":38.3,"transpiration_mm_season":215.3,"transpiration_pct":20.1,
        "percolation_mm_season":445.5,"percolation_pct":41.6,"et_actual_mean_mm_day":6.0,"irrigation_after_transplant_mm":1072.1,
        "nursery_water_mm":104.0,"irrigation_applied_mm_season":1176.1,"grain_yield_kg_m2":0.971,"irrigation_water_productivity_kg_m3":0.86,"crop_water_use_efficiency_kg_m3":1.55},
      "Sakha 104":{"evaporation_mm_season":431.6,"evaporation_pct":38.2,"transpiration_mm_season":241.4,"transpiration_pct":21.4,
        "percolation_mm_season":456.6,"percolation_pct":40.4,"et_actual_mean_mm_day":6.0,"irrigation_after_transplant_mm":1129.6,
        "nursery_water_mm":104.0,"irrigation_applied_mm_season":1233.6,"grain_yield_kg_m2":0.980,"irrigation_water_productivity_kg_m3":0.87,"crop_water_use_efficiency_kg_m3":1.46}}
    units={"evaporation_mm_season":"mm/season","evaporation_pct":"%","transpiration_mm_season":"mm/season","transpiration_pct":"%",
      "percolation_mm_season":"mm/season","percolation_pct":"%","et_actual_mean_mm_day":"mm/day","irrigation_after_transplant_mm":"mm",
      "nursery_water_mm":"mm","irrigation_applied_mm_season":"mm/season","grain_yield_kg_m2":"kg/m2",
      "irrigation_water_productivity_kg_m3":"kg/m3","crop_water_use_efficiency_kg_m3":"kg/m3"}
    for v,metrics in seasonal.items():
      for metric,value in metrics.items():
        loc="Table 3 / Results text" if metric.endswith(("_pct","_mm_season")) else "Table 4 or Table 5 / Results text"
        add(None,"mean_of_2012_and_2013_seasons",v,metric,value,units[metric],loc)
    # Table 1 monthly climatic summaries: max/min/mean T and RH, U2, Class A pan, rainfall.
    climate={
      2012:{"July":[33.16,25.30,29.23,84.05,53.02,68.53,91.74,6.0,None],"August":[34.65,25.02,29.83,84.90,52.14,68.52,90.91,5.7,None],"September":[32.28,22.73,27.50,82.87,52.30,67.58,86.33,6.6,None],"October":[29.92,20.64,25.28,85.24,55.31,70.27,74.15,4.3,0.2]},
      2013:{"July":[32.32,24.31,28.31,79.57,54.70,67.13,110.99,6.1,None],"August":[33.79,24.76,29.27,83.63,60.52,72.07,90.24,5.1,None],"September":[32.50,22.93,27.71,81.00,56.60,68.80,87.60,3.8,None],"October":[27.79,19.42,23.60,76.23,57.36,66.79,108.99,2.8,None]}}
    climate_names=[("temperature_max","degC"),("temperature_min","degC"),("temperature_mean","degC"),("rh_max","%"),("rh_min","%"),("rh_mean","%"),
      ("wind_speed_2m","km_day_or_km_hour_as_published_ambiguous"),("pan_evaporation","mm/day"),("rainfall","mm")]
    for year,months in climate.items():
      for month,values in months.items():
       for (metric,unit),value in zip(climate_names,values):
        if value is not None: add(year,f"monthly_{month.lower()}_station_mean",None,metric,value,unit,"Table 1")
    # Table 4: two-season monthly means, ETo methods, Kc, measured ETa by cultivar, estimated ETc.
    t4={
      "July":{"eto_hargreaves":5.7,"eto_penman_monteith":6.2,"eto_class_a_pan":5.1,"kc":1.07,
        "eta":{"Giza 178":7.9,"Sakha 102":8.1,"Sakha 104":7.8},"etc_hargreaves":6.1,"etc_penman_monteith":6.6,"etc_class_a_pan":5.5},
      "August":{"eto_hargreaves":5.4,"eto_penman_monteith":5.5,"eto_class_a_pan":4.6,"kc":1.16,
        "eta":{"Giza 178":6.7,"Sakha 102":6.7,"Sakha 104":7.0},"etc_hargreaves":6.3,"etc_penman_monteith":6.4,"etc_class_a_pan":5.3},
      "September":{"eto_hargreaves":4.9,"eto_penman_monteith":4.5,"eto_class_a_pan":4.5,"kc":1.19,
        "eta":{"Giza 178":5.8,"Sakha 102":5.5,"Sakha 104":5.6},"etc_hargreaves":5.8,"etc_penman_monteith":5.4,"etc_class_a_pan":5.3},
      "October":{"eto_hargreaves":3.7,"eto_penman_monteith":3.4,"eto_class_a_pan":3.0,"kc":1.04,
        "eta":{"Giza 178":3.9,"Sakha 102":3.7,"Sakha 104":3.8},"etc_hargreaves":3.8,"etc_penman_monteith":3.5,"etc_class_a_pan":3.1}}
    for month,values in t4.items():
      for metric,value in values.items():
       if metric=="eta":
        for v,x in value.items(): add(None,f"monthly_{month.lower()}_mean_of_2012_2013",v,"et_actual",x,"mm/day","Table 4")
       else: add(None,f"monthly_{month.lower()}_mean_of_2012_2013",None,metric,value,"dimensionless" if metric=="kc" else "mm/day","Table 4")
    return rows

def main():
    rows=make_rows()
    with OUT.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    backup=DB.with_name(f"{DB.stem}_before_moursi_trial_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB,backup)
    con=sqlite3.connect(DB);con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO data_source(name,url,notes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,notes=excluded.notes",
          ("Moursi and Abdelkhalek 2015 Sakha rice water requirements",URL,"Tables 1, 3, 4, 5 and results text transcribed; 2012-2013 Sakha station experiments; mixed annual and two-season means."))
        con.execute("INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,latitude=excluded.latitude,longitude=excluded.longitude,methods_summary=excluded.methods_summary,limitations=excluded.limitations,data_status=excluded.data_status",
          (STUDY,"Water Requirement Components of some Egyptian Rice Varieties in North Nile Delta","E. A. Moursi; A. A. Abdelkhalek",2015,"10.21608/asejaiqjsae.2015.2859",URL,"Sakha Agricultural Research Station, Kafr El-Sheikh",31.1167,30.95,"Two experiments in summer 2012 and 2013; Giza 178, Sakha 102, Sakha 104; measured actual ETa with micro-paddy lysimeter; estimated ETo by Hargreaves, Penman-Monteith, Class A pan; irrigation water balance and seasonal productivity.","Research station only, not farmer labels. Mixes season-specific climate summaries and two-season mean treatment summaries. Rainfall/drainage/runoff/seepage treated as negligible or unavailable in the study water budget. Wind-speed unit is inconsistent between table and narrative and is preserved as ambiguous. Values transcribed from tables/results; do not use directly as parcel or pump-run-time recommendations.","PUBLISHED_PRIMARY_RESEARCH_STATION_TRIAL"))
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?",(STUDY,))
        con.executemany("INSERT INTO literature_trial_observation(study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,source_locator,data_status,source_url) VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,:depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,:replicate_count,:source_locator,:data_status,:source_url)",rows)
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)",("moursi_sakha_water_components_2012_2013",f"Imported {len(rows)} published observations from Tables 1, 3, 4, 5 and results text; location-specific station results, not field labels. Source: {URL}"))
        assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
    except Exception: con.rollback();raise
    finally: con.close()
    print(f"Imported {len(rows)} observations; backup: {backup}")

if __name__=="__main__": main()
