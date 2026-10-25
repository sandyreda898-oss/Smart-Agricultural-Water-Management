"""Create a separate, documented release package from the current SQLite source of truth.

Source files and the original database are never changed. Table exports are generated
from SQLite, so they match the database snapshot exactly.
"""
from pathlib import Path
import csv, gzip, json, shutil, sqlite3
from datetime import datetime

ROOT=Path(__file__).resolve().parent
SOURCE_DB=ROOT/'database'/'agriwater_v2.sqlite'
PACKAGE=ROOT/'AgriWater_Clean_Data'
STAMP='2026-10-25'

TABLE_DESCRIPTIONS={
'agronomy_recommendation':'إرشادات زراعية مرجعية مع النطاق الجغرافي والصنف والمرحلة والمصدر.',
'canal_schedule':'مواعيد مناوبات/فتح المياه حسب الموقع والفترة؛ فارغ لعدم وجود مصدر محلي موثق.',
'crop_calendar':'تقويم زراعي موسمي مرجعي للأرز.',
'crop_history':'تاريخ محاصيل قطعة المزارع؛ لا توجد سجلات حقول عامة.',
'crop_reference':'قاموس موحد للمحاصيل المستخدمة في التتابع الزراعي.',
'crop_water_parameter':'معاملات ومعلمات احتياج المياه، وبعضها مرجعي أو افتراضي.',
'data_source':'مصادر البيانات وروابطها وملاحظاتها.',
'database_metadata':'ملاحظات النسخ والاستيراد وإصدارات مراحل البناء.',
'district':'المحافظة والمراكز الإدارية المستخدمة في الربط المكاني.',
'field':'هوية/موقع قطعة المزارع؛ فارغ لعدم وجود بيانات حقول ميدانية.',
'field_operation':'عمليات حقلية مسجلة من المزارع؛ فارغ.',
'field_season':'موسم حقل ومخرجاته مثل إجمالي الري والغلة؛ فارغ.',
'grid_point':'نقاط الشبكة المرجعية للطقس والتربة.',
'groundwater_level':'قياسات منسوب ماء جوفي نقطية؛ فارغ، مع وجود ملخص خريطة في الأدلة المنشورة.',
'irrigation_event':'أحداث/ريات فعلية لحقول المستخدمين؛ فارغ.',
'irrigation_method':'قاموس طرق الري.',
'literature_environmental_measurement':'قياسات بيئية منشورة طويلة الشكل: تربة/مياه/ملخصات خرائطية مع مصدر وحالة.',
'literature_evidence':'نتائج واستنتاجات وصفية من دراسات منشورة.',
'literature_study':'بيانات تعريف الدراسات المنشورة وحدودها.',
'literature_trial_observation':'ملاحظات طويلة الشكل من تجارب منشورة (تربة/ماء/مناخ/محصول).',
'literature_trial_result':'نتائج رقمية بحسب الدراسة والسنة والصنف والمعاملة والمقياس.',
'machinery_inventory':'جرد حكومي إجمالي للآلات؛ لا يمثل قوائم مضخات مزارعين.',
'ministry_rule':'قواعد منسوبة لتوصيات إرشادية؛ بعض السجلات ثانوية وغير متحقق منها.',
'plant_protection_reference':'أعراض ونوافذ رصد/توقيت؛ ليست وصفات مبيدات أو جرعات.',
'point_season_summary':'ملخصات مناخية ومائية مشتقة لكل نقطة وموسم.',
'pump_catalog_series':'نطاقات مواصفات سلاسل مضخات من كتالوج مصنع، وليست نقاط أداء ميدانية.',
'pump_type':'أنواع/تصرفات موحدة لمضخات مستخدمين؛ فارغ لغياب موديل ونقطة تشغيل مؤكدة.',
'regional_stats':'إحصاءات الأرز السنوية على مستوى المحافظة.',
'rice_daily_water_demand':'تقدير يومي مرجعي لاحتياج ماء الأرز ETc.',
'rice_variety':'قاموس أصناف الأرز ومدد الموسم المتاحة.',
'rice_variety_field_guide':'بطاقات إرشادية منفصلة للصنف مع مصدر وتاريخ ونطاق مدة عند توافره.',
'rice_variety_reference':'صفات مرجعية للأصناف من ARC.',
'season':'قاموس السنوات/المواسم.',
'sentinel2_scene':'فهرس مشاهد Sentinel-2، وليس الصور أو مؤشرات الغطاء النباتي.',
'sentinel2_shortlist':'المشاهد المرشحة للمعالجة اللاحقة.',
'soil_awc':'السعة المائية المتاحة وتقدير عمق الجذر؛ مرجع خرائطي غير حقلي.',
'soil_point':'خصائص تربة مرتبطة بنقاط الشبكة ووحدات الخريطة.',
'soil_salinity':'قياس ملوحة نقطي/حقلي؛ فارغ. بعض دراسات الملوحة محفوظة في أدلة منفصلة.',
'vegetation_index':'قيم NDVI/EVI؛ فارغ ومؤجل حسب نطاق المشروع.',
'water_scenario':'سيناريوهات عامة لكمية الماء، وليست قياسًا فعليًا.',
'water_scenario_by_variety':'سيناريوهات أولية حسب الصنف؛ راجع الإصدار v3 قبل الاستخدام.',
'water_scenario_by_variety_clay':'سيناريوهات مكيّفة مع افتراضات القوام؛ ليست معايرة ميدانية.',
'water_scenario_by_variety_v3':'أحدث إصدار سيناريوهات كمية الماء حسب الصنف؛ تقديرات مشتقة.',
'weather_daily':'تقديرات طقس يومية شبكية من NASA POWER؛ ليست قياسات محطة/حقل.'}

