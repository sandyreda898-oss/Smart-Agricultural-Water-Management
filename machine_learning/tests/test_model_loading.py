import unittest
from pathlib import Path

from src.model_loader import ModelUnavailableError, load_model


class ModelLoadingTests(unittest.TestCase):
    def test_blocked_package_is_not_loaded(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ModelUnavailableError):
            load_model(root)


if __name__ == "__main__":
    unittest.main()
