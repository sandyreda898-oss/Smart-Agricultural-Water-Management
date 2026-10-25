import sqlite3
c = sqlite3.connect("database/agriwater_v2.sqlite")
print("متوسط الطقس 13 يونيو - 15 أكتوبر (كل النقط والسنين):")
for r in c.execute("select parameter, round(avg(value),2), round(min(value),2), round(max(value),2) from weather_daily where substr(obs_date,6,5) between '06-13' and '10-15' and parameter in ('WS2M','ALLSKY_SFC_SW_DWN','T2M_MAX','T2M_MIN','RH2M','PS') group by parameter"):
    print("  ", r)
print("ET0 المحسوب (مم/يوم) لنفس الفترة:")
for r in c.execute("select substr(obs_date,1,4), round(avg(et0_mm_day),2) from rice_daily_water_demand where substr(obs_date,6,5) between '06-13' and '10-15' group by 1"):
    print("  ", r)
