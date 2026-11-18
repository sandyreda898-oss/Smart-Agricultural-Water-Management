import json
import unittest
from pathlib import Path

from src.model_training import run, training_readiness


class IntegrationTests(unittest.TestCase):
    def test_no_labels_produce_blocked_status_and_no_model(self):
        root = Path(__file__).resolve().parents[1]
        frame, reasons = training_readiness(root)
        self.assertIsNone(frame)
        self.assertTrue(reasons)
        self.assertFalse(run(root))
        metrics = json.loads((root / "models" / "model_metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["training_status"], "blocked")
        self.assertIsNone(metrics["metrics"])
        self.assertFalse((root / "models" / "best_model.joblib").exists())


if __name__ == "__main__":
    unittest.main()
