"""Import irrigation, yield, water-saving and WUE values from Ghazy et al. 2024 Table 8."""
import csv,shutil,sqlite3
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"database"/"agriwater_v2.sqlite"
OUT=ROOT/"data"/"processed"/"ghazy_sakha_sakha106_water_trial_2022_2023.csv"
URL="https://jenvbs.journals.ekb.eg/article_381943_b6ecf5a9d1e34c93ee93c4aa9ae8bd96.pdf"
STUDY="GHAZY_SAKHA106_IRRIGATION_COMPOST_SILICATE_2022_2023"
DATA={
  (2022,4):{"total_irrigation_water":13005,"grain_yield":9.90,"water_saving":None,"water_use_efficiency":0.761},
  (2023,4):{"total_irrigation_water":12689,"grain_yield":10.36,"water_saving":None,"water_use_efficiency":0.816},
  (2022,8):{"total_irrigation_water":10680,"grain_yield":8.88,"water_saving":17.87,"water_use_efficiency":0.831},
  (2023,8):{"total_irrigation_water":10256,"grain_yield":9.21,"water_saving":19.17,"water_use_efficiency":0.898},
  (2022,12):{"total_irrigation_water":9627,"grain_yield":7.94,"water_saving":25.97,"water_use_efficiency":0.824},
  (2023,12):{"total_irrigation_water":9435,"grain_yield":8.30,"water_saving":25.64,"water_use_efficiency":0.879},
}
UNITS={"total_irrigation_water":"m3/ha","grain_yield":"t/ha","water_saving":"%","water_use_efficiency":"kg/m3"}
def main():
 rows=[]
 for (year,days),metrics in DATA.items():
  for metric,value in metrics.items():
   if value is None: continue
   rows.append(dict(study_id=STUDY,study_year=year,observation_period=f"irrigation_every_{days}_days",preceding_crop=None,puddling="not_stated_in_table_8",depth_top_cm=None,depth_bottom_cm=None,metric_name=metric,metric_value=value,unit=UNITS[metric],aggregation_level="irrigation interval marginal mean; Sakha 106; fertilizer treatments part of factorial trial",replicate_count=3,source_locator="Table 8",data_status="PUBLISHED_SAKHA_STATION_TREATMENT_MEAN_NOT_FARM_LABEL",source_url=URL))
 with OUT.open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 backup=DB.with_name(f"{DB.stem}_before_ghazy_2022_2023_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
 shutil.copy2(DB,backup)
 con=sqlite3.connect(DB);con.execute("PRAGMA foreign_keys=ON")
 try:
  con.execute("BEGIN IMMEDIATE")
  con.execute("INSERT INTO data_source(name,url,notes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,notes=excluded.notes",("Ghazy et al. 2024 Sakha 106 water and compost/silicate trial",URL,"Table 8 irrigation interval marginal means from Sakha station, 2022 and 2023; experimental results, not field-season farmer labels."))
  con.execute("INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,latitude=excluded.latitude,longitude=excluded.longitude,methods_summary=excluded.methods_summary,limitations=excluded.limitations,data_status=excluded.data_status",(STUDY,"Role of Composted Rice Straw and Potassium Silicate in Improving Productivity of Sakha 106 Rice Cultivar with Raised Water Use Efficiency","Hasnaa A. Ghazy; I. M. Hashem; I. A. Sheta",2024,"10.21608/jenvbs.2024.302891.1252",URL,"Experimental Farm, Sakha Agriculture Research Station, Kafr El-Sheikh",31.1167,30.95,"Rice seasons 2022 and 2023; Sakha 106; irrigation every 4, 8, and 12 days; 3 replications; factorial compost/potassium-silicate treatments. Table 8 contains irrigation-interval marginal means.","Station experiment only. Table 8 values are marginal means across fertilizer combinations; not individual fertilizer-treatment outcomes and not farmer observations. Irrigation totals cannot be converted to pump run times without a farm duty point. Verify transcribed values and method context against the PDF before operational use.","PUBLISHED_PRIMARY_RESEARCH_STATION_TRIAL"))
  con.execute("DELETE FROM literature_trial_observation WHERE study_id=?",(STUDY,))
  con.executemany("INSERT INTO literature_trial_observation(study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,source_locator,data_status,source_url) VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,:depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,:replicate_count,:source_locator,:data_status,:source_url)",rows)
  con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)",("ghazy_sakha106_water_trial_2022_2023",f"Imported {len(rows)} Table 8 observations: irrigation volume, yield, water saving, WUE by irrigation interval and season. Marginal experiment means; not field labels. Source {URL}"))
  assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
  assert not con.execute("PRAGMA foreign_key_check").fetchall()
  con.commit()
 except Exception: con.rollback();raise
 finally: con.close()
 print(f"Imported {len(rows)} observations; backup: {backup}")
if __name__=="__main__":main()
