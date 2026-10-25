"""Store the ARC's date-dependent maturity interval for Sakha Super 300."""
from pathlib import Path
import csv, json, shutil, sqlite3
from datetime import datetime

ROOT=Path(__file__).resolve().parent
DB=ROOT/'database'/'agriwater_v2.sqlite'
CSV=ROOT/'data'/'processed'/'rice_variety_field_guide_2025.csv'
URL='https://www.arc.sci.eg/products/details/9560'

def main():
    fields=['variety_name','maturity_days_min','maturity_days_max','yield_min_ton_feddan','yield_max_ton_feddan','planting_spacing_cm','hills_per_m2','plants_per_hill_min','plants_per_hill_max','urea_bags_per_feddan','suitability_note','salinity_response','water_stress_response','disease_note','source_url','source_status','notes']
    row={k:'' for k in fields}; row.update(variety_name='Sakha Super 300',maturity_days_min='114',maturity_days_max='147',source_url=URL,
      source_status='ARC_official_product_page',notes='ARC reports 114 days for late planting and 147 days for early planting; duration depends on planting date. Source page date shown as 18/12/2025.')
    with CSV.open(newline='',encoding='utf-8-sig') as f:
      if any(r.get('source_url')==URL for r in csv.DictReader(f)):
        append_csv=False
      else: append_csv=True
    if append_csv:
      with CSV.open('a',newline='',encoding='utf-8-sig') as f:
        csv.DictWriter(f,fieldnames=fields,extrasaction='ignore').writerow(row)
    backup=DB.with_name(f'{DB.stem}_before_super300_duration_{datetime.now():%Y%m%d_%H%M%S}.sqlite')
    con=sqlite3.connect(DB)
    try:
      with sqlite3.connect(backup) as b: con.backup(b)
      con.execute('PRAGMA foreign_keys=ON')
      with con:
       vid=con.execute("SELECT variety_id FROM rice_variety WHERE name_en='Sakha Super 300'").fetchone()[0]
       con.execute('''INSERT INTO rice_variety_field_guide
          (variety_id,guide_date,maturity_days_min,maturity_days_max,source_url,source_status,notes)
          VALUES (?,?,?,?,?,?,?) ON CONFLICT(variety_id,guide_date,source_url) DO UPDATE SET
          maturity_days_min=excluded.maturity_days_min,maturity_days_max=excluded.maturity_days_max,
          source_status=excluded.source_status,notes=excluded.notes''',
          (vid,'2025-12-18',114,147,URL,'ARC_official_product_page',row['notes']))
      fk=con.execute('PRAGMA foreign_key_check').fetchall(); ok=con.execute('PRAGMA integrity_check').fetchone()[0]
      if fk or ok!='ok': raise RuntimeError((fk,ok))
    finally: con.close()
    registry=ROOT/'source_registry.json'; sources=json.loads(registry.read_text(encoding='utf-8'))
    if not any(s.get('url')==URL for s in sources): sources.append({'source':'ARC Rice Research Department, Sakha Super 300 product page','url':URL,
      'dataset':'Cultivar attributes and maturity duration by planting timing','coverage':'Sakha Super 300 cultivar; official ARC product page',
      'access':'Public ARC page','limitations':'The source reports different duration for early versus late planting (147 versus 114 days); this is not a single fixed season length.'})
    registry.write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Imported maturity range 114–147 days; FK={len(fk)}; integrity={ok}; backup={backup.name}')
if __name__=='__main__': main()
