"""Import Table 3 factorial treatment means from Eid et al. (2025), Northern Nile Delta rice trial."""
import csv,shutil,sqlite3
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"database"/"agriwater_v2.sqlite"
OUT=ROOT/"data"/"processed"/"eid_north_delta_planting_irrigation_2023_2024.csv"
URL="https://ejss.journals.ekb.eg/article_454852_c802bb5b9041bcd26fd8efe4eebbce92.pdf"
STUDY="EID_NORTH_DELTA_RICE_PLANTING_DEPTH_2023_2024"
# Table 3 rows: irrigation applied m3/ha, yield kg/ha, and PIW kg/m3 by treatment and season.
TABLE={
 "TPM":{7:{2023:(14689,13000,.88),2024:(14566,12947,.89)},5:{2023:(13145,12200,.89),2024:(12971,11495,.89)},3:{2023:(11595,12200,.89),2024:(11138,9996,.90)}},
 "FPM":{7:{2023:(12512,11700,1.03),2024:(12138,13090,1.08)},5:{2023:(11138,11300,1.01),2024:(10710,11376,1.06)},3:{2023:(9887,11000,1.03),2024:(10781,10234,1.06)}},
 "BPM":{7:{2023:(10886,10334,1.12),2024:(9639,12186,1.13)},5:{2023:(9691,10201,1.14),2024:(9544,10924,1.14)},3:{2023:(8604,9789,1.14),2024:(8473,10017,1.18)}}}
METHODS={"TPM":"traditional_planting_method","FPM":"furrow_planting_method","BPM":"bed_planting_method"}
def main():
 rows=[]
 for method,depths in TABLE.items():
  for depth,years in depths.items():
   for year,vals in years.items():
    for metric,value,unit in zip(("irrigation_water_applied","grain_yield","irrigation_water_productivity"),vals,("m3/ha","kg/ha","kg/m3")):
     rows.append(dict(study_id=STUDY,study_year=year,observation_period=f"{METHODS[method]}_ponding_depth_{depth}_cm",preceding_crop=None,puddling="not_stated_in_table_3",depth_top_cm=None,depth_bottom_cm=None,metric_name=metric,metric_value=value,unit=unit,aggregation_level=f"treatment mean; method={METHODS[method]}; irrigation depth={depth} cm; cultivar_not_reported_in_table_3",replicate_count=None,source_locator="Table 3",data_status="PUBLISHED_NORTHERN_DELTA_TREATMENT_MEAN_LOCATION_NOT_PARCEL",source_url=URL))
 with OUT.open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 backup=DB.with_name(f"{DB.stem}_before_eid_north_delta_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}");shutil.copy2(DB,backup)
 con=sqlite3.connect(DB);con.execute("PRAGMA foreign_keys=ON")
 try:
  con.execute("BEGIN IMMEDIATE")
  con.execute("INSERT INTO data_source(name,url,notes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,notes=excluded.notes",("Eid et al. 2025 Northern Nile Delta rice planting and irrigation depth trial",URL,"Table 3 treatment means from 2023-2024 trial; regional paper; precise study site and cultivar not included in extracted table fields."))
  con.execute("INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,latitude=excluded.latitude,longitude=excluded.longitude,methods_summary=excluded.methods_summary,limitations=excluded.limitations,data_status=excluded.data_status",(STUDY,"Planting Methods and Irrigation Depth Management to Enhance Water Productivity and Yield of Rice in the Northern Nile Delta, Egypt","Mona S. M. Eid; Ibrahim M. Abdel-Fattah; Mai A. M. Elsaka; Hesham M. Abo-Elsoud",2025,"10.21608/ejss.2025.410842.2305",URL,"Northern Nile Delta, Egypt; exact station/location not confirmed in this extract",None,None,"Factorial study, seasons 2023 and 2024; traditional/furrow/bed planting × 7/5/3 cm water depth. Table 3 reports irrigation water, grain yield, and irrigation water productivity treatment means.","Regional Northern Nile Delta paper. Exact field/station location, cultivar, and replication count were not carried into this extracted table record; do not spatially assign it to a Kafr El-Sheikh parcel. These are trial treatment means, not farmer labels or pump runtime instructions.","PUBLISHED_PRIMARY_RESEARCH_REGIONAL_TRIAL"))
  con.execute("DELETE FROM literature_trial_observation WHERE study_id=?",(STUDY,))
  con.executemany("INSERT INTO literature_trial_observation(study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,source_locator,data_status,source_url) VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,:depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,:replicate_count,:source_locator,:data_status,:source_url)",rows)
  con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)",("eid_north_delta_trial_2023_2024",f"Imported {len(rows)} numeric Table 3 values from regional Northern Nile Delta rice study. Exact site and cultivar not recorded in this table extract. Source: {URL}"))
  assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok";assert not con.execute("PRAGMA foreign_key_check").fetchall();con.commit()
 except Exception: con.rollback();raise
 finally: con.close()
 print(f"Imported {len(rows)} observations; backup: {backup}")
if __name__=="__main__":main()
