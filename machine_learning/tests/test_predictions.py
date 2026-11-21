from pathlib import Path
import unittest

from src.model_loader import ModelUnavailableError
from src.predict import predict_water_requirement


class PredictionTests(unittest.TestCase):
    def test_prediction_is_disabled_until_reviewed_artifacts_exist(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ModelUnavailableError):
            predict_water_requirement({"temperature": 20}, root)


if __name__ == "__main__":
    unittest.main()
