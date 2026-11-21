import unittest

import numpy as np
import pandas as pd

from src.data_cleaning import _trim_strings
from src.preprocessing import build_preprocessor


class DataPreprocessingTests(unittest.TestCase):
    def test_trim_strings_preserves_rows_and_normalizes_text(self):
        frame = pd.DataFrame({"name": ["  rice   A ", None], "value": [1, 2]})
        cleaned, changed = _trim_strings(frame)
        self.assertEqual(len(cleaned), len(frame))
        self.assertEqual(cleaned.loc[0, "name"], "rice A")
        self.assertTrue(pd.isna(cleaned.loc[1, "name"]))
        self.assertEqual(changed, 1)

    def test_preprocessor_fits_on_train_and_handles_unknown_category(self):
        train = pd.DataFrame({"temperature": [20.0, np.nan, 24.0], "variety": ["A", "B", "A"]})
        transform = build_preprocessor(train, ["temperature", "variety"])
        train_out = transform.fit_transform(train)
        new_out = transform.transform(pd.DataFrame({"temperature": [22.0], "variety": ["unseen"]}))
        self.assertEqual(train_out.shape[1], new_out.shape[1])
        self.assertTrue(np.isfinite(new_out).all())


if __name__ == "__main__":
    unittest.main()
