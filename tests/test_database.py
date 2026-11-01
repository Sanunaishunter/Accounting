"""database.py 的測試：整天刪除（用暫存資料庫，不碰真實資料）"""
import tempfile
import unittest
from pathlib import Path

import database as db


class DeleteDayAll(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig
        self._tmp.cleanup()

    def test_removes_everything_for_that_day_only(self):
        db.add_expense("2026-10-22", "點心", "阿鵰", 70, 1, "")
        db.add_memo("2026-10-22", "x", None)
        db.add_pending_review("阿鵰", "阿鵰", "2026-10-22")
        db.save_day_input("2026-10-22", "raw", "magic", True)
        db.add_expense("2026-10-23", "點心", "阿鵰", 70, 1, "")
        db.save_day_input("2026-10-23", "raw", "magic", True)

        counts = db.delete_day_all("2026-10-22")

        self.assertEqual(counts, {"expenses": 1, "memos": 1, "pending": 1, "saved_input": 1})
        self.assertEqual(db.get_expenses_by_date("2026-10-22"), [])
        self.assertIsNone(db.get_day_input("2026-10-22"))
        self.assertEqual(len(db.get_expenses_by_date("2026-10-23")), 1)
        self.assertIsNotNone(db.get_day_input("2026-10-23"))


class DayOff(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig
        self._tmp.cleanup()

    def test_mark_and_unmark(self):
        db.set_day_off("2026-09-05", True)
        db.set_day_off("2026-09-05", True)  # 重複標注不會出錯
        db.set_day_off("2026-10-05", True)
        self.assertEqual(db.get_day_off_days(2026, 9), {5})
        db.set_day_off("2026-09-05", False)
        self.assertEqual(db.get_day_off_days(2026, 9), set())
        self.assertEqual(db.get_day_off_days(2026, 10), {5})


if __name__ == "__main__":
    unittest.main()
