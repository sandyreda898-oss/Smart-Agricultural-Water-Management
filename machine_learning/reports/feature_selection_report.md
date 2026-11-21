# Feature selection report

**Status: descriptive candidate features only. Supervised selection is blocked because no verified field-measured target exists.**

No target correlation, model feature importance, or supervised selector was computed.

| Candidate feature | Unit | Definition | Availability / limitation |
|---|---|---|---|
| `tmin_c_season_mean` | degC | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `tmax_c_season_mean` | degC | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `diurnal_temp_range_c` | degC | Seasonal mean daily max minus min temperature; retrospective. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `tmean_proxy_c_season_mean` | degC | Proxy: average of seasonal maximum and minimum means. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `relative_humidity_pct_season_mean` | % | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `vpd_proxy_season_kpa` | kPa | Vapor-pressure-deficit proxy based on seasonal mean temperature and humidity. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `wind_speed_m_s_season_mean` | m/s | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `solar_radiation_mj_m2_day_season_mean` | MJ/m2/day | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `pressure_kpa_season_mean` | kPa | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `rainfall_season_mm` | mm/season | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `sand_pct` | % | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `silt_pct` | % | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `clay_pct` | % | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `bulk` | g/cm3 (source metadata; verify) | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `organic_carbon` | % (source metadata; verify) | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `ph_water` | pH | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `latitude` | degrees north | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |
| `longitude` | degrees east | Source table field; review source metadata. | Seasonal aggregates are retrospective; mapped soil is coarse and not field-specific. |

Do not use seasonal weather summaries for a prediction made before that season ends. Do not use ET0, ETc, water scenarios, or any quantity derived from the target as a feature.
