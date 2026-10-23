"""normalizer.py 的測試（案例與 Accounting_web/tests/normalizer.test.js 相同）"""
import unittest

from normalizer import check, normalize_text

NAMES = ["傑森", "泰禎", "阿鵰", "紫緹", "米媽媽", "台北媽媽"]

# 每筆案例：(名稱, 輸入, [(原文, 改後), ...])；把替換套用在輸入上就得到預期輸出
CASES = [
    (
        "米媽媽：單價*數量與無金額",
        """9/30（三）
⚠️米媽媽小卷190*20⚠️
⚠️米媽媽蛋塔

早餐：無

點心：傑森點心+140、紫緹點心+140

晚餐：傑森*2、阿鵰、紫緹
晚餐 ：泰禎

牛奶*1.5:泰禎、阿鵰、傑森、紫緹
牛奶*3:無""",
        [
            ("⚠️米媽媽小卷190*20⚠️", "⚠️米媽媽小卷(190*20)+$3800⚠️"),
            ("⚠️米媽媽蛋塔", "⚠️米媽媽蛋塔+$0000⚠️"),
        ],
    ),
    (
        "跨日期備忘與晚餐非人名",
        """9/25、9/26
傑森直接+5000

9/26（六）

早餐：傑森

中餐：傑森+1000

飲料：傑森飲料+200

晚餐：傑森烤肉裕毛屋棉花田
晚餐 ：無

牛奶*1.5:無""",
        [
            ("傑森直接+5000", "⚠️ 9/25、9/26傑森直接+$5000⚠️"),
            ("9/26（六）\n\n", "9/26（六）\n\n⚠️傑森烤肉裕毛屋棉花田+$0000⚠️\n"),
            ("晚餐：傑森烤肉裕毛屋棉花田", "晚餐："),
        ],
    ),
    (
        "晚餐非人名拉出（單日）",
        """9/25（五）

早餐：傑森

點心：傑森點心+100

晚餐：傑森烤肉裕毛屋棉花田
晚餐 ：無""",
        [
            ("9/25（五）\n\n", "9/25（五）\n\n⚠️傑森烤肉裕毛屋棉花田+$0000⚠️\n"),
            ("晚餐：傑森烤肉裕毛屋棉花田", "晚餐："),
        ],
    ),
    (
        "無金額、多人同行、算式",
        """9/24（四）
⚠️泰禎家雞蛋4盒⚠️
⚠️泰禎夜市+200、傑森夜市+200-230、紫緹夜市+330⚠️

點心：泰禎點心+40

晚餐：阿鵰、紫緹、傑森*2""",
        [
            ("⚠️泰禎家雞蛋4盒⚠️", "⚠️泰禎家雞蛋4盒+$0000⚠️"),
            ("⚠️泰禎夜市+200、傑森夜市+200-230、紫緹夜市+330⚠️", "⚠️泰禎夜市+$200⚠️\n⚠️傑森夜市(+200-230)+$-30⚠️\n⚠️紫緹夜市+$330⚠️"),
        ],
    ),
    (
        "米媽媽三久、全部的科學玩具",
        """9/23（三）
⚠️米媽媽三久280*6⚠️
⚠️全部的科學玩具⚠️

點心：紫緹點心+60、阿鵰點心+60""",
        [
            ("⚠️米媽媽三久280*6⚠️", "⚠️米媽媽三久(280*6)+$1680⚠️"),
            ("⚠️全部的科學玩具⚠️", "⚠️全部的科學玩具+$0000⚠️"),
        ],
    ),
    (
        "前綴逗號與尾端數字金額",
        """9/21（一）
⚠️紫緹家，柚子*1⚠️
⚠️阿鵰多益1200⚠️

文具：傑森文具+50、阿鵰文具+50、紫緹文具+50""",
        [
            ("⚠️紫緹家，柚子*1⚠️", "⚠️紫緹家柚子*1+$0000⚠️"),
            ("⚠️阿鵰多益1200⚠️", "⚠️阿鵰多益1200+$1200⚠️"),
        ],
    ),
    (
        "一大串拆成一品項一行、電費拉出",
        """9/20（日）
⚠️傑森家，柚子*2、泡芙、全民英檢*2、蛋糕1700、牛排3000⚠️

早餐：紫緹、阿鵰、傑森

電費：全部九月+500

文具：紫緹文具+750""",
        [
            ("⚠️傑森家，柚子*2、泡芙、全民英檢*2、蛋糕1700、牛排3000⚠️", "⚠️傑森家柚子*2+$0000⚠️\n⚠️傑森家泡芙+$0000⚠️\n⚠️傑森家全民英檢*2+$0000⚠️\n⚠️傑森家蛋糕1700+$1700⚠️\n⚠️傑森家牛排3000+$3000⚠️\n⚠️全部九月電費+$500⚠️"),
            ("電費：全部九月+500", "電費："),
        ],
    ),
    (
        "名稱前綴套用到所有品項",
        """9/11（五）
⚠️台北媽媽水餃、牛奶、蛋黃酥⚠️
⚠️米媽媽、泰禎，好市多⚠️

點心：傑森點心+120""",
        [
            ("⚠️台北媽媽水餃、牛奶、蛋黃酥⚠️", "⚠️台北媽媽水餃+$0000⚠️\n⚠️台北媽媽牛奶+$0000⚠️\n⚠️台北媽媽蛋黃酥+$0000⚠️"),
            ("⚠️米媽媽、泰禎，好市多⚠️", "⚠️米媽媽好市多+$0000⚠️\n⚠️泰禎好市多+$0000⚠️"),
        ],
    ),
    (
        "逗號當分項、錯字人名保留",
        """9/9（三）
⚠️全部的坤哥費用，還有洋蔥圈⚠️

飲料：傑森飲料+250、紫提飲料+185、泰禎飲料+100""",
        [
            ("⚠️全部的坤哥費用，還有洋蔥圈⚠️", "⚠️全部的坤哥費用+$0000⚠️\n⚠️洋蔥圈+$0000⚠️"),
        ],
    ),
    (
        "+後接文字是分項、+後接數字是金額",
        """9/2（三）
⚠️米媽媽太陽餅一大一小+蛋黃酥、好市多、小泡芙、水餃、義美⚠️
⚠️泰禎家好市多⚠️
⚠️還書+100⚠️

點心：傑森點心+110""",
        [
            ("⚠️米媽媽太陽餅一大一小+蛋黃酥、好市多、小泡芙、水餃、義美⚠️", "⚠️米媽媽太陽餅一大一小+$0000⚠️\n⚠️米媽媽蛋黃酥+$0000⚠️\n⚠️米媽媽好市多+$0000⚠️\n⚠️米媽媽小泡芙+$0000⚠️\n⚠️米媽媽水餃+$0000⚠️\n⚠️米媽媽義美+$0000⚠️"),
            ("⚠️泰禎家好市多⚠️", "⚠️泰禎家好市多+$0000⚠️"),
            ("⚠️還書+100⚠️", "⚠️還書+$100⚠️"),
        ],
    ),
]


