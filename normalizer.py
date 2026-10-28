"""normalizer.py - 把原始記帳文字整理成 parser 好處理的格式

移植自 Accounting_web 的 assets/js/normalizer.js。

只動兩種內容，其餘行原樣保留：
 1. ⚠️ 備忘行（含日期行底下的獨立備忘）
 2. 類別行裡「不是人名」的項目（例如 晚餐：傑森烤肉裕毛屋棉花田），會被拉成 ⚠️ 備忘

⚠️ 行規則：
 - 以 、 或 「+文字」 拆成一個品項一行；名稱前綴（米媽媽、泰禎，好市多）與品項交叉組合
 - 每項金額統一寫成 +$金額；沒有金額補 +$0000
 - 算式保留在括號內：單價*數量 -> (190*20)+$3800、+200-230 -> (+200-230)+$-30

純函式，不碰資料庫與 Streamlit。
"""
import ast
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

DEFAULT_CATEGORIES = ["早餐", "中餐", "晚餐", "點心", "電費", "飲料", "文具", "牛奶"]
WARN = "⚠️"

# JavaScript 的 \s / trim() 所涵蓋的空白（與 Python 預設不同），保持與網頁版同樣的切行結果
_WS = " \t\n\v\f\r\xa0  -     　﻿"
_WS_CHARS = (
    " \t\n\v\f\r\xa0     　﻿"
    + "".join(chr(c) for c in range(0x2000, 0x200B))
)

# 只認 ASCII 數字（Python 的 \d 會吃全形與其他文字的數字）
_NUM = r"[0-9]+(?:\.[0-9]+)?"

_DATE_LINE = re.compile(r"[0-9]{1,2}/[0-9]{1,2}(?:[、,，][0-9]{1,2}/[0-9]{1,2})*(?:[（(].*[）)])?")
_DATE_PREFIX = re.compile(r"[0-9]{1,2}/[0-9]{1,2}(?:、[0-9]{1,2}/[0-9]{1,2})*")
_CATEGORY_LINE = re.compile(r"(.+?)([：:])(.*)")
_SPLIT_PLUS_TEXT = re.compile(r"[+＋](?![0-9$＄])")
_CONNECTOR = re.compile(r"^(還有|以及)")
_QTY_SUFFIX = re.compile(r"\*" + _NUM + r"\Z")
_TRAILING_DIGITS = re.compile(r"[0-9]+\Z")
_TRAILING_AMOUNT = re.compile(r"[+＋][$＄]?[0-9.+\-*/]+\Z")

_RE_NORMALIZED = re.compile(r"(.*?)(\+[$＄]-?" + _NUM + r")")
_RE_PLUS_EXPR = re.compile(r"(.*?)[+＋](" + _NUM + r"(?:[+\-*/]" + _NUM + r")+)")
_RE_PLUS_AMOUNT = re.compile(r"(.*?)[+＋](" + _NUM + r")")
_RE_PRODUCT = re.compile(r"(.*?)(" + _NUM + r"(?:\*" + _NUM + r")+)")
_RE_TRAILING_NUM = re.compile(r"(.*[^0-9.{ws}*+\-])({num})".format(ws=_WS, num=_NUM))

_RE_SUM_PAREN = re.compile(r"\([^)]*\)")
_RE_SUM_AMOUNT = re.compile(r"[+＋][$＄]?(-?" + _NUM + r"(?:[+\-*/]" + _NUM + r")*)")
_RE_WARN_LINE_FORMAT = re.compile(WARN + r" ?.+[+][$＄]-?" + _NUM + WARN)
_RE_CJK = re.compile("[一-鿿]")
_RE_EXPR_CHARS = re.compile(r"[0-9.+\-*/{ws}]+".format(ws=_WS))
# JS strict mode 不接受 007、0800 這類前導 0 的數字，算式視為無法計算
_RE_LEADING_ZERO = re.compile(r"(?<![0-9.])0[0-9]")


def _trim(s: str) -> str:
    return s.strip(_WS_CHARS)


def _fmt(v: float) -> str:
    """數字轉字串（整數不帶小數點，與網頁版 String(Number) 一致）"""
    if v == int(v):
        return str(int(v))
    return repr(v)


def _is_warn_line(line: str) -> bool:
    return "⚠" in line


