import unittest

import pandas as pd

from src.preprocessing import build_preprocessor


class PreprocessingTests(unittest.TestCase):
    def test_numeric_and_categorical_columns_transform(self):
        frame = pd.DataFrame({"temperature": [20.0, None, 24.0], "stage": ["early", "mid", "late"]})
        preprocessor = build_preprocessor(frame)
        transformed = preprocessor.fit_transform(frame)
        self.assertEqual(transformed.shape[0], 3)
        self.assertGreaterEqual(transformed.shape[1], 3)


if __name__ == "__main__":
    unittest.main()