def expected_output(text, edits):
    for src, dst in edits:
        assert src in text, f"測試資料錯誤：找不到「{src}」"
        text = text.replace(src, dst, 1)
    return text


class NormalizeCases(unittest.TestCase):
    def test_cases(self):
        for name, text, edits in CASES:
            with self.subTest(name):
                r = normalize_text(text, names=NAMES)
                self.assertEqual(r.text, expected_output(text, edits))
                self.assertEqual(r.problems, [])

    def test_idempotent(self):
        for name, text, _ in CASES:
            with self.subTest(name):
                once = normalize_text(text, names=NAMES).text
                twice = normalize_text(once, names=NAMES)
                self.assertEqual(twice.text, once)
                self.assertEqual(twice.problems, [])


class Checker(unittest.TestCase):
    def test_catches_lost_chars_and_amount_mismatch(self):
        text = "9/1（一）\n⚠️還書+100⚠️"
        self.assertTrue(normalize_text(text, names=NAMES).ok)
        self.assertFalse(check(text, "9/1（一）\n⚠️還+$100⚠️")[0])
        self.assertFalse(check(text, "9/1（一）\n⚠️還書+$200⚠️")[0])

    def test_unknown_category_is_left_alone_and_flagged(self):
        text = "9/1（一）\n奇怪類別：傑森烤肉"
        r = normalize_text(text, names=NAMES)
        self.assertEqual(r.text, text)
        self.assertTrue(any("未知類別" in f for f in r.flags))

    def test_extra_categories_are_recognised(self):
        text = "9/1（一）\n交通：傑森交通+30"
        r = normalize_text(text, names=NAMES, categories=["交通"])
        self.assertEqual(r.text, text)
        self.assertEqual(r.flags, [])

    def test_fullwidth_digits_are_not_amounts(self):
        # Python 的 \d 會吃全形數字，這裡確認只認 ASCII 數字
        r = normalize_text("9/1（一）\n⚠️書１２０⚠️", names=NAMES)
        self.assertEqual(r.text, "9/1（一）\n⚠️書１２０+$0000⚠️")


if __name__ == "__main__":
    unittest.main()