QUALITY_ISSUES=[
('Q01','weather_daily','value','1292 قيمة NULL موزعة في سجل الطقس؛ 2026 سنة جزئية/قريبة من الزمن الحقيقي.','إبقاء NULL كما هو؛ لا تعويض متوسطات تلقائيًا؛ فحص مصدر اليوم والعنصر قبل ET0.'),
('Q02','soil_point','soil_data_status','36 من 38 نقطة مكتملة؛ تعتمد النقاط على 8 وحدات خريطة فقط.','عدم تقديمها كتحليل للتربة أو قياس لكل قطعة؛ استخدام الحالة المعلنة.'),
('Q03','field / field_season / irrigation_event','كل السجلات','جداول الحقول والمواسم والريات بلا صفوف.','تسميات التدريب والمخرجات الحقلية غير متاحة من الإنترنت؛ لا تُنشأ بيانات اصطناعية.'),
('Q04','pump_type / pump_catalog_series','discharge/head','لا توجد نقطة تصرف مؤكدة لمضخة بعينها عند الرفع الكلي الفعلي؛ الموجود 6 نطاقات كتالوج.','لا تحوّل كمية الماء إلى زمن تشغيل مؤكد من بيانات السلسلة فقط.'),
('Q05','canal_schedule','كل السجلات','جدول المناوبات فارغ؛ المواعيد محلية وموسمية.','لا تستنتج دور مياه ثابتًا للمحافظة.'),
('Q06','soil_salinity / groundwater_level','كل السجلات','الجداول النقطية/الحقلية فارغة. توجد نتائج منشورة منفصلة؛ خريطة 2023 جيوتقنية ومجموع مساحتها يخالف مساحة المحافظة المذكورة بالمقال.','حفظ الدليل المنشور في literature_environmental_measurement وعدم ربطه بحقل فردي.'),
('Q07','vegetation_index','كل السجلات','لا توجد قيم NDVI/EVI؛ فهرس المشاهد موجود فقط.','مؤجل حسب نطاق المستخدم؛ لا يُعد نقصًا مطلوبًا لإقفال الحزمة الحالية.'),
('Q08','ministry_rule','source_status','7 قواعد منقولة من مصادر ثانوية/صحفية وليست مطابقة لمصدر رسمي داخل المشروع.','استبعادها من التوصيات التشغيلية إلى حين المطابقة الرسمية.'),
('Q09','plant_protection_reference','pesticide_product / rate / preharvest interval','خمسة سجلات أعراض/توقيت، لكن اسم المنتج والمادة والجرعة وفترة ما قبل الحصاد غير مكتملة.','لا تعرض كتعليمات رش؛ التحقق من كتاب APC الرسمي وتسجيل المنتج.'),
('Q10','crop_water_parameter','kc / seepage','Kc المتأخر مخزن كنطاق/غير محدد كرقم واحد؛ الرشح والتهيئة افتراضات نطاقية/مرجعية.','إبقاء حدود القيم ووصف المرجع؛ لا استخدام كجدول ري معاير.'),
('Q11','rice_variety / rice_variety_field_guide','season_length_days','سخا سوبر 300 مدة نموه متغيرة حسب موعد الزراعة؛ عمود المدة المفردة NULL والنطاق موجود في البطاقة.','على المستهلك استخدام maturity_days_min/max وربطها بموعد الزراعة.'),
('Q12','rice_variety','name_en','السجل NOT_SPECIFIED صف بديل للتجميعات التي لا تحدد صنفًا.','استبعاده من توصية صنف مزارع أو من فئات الأصناف دون معالجة صريحة.'),
('Q13','water_scenario*','scenario/model versions','توجد إصدارات متعددة لسيناريوهات الماء؛ بعضها حسب الطين وبعضها أقدم.','اعتماد v3 عند الحاجة مع تسجيل إصدار المعادلة؛ لا تجمع الجداول كأنها ملاحظات مستقلة.'),
('Q14','literature_environmental_measurement','sample_kind / unit / source_locator','الجدول يضم قياسات تجربة، مؤشرات مشتقة، وملخصات خريطة؛ الوحدات والمستوى تختلف حسب المصدر.','التصفية حسب sample_kind وdata_status وstudy_id وsource_locator قبل التحليل.'),
('Q15','crop_history / fertilizer evidence','previous_crop','أدلة أثر المحصول السابق محدودة ولا تعطي معاملات NPK محلية موحدة لكل محاصيل التتابع.','استخدم تاريخ المحصول كميزة سياقية، لا كبديل جرعة سماد أو تحليل تربة.'),
('Q16','source registry / file extracts','versioning','مجلد المصدر يحتوي نسخًا قديمة/مراجعة وملفات وسيطة؛ بعض الأسماء تشير إلى OLD أو before_* ولا ينبغي اعتبارها النسخة النهائية.','الحزمة تعتمد SQLite الحالية وتصديراتها؛ يحتفظ المشروع الأم بالأصول والنسخ السابقة للتتبع.')]

