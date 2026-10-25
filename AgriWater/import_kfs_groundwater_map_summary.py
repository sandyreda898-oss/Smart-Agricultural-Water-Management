"""Import published area-class summary from an interpolated Kafr El-Sheikh groundwater map."""
from pathlib import Path
import csv,json,shutil,sqlite3
from datetime import datetime

ROOT=Path(__file__).resolve().parent
DB=ROOT/'database'/'agriwater_v2.sqlite'
CSV=ROOT/'data'/'processed'/'kfs_groundwater_map_area_summary_2023.csv'
URL='https://www.degruyterbrill.com/document/doi/10.1515/geo-2022-0495/html'
STUDY='elbanna_kfs_geotechnical_groundwater_map_2023'
CLASSES=[('<1.5 m',979.7891,25.55),(1.5,2697.007,70.31),(3,114.1498,2.98),(4,34.35236,0.89),('>5.6 m',10.19678,0.27)]

def main():
 rows=[]
 for depth,area,share in CLASSES:
  tag=str(depth).replace(' ','_').replace('>','gt_').replace('<','lt_').replace('.','p')
  for metric,value,unit in ((f'area_{tag}',area,'km2'),(f'area_share_{tag}',share,'%')):
   rows.append({'sample_kind':'other','sample_label':'published governorate interpolated groundwater-depth map class',
    'sample_year':2023,'treatment_code':'MIDW_interpolated_map','parameter_name':metric,'parameter_value':value,'unit':unit,
    'source_locator':'Table 1, groundwater depth map class areas and percentages','data_status':'published_interpolated_map_summary_not_current_field_observation'})
 rows += [{'sample_kind':'other','sample_label':'published governorate interpolated groundwater-depth map class','sample_year':2023,
  'treatment_code':'MIDW_interpolated_map','parameter_name':'mapped_total_area','parameter_value':3835.461,'unit':'km2',
  'source_locator':'Table 1, total mapped area','data_status':'published_interpolated_map_summary_area_conflicts_with_reported_governorate_area'},
  {'sample_kind':'other','sample_label':'published governorate interpolated groundwater-depth map class','sample_year':2023,
  'treatment_code':'MIDW_interpolated_map','parameter_name':'mapped_total_share','parameter_value':100,'unit':'%',
  'source_locator':'Table 1, total mapped area','data_status':'published_interpolated_map_summary_area_conflicts_with_reported_governorate_area'}]
 CSV.parent.mkdir(parents=True,exist_ok=True)
 with CSV.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 backup=DB.with_name(f'{DB.stem}_before_kfs_groundwater_map_{datetime.now():%Y%m%d_%H%M%S}.sqlite')
 con=sqlite3.connect(DB)
 try:
  with sqlite3.connect(backup) as b:con.backup(b)
  con.execute('PRAGMA foreign_keys=ON')
  with con:
   con.execute('''INSERT OR REPLACE INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,methods_summary,limitations,data_status)
    VALUES (?,?,?,?,?,?,?,?,?,?)''',(STUDY,'Creating digital maps for geotechnical characteristics of soil based on GIS technology and remote sensing',
    'Mohammed A. El-Banna; Ali M. Basha; Ashraf A. A. Beshr',2023,'10.1515/geo-2022-0495',URL,'Kafr El-Sheikh Governorate, Egypt',
    '119 geotechnical soil borings, laboratory tests, and modified inverse-distance-weighted interpolation; groundwater depths monitored during boring and after 24 hours; published Table 1 reports interpolated area by depth class.',
    'This is a geotechnical map summary, not parcel-level agricultural groundwater monitoring. The article reports a mapped area (3835.461 km2) that differs from its stated governorate area (3716.68 km2); use only as coarse contextual reference, never as a field-specific value.',
    'publisher_article_area_summary_transcribed'))
   con.execute('DELETE FROM literature_environmental_measurement WHERE study_id=?',(STUDY,))
   con.executemany('''INSERT INTO literature_environmental_measurement(study_id,sample_kind,sample_label,sample_year,treatment_code,parameter_name,parameter_value,unit,source_locator,data_status,source_url)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',[(STUDY,r['sample_kind'],r['sample_label'],r['sample_year'],r['treatment_code'],r['parameter_name'],r['parameter_value'],r['unit'],r['source_locator'],r['data_status'],URL) for r in rows])
  fk=con.execute('PRAGMA foreign_key_check').fetchall(); integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
  if fk or integrity!='ok':raise RuntimeError((fk,integrity))
 finally:con.close()
 reg=ROOT/'source_registry.json';sources=json.loads(reg.read_text(encoding='utf-8'))
 if not any(s.get('url')==URL for s in sources):sources.append({'source':'El-Banna et al. (2023), Kafr El-Sheikh geotechnical maps','url':URL,
  'dataset':'119 borehole investigations and interpolated spatial summaries including groundwater depth','coverage':'Kafr El-Sheikh Governorate; geotechnical boreholes with depth up to 20–30 m','access':'Public Open Geosciences article',
  'limitations':'Area classes are a published interpolated map summary, not parcel-level agricultural groundwater monitoring. Reported mapped area 3835.461 km2 conflicts with article-stated governorate area 3716.68 km2. Do not use as field-specific groundwater depth.'})
 reg.write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'rows={len(rows)}; integrity={integrity}; FK={len(fk)}; backup={backup.name}')
if __name__=='__main__':main()
