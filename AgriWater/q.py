import sqlite3
c = sqlite3.connect("database/agriwater_v2.sqlite")
print("فئات الرشح (عدد النقط):")
for r in c.execute("select seepage_class, count(distinct point_id) from water_scenario_by_variety_clay group by 1"):
    print("  ", r)
