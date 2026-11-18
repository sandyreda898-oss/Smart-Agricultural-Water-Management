import unittest

import pandas as pd

from src.feature_engineering import engineer_features


class FeatureEngineeringTests(unittest.TestCase):
    def test_creates_retrospective_features_without_target(self):
        frame = pd.DataFrame({
            "tmax_c_season_mean": [32.0], "tmin_c_season_mean": [22.0],
            "relative_humidity_pct_season_mean": [60.0], "rainfall_season_mm": [30.0],
            "clay_pct": [40.0], "sand_pct": [30.0], "awc_smu_mm_per_m": [120.0],
        })
        result = engineer_features(frame)
        self.assertAlmostEqual(result.loc[0, "diurnal_temp_range_c"], 10.0)
        self.assertIn("vpd_proxy_season_kpa", result)
        self.assertIn("season_aridity_index", result)
        self.assertIn("soil_water_retention_index_mm_per_m", result)
        self.assertNotIn("total_irrigation_m3_per_feddan", result)


if __name__ == "__main__":
    unittest.main()
