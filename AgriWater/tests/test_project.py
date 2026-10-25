import json
import unittest
from pathlib import Path
from datetime import date
from src.collector import date_chunks, CONFIG, ROOT

class CollectorTests(unittest.TestCase):
    def test_config_dates_valid(self):
        start = date.fromisoformat(CONFIG["date_range"]["start"])
        end = date.fromisoformat(CONFIG["date_range"]["end"])
        self.assertLessEqual(start, end)

    def test_date_chunks_contiguous(self):
        chunks = list(date_chunks("2020-01-01", "2020-12-31", 90))
        self.assertEqual(chunks[0][0], date(2020, 1, 1))
        self.assertEqual(chunks[-1][1], date(2020, 12, 31))
        for i in range(1, len(chunks)):
            from datetime import timedelta
            self.assertEqual(chunks[i-1][1] + timedelta(days=1), chunks[i][0])

    def test_required_files_exist(self):
        for name in ("config.json", "source_registry.json", "requirements.txt", "RUN_COLLECTOR.bat"):
            self.assertTrue((ROOT / name).exists(), name)

if __name__ == "__main__":
    unittest.main()
