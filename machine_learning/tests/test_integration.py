import json
from pathlib import Path
import unittest

from src.model_training import training_readiness


class IntegrationTests(unittest.TestCase):
    def test_integrated_release_state_is_blocked_without_field_labels(self):
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / "models" / "model_metadata.json").read_text(encoding="utf-8"))
        frame, reasons, _ = training_readiness(root)
        self.assertEqual(metadata["training_status"], "blocked")
        self.assertIsNone(frame)
        self.assertTrue(reasons)
        self.assertFalse((root / "models" / "best_model.joblib").exists())


if __name__ == "__main__":
    unittest.main()
