import unittest

from src.input_validation import validate_frame


class InputValidationTests(unittest.TestCase):
    def test_input_validation_refuses_blocked_schema(self):
        schema = {"training_status": "blocked", "features": []}
        with self.assertRaisesRegex(ValueError, "disabled"):
            validate_frame({"temperature": 20}, schema)


if __name__ == "__main__":
    unittest.main()
