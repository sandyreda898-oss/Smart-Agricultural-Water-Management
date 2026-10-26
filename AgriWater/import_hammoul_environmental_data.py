"""Import soil and irrigation-water chemistry transcribed from Eid et al. (2022)."""
from pathlib import Path
import csv, json, shutil, sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'database' / 'agriwater_v2.sqlite'
CSV = ROOT / 'data' / 'processed' / 'hammoul_soil_water_chemistry_2020_2021.csv'
URL = 'https://jssae.journals.ekb.eg/article_243275_4763f4aa42c43aa2757cd3f2ece14627.pdf'
STUDY = 'eid_hammoul_rice_water_soil_2020_2021'

def main():
    rows=[]
    soil = {
      'sand':(14.7,'%'), 'silt':(32.3,'%'), 'clay':(53.0,'%'),
      'pH_1_to_1':(None,'pH'), 'EC_1_to_1':(None,'dS/m'),
      'Ca':(None,'meq/L'), 'Mg':(None,'meq/L'), 'Na':(None,'meq/L'), 'K':(None,'meq/L'),
      'CO3':(0,'meq/L'), 'HCO3':(1.6,'meq/L'), 'Cl':(None,'meq/L'), 'SO4':(None,'meq/L'),
      'available_K':(None,'mg/kg'), 'available_P':(None,'mg/kg'), 'available_N':(None,'mg/kg')}
    vals={
      'pH_1_to_1':(8.2,8.4),'EC_1_to_1':(5.57,3.86),'Ca':(6.64,6.264),'Mg':(13.08,12.744),
      'Na':(34.65,16.87),'K':(1.44,2.66),'Cl':(19.7,16.5),'SO4':(34.5,20.5),
      'available_K':(900,901.6),'available_P':(23.4,23.1),'available_N':(54.6,54.4)}
    for p,(v,u) in soil.items():
      a,b=vals.get(p,(v,v))
      for year,value in ((2020,a),(2021,b)):
        rows.append(dict(sample_kind='soil',sample_label='pre-cultivation soil',sample_year=year,treatment_code='',
          parameter_name=p,parameter_value=value,unit=u,source_locator='Table 1, p. 135',
          data_status='transcribed_published_site_trial_not_farmer_field'))
    # water chemistry: [blended 2020, drainage 2020, blended 2021, drainage 2021]
    water={
      'EC':([1.67,2.70,1.73,2.86],'dS/m'),'pH':([7.56,7.25,7.40,7.78],'pH'),
      'Na':([8.8,14.3,9.5,16.8],'meq/L'),'K':([0.8,2.2,0.9,1.5],'meq/L'),
      'Ca':([3.5,6.0,3.4,6.1],'meq/L'),'Mg':([3.8,5.4,3.7,5.5],'meq/L'),
      'CO3':([0,0,0,0],'meq/L'),'HCO3':([5.4,9.7,5.3,9.9],'meq/L'),
      'Cl':([8.0,12.6,7.3,14.1],'meq/L'),'SO4':([3.5,4.7,4.9,5.9],'meq/L')}
    labels=[(2020,'blended_canal_water'),(2020,'agricultural_drainage_water'),
            (2021,'blended_canal_water'),(2021,'agricultural_drainage_water')]
    for p,(vs,u) in water.items():
      for (year,label),value in zip(labels,vs):
        rows.append(dict(sample_kind='irrigation_water',sample_label=label,sample_year=year,treatment_code=label,
          parameter_name=p,parameter_value=value,unit=u,source_locator='Table 2, p. 135',
          data_status='transcribed_published_site_trial_not_farmer_field'))
    # Derived indices reported in Table 4; preserve reported values.
    indices={
      'SAR':([4.6,6.3,5.0,7.0],'dimensionless'), 'RSC':([0,0,0,0],'meq/L'),
      'SSP':([52.1,51.3,54.3,56.2],'%'), 'SMgP':([22.5,19.4,21.1,18.4],'%'),
      'PS':([9.8,14.9,9.8,16.4],'meq/L')}
    for p,(vs,u) in indices.items():
      for (year,label),value in zip(labels,vs):
        rows.append(dict(sample_kind='irrigation_water',sample_label=label,sample_year=year,treatment_code=label,
          parameter_name=p,parameter_value=value,unit=u,source_locator='Table 4, p. 136',
          data_status='transcribed_published_derived_water_quality_index'))
    CSV.parent.mkdir(parents=True,exist_ok=True)
    with CSV.open('w',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    backup=DB.with_name(f'{DB.stem}_before_hammoul_environmental_{datetime.now():%Y%m%d_%H%M%S}.sqlite')
    shutil.copy2(DB,backup)
    con=sqlite3.connect(DB)
    try:
      con.execute('PRAGMA foreign_keys=ON')
      con.execute('''CREATE TABLE IF NOT EXISTS literature_environmental_measurement (
        measurement_id INTEGER PRIMARY KEY, study_id TEXT NOT NULL REFERENCES literature_study(study_id),
        sample_kind TEXT NOT NULL CHECK(sample_kind IN ('soil','irrigation_water','other')),
        sample_label TEXT NOT NULL, sample_year INTEGER, treatment_code TEXT, depth_top_cm REAL,
        depth_bottom_cm REAL, parameter_name TEXT NOT NULL, parameter_value REAL NOT NULL,
        unit TEXT NOT NULL, source_locator TEXT NOT NULL, data_status TEXT NOT NULL, source_url TEXT NOT NULL)''')
      with con:
        con.execute('''INSERT OR REPLACE INTO literature_study
          (study_id,title,authors,publication_year,doi,source_url,location_name,methods_summary,limitations,data_status)
          VALUES (?,?,?,?,?,?,?,?,?,?)''',(
          STUDY,'Effect of Irrigation with Drainage and Blended Waters on Yield and Quality of some Rice Varieties (Oryza sativa) as well as Soil Quality at North Part of Nile Delta',
          'Mona S. M. Eid; I. M. Abdel-Fattah; Amira M. Okasha',2022,'10.21608/jssae.2022.124127.1056',URL,
          'Hammoul District, North Nile Delta, Egypt',
          'Two seasons (2020 and 2021); three rice cultivars (Sakha 104, Giza 177, Giza 178); irrigation treatments: agricultural drainage water, alternating drainage and blended canal water, and blended canal water.',
          'The transcribed soil and water chemistry are published experimental-site values, not parcel-level measurements. These tables do not establish each farmer pump runtime or an operational safe-use prescription. Table 5 has conflicting soil EC reporting and was excluded.',
          'publisher_pdf_tables_transcribed'))
        con.execute('DELETE FROM literature_environmental_measurement WHERE study_id=?',(STUDY,))
        con.executemany('''INSERT INTO literature_environmental_measurement
          (study_id,sample_kind,sample_label,sample_year,treatment_code,parameter_name,parameter_value,unit,source_locator,data_status,source_url)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)''',[(STUDY,r['sample_kind'],r['sample_label'],int(r['sample_year']),r['treatment_code'] or None,
          r['parameter_name'],float(r['parameter_value']),r['unit'],r['source_locator'],r['data_status'],URL) for r in rows])
      fk=con.execute('PRAGMA foreign_key_check').fetchall()
      integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
      count=con.execute('SELECT COUNT(*) FROM literature_environmental_measurement WHERE study_id=?',(STUDY,)).fetchone()[0]
      if fk or integrity!='ok': raise RuntimeError(f'Integrity failure: {integrity}; FK={fk[:3]}')
    finally: con.close()
    registry=ROOT/'source_registry.json'
    sources=json.loads(registry.read_text(encoding='utf-8'))
    sources=[s for s in sources if s.get('source')!='Eid et al. (2022), Hammoul rice soil and irrigation-water chemistry']
    sources.append({'source':'Eid et al. (2022), Hammoul rice soil and irrigation-water chemistry','url':URL,
      'dataset':'Published baseline soil chemistry, irrigation-water chemistry, and reported water-quality indices',
      'coverage':'Hammoul District; two rice seasons 2020 and 2021; soil before cultivation and blended canal/drainage water samples',
      'access':'Public publisher PDF; DOI 10.21608/jssae.2022.124127.1056',
      'limitations':'Experimental-site observations only; not a spatial layer or farmer field measurements. Transcribed Tables 1, 2, and 4; Table 5 omitted because reported baseline EC values conflict. Values do not determine irrigation volume or pump runtime.'})
    registry.write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'CSV rows={len(rows)}; imported rows={count}; backup={backup.name}; integrity={integrity}; fk_violations={len(fk)}')

if __name__=='__main__': main()
