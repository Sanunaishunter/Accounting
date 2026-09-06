"""解析器模組 - 解析半結構化的中文記帳文字"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional

import database as db


class MatchConfidence(Enum):
    """匹配信心度"""
    EXACT = "exact"        # 完全匹配
    PREFIX = "prefix"      # 前綴匹配
    FUZZY = "fuzzy"        # 模糊匹配
    NONE = "none"          # 無法匹配


class ParseStatus(Enum):
    """解析狀態"""
    SUCCESS = "success"       # 成功
    NEEDS_CONFIRM = "confirm" # 待確認
    FAILED = "failed"         # 失敗
    DUPLICATE = "duplicate"   # 重複
    SKIPPED = "skipped"       # 跳過（如「無」）


@dataclass
class ParsedExpense:
    """解析後的支出項目"""
    date: str
    category: str
    person: str
    amount: int
    quantity: float = 1.0
    note: str = ""
    status: ParseStatus = ParseStatus.SUCCESS
    confidence: MatchConfidence = MatchConfidence.EXACT
    original_text: str = ""
    matched_person: Optional[str] = None  # 實際匹配到的人名


@dataclass
class ParsedMemo:
    """解析後的備忘"""
    date: str
    content: str
    has_warning: bool = False  # 是否有 ⚠️
    person: Optional[str] = None  # 關聯人員（由 memo_person_mapping 決定）


@dataclass
class ParseResult:
    """整體解析結果"""
    expenses: list[ParsedExpense] = field(default_factory=list)
    memos: list[ParsedMemo] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)  # 待審核項目
    duplicates: list[ParsedExpense] = field(default_factory=list)


class ExpenseParser:
    """記帳文字解析器"""

    # 日期行正則：數字/數字（星期）或 數字/數字(星期) 或 數字/數字
    DATE_PATTERN = re.compile(r"^(\d{1,2})/(\d{1,2})(?:[（(].*[）)])?$")

    # 類別行：含有 ： 或 :
    CATEGORY_PATTERN = re.compile(r"^(.+?)[：:](.*)$")

    # 類別帶次數：類別*數字
    CATEGORY_QUANTITY_PATTERN = re.compile(r"^(.+?)\*(\d+(?:\.\d+)?)$")

    # 人名帶金額：人名+數字 或 人名＋數字
    PERSON_AMOUNT_PATTERN = re.compile(r"^(.+?)[+＋](\d+)$")

    # 人名帶次數：人名*數字
    PERSON_QUANTITY_PATTERN = re.compile(r"^(.+?)\*(\d+(?:\.\d+)?)$")

    def __init__(self, year: Optional[int] = None):
        """初始化解析器"""
        self.year = year or datetime.now().year
        self.persons_cache: dict[str, dict] = {}
        self.aliases_cache: dict[str, str] = {}  # alias -> name
        self.category_prices: dict[str, int] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """載入人名、價格、備忘關鍵字快取"""
        persons = db.get_all_persons()
        for p in persons:
            self.persons_cache[p["name"]] = p
            if p["aliases"]:
                for alias in p["aliases"].split(","):
                    alias = alias.strip()
                    if alias:
                        self.aliases_cache[alias] = p["name"]
        self.category_prices = db.get_all_category_prices()
        self.memo_person_mapping: dict[str, str] = db.get_memo_person_mappings()
        self.person_proxy_mapping: dict[str, str] = db.get_person_proxy_mappings()

    def reload_cache(self) -> None:
        """重新載入快取"""
        self.persons_cache.clear()
        self.aliases_cache.clear()
        self.memo_person_mapping = {}
        self.person_proxy_mapping = {}
        self._load_cache()

    def parse_text(self, text: str, target_date: Optional[str] = None) -> ParseResult:
        """解析整段文字

        Args:
            text: 記帳文字
            target_date: 目標日期（格式：YYYY-MM-DD），如果提供則忽略文字中的日期行
        """
        result = ParseResult()
        current_date = target_date or ""

        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. 判斷是否為日期行（忽略，使用傳入的 target_date）
            date_match = self.DATE_PATTERN.match(line)
            if date_match:
                # 如果沒有提供 target_date，才從文字解析日期
                if not target_date:
                    month = int(date_match.group(1))
                    day = int(date_match.group(2))
                    current_date = f"{self.year}-{month:02d}-{day:02d}"
                continue

            # 2. 判斷是否為 ⚠️ 備忘
            if "⚠️" in line or "⚠" in line:
                content = line.replace("⚠️", "").replace("⚠", "").strip()
                if content and current_date:
                    # 從 person_proxy 查關鍵字，找到第一個匹配的就設 person
                    matched_person = None
                    for keyword, person in self.person_proxy_mapping.items():
                        if keyword in content:
                            matched_person = person
                            break
                    result.memos.append(ParsedMemo(
                        date=current_date,
                        content=content,
                        has_warning=True,
                        person=matched_person,
                    ))
                continue

            # 3. 判斷是否為類別行
            category_match = self.CATEGORY_PATTERN.match(line)
            if category_match:
                category_part = category_match.group(1).strip()
                content_part = category_match.group(2).strip()

                # 處理「無」的情況
                if content_part == "無" or not content_part:
                    continue

                # 解析類別（可能帶預設次數）
                category, default_qty = self._parse_category_with_quantity(category_part)

                # 確認類別是否有效
                if category not in self.category_prices:
                    # 未知類別，當作備忘處理
                    if current_date:
                        result.memos.append(ParsedMemo(
                            date=current_date,
                            content=line
                        ))
                    continue

                # 解析人員列表
                self._parse_expense_items(
                    content_part, category, default_qty, current_date, line, result
                )
                continue

            # 4. 獨立備忘（以上都不符合）
            if current_date:
                result.memos.append(ParsedMemo(
                    date=current_date,
                    content=line
                ))

        return result

    def _parse_category_with_quantity(self, category_str: str) -> tuple[str, float]:
        """解析類別，可能帶預設次數（如 牛奶*1.5）"""
        match = self.CATEGORY_QUANTITY_PATTERN.match(category_str)
        if match:
            return match.group(1), float(match.group(2))
        return category_str, 1.0

    def _parse_expense_items(
        self,
        content: str,
        category: str,
        default_qty: float,
        date: str,
        source_line: str,
        result: ParseResult
    ) -> None:
        """解析類別行中的人員項目"""
        # 分隔符：頓號、逗號
        items = re.split(r"[、,，]", content)

        for item in items:
            item = item.strip()
            if not item:
                continue

            expense = self._parse_single_item(item, category, default_qty, date, source_line)

            if expense.status == ParseStatus.FAILED:
                result.pending.append({
                    "raw_text": item,
                    "source_line": source_line,
                    "date": date
                })
            elif expense.status == ParseStatus.DUPLICATE:
                result.duplicates.append(expense)
            else:
                result.expenses.append(expense)

    def _parse_single_item(
        self,
        item: str,
        category: str,
        default_qty: float,
        date: str,
        source_line: str
    ) -> ParsedExpense:
        """解析單一人員項目"""
        amount = 0
        quantity = default_qty
        note = ""
        person_text = item

        # 檢查是否帶金額（+數字）
        amount_match = self.PERSON_AMOUNT_PATTERN.match(item)
        if amount_match:
            person_text = amount_match.group(1)
            amount = int(amount_match.group(2))
            note = f"+{amount}"
        else:
            # 嘗試解析「人名數字」格式（無加號），如「阿鵰240」
            extracted = self._extract_person_and_amount(item)
            if extracted:
                person_text, amount = extracted
                note = f"+{amount}"

        # 檢查是否帶次數（*數字）
        qty_match = self.PERSON_QUANTITY_PATTERN.match(person_text)
        if qty_match:
            person_text = qty_match.group(1)
            quantity = float(qty_match.group(2))

        # 匹配人名
        matched_name, confidence = self._match_person(person_text)

        # 計算金額（儲存單價，報表會乘以 quantity）
        if amount == 0:
            amount = self.category_prices.get(category, 0)

        # 判斷狀態
        if confidence == MatchConfidence.NONE:
            status = ParseStatus.FAILED
        elif confidence == MatchConfidence.FUZZY:
            status = ParseStatus.NEEDS_CONFIRM
        else:
            status = ParseStatus.SUCCESS
            # 檢查重複
            if matched_name and db.expense_exists(date, category, matched_name):
                status = ParseStatus.DUPLICATE

        return ParsedExpense(
            date=date,
            category=category,
            person=matched_name or person_text,
            amount=amount,
            quantity=quantity,
            note=note,
            status=status,
            confidence=confidence,
            original_text=item,
            matched_person=matched_name
        )

    def _extract_person_and_amount(self, text: str) -> Optional[tuple[str, int]]:
        """嘗試從「人名數字」格式提取人名和金額

        例如：「阿鵰240」→ (「阿鵰」, 240)
              「牧恩晚餐180」→ (「牧恩晚餐」, 180)，後續前綴匹配會處理
        """
        text = text.strip()

        # 如果是數量格式（人名*數字），不應該在這裡處理
        if self.PERSON_QUANTITY_PATTERN.match(text):
            return None

        # 嘗試找出結尾的數字
        match = re.match(r"^(.+?)(\d+)$", text)
        if not match:
            return None

        potential_name = match.group(1)
        amount = int(match.group(2))

        # 檢查是否能匹配到人名（完全匹配或前綴匹配）
        # 完全匹配
        if potential_name in self.persons_cache or potential_name in self.aliases_cache:
            return potential_name, amount

        # 前綴匹配（例如「阿鵰晚餐」開頭是「阿鵰」）
        for name in self.persons_cache:
            if potential_name.startswith(name):
                return potential_name, amount  # 回傳原始文字，讓 _match_person 處理前綴
        for alias in self.aliases_cache:
            if potential_name.startswith(alias):
                return potential_name, amount

        return None

    def _match_person(self, text: str) -> tuple[Optional[str], MatchConfidence]:
        """匹配人名，回傳 (匹配到的名字, 信心度)"""
        text = text.strip()

        # 1. 完全匹配詞庫
        if text in self.persons_cache:
            return text, MatchConfidence.EXACT

        # 2. 別名完全匹配
        if text in self.aliases_cache:
            return self.aliases_cache[text], MatchConfidence.EXACT

        # 3. 前綴匹配（處理「阿鵰點心」→「阿鵰」）
        for name in self.persons_cache:
            if text.startswith(name):
                return name, MatchConfidence.PREFIX
        for alias, name in self.aliases_cache.items():
            if text.startswith(alias):
                return name, MatchConfidence.PREFIX

        # 4. 模糊匹配（相似度 >= 0.6）
        best_match = None
        best_ratio = 0.0

        all_names = list(self.persons_cache.keys()) + list(self.aliases_cache.keys())
        for name in all_names:
            ratio = SequenceMatcher(None, text, name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = name

        if best_ratio >= 0.6:
            actual_name = self.aliases_cache.get(best_match, best_match)
            return actual_name, MatchConfidence.FUZZY

        # 5. 無法匹配
        return None, MatchConfidence.NONE


def parse_accounting_text(
    text: str,
    target_date: Optional[str] = None,
    year: Optional[int] = None
) -> ParseResult:
    """便捷函式：解析記帳文字

    Args:
        text: 記帳文字
        target_date: 目標日期（格式：YYYY-MM-DD）
        year: 年份（僅在 target_date 未提供時使用）
    """
    parser = ExpenseParser(year)
    return parser.parse_text(text, target_date)
