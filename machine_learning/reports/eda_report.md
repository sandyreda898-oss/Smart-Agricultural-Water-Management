# Exploratory data analysis report

## Scope

- Rows in joined seasonal feature table: 266.
- Numeric feature columns summarized: 18.
- Target-related correlations and target plots were not produced: current water values are calculated estimates, not verified measured irrigation.
- Input features are seasonal summaries and therefore retrospective; they are not available at planting time.

## Numeric summary

```text
                                       count      mean      std       min       25%       50%       75%       max
tmin_c_season_mean                     266.0   22.5294   1.2750   20.3323   21.2073   23.2041   23.5895   24.0279
tmax_c_season_mean                     266.0   32.5613   3.2436   29.0743   29.7077   30.2199   36.1702   37.5357
diurnal_temp_range_c                   266.0   10.0319   4.4664    5.5726    6.1370    6.7544   14.8776   16.5237
tmean_proxy_c_season_mean              266.0   27.5453   1.0421   26.1281   26.6191   27.0150   28.5764   29.5696
relative_humidity_pct_season_mean      266.0   60.9504   5.5953   53.0197   54.6986   64.5427   65.9797   67.4287
vpd_proxy_season_kpa                   266.0    1.4518   0.2961    1.1219    1.1891    1.2653    1.7772    1.9410
wind_speed_m_s_season_mean             266.0    3.6151   0.5657    2.7414    3.0486    4.0065    4.1135    4.1949
solar_radiation_mj_m2_day_season_mean  266.0   24.0686   0.3571   23.4187   23.7782   24.1714   24.2833   24.6977
pressure_kpa_season_mean               266.0  101.0719   0.0469  100.9721  101.0439  101.0753  101.0988  101.1613
rainfall_season_mm                     266.0   17.0789  23.6015    1.0800    2.6800    8.2600   16.9200   84.2800
sand_pct                               252.0   39.6667  10.6592   21.0000   40.0000   43.0000   50.0000   50.0000
silt_pct                               252.0   28.8333   5.6755   24.0000   26.0000   26.0000   28.0000   40.0000
clay_pct                               252.0   31.5000  12.9626   20.0000   24.0000   26.5000   29.0000   55.0000
bulk                                   252.0    1.4667   0.1100    1.3300    1.3300    1.4500    1.4900    1.6400
organic_carbon                         252.0    0.7154   0.1039    0.6200    0.6200    0.6860    0.6950    0.9010
ph_water                               252.0    8.0528   0.4326    7.3000    8.1000    8.1000    8.5000    8.5000
latitude                               266.0   31.2944   0.1539   31.0129   31.2129   31.3129   31.4129   31.5129
longitude                              266.0   30.9496   0.2083   30.5180   30.8180   30.9180   31.1180   31.3180
```

## Interpretation and modeling implications

The seasonal summary joins NASA POWER gridded weather to mapped soil and project points. Nearby points may share the same weather series. Any future evaluation must hold out field/farm/experiment groups and account for seasons; random-row splitting would overstate generalization.
No causal interpretation should be made from correlations. Soil profiles are mapped proxies, not individual-field tests.

## Figures

- `visualizations/distributions/feature_distributions.png`
- `visualizations/correlations/feature_correlations.png`
