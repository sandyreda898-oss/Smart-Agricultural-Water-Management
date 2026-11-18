import unittest
from pathlib import Path

from src.input_validation import validate_frame, validate_input


class InputValidationTests(unittest.TestCase):
    def test_accepts_schema_order_and_warns_outside_range(self):
        schema = {"training_status": "ready", "features": ["x"],
                  "feature_ranges": {"x": {"min": 0, "max": 10}}}
        frame, warnings = validate_frame({"x": 12.0}, schema)
        self.assertEqual(frame.columns.tolist(), ["x"])
        self.assertEqual(len(warnings), 1)

    def test_missing_column_is_rejected(self):
        schema = {"training_status": "ready", "features": ["x"]}
        with self.assertRaises(ValueError):
            validate_frame({"other": 1}, schema)

    def test_current_package_schema_blocks_prediction(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ValueError):
            validate_input({"diurnal_temp_range_c": 10.0}, root)


if __name__ == "__main__":
    unittest.main()
