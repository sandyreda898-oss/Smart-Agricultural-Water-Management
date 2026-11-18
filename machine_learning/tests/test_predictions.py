import unittest
from pathlib import Path

from src.model_loader import ModelUnavailableError
from src.predict import predict_water_requirement


class PredictionTests(unittest.TestCase):
    def test_prediction_is_unavailable_without_approved_model(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ModelUnavailableError):
            predict_water_requirement({"diurnal_temp_range_c": 10.0}, root)


if __name__ == "__main__":
    unittest.main()