def write_csv(path, rows, headers):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def main():
    if not SOURCE_DB.exists(): raise FileNotFoundError(SOURCE_DB)
    if PACKAGE.exists(): raise FileExistsError(f'Refusing to overwrite existing package: {PACKAGE}')
    for d in ['database','schema','data/table_exports','metadata','reports']:
        (PACKAGE/d).mkdir(parents=True,exist_ok=True)
    src=sqlite3.connect(SOURCE_DB)
    dst_path=PACKAGE/'database'/'agriwater_clean.sqlite'
    dst=sqlite3.connect(dst_path)
    src.backup(dst)
    dst.close()
    dst=sqlite3.connect(dst_path)
    dst.execute('PRAGMA foreign_keys=ON')
    integrity=dst.execute('PRAGMA integrity_check').fetchone()[0]
    fk_errors=dst.execute('PRAGMA foreign_key_check').fetchall()
    if integrity!='ok' or fk_errors: raise RuntimeError(f'Copied DB failed validation: {integrity}, {fk_errors[:3]}')
    tables=[r[0] for r in dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    shutil.copy2(ROOT/'schema.sql',PACKAGE/'schema'/'schema.sql')
    shutil.copy2(ROOT/'source_registry.json',PACKAGE/'metadata'/'source_registry.json')

    table_rows=[]; relation_rows=[]; dictionary_rows=[]; profile_rows=[]; export_rows=[]
    mermaid=['erDiagram']
    for table in tables:
        qtable='"'+table.replace('"','""')+'"'
        count=dst.execute(f'SELECT COUNT(*) FROM {qtable}').fetchone()[0]
        table_rows.append({'table_name':table,'row_count':count,'purpose_ar':TABLE_DESCRIPTIONS.get(table,'جدول مرجعي/مشتق؛ راجع قاموس الأعمدة ومصدر البيانات.'),'export_file':''})
        cols=dst.execute(f'PRAGMA table_info({qtable})').fetchall()
        fks=dst.execute(f'PRAGMA foreign_key_list({qtable})').fetchall()
        fkmap={r[3]:(r[2],r[4]) for r in fks}
        expressions=[]; alias_map=[]
        for i,col in enumerate(cols):
            name,decl=(col[1],(col[2] or '').upper())
            alias=f'n{i}'; expressions.append(f'SUM(CASE WHEN "{name.replace(chr(34),chr(34)*2)}" IS NULL THEN 1 ELSE 0 END) AS {alias}'); alias_map.append(('null',name,alias))
            if 'TEXT' in decl or 'CHAR' in decl or 'CLOB' in decl:
                alias=f'b{i}'; expressions.append(f'SUM(CASE WHEN "{name.replace(chr(34),chr(34)*2)}" IS NOT NULL AND TRIM(CAST("{name.replace(chr(34),chr(34)*2)}" AS TEXT)) = \'\' THEN 1 ELSE 0 END) AS {alias}'); alias_map.append(('blank',name,alias))
            if any(t in decl for t in ['INT','REAL','NUM','DEC','FLOA','DOUB']):
                alias=f'min{i}'; expressions.append(f'MIN("{name.replace(chr(34),chr(34)*2)}") AS {alias}')
                alias=f'max{i}'; expressions.append(f'MAX("{name.replace(chr(34),chr(34)*2)}") AS {alias}')
        agg={}
        if count and expressions:
            values=dst.execute(f'SELECT {", ".join(expressions)} FROM {qtable}').fetchone()
            agg=dict(zip([a for a,_,_ in alias_map]+[f'min{i}' for i,c in enumerate(cols) if any(t in (c[2] or '').upper() for t in ['INT','REAL','NUM','DEC','FLOA','DOUB'])]+[f'max{i}' for i,c in enumerate(cols) if any(t in (c[2] or '').upper() for t in ['INT','REAL','NUM','DEC','FLOA','DOUB'])],values))
            # Stable explicit access to generated aliases (the mapping above is used only for counts).
            for kind,name,alias in alias_map: agg[alias]=values[expressions.index(next(x for x in expressions if f' AS {alias}' in x))]
            for i,col in enumerate(cols):
                decl=(col[2] or '').upper()
                if any(t in decl for t in ['INT','REAL','NUM','DEC','FLOA','DOUB']):
                    for prefix in ('min','max'):
                        alias=f'{prefix}{i}'; agg[alias]=values[expressions.index(next(x for x in expressions if f' AS {alias}' in x))]
        for col in cols:
            cid,name,decl,notnull,default,pk=col
            nulls=agg.get(f'n{cid}',0) if count else 0
            blanks=agg.get(f'b{cid}',0) if count else 0
            pct=(100.0*nulls/count) if count else 0.0
            fk=fkmap.get(name)
            minv=agg.get(f'min{cid}') if any(t in (decl or '').upper() for t in ['INT','REAL','NUM','DEC','FLOA','DOUB']) else None
            maxv=agg.get(f'max{cid}') if any(t in (decl or '').upper() for t in ['INT','REAL','NUM','DEC','FLOA','DOUB']) else None
            dictionary_rows.append({'table_name':table,'table_purpose_ar':TABLE_DESCRIPTIONS.get(table,''),'column_name':name,'declared_type':decl or 'UNDECLARED','primary_key_order':pk,
                'not_null':bool(notnull),'default_value':default,'foreign_key_table':fk[0] if fk else '', 'foreign_key_column':fk[1] if fk else '',
                'row_count':count,'null_count':nulls,'null_percent':round(pct,4),'blank_string_count':blanks,'numeric_min':minv,'numeric_max':maxv})
            profile_rows.append({'table_name':table,'column_name':name,'declared_type':decl or 'UNDECLARED','row_count':count,'null_count':nulls,
                'null_percent':round(pct,4),'blank_string_count':blanks,'numeric_min':minv,'numeric_max':maxv,'not_null':bool(notnull),'primary_key_order':pk,
                'foreign_key':f'{fk[0]}.{fk[1]}' if fk else ''})
        for fkrow in fks:
            fid,seq,parent,from_col,to_col,on_update,on_delete,match=fkrow
            relation_rows.append({'child_table':table,'child_column':from_col,'parent_table':parent,'parent_column':to_col,'fk_id':fid,'sequence':seq,'on_update':on_update,'on_delete':on_delete})
            mermaid.append(f'  {parent} ||--o{{ {table} : "{from_col}"')

        export_file=''
        if count:
            compressed=count>100000
            export_file=f'{table}.csv.gz' if compressed else f'{table}.csv'
            out=PACKAGE/'data'/'table_exports'/export_file
            open_fn=gzip.open if compressed else open
            with open_fn(out,'wt',newline='',encoding='utf-8-sig') as f:
                cur=dst.execute(f'SELECT * FROM {qtable}')
                writer=csv.writer(f); writer.writerow([d[0] for d in cur.description])
                while True:
                    batch=cur.fetchmany(20000)
                    if not batch: break
                    writer.writerows(batch)
            export_rows.append({'table_name':table,'row_count':count,'file':f'data/table_exports/{export_file}','format':'CSV.GZ' if compressed else 'CSV','generated_from':'database/agriwater_clean.sqlite','notes':TABLE_DESCRIPTIONS.get(table,'')})
        table_rows[-1]['export_file']=export_file

    write_csv(PACKAGE/'schema'/'table_inventory.csv',table_rows,['table_name','row_count','purpose_ar','export_file'])
    write_csv(PACKAGE/'schema'/'foreign_key_relationships.csv',relation_rows,['child_table','child_column','parent_table','parent_column','fk_id','sequence','on_update','on_delete'])
    write_csv(PACKAGE/'schema'/'data_dictionary.csv',dictionary_rows,['table_name','table_purpose_ar','column_name','declared_type','primary_key_order','not_null','default_value','foreign_key_table','foreign_key_column','row_count','null_count','null_percent','blank_string_count','numeric_min','numeric_max'])
    write_csv(PACKAGE/'schema'/'column_profile.csv',profile_rows,['table_name','column_name','declared_type','row_count','null_count','null_percent','blank_string_count','numeric_min','numeric_max','not_null','primary_key_order','foreign_key'])
    write_csv(PACKAGE/'metadata'/'export_manifest.csv',export_rows,['table_name','row_count','file','format','generated_from','notes'])
    write_csv(PACKAGE/'metadata'/'data_quality_issues.csv',[dict(zip(['issue_id','table_or_column','field','issue_ar','handling_ar'],r)) for r in QUALITY_ISSUES],['issue_id','table_or_column','field','issue_ar','handling_ar'])
    (PACKAGE/'schema'/'erd_all_tables.mmd').write_text('\n'.join(mermaid)+'\n',encoding='utf-8')
    # Main high-level ERD is easier to read than the complete 44-table relationship graph.
    core='''erDiagram
  DISTRICT ||--o{ GRID_POINT : contains
  GRID_POINT ||--o{ WEATHER_DAILY : climate_estimates
  GRID_POINT ||--|| SOIL_POINT : mapped_soil
  GRID_POINT ||--|| SOIL_AWC : available_water
  SEASON ||--o{ REGIONAL_STATS : annual_statistics
  SEASON ||--o{ CROP_CALENDAR : season_calendar
  RICE_VARIETY ||--o{ CROP_CALENDAR : cultivar_calendar
  RICE_VARIETY ||--o| RICE_VARIETY_REFERENCE : catalogue_profile
  RICE_VARIETY ||--o{ RICE_VARIETY_FIELD_GUIDE : dated_guide
  RICE_VARIETY ||--o{ LITERATURE_TRIAL_RESULT : trial_cultivar
  LITERATURE_STUDY ||--o{ LITERATURE_TRIAL_RESULT : publishes
  LITERATURE_STUDY ||--o{ LITERATURE_TRIAL_OBSERVATION : publishes
  LITERATURE_STUDY ||--o{ LITERATURE_ENVIRONMENTAL_MEASUREMENT : publishes
  LITERATURE_STUDY ||--o{ LITERATURE_EVIDENCE : publishes
  FIELD ||--o{ FIELD_SEASON : has_seasons
  FIELD_SEASON ||--o{ IRRIGATION_EVENT : has_events
  FIELD_SEASON ||--o{ FIELD_OPERATION : has_operations
  FIELD ||--o{ CROP_HISTORY : previous_crops
  PUMP_TYPE ||--o{ FIELD : assigned_pump
  RICE_VARIETY ||--o{ WATER_SCENARIO_BY_VARIETY_V3 : scenario
  GRID_POINT ||--o{ POINT_SEASON_SUMMARY : seasonal_features
  GRID_POINT ||--o{ WATER_SCENARIO : estimated_water'''
    (PACKAGE/'schema'/'erd_core.mmd').write_text(core+'\n',encoding='utf-8')
    src.close(); dst.close()

    # Derived summary metrics for the package report.
    summary={}
    con=sqlite3.connect(dst_path)
    for t in ['weather_daily','grid_point','soil_point','soil_awc','literature_study','literature_trial_observation','literature_trial_result','literature_environmental_measurement','rice_variety','rice_variety_reference','rice_variety_field_guide','agronomy_recommendation','crop_calendar','pump_catalog_series','regional_stats','rice_daily_water_demand','point_season_summary','water_scenario','water_scenario_by_variety_v3','sentinel2_scene','sentinel2_shortlist']:
        summary[t]=con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    summary['tables']=len(tables); summary['foreign_keys']=len(relation_rows); summary['empty_tables']=[t for t in tables if con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]==0]
    summary['weather_nulls']=con.execute('SELECT COUNT(*) FROM weather_daily WHERE value IS NULL').fetchone()[0]
    summary['weather_points']=con.execute('SELECT COUNT(DISTINCT point_id) FROM weather_daily').fetchone()[0]
    summary['weather_parameters']=con.execute('SELECT COUNT(DISTINCT parameter) FROM weather_daily').fetchone()[0]
    summary['weather_start']=con.execute('SELECT MIN(obs_date) FROM weather_daily').fetchone()[0]
    summary['weather_end']=con.execute('SELECT MAX(obs_date) FROM weather_daily').fetchone()[0]
    summary['foreign_key_errors']=len(con.execute('PRAGMA foreign_key_check').fetchall())
    summary['integrity']=con.execute('PRAGMA integrity_check').fetchone()[0]
    summary['column_count']=len(dictionary_rows)
    summary['files_exported']=len(export_rows)
    summary['environment_statuses']=[list(x) for x in con.execute('SELECT data_status,COUNT(*) FROM literature_environmental_measurement GROUP BY data_status ORDER BY data_status')]
    summary['source_studies']=[list(x) for x in con.execute('SELECT study_id,publication_year,location_name,data_status FROM literature_study ORDER BY publication_year,study_id')]
    summary['source_db_size_mb']=round(SOURCE_DB.stat().st_size/1024/1024,2)
    summary['package_db_size_mb']=round(dst_path.stat().st_size/1024/1024,2)
    con.close()
    (PACKAGE/'metadata'/'package_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PACKAGE/'metadata'/'quality_issues.json').write_text(json.dumps([dict(zip(['issue_id','table_or_column','field','issue_ar','handling_ar'],r)) for r in QUALITY_ISSUES],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_readme(PACKAGE,summary,table_rows)
    write_report(PACKAGE,summary,table_rows,relation_rows,profile_rows)
    print(json.dumps({'package':str(PACKAGE),'tables':summary['tables'],'foreign_keys':summary['foreign_keys'],'column_count':summary['column_count'],'nonempty_exports':summary['files_exported'],'empty_tables':len(summary['empty_tables']),'integrity':summary['integrity'],'fk_errors':summary['foreign_key_errors']},ensure_ascii=False))

def write_readme(pkg,s,tables):
    empty='، '.join(s['empty_tables'])
    text=f'''# حزمة بيانات AgriWater النظيفة

**النطاق:** قاعدة بيانات مرجعية منظمة للأرز في كفر الشيخ، موجهة للتحليل والبناء اللاحق. هذه الحزمة منفصلة عن ملفات المصدر الأصلية.

## نقطة البداية

- `database/agriwater_clean.sqlite`: نسخة موحدة من قاعدة SQLite الرئيسية، مع الجداول والعلاقات كما هي.
- `schema/schema.sql`: تعريف الجداول والقيود.
- `schema/erd_core.mmd`: رسم العلاقات الأساسية بصيغة Mermaid.
- `schema/erd_all_tables.mmd`: العلاقات المستخرجة من مفاتيح SQLite الخارجية لكل الجداول.
- `schema/data_dictionary.csv`: قاموس جميع الأعمدة والأنواع والمفاتيح والمصدر المرجعي وعدد القيم المفقودة/الفارغة ونطاق الأعمدة الرقمية.
- `schema/foreign_key_relationships.csv`: كل العلاقات الخارجية الـ{s['foreign_keys']}.
- `schema/column_profile.csv`: تقرير جودة لكل عمود.
- `schema/table_inventory.csv`: عدد الصفوف ووصف كل جدول.
- `data/table_exports/`: تصدير مطابق للجداول غير الفارغة؛ الجداول الكبيرة مضغوطة gzip لتقليل المساحة.
- `metadata/source_registry.json`: سجل المصادر وحدود الاستخدام.
- `metadata/data_quality_issues.csv`: قائمة المشكلات وقواعد التعامل معها.
- `reports/AgriWater_Clean_Database_Report.pdf`: التقرير التفصيلي.

## ماذا تعني كلمة "نظيفة" هنا؟

التنظيف هنا يعني قاعدة موحدة، مفاتيح وعلاقات سليمة، وتصديرات مولدة من قاعدة البيانات نفسها، مع توثيق الوحدة والمصدر والنواقص. لم أملأ قيمًا مفقودة بالتخمين ولم أدمج متوسطات الدراسات كأنها قياسات حقول. سجلات المصدر الثانوي أو الافتراضي باقية مع حالة الجودة ليقرر مستخدم النموذج إدراجها أو استبعادها.

## ملخص اللقطة

- {s['tables']} جدولًا، {s['foreign_keys']} علاقة بمفتاح خارجي، و{s['column_count']} عمودًا موثقًا.
- {s['files_exported']} جدولًا غير فارغًا له تصدير CSV/CSV.GZ.
- الطقس: {s['weather_points']} نقطة × {s['weather_parameters']} متغيرات يومية من {s['weather_start']} إلى {s['weather_end']}، وعدد القيم NULL = {s['weather_nulls']}.
- سلامة SQLite: `{s['integrity']}`؛ مخالفات المفاتيح الخارجية: {s['foreign_key_errors']}.
- الجداول الفارغة: {empty}.

## تشغيل سريع

يمكن فتح `database/agriwater_clean.sqlite` مباشرةً باستخدام SQLite. لا تبدأ تدريب نموذج قبل قراءة `reports/AgriWater_Clean_Database_Report.pdf` وملف `schema/data_quality_issues.csv`، واختيار جداول السمات والهدف المناسبين.
'''
    (pkg/'README_AR.md').write_text(text,encoding='utf-8')

def write_report(pkg,s,tables,relations,profiles):
    rows=''.join(f"<tr><td dir='ltr'>{r['table_name']}</td><td>{r['row_count']:,}</td><td>{r['purpose_ar']}</td></tr>" for r in tables)
    empty_rows=''.join(f"<tr><td dir='ltr'>{t}</td><td>{TABLE_DESCRIPTIONS.get(t,'')}</td></tr>" for t in s['empty_tables'])
    relation_display=['district → grid_point','grid_point → weather_daily','grid_point → soil_point / soil_awc','season → regional_stats / crop_calendar / seasonal summaries','rice_variety → variety reference / guide / trial results / scenarios','literature_study → trial results / observations / environmental measurements / evidence','field → field_season → irrigation_event / field_operation (all empty pending farmer records)']
    qrows=''.join(f"<tr><td>{r[0]}</td><td dir='ltr'>{r[1]}</td><td dir='ltr'>{r[2]}</td><td>{r[3]}</td></tr>" for r in QUALITY_ISSUES)
    # Highest missingness is presented with context; long-form study columns are naturally sparse.
    nonempty=[p for p in profiles if p['row_count'] and p['null_percent']>=50]
    nonempty.sort(key=lambda x:(-x['null_percent'],-x['row_count']))
    nullrows=''.join(f"<tr><td dir='ltr'>{p['table_name']}</td><td dir='ltr'>{p['column_name']}</td><td>{p['null_count']:,} / {p['row_count']:,}</td><td>{p['null_percent']:.1f}%</td></tr>" for p in nonempty[:24])
    html=f'''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><style>
@page{{size:A4;margin:16mm 15mm}}body{{font-family:Arial,Tahoma,sans-serif;color:#193441;font-size:10pt;line-height:1.65}}h1{{font-size:27pt;color:#fff}}h2{{color:#0d6467;border-bottom:2px solid #cce3df;padding-bottom:3mm;margin-top:0;break-after:avoid}}h3{{color:#176b73;break-after:avoid}}p{{margin:0 0 3mm}}li{{margin:1mm 0}}ul,ol{{padding-right:6mm}}.cover{{height:250mm;padding:25mm 18mm;background:linear-gradient(135deg,#0b3548,#087d78);color:#fff;border-radius:4mm;position:relative}}.cover .sub{{font-size:15pt;color:#def0ed}}.cover .meta{{position:absolute;bottom:20mm;right:18mm;color:#cce7e1}}.page{{break-before:page}}table{{width:100%;border-collapse:collapse;margin:3mm 0 5mm;font-size:8.2pt;break-inside:auto}}thead{{display:table-header-group}}tr{{break-inside:avoid}}th{{background:#0c5962;color:#fff}}td,th{{border:1px solid #c8d7d9;padding:1.3mm 1.5mm;vertical-align:top}}tr:nth-child(even) td{{background:#f2f8f7}}.call{{padding:3mm 4mm;margin:3mm 0 5mm;border-right:4px solid #0c8077;background:#eff8f6}}.warn{{padding:3mm 4mm;margin:3mm 0 5mm;border-right:4px solid #d69a2b;background:#fff6e8}}.bad{{padding:3mm 4mm;margin:3mm 0 5mm;border-right:4px solid #c54e43;background:#fff0ee}}.small{{font-size:8.3pt;color:#536d77}}.ltr{{direction:ltr;text-align:left;unicode-bidi:embed;overflow-wrap:anywhere}}.source{{font-size:8pt;direction:ltr;text-align:left;overflow-wrap:anywhere}}.cards{{display:flex;gap:3mm;margin:3mm 0 5mm}}.card{{flex:1;text-align:center;border:1px solid #cddfdf;background:#f7fbfa;padding:3mm;border-radius:2mm}}.card b{{font-size:16pt;color:#087a73;display:block}}.mono{{font-family:Consolas,monospace;direction:ltr;text-align:left}}
</style><body>
<section class="cover"><p>AgriWater | تسليم مرحلة البيانات</p><h1>حزمة البيانات النظيفة<br>وقاموس قاعدة البيانات</h1><p class="sub">مخطط الجداول والعلاقات، وصف الأعمدة، مراجعة الجودة، وجاهزية بيانات النموذج</p><div class="meta">التاريخ: {STAMP}<br>المصدر: قاعدة SQLite للمشروع<br>هذه الحزمة لا تستبدل ملفات الأصول الأصلية</div></section>
<section class="page"><h2>1. ملخص التنفيذ</h2><p>أنشأت نسخة منفصلة على سطح المكتب داخل مجلد المشروع باسم AgriWater_Clean_Data. قاعدة البيانات الأصلية لم تُعدّل. الحزمة الجديدة تحتوي نسخة SQLite، ملف SQL، مخطط علاقات، قاموس كل الأعمدة، تقرير جودة لكل عمود، وتصديرات متطابقة مع الجداول غير الفارغة.</p><div class="cards"><div class="card"><b>{s['tables']}</b>جدولًا</div><div class="card"><b>{s['foreign_keys']}</b>علاقة FK</div><div class="card"><b>{s['column_count']}</b>عمود موثق</div><div class="card"><b>{s['files_exported']}</b>تصدير جدول</div></div><div class="call"><b>تعريف النسخة النظيفة:</b> توحيد مصدر البيانات إلى SQLite واحد، وتصدير قيمه دون نسخ نسخ وسيطة متضاربة. لم يتم اختلاق أو تعويض القيم المفقودة؛ جميع درجات المصدر والاشتقاق محفوظة.</div><p>القاعدة اجتازت <span class="ltr">integrity_check={s['integrity']}</span> ولم يظهر أي خرق مفاتيح خارجية. القاعدة تضم {len(s['empty_tables'])} جداول فارغة مصممة لبيانات مستقبلية/غير متاحة من الإنترنت.</p><h3>مكونات التسليم</h3><ul><li>قاعدة SQLite قابلة للتشغيل مباشرة.</li><li>تعريف SQL والمخطط الكامل للعلاقات المستخرجة من القيود الفعلية.</li><li>قاموس بيانات لجميع الأعمدة: النوع، المفتاح، علاقات FK، النقص، القيم الفارغة، وملخص النطاق الرقمي.</li><li>تصدير CSV أو CSV مضغوط لكل جدول غير فارغ.</li><li>سجل جودة وملاحظات استخدام، ونسخة سجل المصادر.</li></ul></section>
<section class="page"><h2>2. شكل قاعدة البيانات والعلاقات</h2><p>القاعدة علائقية متعددة المجالات. علاقاتها المعتمدة هنا مستخرجة من قيود SQLite نفسها، لا من تخمين أسماء الأعمدة. الملف <span class="mono">schema/erd_all_tables.mmd</span> يحتوي كل الجداول والعلاقات. والملف <span class="mono">schema/erd_core.mmd</span> يختصر المسار الأساسي.</p><h3>العلاقات الأساسية</h3><ul>{''.join(f'<li>{x}</li>' for x in relation_display)}</ul><div class="warn">جداول الحقل والموسم والري موجودة في التصميم لكنها فارغة؛ لذلك هذه العلاقات جاهزة لتسجيل البيانات لاحقًا وليست سجلًا ميدانيًا حاليًا. بعض الروابط المنطقية مثل المطر/المكان تتم عبر point_id والتواريخ، لا عبر FK مباشر إلى جدول واحد.</div><h3>طريقة قراءة المفاتيح</h3><p><b>PK</b> يميز الصف داخل جدوله. <b>FK</b> يربط الصف بمرجع أساسي. علاقة parent 1-to-many تعني أن المرجع مثل المركز أو الدراسة يمكن أن يظهر في صفوف كثيرة تابعة له. قاموس العلاقات يذكر عمود child وعمود parent وقيود الحذف/التحديث.</p><table><thead><tr><th>المجموعة</th><th>الجداول المحورية</th><th>دورها في المشروع</th></tr></thead><tbody><tr><td>المكان</td><td class="ltr">district, grid_point</td><td>تجميع نقاط الطقس/التربة وربط النقطة بالمركز.</td></tr><tr><td>المناخ والماء</td><td class="ltr">weather_daily, point_season_summary, rice_daily_water_demand, water_scenario*</td><td>طقس، ETc، ومخرجات سيناريو محسوبة وموسومة بأنها تقديرية.</td></tr><tr><td>المحصول والإرشاد</td><td class="ltr">rice_variety, rice_variety_reference, rice_variety_field_guide, agronomy_recommendation, crop_calendar</td><td>صفات الصنف ومواعيد/قواعد إرشادية ذات مصادر ونطاقات.</td></tr><tr><td>المصادر البحثية</td><td class="ltr">literature_study, literature_trial_result, literature_trial_observation, literature_environmental_measurement, literature_evidence</td><td>الأدلة المنشورة مفصولة عن بيانات المزارع.</td></tr><tr><td>الحقل الفعلي</td><td class="ltr">field, field_season, irrigation_event, field_operation, crop_history</td><td>مصممة لملاحظات المستخدم؛ فارغة حاليًا.</td></tr></tbody></table></section>
<section class="page"><h2>3. قائمة الجداول كاملة</h2><p class="small">الأعداد من النسخة المصدر يوم 25 أكتوبر 2026. الجدول يضم كل {len(tables)} جدولًا؛ الصفوف الفارغة تبقى جزءًا من المخطط.</p><table><thead><tr><th>اسم الجدول</th><th>الصفوف</th><th>الغرض وحدود الاستخدام</th></tr></thead><tbody>{rows}</tbody></table></section>
<section class="page"><h2>4. الملفات المصدّرة وآلية التنظيف</h2><p>جميع ملفات <span class="mono">data/table_exports/</span> تم توليدها من نسخة SQLite الجديدة؛ لا توجد إعادة كتابة يدوية للصفوف. الجداول حتى 100 ألف صف صدرت CSV، والجداول الأكبر مضغوطة بصيغة CSV.GZ. قاعدة البيانات نفسها تظل النسخة المرجعية عند اختلاف عرض Excel أو طريقة تحويل النوع.</p><h3>الملفات التي لم تُنسخ إلى الحزمة</h3><ul><li>المجلدات الخام الأصلية والـPDFs الكاملة والنسخ المؤقتة؛ تظل في المشروع الأم لتقليل التكرار وتجنب خلط الإصدارات.</li><li>ملفات NDVI/صور الأقمار غير موجودة أصلًا كقيم تحليل؛ فهرس المشاهد فقط ضمن جدول Sentinel.</li><li>قوالب الاستبيان القديمة أو ملفات before/OLD لا تعامل كبيانات نهائية.</li></ul><p>تصدير الجداول لا يعني أن كل صف صالح كمدخل لموديل. قبل التدريب استخدم قاموس الأعمدة، ثم اختر نطاق المصدر، الوحدة، السنة، الصنف، الموقع، data_status، وحالة القياس/الاشتقاق.</p><h3>محتويات المجلد</h3><table><thead><tr><th>المجلد</th><th>المحتوى</th></tr></thead><tbody><tr><td class="mono">database/</td><td>نسخة SQLite النظيفة.</td></tr><tr><td class="mono">schema/</td><td>SQL وERD وقاموس بيانات وعلاقات وملفات profiling.</td></tr><tr><td class="mono">data/table_exports/</td><td>تصدير كل جدول غير فارغ من قاعدة البيانات.</td></tr><tr><td class="mono">metadata/</td><td>مصادر البيانات، قائمة التصدير، ملخص الحزمة، ومشكلات الجودة.</td></tr><tr><td class="mono">reports/</td><td>التقرير الكامل بصيغتي PDF وMarkdown.</td></tr></tbody></table></section>
<section class="page"><h2>5. مراجعة الأعمدة ومشكلات الجودة</h2><p>تم مسح عدد الصفوف، أنواع الأعمدة، مفاتيحها، القيم NULL، النصوص الفارغة، وحدود الأعمدة الرقمية. التقرير الكامل لكل عمود موجود في <span class="mono">schema/column_profile.csv</span>. ارتفاع النقص في جدول أدلة طويل الشكل قد يكون طبيعيًا لأن القياس لا ينطبق على كل دراسة؛ لا تعتبر النسبة وحدها سببًا للحذف.</p><h3>أعمدة ذات نقص مرتفع في جداول غير فارغة (أعلى 24 بعدد الصفوف والنسبة)</h3><table><thead><tr><th>الجدول</th><th>العمود</th><th>NULL / الإجمالي</th><th>النسبة</th></tr></thead><tbody>{nullrows}</tbody></table><p class="small">راجع ملف العمود للحصول على كامل الأعمدة التي يتجاوز نقصها 50%، لأن عرض جميعها في التقرير قد يشتت القارئ.</p><h3>ملاحظات الجودة والإجراء</h3><table><thead><tr><th>ID</th><th>الجدول/العمود</th><th>المشكلة</th><th>طريقة التعامل</th></tr></thead><tbody>{qrows}</tbody></table></section>
<section class="page"><h2>6. الأعمدة المهمة ومعناها للموديل</h2><table><thead><tr><th>مدخل الفلاح</th><th>سمات مرجعية يمكن اشتقاقها</th><th>قيود/هدف غير موجود</th></tr></thead><tbody><tr><td>المكان على الخريطة</td><td>المركز، نقطة شبكة الطقس، طبقة تربة/سعة ماء، سياق الدراسات.</td><td>الخرائط ليست تحليل حقل أو حدود قطعة قانونية.</td></tr><tr><td>مساحة الأرض</td><td>تحويل عمق الماء من mm إلى حجم: للفدان 1mm = 4.2m³.</td><td>لا يوجد حجم ري حقيقي للحقل لتدريب نموذج زمن المضخة.</td></tr><tr><td>المحاصيل السابقة الثلاثة</td><td>قاموس crop_reference وأدلة المنشورات كسياق للدورة الزراعية.</td><td>لا يوجد تاريخ عام لكل قطعة أو علاقة خصم سماد موثقة.</td></tr><tr><td>نوع المضخة</td><td>كتالوج سلسلة ومواصفات اسمية.</td><td>تصرف الموديل عند TDH/مواسير المزرعة غير متوفر.</td></tr><tr><td>الصنف الذي ينوي زراعته</td><td>مرجع ARC، دليل إرشاد، مدة/صفة مع المصدر؛ 23 قاعدة توصية.</td><td>توافر التقاوي، أسلوب الزراعة الفعلي، ومعايرة الصنف/الموسم.</td></tr><tr><td>طقس المكان/اليوم</td><td>ET0/ETc ومطر وإشعاع ورطوبة/حرارة.</td><td>تقديرات شبكة، 2026 جزئية؛ لا هدف ري مقاس للحقل.</td></tr></tbody></table><h3>السمات والهدف</h3><div class="call"><b>Features متاحة:</b> الموقع، الطقس، خصائص تربة خرائطية، الصنف، مرحلة الموسم، وبعض محاصيل سابقة مرجعية. <br><b>Targets الميدانية غير متاحة:</b> عمق/حجم الماء الفعلي، زمن الري، الغلة الحقلية، جودة التربة في القطعة، الالتزام بالتوصية، كلفة/طاقة الضخ.</div><p>توجد جداول مشتقة بها 266 موسم/نقطة و9,044 صف سيناريو حسب الصنف، لكن هذه ليست تسميات تدريب حقيقية. يمكن استخدامها لاختبار الحسابات أو مقارنة السيناريوهات، لا لتدريب نموذج إشرافي يدعي توقع الغلة أو كمية الري الفعلية.</p></section>
<section class="page"><h2>7. ما لم يمكن جمعه من الإنترنت وما يحتاج استكمالًا</h2><ul><li>ريات الحقول الفعلية، الغلة، المواعيد والعمليات وسجل المحاصيل الثلاثة لكل مزارع.</li><li>تصرف المضخة الفعلي عند الرفع والضغط والمواسير، ونقطة منحنى المضخة.</li><li>مناوبات مياه كل ترعة/قرية في الموسم الحالي.</li><li>تحليل NPK/EC حديث لكل قطعة مع العمق وطريقة المختبر.</li><li>ملوحة ومنسوب مياه جوفية زراعيان بإحداثيات وتاريخ وتغطية يمكن ربطها بالأرض.</li><li>معاملات/حدود حرجة تربط تحليل التربة بجرعة سماد الأرز بحسب المصدر وطريقة القياس.</li><li>توصيات مبيد رسمية حديثة كاملة: المادة والجرعة وفترة ما قبل الحصاد، بعد مطابقة APC.</li><li>توافر صنف التقاوي لدى المورد المحلي وقت الزراعة.</li></ul><div class="warn">الخريطة الجيوتقنية للمنسوب الجوفي موجودة كملخص جغرافي منشور في الأدلة، لكنها غير مناسبة كقياس مزرعة. بيانات دراسات الحامول وسخا تصف مواقعها التجريبية ولا تعمم على جميع قرى كفر الشيخ.</div><h3>أعمال جمع عامة يمكن أن تستمر</h3><ul><li>استخراج جداول دراسة Basiouny 2020 بعد التحقق اليدوي من النسب والوحدات وربطها بسياقها.</li><li>استكمال تقرير جودة مياه ترعة الدقلت من المقال/المكملات المنشورة.</li><li>توثيق صفحات توصيات ARC/APC الرسمية لكل طريقة زراعة ومرحلة، ووسم المصدر/تاريخ النفاذ.</li><li>استكشاف WaPOR كبيانات ET فعلية مشتقة دون تنزيل صور NDVI الضخمة، مع عدم خلط ET بحجم الري.</li></ul></section>
<section class="page"><h2>8. نصائح التسليم للشخص الذي سيكمل التنظيف</h2><ol><li>ابدأ من <span class="mono">database/agriwater_clean.sqlite</span> و<span class="mono">schema/data_dictionary.csv</span>، لا من ملفات CSV التي أسماؤها OLD أو before.</li><li>استخدم <span class="mono">source_registry.json</span> وعمودي study_id/source_locator/data_status لحصر أصل كل نتيجة.</li><li>حدد هدف الموديل قبل اختيار الصفوف: ETc تقديري؟ مياه مطبقة؟ زمن تشغيل؟ غلة؟ كل هدف يتطلب مصدر تسمية مختلفًا.</li><li>عند بناء مجموعة تعلم، لا تخلط المحطة والخرائط والسيناريوهات مع عينات المزارع تحت نوع سجل واحد. أنشئ split حسب الدراسة/الموسم/الموقع لتجنب تسرب بيانات المصدر.</li><li>وحّد الوحدات بطريقة معلنة، لا تحوّل EC أو تركيزًا أو كمية ماء دون حفظ الوحدة الأصلية والقيمة المحولة والطريقة.</li><li>لا تعوض NULL تلقائيًا، ولا تحذف الصفوف ذات أعمدة لا تنطبق على الدراسة؛ قيم مناسبة قد تكون sparse بطبيعتها في الجداول الطويلة.</li><li>احتفظ بعمود data_status وتاريخ المصدر وإصدار المعادلة لأي قيمة مشتقة.</li><li>قبل توصية فلاحية، أضف مستوى ثقة وشرط إيقاف عند غياب متغير حرج مثل تصرف المضخة.</li></ol><div class="call"><b>تقييم الجاهزية:</b> الحزمة جاهزة لتسليم قاعدة البيانات وشرحها، ولبدء profiling وتنظيف تحليلي منظم. ليست جاهزة لموديل متحقق أو إشعار تشغيل دقيق؛ الهدف الميداني غير موجود.</div></section>
<section class="page"><h2>9. المراجع والملفات</h2><h3>ملفات الحزمة</h3><ul><li><span class="mono">database/agriwater_clean.sqlite</span> - القاعدة المنسوخة والمتحقق من سلامتها.</li><li><span class="mono">schema/schema.sql</span>, <span class="mono">schema/erd_core.mmd</span>, <span class="mono">schema/erd_all_tables.mmd</span>.</li><li><span class="mono">schema/data_dictionary.csv</span>, <span class="mono">schema/column_profile.csv</span>, <span class="mono">schema/foreign_key_relationships.csv</span>.</li><li><span class="mono">metadata/data_quality_issues.csv</span>, <span class="mono">metadata/source_registry.json</span>, <span class="mono">metadata/export_manifest.csv</span>.</li></ul><h3>مصادر رئيسية</h3><ol><li>دراسة الحامول 2020-2021: <span class="source">https://jssae.journals.ekb.eg/article_243275_4763f4aa42c43aa2757cd3f2ece14627.pdf</span></li><li>خريطة كفر الشيخ من 119 جسة، DOI: 10.1515/geo-2022-0495: <span class="source">https://www.degruyterbrill.com/document/doi/10.1515/geo-2022-0495/html</span></li><li>ARC سخا سوبر 300: <span class="source">https://www.arc.sci.eg/products/details/9560</span></li><li>NASA POWER: <span class="source">https://power.larc.nasa.gov/docs/services/api/temporal/daily/</span></li><li>FAO-56 Kc: <span class="source">https://www.fao.org/4/x0490e/x0490e0b.htm</span></li></ol><p class="small">تاريخ اللقطة: {STAMP}. عناوين الأعمدة كاملة في قاموس البيانات؛ يعرض هذا التقرير أبرز العلاقات والمشكلات دون إخفاء السجلات الناقصة أو تحويل الدليل المنشور إلى حقيقة حقلية.</p></section>
</body></html>'''
    (pkg/'reports'/'AgriWater_Clean_Database_Report.html').write_text(html.translate({0x2013:45,0x2014:45,0x2011:45}),encoding='utf-8')
    # Markdown twin keeps the report searchable/editable without a PDF reader.
    md=f'''# تقرير قاعدة البيانات النظيفة - AgriWater\n\n**تاريخ اللقطة:** {STAMP}  \n**قاعدة البيانات:** database/agriwater_clean.sqlite  \n**النطاق:** بيانات الأرز في كفر الشيخ، مرحلة جمع البيانات وقاعدة العلاقات.\n\n## ملخص التنفيذ\n\nأنشئت حزمة منفصلة من قاعدة المشروع الأصلية دون تعديلها. تضم {s['tables']} جدولًا، {s['foreign_keys']} علاقة مفتاح خارجي، {s['column_count']} عمودًا موثقًا و{len(s['empty_tables'])} جداول فارغة. جرى تصدير {s['files_exported']} جدولًا غير فارغ إلى CSV/CSV.GZ. فحص SQLite: {s['integrity']}، ومخالفات المفاتيح الخارجية: {s['foreign_key_errors']}.\n\n## علاقة الجداول الأساسية\n\n- district -> grid_point -> weather_daily / soil_point / soil_awc.\n- season -> regional_stats / crop_calendar / point_season_summary / water_scenario.\n- rice_variety -> reference / field guide / calendar / trial results / water scenarios.\n- literature_study -> trial_result / trial_observation / environmental_measurement / evidence.\n- field -> field_season -> irrigation_event / field_operation؛ جداول سجل الحقول خالية حاليًا.\n\nراجع `schema/erd_all_tables.mmd` و`schema/foreign_key_relationships.csv` لكل العلاقات المستخرجة.\n\n## أعداد المجموعات الرئيسة\n\n- الطقس: {s['weather_daily']:,} صف، {s['weather_points']} نقطة، {s['weather_parameters']} عناصر، {s['weather_start']} إلى {s['weather_end']}؛ NULL={s['weather_nulls']:,}.\n- تربة خرائطية: {s['soil_point']} نقطة؛ AWC={s['soil_awc']}.\n- دراسات: {s['literature_study']}؛ ملاحظات={s['literature_trial_observation']}؛ نتائج رقمية={s['literature_trial_result']}؛ قياسات بيئية منشورة/ملخصات خرائط={s['literature_environmental_measurement']}.\n- أصناف={s['rice_variety']}؛ توصيات={s['agronomy_recommendation']}؛ تقويم={s['crop_calendar']}.\n- تقديرات ETc يومية={s['rice_daily_water_demand']:,}؛ سيناريو v3 حسب الصنف={s['water_scenario_by_variety_v3']:,}.\n- فهرس مشاهد Sentinel={s['sentinel2_scene']:,}؛ قيم NDVI/EVI لم تُحسب (مؤجل).\n\n## مشكلات الأعمدة والجودة\n\nالتفاصيل لكل عمود في `schema/column_profile.csv` و`schema/data_dictionary.csv`. القضايا الرئيسة: نقص 1,292 قيمة طقس، 36/38 نقطة تربة مكتملة، جداول حقول وري فارغة، لا يوجد تصرف مضخة عند الرفع الفعلي، مناوبات الري غير متاحة، 7 قواعد وزارة ثانوية، 5 مراجع حماية نبات بلا جرعة/منتج، مدة سخا سوبر 300 متغيرة حسب تاريخ الزراعة، وإصدارات متعددة لسيناريوهات الماء. النقص في أعمدة الدراسات الطويلة قد يكون طبيعيًا؛ لا تُحذف الأعمدة بسبب null% وحده.\n\n## استخدام البيانات للموديل\n\nالمتاح كسمات: المكان، طقس شبكي، تربة خرائطية، خصائص صنف، تقويم/مرحلة، وبعض سياق المحاصيل السابقة. غير المتاح كأهداف تدريب ميدانية: حجم/عمق ري حقيقي، زمن تشغيل، غلة المزرعة، عمليات فعلية، تحليل التربة الخاص بالحقل، وتصرف المضخة. السيناريوهات المنشورة/المشتقة تصلح للمقارنة والتحقق الحسابي، لا لتدريب نموذج إشرافي كأنها نتائج مزارعين.\n\n## بيانات لا يوفرها الإنترنت على مستوى الحقل\n\nريات كل حقل وغلاته، منسوب الماء الجوفي/ملوحة التربة بإحداثيات ومواعيد رصد زراعية، مناوبات الترع المحلية الحالية، موديل المضخة المركب وأداؤه عند TDH، توافر التقاوي محليًا، وتحليل NPK/EC الخاص بقطعة المستخدم. لا تُملأ هذه القيم بمتوسط المحافظة.\n\n## الملفات\n\n- `schema/schema.sql`: المخطط.\n- `schema/data_dictionary.csv`: تعريف الأعمدة والمفاتيح والقياسات.\n- `schema/foreign_key_relationships.csv`: العلاقات الفعلية.\n- `schema/column_profile.csv`: نسب NULL/النص الفارغ ومجال الأعمدة الرقمية.\n- `metadata/data_quality_issues.csv`: قضايا الجودة والتعامل الموصى به.\n- `metadata/export_manifest.csv`: الملفات المصدرة من قاعدة البيانات.\n'''
    (pkg/'reports'/'AgriWater_Clean_Database_Report.md').write_text(md,encoding='utf-8')

if __name__=='__main__': main()
