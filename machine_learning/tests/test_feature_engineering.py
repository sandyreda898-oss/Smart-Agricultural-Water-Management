import unittest

import pandas as pd

from src.feature_engineering import engineer_features, select_candidate_features


class FeatureEngineeringTests(unittest.TestCase):
    def test_engineer_features_creates_transparent_weather_derivatives(self):
        frame = pd.DataFrame({
            "tmax_c_season_mean": [30.0], "tmin_c_season_mean": [20.0],
            "relative_humidity_pct_season_mean": [50.0], "rainfall_season_mm": [40.0],
        })
        result = engineer_features(frame)
        self.assertEqual(result.loc[0, "diurnal_temp_range_c"], 10.0)
        self.assertEqual(result.loc[0, "tmean_proxy_c_season_mean"], 25.0)
        self.assertGreater(result.loc[0, "vpd_proxy_season_kpa"], 0)
        self.assertNotIn("estimated_etc_season_mm", result.columns)

    def test_candidate_feature_selection_rejects_target_leakage_and_empty_schema(self):
        frame = pd.DataFrame({"temperature": [20.0], "estimated_etc_season_mm": [100.0]})
        with self.assertRaisesRegex(ValueError, "No features"):
            select_candidate_features(frame, [])
        with self.assertRaisesRegex(ValueError, "leakage"):
            select_candidate_features(frame, ["estimated_etc_season_mm"])


if __name__ == "__main__":
    unittest.main()
