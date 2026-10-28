"""parser.py 的測試：人名＋類別的獨立行（用暫存資料庫，不碰真實資料）"""
import tempfile
import unittest
from pathlib import Path

import database as db
from parser import ExpenseParser, ParseStatus


class StandalonePersonCategoryLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._orig = db.DB_PATH
        db.DB_PATH = Path(cls._tmp.name) / "test.db"
        db.init_db()  # 預設人員含 阿鵰、泰禎、傑森；預設類別含 點心(0)、晚餐；預設代理關鍵字含 米媽媽

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls._orig
        cls._tmp.cleanup()

    def parse(self, text):
        return ExpenseParser(2026).parse_text(text, target_date="2026-10-22")

    def test_person_plus_category_becomes_expense(self):
        r = self.parse("阿鵰點心+70\n泰禎點心+70")
        self.assertEqual(
            [(e.category, e.person, e.amount, e.quantity, e.status) for e in r.expenses],
            [("點心", "阿鵰", 70, 1.0, ParseStatus.SUCCESS), ("點心", "泰禎", 70, 1.0, ParseStatus.SUCCESS)],
        )
        self.assertEqual((r.pending, r.memos), ([], []))

    def test_quantity_and_default_price(self):
        r = self.parse("傑森晚餐*2")
        self.assertEqual([(e.category, e.person, e.quantity, e.amount) for e in r.expenses], [("晚餐", "傑森", 2.0, 150)])

    def test_other_standalone_lines_are_still_memos(self):
        r = self.parse("傑森直接+5000\n米媽媽點心+70\n阿鵰點心120")
        self.assertEqual(r.expenses, [])
        self.assertEqual([m.content for m in r.memos], ["傑森直接+5000", "米媽媽點心+70", "阿鵰點心120"])

    def test_category_lines_unchanged(self):
        r = self.parse("點心：阿鵰點心+70、泰禎點心+70")
        self.assertEqual([(e.person, e.amount) for e in r.expenses], [("阿鵰", 70), ("泰禎", 70)])


if __name__ == "__main__":
    unittest.main()
