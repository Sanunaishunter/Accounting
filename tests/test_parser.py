"""parser.py 的測試：人名＋類別的獨立行（用暫存資料庫，不碰真實資料）"""
import tempfile
import unittest
from pathlib import Path

import database as db
from parser import ExpenseParser, MatchConfidence, ParseStatus


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


class VariantAndTypoNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        StandalonePersonCategoryLines.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        StandalonePersonCategoryLines.tearDownClass.__func__(cls)

    def match(self, text):
        return ExpenseParser(2026)._match_person(text)

    def test_variant_characters_need_confirm(self):
        for text, person in [("詠恩", "咏恩"), ("紫題點心", "紫緹"), ("紫提", "紫緹")]:
            self.assertEqual(self.match(text), (person, MatchConfidence.FUZZY), text)

    def test_one_wrong_character_needs_confirm(self):
        self.assertEqual(self.match("泰楨點心"), ("泰禎", MatchConfidence.FUZZY))

    def test_exact_and_prefix_unchanged(self):
        self.assertEqual(self.match("阿鵰"), ("阿鵰", MatchConfidence.EXACT))
        self.assertEqual(self.match("阿鵰點心"), ("阿鵰", MatchConfidence.PREFIX))

    def test_unrelated_text_still_fails(self):
        self.assertEqual(self.match("共四杯"), (None, MatchConfidence.NONE))

    def test_fuzzy_goes_to_pending_not_dropped(self):
        r = ExpenseParser(2026).parse_text("飲料：紫提飲料+1600", target_date="2026-10-22")
        self.assertEqual(r.expenses, [])
        self.assertEqual([p["raw_text"] for p in r.pending], ["紫提飲料+1600"])

    def test_typo_name_with_bare_amount_keeps_amount(self):
        r = ExpenseParser(2026).parse_text("飲料：紫題飲料240", target_date="2026-10-22")
        self.assertEqual([p["raw_text"] for p in r.pending], ["紫題飲料240"])

    def test_clean_person_text_strips_amount_qty_category(self):
        p = ExpenseParser(2026)
        for raw, expected in [
            ("紫提飲料+1600（優格）", "紫提"), ("泰楨點心+70", "泰楨"), ("阿鵰*2", "阿鵰"),
            ("紫題飲料240", "紫題"), ("阿鵰", "阿鵰"), ("點心", "點心"),
        ]:
            self.assertEqual(p.clean_person_text(raw), expected, raw)

    def test_suggest_person(self):
        p = ExpenseParser(2026)
        self.assertEqual(p.suggest_person("紫提飲料+1600（優格）"), "紫緹")
        self.assertEqual(p.suggest_person("詠恩"), "咏恩")
        self.assertIsNone(p.suggest_person("共四杯"))


if __name__ == "__main__":
    unittest.main()
