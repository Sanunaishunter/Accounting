"""輸入頁用：找出某一天的原始資料

找的順序：手機傳來的原文（raw_inputs）→ History/ 底下該月的原始檔。
都只讀不寫；「已儲存」的版本在 database.get_day_input。
"""
import re
from datetime import datetime
from pathlib import Path

import database as db
from normalizer import split_days

_HISTORY_DIR = Path(__file__).parent / "History"
_MD = re.compile(r"(\d{1,2})/(\d{1,2})")


def _title_dates(title: str) -> set[tuple[int, int]]:
    """日期行 -> {(月, 日)}；日期行可能是「5/1、5/2（五）」"""
    head = re.split(r"[（(]", title)[0]
    return {(int(m), int(d)) for m, d in _MD.findall(head)}


def _raw_year(created_at: str, month: int, day: int) -> int:
    """原文只有月/日，年份用傳來的時間推：日期還沒到就是去年"""
    try:
        t = datetime.fromisoformat(created_at)
    except ValueError:
        return datetime.now().year
    return t.year - 1 if (month, day) > (t.month, t.day) else t.year


def raw_input_days(year: int, month: int, limit: int = 500) -> dict[int, str]:
    """手機傳來的原文裡，屬於 year/month 的每一天：{日: 原文}（同一天取最新的）"""
    found: dict[int, str] = {}
    for r in db.get_recent_raw_inputs(limit):  # 新的在前
        for cell in split_days(r["text"]):
            for m, d in _title_dates(cell["title"]):
                if m == month and d not in found and _raw_year(r["created_at"], m, d) == year:
                    found[d] = cell["text"]
    return found


def _history_file(year: int, month: int) -> Path | None:
    for f in sorted(_HISTORY_DIR.glob(f"*{year}{month:02d}.txt")):
        return f
    return None


def find_raw(year: int, month: int, day: int) -> tuple[str, str] | None:
    """找某天的原始資料，回傳（文字, 來源說明）；找不到回傳 None"""
    text = raw_input_days(year, month).get(day)
    if text:
        return text, "手機傳來的原文"
    path = _history_file(year, month)
    if path:
        for cell in split_days(path.read_text(encoding="utf-8")):
            if (month, day) in _title_dates(cell["title"]):
                return cell["text"], f"History/{path.name}"
    return None