def _strip_warn(line: str) -> str:
    return _trim(line.replace("⚠️", "").replace("⚠", ""))


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval_node(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return a / b
    raise ValueError("unsupported expression")


def _eval_expr(expr: str) -> Optional[float]:
    """只允許數字與 + - * / 的四則運算；算不出來回傳 None"""
    if not _RE_EXPR_CHARS.fullmatch(expr) or _RE_LEADING_ZERO.search(expr):
        return None
    try:
        v = _eval_node(ast.parse(expr.strip(), mode="eval"))
    except (ValueError, SyntaxError, OverflowError, ZeroDivisionError, RecursionError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    if abs(v) >= 1e21:  # JS toFixed 在這個量級以上不處理，且 Decimal 會超出精度
        return v
    # 與 JS toFixed(2) 相同：小數第 2 位四捨五入（遠離 0），不用銀行家捨入
    return float(Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# 電費不是支出類別，整理時會被拉成備忘，所以不拿來判斷「人名＋類別」
_NON_EXPENSE_CATEGORIES = {"電費"}

_RE_PERSON_CATEGORY = re.compile(
    r"(.+?)((?:\*" + _NUM + r")?(?:[+＋][$＄]?" + _NUM + r")?)"
)


def infer_person_category(line: str, persons, categories) -> Optional[tuple[str, str]]:
    """獨立行若是「人名＋類別（＋*次數）（＋金額）」，回傳 (類別, 項目)，否則 None

    例：「阿鵰點心+70」→ ("點心", "阿鵰點心+70")；「傑森晚餐*2」→ ("晚餐", "傑森晚餐*2")。
    persons 只放真正的人員與別名（代理關鍵字不算），categories 為已知類別。
    項目裡的金額一律寫成 +數字（parser 不吃 +$）。
    """
    text = _trim(line)
    if not text or "：" in text or ":" in text or _is_warn_line(text):
        return None
    m = _RE_PERSON_CATEGORY.fullmatch(text)
    if not m:
        return None
    head, tail = m[1], m[2]
    for name in sorted({p for p in persons if p}, key=len, reverse=True):
        if head.startswith(name) and head[len(name):] in categories:
            qty = re.search(r"\*" + _NUM, tail)
            amount = re.search(r"[+＋][$＄]?(" + _NUM + ")", tail)
            item = head + (qty[0] if qty else "") + (f"+{amount[1]}" if amount else "")
            return head[len(name):], item
    return None


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    return a[i + 1:] == b[i:] if len(a) > len(b) else a[i:] == b[i + 1:]


@dataclass
class NormalizeResult:
    text: str
    flags: list = field(default_factory=list)
    derived: list = field(default_factory=list)
    ok: bool = True
    problems: list = field(default_factory=list)


class Normalizer:
    def __init__(self, names=None, categories=None, persons=None):
        self.categories = list(categories) if categories else list(DEFAULT_CATEGORIES)
        # 只有真正的人員與別名；有給才會把「阿鵰點心+70」這類獨立行補成類別行
        self.persons = [p for p in dict.fromkeys(persons or []) if p]
        unique = list(dict.fromkeys(n for n in (names or []) if n))
        self.names = sorted(unique, key=len, reverse=True)
        self.flags: list[str] = []
        self.derived: list[dict] = []

    def _flag(self, msg: str) -> None:
        self.flags.append(msg)

    # ---- 名稱判斷 ----

    def leading_name(self, s: str) -> str:
        """開頭的已知名稱（含「家」後綴）；沒有則回傳 ''"""
        for n in self.names:
            if s.startswith(n + "家"):
                return n + "家"
            if s.startswith(n):
                return n
        return ""

    def is_known_token(self, token: str) -> bool:
        if token in self.names:
            return True
        return token.endswith("家") and token[:-1] in self.names

    # ---- 單一品項：算出 名稱 + 金額 ----

    def format_item(self, item: str, name_suffix: str = "") -> str:
        item = _trim(item)

        def add_suffix(name: str) -> str:
            return name + name_suffix if name_suffix and name_suffix not in name else name

        # 已整理過：... +$金額
        m = _RE_NORMALIZED.fullmatch(item)
        if m:
            return add_suffix(m[1]) + m[2].replace("＄", "$").replace("＋", "+")
        # +算式：+200-230
        m = _RE_PLUS_EXPR.fullmatch(item)
        if m:
            v = _eval_expr("+" + m[2])
            if v is not None:
                self._flag(f"「{item}」含算式，已寫成 (+{m[2]})+${_fmt(v)}，請確認")
                return f"{add_suffix(m[1])}(+{m[2]})+${_fmt(v)}"
        # +金額
        m = _RE_PLUS_AMOUNT.fullmatch(item)
        if m:
            return f"{add_suffix(m[1])}+${m[2]}"
        # 單價*數量：190*20
        m = _RE_PRODUCT.fullmatch(item)
        if m and m[1]:
            v = _eval_expr(m[2])
            if v is not None:
                self.derived.append({"kind": "product", "item": item, "value": v})
                return f"{add_suffix(m[1])}({m[2]})+${_fmt(v)}"
        # 名稱後面直接接數字：多益1200
        m = _RE_TRAILING_NUM.fullmatch(item)
        if m:
            self.derived.append({"kind": "trailing", "item": item, "value": float(m[2])})
            self._flag(f"「{item}」尾端數字視為金額 +${m[2]}，請確認")
            return f"{add_suffix(m[1] + m[2])}+${m[2]}"
        return f"{add_suffix(item)}+$0000"

    # ---- ⚠️ 內容：拆項、交叉組合 ----

    def split_items(self, text: str) -> list[str]:
        parts = []
        for seg in re.split(r"[、,，]", text):
            parts.extend(_SPLIT_PLUS_TEXT.split(seg))
        items = (_trim(_CONNECTOR.sub("", _trim(s), count=1)) for s in parts)
        return [s for s in items if s]

    def memo_items(self, content: str) -> list[str]:
        m = re.search(r"[，,]", content)
        if m:
            tokens = [_trim(t) for t in content[:m.start()].split("、")]
            if tokens and all(self.is_known_token(t) for t in tokens):
                items = self.split_items(content[m.start() + 1:])
                return [t + it for t in tokens for it in items]
        items = self.split_items(content)
        if len(items) > 1:
            prefix = self.leading_name(items[0])
            if prefix and len(items[0]) > len(prefix):
                return [
                    prefix + it if i > 0 and not self.leading_name(it) else it
                    for i, it in enumerate(items)
                ]
        return items

    def memo_lines(self, content: str, date_prefix: str = "", name_suffix: str = "") -> list[str]:
        """一行 ⚠️ 備忘（或獨立備忘）-> 多行 ⚠️"""
        content = _strip_warn(content)
        prefix = date_prefix or ""
        dm = _DATE_PREFIX.match(content)
        if dm:
            prefix = dm.group(0)
            content = content[dm.end():]
        sep = f" {prefix}" if prefix else ""
        items = self.memo_items(content)
        if not items:
            return [f"{WARN}{sep}{content}{WARN}"]
        return [f"{WARN}{sep}{self.format_item(it, name_suffix)}{WARN}" for it in items]

    # ---- 類別行：把非人名項目拉出來 ----

    def classify_person_item(self, item: str, base: str) -> str:
        core = _trim(item)
        while True:
            prev = core
            core = _TRAILING_AMOUNT.sub("", core, count=1)
            core = _QTY_SUFFIX.sub("", core, count=1)
            if core == prev:
                break
        core = _TRAILING_DIGITS.sub("", core, count=1) or core

        allowed = {"", base, *self.categories}
        for n in self.names:
            if core.startswith(n) and core[len(n):] in allowed:
                return "person"
        bare = core
        for c in self.categories:
            if c and bare.endswith(c):
                bare = bare[:-len(c)]
        if len(bare) >= 2:
            for n in self.names:
                if len(n) >= 2 and bare != n and _edit_distance_at_most_one(bare, n):
                    self._flag(f"「{item}」疑似「{n}」的錯字，保留在原位")
                    return "person"
        return "other"

    def category_line(self, line: str, m: re.Match) -> tuple[str, list[str]]:
        base = _trim(_QTY_SUFFIX.sub("", _trim(m[1]), count=1))
        if base not in self.categories:
            self._flag(f"未知類別「{base}」，該行未處理")
            return line, []
        content = _trim(m[3])
        if not content or content == "無":
            return line, []

        kept, memos = [], []
        for item in (_trim(s) for s in re.split(r"[、,，]", content)):
            if not item:
                continue
            if self.classify_person_item(item, base) == "person":
                kept.append(item)
            else:
                memos.extend(self.memo_lines(item, "", "電費" if base == "電費" else ""))
        if not memos:
            return line, []
        return f"{_trim(m[1])}{m[2]}{'、'.join(kept)}", memos

    # ---- 主流程 ----

    def normalize(self, text: str) -> tuple[str, list[str], list[dict]]:
        self.flags = []
        self.derived = []
        lines = re.sub(r"\r\n?", "\n", str(text)).split("\n")
        out: list[str] = []
        block: Optional[dict] = None  # {insert_at, prefix, fresh}

        def add_memos(memos: list[str]) -> None:
            if not memos:
                return
            out[block["insert_at"]:block["insert_at"]] = memos
            block["insert_at"] += len(memos)

        for line_no, raw_line in enumerate(lines):
            line = _trim(raw_line)

            if _DATE_LINE.fullmatch(line):
                multi = re.search(r"[、,，]", line) is not None
                block = {
                    "insert_at": len(out) + 1,
                    "prefix": _trim(re.sub(r"[（(].*[）)]\Z", "", line, count=1)) if multi else "",
                    "fresh": True,
                }
                out.append(raw_line)
                continue
            if block is None:
                out.append(raw_line)
                continue
            if not line:
                out.append(raw_line)
                if block["fresh"] and block["insert_at"] == len(out) - 1:
                    block["insert_at"] = len(out)
                continue

            adjacent = block["insert_at"] == len(out)
            block["fresh"] = False

            if _is_warn_line(line):
                out.extend(self.memo_lines(line, block["prefix"]))
                if adjacent:
                    block["insert_at"] = len(out)
                continue

            m = _CATEGORY_LINE.fullmatch(line)
            if m:
                new_line, memos = self.category_line(line, m)
                out.append(raw_line if new_line == line else new_line)
                add_memos(memos)
                continue

            # 「人名＋類別」的獨立行（如 阿鵰點心+70）-> 補上類別前綴
            inferred = None
            if self.persons:
                expense_cats = [c for c in self.categories if c not in _NON_EXPENSE_CATEGORIES]
                inferred = infer_person_category(line, self.persons, expense_cats)
            if inferred:
                category, item = inferred
                out.append(f"{category}：{item}")
                self.derived.append({"kind": "category", "item": line, "category": category, "line": line_no})
                self._flag(f"獨立行「{line}」判斷為「{category}：{item}」，請確認")
                continue

            # 不屬於任何類別的獨立行 -> 備忘
            self._flag(f"獨立行「{line}」轉為 ⚠️ 備忘")
            out.extend(self.memo_lines(line, block["prefix"]))
            if adjacent:
                block["insert_at"] = len(out)

        return "\n".join(out), self.flags, self.derived


# ===== 獨立檢查：用不同於轉換器的角度驗證輸出 =====

def _sum_amounts(text: str) -> float:
    total = 0.0
    for raw in text.split("\n"):
        if _DATE_LINE.fullmatch(_trim(raw)):
            continue
        line = _RE_SUM_PAREN.sub("", raw)
        for m in _RE_SUM_AMOUNT.finditer(line):
            v = _eval_expr(m[1] if m[1].startswith("-") else "+" + m[1])
            if v is not None:
                total += v
    return total


def _cjk_chars(text: str) -> dict[str, None]:
    """依首次出現順序保留的字集合"""
    return dict.fromkeys(_RE_CJK.findall(re.sub(r"還有|以及", "", text)))


def check(input_text: str, output: str, derived=None, categories=None) -> tuple[bool, list[str]]:
    """回傳 (是否通過, 問題清單)"""
    categories = list(categories) if categories else DEFAULT_CATEGORIES
    problems: list[str] = []
    in_lines = [_trim(s) for s in re.sub(r"\r\n?", "\n", str(input_text)).split("\n")]
    out_lines = [_trim(s) for s in str(output).split("\n")]

    def seq(lines, pick):
        return "|".join(x for x in map(pick, lines) if x)

    def date_of(l):
        return l if _DATE_LINE.fullmatch(l) else ""

    if seq(in_lines, date_of) != seq(out_lines, date_of):
        problems.append("日期行與原文不一致")

    inferred_cat = {d["line"]: d["category"] for d in (derived or []) if d.get("kind") == "category"}

    def cat_of(l):
        if _is_warn_line(l):
            return ""
        m = _CATEGORY_LINE.fullmatch(l)
        if not m:
            return ""
        base = _trim(_QTY_SUFFIX.sub("", _trim(m[1]), count=1))
        return base if base in categories else ""

    in_cats = "|".join(x for x in (inferred_cat.get(i) or cat_of(l) for i, l in enumerate(in_lines)) if x)
    if in_cats != seq(out_lines, cat_of):
        problems.append("類別行的數量或順序與原文不一致")

    for l in out_lines:
        if _is_warn_line(l) and not _RE_WARN_LINE_FORMAT.fullmatch(l):
            problems.append(f"⚠️ 行格式不符：{l}")

    out_chars = _cjk_chars(output)
    lost = [c for c in _cjk_chars(input_text) if c not in out_chars]
    if lost:
        problems.append(f"原文的字在輸出中消失：{''.join(lost)}")

    derived = derived or []
    derived_sum = sum(d["value"] for d in derived if "value" in d)
    out_sum, in_sum = _sum_amounts(output), _sum_amounts(input_text)
    if abs(out_sum - in_sum - derived_sum) > 0.001:
        problems.append(f"金額合計不符：輸入 {_fmt(in_sum)} + 推算 {_fmt(derived_sum)} ≠ 輸出 {_fmt(out_sum)}")

    for d in derived:
        if d["kind"] == "trailing" and _fmt(d["value"]) not in input_text:
            problems.append(f"推算金額 {_fmt(d['value'])} 在原文中找不到")

    return not problems, problems


def normalize_text(text: str, names=None, categories=None, persons=None) -> NormalizeResult:
    """整理記帳文字並自動檢查。

    names: 已知人名（含別名、代理關鍵字）；categories: 已知類別（會與預設類別合併使用者傳入的值）
    persons: 只有真正的人員與別名；有給的話，「阿鵰點心+70」這類獨立行會補成「點心：阿鵰點心+70」
    """
    n = Normalizer(names=names, categories=categories, persons=persons)
    out, flags, derived = n.normalize(text)
    ok, problems = check(text, out, derived, n.categories)
    return NormalizeResult(text=out, flags=flags, derived=derived, ok=ok, problems=problems)


# ===== 給輸入頁用：依日期拆格、單日整理 =====

PREAMBLE_TITLE = "（日期行之前）"


def split_days(text: str) -> list[dict]:
    """依日期行把整段文字切成一天一格：[{"title": 日期行, "text": 含日期行的該天文字}]

    第一個日期行之前若有內容，會放在標題為 PREAMBLE_TITLE 的第一格，避免資料遺失。
    每格頭尾的空行會被去掉；格與格之間用空行串回去，與原文在解析上等價。
    """
    cells: list[list] = []  # [title, [lines]]
    for raw in re.sub(r"\r\n?", "\n", str(text)).split("\n"):
        line = _trim(raw)
        if _DATE_LINE.fullmatch(line):
            cells.append([line, [raw]])
        elif cells:
            cells[-1][1].append(raw)
        elif line:
            cells.append([PREAMBLE_TITLE, [raw]])

    result = []
    for title, lines in cells:
        while lines and not _trim(lines[0]):
            lines.pop(0)
        while lines and not _trim(lines[-1]):
            lines.pop()
        result.append({"title": title, "text": "\n".join(lines)})
    return result


def normalize_day(text: str, header: str, names=None, categories=None, persons=None) -> NormalizeResult:
    """整理「單日」文字。文字沒有日期行時，暫時補上 header 讓整理器能運作，輸出再拿掉。"""
    first = next((_trim(l) for l in str(text).split("\n") if _trim(l)), "")
    if _DATE_LINE.fullmatch(first):
        return normalize_text(text, names=names, categories=categories, persons=persons)
    result = normalize_text(f"{header}\n{text}", names=names, categories=categories, persons=persons)
    result.text = result.text.split("\n", 1)[1] if "\n" in result.text else ""
    return result
