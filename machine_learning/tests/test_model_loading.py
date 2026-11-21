from pathlib import Path
import unittest

from src.model_loader import ModelUnavailableError, load_model


class ModelLoadingTests(unittest.TestCase):
    def test_model_loader_refuses_to_load_when_model_is_not_available(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ModelUnavailableError):
            load_model(root)


if __name__ == "__main__":
    unittest.main()
