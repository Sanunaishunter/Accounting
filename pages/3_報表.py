"""報表頁面 - 統計報表與匯出"""
import json
import re
from itertools import groupby
from pathlib import Path

import pandas as pd
import streamlit as st
from datetime import datetime

import database as db
from ui import apply_theme, is_mobile, page_header

MEMO_AMOUNT_RE = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*$')

# ===== 對帳輔助 =====

_HISTORY_DIR = Path(__file__).parent.parent / "History"
_RAW_DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})[（(]?')
_CAT_LINE_RE = re.compile(r'^([^：:]+)[：:](.+)$')
_ITEM_AMT_RE = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*$')
_KNOWN_CATS = {"早餐", "中餐", "晚餐", "牛奶", "點心", "飲料", "文具", "電費"}


def _find_history_file(year: int, month: int) -> Path | None:
    candidate = _HISTORY_DIR / f"…{year}{month:02d}.txt"
    if candidate.exists():
        return candidate
    for f in _HISTORY_DIR.glob("*.txt"):
        if f"{year}{month:02d}" in f.name:
            return f
    return None


def _dedupe_key(existing_items: list, base_key: str) -> str:
    """Append #N suffix if base_key already used, so identical same-day items get unique keys."""
    existing_keys = {it["key"] for it in existing_items}
    key = base_key
    n = 1
    while key in existing_keys:
        n += 1
        key = f"{base_key}#{n}"
    return key


def _parse_history(year: int, month: int, persons: list[str]) -> dict:
    """Parse raw history file → {person: [{date, category, item_text, amount_str, key}]}"""
    path = _find_history_file(year, month)
    if not path:
        return {}

    proxy_mapping: dict[str, str] = db.get_person_proxy_mappings()
    persons_by_len = sorted(persons, key=len, reverse=True)

    result: dict[str, list] = {p: [] for p in persons}
    current_date = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        m = _RAW_DATE_RE.match(line)
        if m:
            current_date = f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            continue

        if not current_date:
            continue

        # ⚠️ 備忘行：不跳過，解析為備忘加項
        if "⚠" in line:
            content = line.replace("⚠️", "").replace("⚠", "").strip()
            if not content:
                continue
            # 先用 person_proxy_mapping（跟 parser 相同邏輯）
            matched = next(
                (person for kw, person in proxy_mapping.items() if kw in content),
                None,
            )
            # fallback：找第一個出現在 content 的人名
            if not matched:
                matched = next(
                    (p for p in persons_by_len if p in content),
                    None,
                )
            if matched and matched in result:
                amt_m = _ITEM_AMT_RE.search(content)
                amount_str = amt_m.group(1) if amt_m else ""
                ikey = _dedupe_key(result[matched], f"{current_date}|⚠️備忘|{content}")
                result[matched].append({
                    "date": current_date,
                    "category": "⚠️備忘",
                    "item_text": content,
                    "amount_str": amount_str,
                    "raw_line": line,
                    "key": ikey,
                })
            continue

        cat_m = _CAT_LINE_RE.match(line)
        if not cat_m:
            continue

        cat_raw = cat_m.group(1).strip()
        content = cat_m.group(2).strip()

        if not content or content == "無":
            continue

        cat = "牛奶" if cat_raw.startswith("牛奶") else cat_raw
        if cat not in _KNOWN_CATS:
            continue

        for item in re.split(r"[、,，]", content):
            item = item.strip()
            if not item or item == "無":
                continue
            # remove *N quantity suffix for person matching
            item_for_match = re.sub(r"\*\d+\.?\d*$", "", item).strip()
            matched = next(
                (p for p in sorted(persons, key=len, reverse=True) if item_for_match.startswith(p)),
                None,
            )
            if matched and matched in result:
                amt_m = _ITEM_AMT_RE.search(item)
                amount_str = f"+{amt_m.group(1)}" if amt_m else ""
                ikey = _dedupe_key(result[matched], f"{current_date}|{cat}|{item}")
                result[matched].append({
                    "date": current_date,
                    "category": cat,
                    "item_text": item,
                    "amount_str": amount_str,
                    "raw_line": line,
                    "key": ikey,
                })

    return result


def _recon_path(year: int, month: int) -> Path:
    return _HISTORY_DIR / f"reconcile_{year}{month:02d}.json"


def _load_recon(year: int, month: int) -> dict:
    p = _recon_path(year, month)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_recon_item(year: int, month: int, person: str, ikey: str, cb_key: str) -> None:
    rkey = f"recon_{year}_{month}"
    state = st.session_state.get(rkey, {})
    state.setdefault(person, {})[ikey] = st.session_state[cb_key]
    st.session_state[rkey] = state
    _recon_path(year, month).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

_KAI = '"LXGW WenKai TC","AR PL UKai TW","BiauKai","Kaiti TC","KaiTi",serif'
_REPORT_CSS = """\
  .report { font-family: "Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif; font-variant-numeric: tabular-nums; font-size: 14px; padding: 1rem 1.25rem 1.1rem; background: #FFF8E2; border: 1px solid #D8BF78; border-radius: 4px; color: #2B2118; max-width: 360px; }
  .report .rp-month { color: #6E5A42; font-size: 12.5px; }
  .report .rp-name { font-family: KAI; font-size: 28px; line-height: 1.25; border-bottom: 1.5px solid #2B2118; padding-bottom: 4px; margin-bottom: 4px; }
  .report h3 { font-size: 15px; margin: 0 0 4px; }
  .report table { width: 100%; border-collapse: collapse; }
  .report td { padding: 5px 6px; border: none; border-bottom: 1px solid #E5D29A; }
  .report td.label { color: #6E5A42; }
  .report .sym { text-align: right; width: 22px; color: #6E5A42; }
  .report .amt { text-align: right; width: 84px; }
  .report .divider td { font-weight: 700; border-bottom: none; padding-top: 7px; }
  .report .section-title { color: #6E5A42; font-size: 12.5px; padding-top: 14px; border-bottom: none; }
  .report .memo-date { width: 40px; color: #6E5A42; white-space: nowrap; }
  .report .memo-who { width: 48px; color: #6E5A42; white-space: nowrap; }
  .report .total-row td { font-weight: 700; font-size: 16px; padding-top: 8px; border-bottom: none; }
  .report .total-row td.amt { border-bottom: 4px double #2B2118; }
  .tooltip-container { position: relative; display: inline-block; cursor: pointer; }
  .tooltip-container .tooltip-text { visibility: hidden; background-color: #1E2A38; color: #fff; text-align: left; border-radius: 4px; padding: 8px 12px; position: absolute; z-index: 1000; left: 105%; top: 50%; transform: translateY(-50%); white-space: nowrap; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
  .tooltip-container:hover .tooltip-text { visibility: visible; }""".replace("KAI", _KAI)


st.set_page_config(page_title="報表", page_icon="📊", layout="wide")
apply_theme()
MOBILE = is_mobile()
GRID = 1 if MOBILE else 3  # 每排幾張卡片
page_header("統計報表", "月報、月份比較、年度統計與費用查詢")

# Tooltip CSS 樣式
st.markdown("""
<style>
.tooltip-container {
    position: relative;
    display: inline-block;
    cursor: pointer;
    padding: 2px 5px;
    border-radius: 4px;
}
.tooltip-container:hover {
    background-color: rgba(128, 133, 149, .22);
}
.tooltip-container .tooltip-text {
    visibility: hidden;
    background-color: #1E2A38;
    color: #fff;
    text-align: left;
    border-radius: 6px;
    padding: 8px 12px;
    position: absolute;
    z-index: 1000;
    left: 105%;
    top: 50%;
    transform: translateY(-50%);
    white-space: nowrap;
    font-size: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
}
.tooltip-container:hover .tooltip-text {
    visibility: visible;
}
@media (max-width: 640px) {
    .tooltip-container .tooltip-text {
        left: auto; right: 0; top: calc(100% + 4px); transform: none;
        white-space: normal; max-width: 60vw;
    }
    .tooltip-text::before { display: none; }
}
.tooltip-text::before {
    content: "";
    position: absolute;
    top: 50%;
    right: 100%;
    margin-top: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: transparent #1E2A38 transparent transparent;
}
</style>
""", unsafe_allow_html=True)
st.markdown(f"<style>{_REPORT_CSS}</style>", unsafe_allow_html=True)

# 中文月份
MONTH_NAMES = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月",
    5: "五月", 6: "六月", 7: "七月", 8: "八月",
    9: "九月", 10: "十月", 11: "十一月", 12: "十二月"
}

# 類別顯示順序和別名
CATEGORY_ORDER = ["早餐", "中餐", "晚餐", "牛奶", "點心", "飲料", "文具"]
CATEGORY_DISPLAY = {
    "早餐": "早餐",
    "中餐": "午餐",
    "晚餐": "晚餐",
    "牛奶": "鮮奶",
    "點心": "點心",
    "飲料": "飲料",
    "文具": "文具"
}


def get_month_name(m: int) -> str:
    """取得中文月份名稱"""
    return MONTH_NAMES.get(m, f"{m}月")


def _build_category_details(person_df: pd.DataFrame) -> dict:
    """Build per-category list of 'M/D: $amt' strings for tooltip display."""
    details = {}
    for cat in CATEGORY_ORDER:
        cat_df = person_df[person_df["category"] == cat]
        if not cat_df.empty:
            rows = []
            for _, row in cat_df.iterrows():
                date_parts = row["date"].split("-")
                display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                rows.append(f"{display_date}: ${row['total']:.0f}")
            details[cat] = rows
    return details


def categorize_memos_by_person(memos: list[dict], person_names: list[str]) -> tuple[dict, list[dict]]:
    """將備忘依人名分類

    Returns:
        (person_memos, uncategorized_memos)
        - person_memos: {人名: [備忘列表]}
        - uncategorized_memos: 無法歸類的備忘列表
    """
    person_memos = {name: [] for name in person_names}
    uncategorized = []

    for memo in memos:
        matched = False
        # 優先用 DB 記錄的 person 欄位（由 memo_person_mapping 決定）
        memo_person = memo.get("person")
        if memo_person and memo_person in person_memos:
            person_memos[memo_person].append(memo)
            matched = True
        else:
            # 退而其次：內容包含人名
            for name in person_names:
                if name in memo["content"]:
                    person_memos[name].append(memo)
                    matched = True
                    break
        if not matched:
            uncategorized.append(memo)

    return person_memos, uncategorized


def _build_card_html(person: str, category_totals: dict, month_label: str,
                     person_memos: list[dict], category_details: dict = None) -> str:
    """生成單人月結報表的 HTML 卡片字串（供頁面渲染與 HTML 匯出共用）"""
    subtotal = sum(category_totals.get(cat, 0) for cat in CATEGORY_ORDER)

    memo_with_amt = []  # (date_str, who, desc, amount)
    memo_no_amt = []    # (date_str, who, desc)
    if person_memos:
        for memo in person_memos:
            date_parts = memo["date"].split("-")
            display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
            who = memo.get("person") or ""
            content = memo["content"]
            m = MEMO_AMOUNT_RE.search(content)
            if m:
                amount = int(float(m.group(1)))
                desc = (content[:m.start()].rstrip() + " " + content[m.end():].lstrip()).strip()
                memo_with_amt.append((display_date, who, desc or content, amount))
            else:
                memo_no_amt.append((display_date, who, content))

    memo_subtotal = sum(amt for _, _, _, amt in memo_with_amt)
    total = subtotal + memo_subtotal

    cat_rows = ""
    for cat in CATEGORY_ORDER:
        amount = category_totals.get(cat, 0)
        display_name = CATEGORY_DISPLAY.get(cat, cat)
        if category_details and category_details.get(cat):
            tip = "<br>".join(category_details[cat])
            amt_cell = f'<span class="tooltip-container">{amount:,.0f}<span class="tooltip-text">{tip}</span></span>'
        else:
            amt_cell = f'{amount:,.0f}'
        cat_rows += f'    <tr><td class="label">{display_name}</td><td class="sym">$</td><td class="amt">{amt_cell}</td></tr>\n'

    memo_amt_table = ""
    if memo_with_amt:
        rows = ""
        for d, w, desc, amt in memo_with_amt:
            sym = "+$" if amt >= 0 else "-$"
            rows += f'    <tr><td class="memo-date">{d}</td><td class="memo-who">{w}</td><td>{desc}</td><td class="sym">{sym}</td><td class="amt">{abs(amt):,.0f}</td></tr>\n'
        sub_sym = "+$" if memo_subtotal >= 0 else "-$"
        rows += f'    <tr class="divider"><td colspan="3">備忘小計</td><td class="sym">{sub_sym}</td><td class="amt">{abs(memo_subtotal):,.0f}</td></tr>\n'
        memo_amt_table = f'\n  <table style="margin-top:1rem">\n    <tr><td colspan="5" class="section-title">備忘加項：</td></tr>\n{rows}  </table>'

    memo_no_amt_table = ""
    if memo_no_amt:
        rows = ""
        for d, w, desc in memo_no_amt:
            rows += f'    <tr><td class="memo-date">{d}</td><td class="memo-who">{w}</td><td colspan="3">{desc}</td></tr>\n'
        memo_no_amt_table = f'\n  <table style="margin-top:1rem">\n    <tr><td colspan="5" class="section-title">無金額備忘：</td></tr>\n{rows}  </table>'

    pending_note = ""
    if memo_no_amt:
        parts = [f"+ {d} {w}{desc}（待補）" for d, w, desc in memo_no_amt]
        pending_note = "；".join(parts)

    return f"""<div class="report">
  <div class="rp-month">{month_label}</div>
  <div class="rp-name">{person}</div>
  <table>
{cat_rows}    <tr class="divider"><td>小計</td><td class="sym">$</td><td class="amt">{subtotal:,.0f}</td></tr>
  </table>{memo_amt_table}{memo_no_amt_table}
  <table style="margin-top:1rem">
    <tr class="total-row"><td>合計</td><td class="sym">$</td><td class="amt">{total:,.0f}</td><td style="color:#5E6D7C;font-size:12.5px;padding-left:12px;border:none">{pending_note}</td></tr>
  </table>
</div>"""


def render_person_card(person: str, person_df: pd.DataFrame, year: int, month: int,
                       manage_mode: bool = False, card_key: str = "",
                       person_memos: list[dict] = None):
    """渲染單人報表卡片（HTML table 格式）"""
    month_label = f"{year} {get_month_name(month)}"

    if person_df.empty:
        category_totals = {}
        category_details = {}
    else:
        category_totals = person_df.groupby("category")["total"].sum().to_dict()
        category_details = _build_category_details(person_df)

    st.markdown(_build_card_html(person, category_totals, month_label, person_memos, category_details),
                unsafe_allow_html=True)

    # 管理模式：刪除支出
    if manage_mode and not person_df.empty:
        with st.expander("🗑️ 刪除記錄"):
            for _, row in person_df.iterrows():
                record_id = row["id"]
                cat_display = CATEGORY_DISPLAY.get(row["category"], row["category"])
                date_short = row["date"].split("-")[2]
                label = f"{date_short}日 {cat_display} ${row['total']:.0f}"
                if st.button(f"❌ {label}", key=f"del_{card_key}_{record_id}"):
                    db.delete_expense(record_id)
                    st.success(f"已刪除：{label}")
                    st.rerun()

    # 管理模式：刪除備忘
    if manage_mode and person_memos:
        with st.expander("🗑️ 刪除備忘"):
            for memo in person_memos:
                date_parts = memo["date"].split("-")
                display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                label = f"{display_date} {memo['content']}"
                if st.button(f"❌ {label}", key=f"del_pmemo_{card_key}_{memo['id']}"):
                    db.delete_memo(memo["id"])
                    st.rerun()


def render_empty_card():
    """渲染空白卡片（佔位）"""
    st.write("")  # 空白佔位


# 功能列：篩選條件（桌面一條橫列；手機收進展開區）
available_years = db.get_expense_years() or [datetime.now().year]

with (st.expander("篩選條件", expanded=True) if MOBILE else st.container(horizontal=True, vertical_alignment="bottom", key="toolbar")):
    year = st.selectbox("年份", options=available_years, width="stretch" if MOBILE else 110)

    # 取得該年份的月份
    available_months = db.get_expense_months(year) if year else []
    if not available_months:
        available_months = list(range(1, 13))

    month = st.selectbox(
        "月份",
        options=available_months,
        format_func=lambda x: f"{x}月",
        width="stretch" if MOBILE else 100,
    )

    report_type = st.segmented_control(
        "報表類型",
        options=["全員月報", "月份比較", "年度統計"],
        default="全員月報",
        key="report_type_sel",
    ) or "全員月報"

    manage_mode = st.toggle("管理模式", value=False, help="開啟後可刪除記錄")


# 取得人員列表
persons = db.get_all_persons()
person_names = [p["name"] for p in persons]

# 取得資料
expenses = db.get_expenses(year=year, month=month)

if report_type == "全員月報":
    # ========== 全員月報：垂直堆疊 ==========

    memos = db.get_memos(year=year, month=month)
    person_memos_dict, uncategorized_memos = categorize_memos_by_person(memos, person_names)

    if not expenses and not memos:
        st.info(f"{year}年{month}月 尚無資料")
    else:
        month_label = f"{year} {get_month_name(month)}"
        df = pd.DataFrame(expenses) if expenses else pd.DataFrame()
        if not df.empty:
            df["total"] = df["amount"] * df["quantity"]

        # 對帳：解析原始歷史檔（每次選月份只解析一次）
        _hist_key = f"raw_hist_{year}_{month}"
        if _hist_key not in st.session_state:
            st.session_state[_hist_key] = _parse_history(year, month, person_names)
        raw_hist = st.session_state[_hist_key]

        # 對帳狀態（從 JSON 載入，每月只載一次）
        _rkey = f"recon_{year}_{month}"
        if _rkey not in st.session_state:
            st.session_state[_rkey] = _load_recon(year, month)

        # DB lookup sets for fast matching
        _db_set = {(e["date"], e["category"], e["person"]) for e in expenses}
        _memo_set = {(m["date"], m["content"]) for m in memos}

        # 還沒對上的歷史項目（資料庫沒有、也沒勾已確認）＝ 你還需要校對的筆數
        _open_total = 0
        for _p in person_names:
            _ps = st.session_state[_rkey].get(_p, {})
            for _it in raw_hist.get(_p, []):
                if _it["category"] == "⚠️備忘":
                    _hit = (_it["date"], _it["item_text"]) in _memo_set
                else:
                    _hit = (_it["date"], _it["category"], _p) in _db_set
                if not _hit and not _ps.get(_it["key"], False):
                    _open_total += 1

        sum1, sum2, sum3, sum4, sum5 = st.columns(5)
        sum1.metric("全體總計", f"${df['total'].sum():,.0f}" if not df.empty else "$0")
        sum2.metric("有支出人數", df["person"].nunique() if not df.empty else 0)
        sum3.metric("支出筆數", len(df))
        sum4.metric("備忘", len(memos))
        sum5.metric("待校對", _open_total, help="History 原文有、資料庫對不上、也還沒勾「已確認」的項目")
        st.html("<div style='height:.8rem'></div>")


        grid_cols = None
        for idx, person in enumerate(person_names):
            if idx % GRID == 0:
                grid_cols = st.columns(GRID)
            with grid_cols[idx % GRID]:
                person_df = df[df["person"] == person] if not df.empty else pd.DataFrame()
                person_memo_list = person_memos_dict.get(person, [])

                category_totals = (
                    person_df.groupby("category")["total"].sum().to_dict()
                    if not person_df.empty else {}
                )
                category_details = _build_category_details(person_df) if not person_df.empty else {}
                card_html = _build_card_html(person, category_totals, month_label, person_memo_list, category_details)
                st.markdown(card_html, unsafe_allow_html=True)

                if manage_mode and not person_df.empty:
                    with st.expander("🗑️ 刪除記錄"):
                        for _, row in person_df.iterrows():
                            record_id = row["id"]
                            cat_display = CATEGORY_DISPLAY.get(row["category"], row["category"])
                            date_short = row["date"].split("-")[2]
                            label = f"{date_short}日 {cat_display} ${row['total']:.0f}"
                            if st.button(f"❌ {label}", key=f"del_monthly_{person}_{record_id}"):
                                db.delete_expense(record_id)
                                st.success(f"已刪除：{label}")
                                st.rerun()

                if manage_mode and person_memo_list:
                    with st.expander("🗑️ 刪除備忘"):
                        for memo in person_memo_list:
                            date_parts = memo["date"].split("-")
                            display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                            label = f"{display_date} {memo['content']}"
                            if st.button(f"❌ {label}", key=f"del_monthly_pmemo_{person}_{memo['id']}"):
                                db.delete_memo(memo["id"])
                                st.rerun()

                single_html = (
                    f'<!DOCTYPE html>\n<html lang="zh-TW">\n<head>\n'
                    f'  <meta charset="utf-8">\n'
                    f'  <title>{month_label} {person}</title>\n'
                    f'  <style>\n    body {{ background: #FBFCF9; color: #1E2A38; font-family: sans-serif; padding: 2rem; }}\n'
                    f'{_REPORT_CSS}\n  </style>\n</head>\n<body>\n{card_html}\n</body>\n</html>'
                )
                st.download_button(
                    label="📄 輸出報表",
                    data=single_html.encode("utf-8"),
                    file_name=f"{year}{month:02d}_{person}.html",
                    mime="text/html",
                    key=f"export_card_{person}",
                )

                # ===== 對帳 expander =====
                person_raw = raw_hist.get(person, [])
                if person_raw:
                    _pstate = st.session_state[_rkey].get(person, {})
                    def _item_in_db(it):
                        if it["category"] == "⚠️備忘":
                            return (it["date"], it["item_text"]) in _memo_set
                        return (it["date"], it["category"], person) in _db_set
                    _auto_match = sum(1 for it in person_raw if _item_in_db(it))
                    _confirmed = sum(1 for it in person_raw if _pstate.get(it["key"], False))
                    _total = len(person_raw)
                    _exp_label = (
                        f"🔍 對帳 {person}　"
                        f"{'✅' if _auto_match == _total else '⚠️'} "
                        f"{_auto_match}/{_total} 自動比對　"
                        f"☑ {_confirmed} 已確認"
                    )
                    with st.expander(_exp_label):
                        for _date, _items_iter in groupby(person_raw, key=lambda x: x["date"]):
                            _items = list(_items_iter)
                            _dp = _date.split("-")
                            st.caption(f"📅 {int(_dp[1])}/{int(_dp[2])}")
                            for _it in _items:
                                _in_db = _item_in_db(_it)
                                _auto_icon = "✅" if _in_db else "🔴"
                                _cat_d = CATEGORY_DISPLAY.get(_it["category"], _it["category"])
                                _cb_label = f"{_auto_icon} {_cat_d} {_it['amount_str']}　`{_it['item_text']}`"
                                _cb_key = f"rcb_{person}_{_it['key']}"
                                if _cb_key not in st.session_state:
                                    st.session_state[_cb_key] = _pstate.get(_it["key"], _in_db)
                                st.checkbox(
                                    _cb_label,
                                    key=_cb_key,
                                    on_change=_save_recon_item,
                                    args=(year, month, person, _it["key"], _cb_key),
                                )
                elif _find_history_file(year, month) is None:
                    with st.expander(f"🔍 對帳 {person}"):
                        st.warning(f"找不到 History/…{year}{month:02d}.txt")

        if df.empty:
            st.info("本月無支出記錄")

        if uncategorized_memos:
            st.divider()
            st.subheader("📝 備忘（未歸類）")
            for memo in uncategorized_memos:
                date_parts = memo["date"].split("-")
                display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                if manage_mode:
                    col_memo, col_del = st.columns([10, 1])
                    with col_memo:
                        st.markdown(f"• **{display_date}** {memo['content']}")
                    with col_del:
                        if st.button("❌", key=f"del_memo_{memo['id']}"):
                            db.delete_memo(memo["id"])
                            st.rerun()
                else:
                    st.markdown(f"• **{display_date}** {memo['content']}")


elif report_type == "月份比較":
    # ========== 月份比較：選擇人員，不同月份並排 ==========

    st.subheader("月份比較")

    # 選擇人員
    selected_person = st.selectbox("選擇人員", options=person_names)

    # 選擇要比較的月份
    compare_months = st.multiselect(
        "選擇月份（可多選）",
        options=list(range(1, 13)),
        default=available_months[:3] if len(available_months) >= 3 else available_months,
        format_func=lambda x: f"{x}月"
    )

    if not compare_months:
        st.warning("請選擇至少一個月份")
    else:
        # 取得全年資料
        yearly_expenses = db.get_expenses(year=year, persons=[selected_person])

        if not yearly_expenses:
            st.info(f"{selected_person} 在 {year} 年尚無資料")
        else:
            yearly_df = pd.DataFrame(yearly_expenses)
            yearly_df["total"] = yearly_df["amount"] * yearly_df["quantity"]
            yearly_df["month"] = pd.to_datetime(yearly_df["date"]).dt.month

            # 按3個月一排顯示
            for i in range(0, len(compare_months), GRID):
                cols = st.columns(GRID)
                batch = compare_months[i:i+GRID]

                for j, col in enumerate(cols):
                    with col:
                        if j < len(batch):
                            m = batch[j]
                            month_df = yearly_df[yearly_df["month"] == m]
                            render_person_card(selected_person, month_df, year, m,
                                             manage_mode, f"compare_{selected_person}_{m}")
                        else:
                            render_empty_card()

                st.divider()

            # 總計表格
            st.subheader("月份總計比較")
            summary_data = []
            for m in compare_months:
                month_df = yearly_df[yearly_df["month"] == m]
                total = month_df["total"].sum() if not month_df.empty else 0
                summary_data.append({
                    "月份": get_month_name(m),
                    "總計": float(total)
                })
            st.dataframe(
                pd.DataFrame(summary_data),
                hide_index=True,
                width='stretch',
                column_config={"總計": st.column_config.NumberColumn(format="$%.0f")},
            )


elif report_type == "年度統計":
    # ========== 年度統計：全年加總 ==========

    st.subheader(f"{year} 年度統計")

    # 取得全年資料
    yearly_expenses = db.get_expenses(year=year)

    # 取得全年備忘並分類
    yearly_memos = db.get_memos(year=year)
    yearly_person_memos, yearly_uncategorized = categorize_memos_by_person(yearly_memos, person_names)

    if not yearly_expenses:
        st.info(f"{year} 年尚無資料")
    else:
        yearly_df = pd.DataFrame(yearly_expenses)
        yearly_df["total"] = yearly_df["amount"] * yearly_df["quantity"]

        # 每人全年總計，3人一排
        for i in range(0, len(person_names), GRID):
            cols = st.columns(GRID)
            batch = person_names[i:i+GRID]

            for j, col in enumerate(cols):
                with col:
                    if j < len(batch):
                        person = batch[j]
                        person_df = yearly_df[yearly_df["person"] == person]
                        with st.container(border=True):

                            # 標題
                            st.markdown(f"**{year} 全年**")
                            st.markdown(f"### {person}")
                            st.write("")

                            # 按類別統計
                            if person_df.empty:
                                category_totals = {}
                                category_details = {}
                            else:
                                category_totals = person_df.groupby("category")["total"].sum().to_dict()
                                # 建立每個類別的明細（按月份分組）
                                category_details = {}
                                for cat in CATEGORY_ORDER:
                                    cat_df = person_df[person_df["category"] == cat]
                                    if not cat_df.empty:
                                        details = []
                                        for _, row in cat_df.iterrows():
                                            date_parts = row["date"].split("-")
                                            display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                                            details.append(f"{display_date}: ${row['total']:.0f}")
                                        category_details[cat] = details

                            total_amount = 0
                            rows_html = ""
                            for cat in CATEGORY_ORDER:
                                amount = category_totals.get(cat, 0)
                                display_name = CATEGORY_DISPLAY.get(cat, cat)

                                if cat in category_details and category_details[cat]:
                                    # 有明細，顯示 tooltip
                                    tooltip_content = "<br>".join(category_details[cat])
                                    amt_cell = (f'<span class="tooltip-container">{amount:,.0f}'
                                                f'<span class="tooltip-text">{tooltip_content}</span></span>')
                                else:
                                    amt_cell = f"{amount:,.0f}"
                                rows_html += (f'<tr><td>{display_name}</td><td class="sym">$</td>'
                                              f'<td class="amt">{amt_cell}</td></tr>')
                                total_amount += amount

                            st.markdown(
                                f'<div class="report flat"><table>{rows_html}'
                                f'<tr class="total-row"><td>合計</td><td class="sym">$</td>'
                                f'<td class="amt">{total_amount:,.0f}</td></tr></table></div>',
                                unsafe_allow_html=True,
                            )

                            # 管理模式：顯示刪除選項
                            if manage_mode and not person_df.empty:
                                with st.expander("🗑️ 刪除記錄"):
                                    for _, row in person_df.iterrows():
                                        record_id = row["id"]
                                        cat_display = CATEGORY_DISPLAY.get(row["category"], row["category"])
                                        date_parts = row["date"].split("-")
                                        date_short = f"{int(date_parts[1])}/{int(date_parts[2])}"
                                        label = f"{date_short} {cat_display} ${row['total']:.0f}"
                                        if st.button(f"❌ {label}", key=f"del_yearly_{person}_{record_id}"):
                                            db.delete_expense(record_id)
                                            st.success(f"已刪除：{label}")
                                            st.rerun()

                            # 顯示該人員相關的備忘
                            p_memos = yearly_person_memos.get(person, [])
                            if p_memos:
                                st.write("")
                                st.caption("📝 備忘")
                                for memo in p_memos:
                                    date_parts = memo["date"].split("-")
                                    display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                                    if manage_mode:
                                        col_memo, col_del = st.columns([8, 1])
                                        with col_memo:
                                            st.markdown(f"<small>• {display_date} {memo['content']}</small>",
                                                      unsafe_allow_html=True)
                                        with col_del:
                                            if st.button("❌", key=f"del_ypmemo_{person}_{memo['id']}"):
                                                db.delete_memo(memo["id"])
                                                st.rerun()
                                    else:
                                        st.markdown(f"<small>• {display_date} {memo['content']}</small>",
                                                  unsafe_allow_html=True)
                    else:
                        render_empty_card()

            st.divider()

        # 全體年度總計
        grand_total = yearly_df["total"].sum()
        st.metric("全年總計", f"${grand_total:,.0f}")

        # 月份趨勢
        st.subheader("月度趨勢")
        yearly_df["month"] = pd.to_datetime(yearly_df["date"]).dt.month
        monthly_totals = yearly_df.groupby("month")["total"].sum()

        # 確保12個月都有
        full_months = pd.Series(index=range(1, 13), data=0)
        for m, v in monthly_totals.items():
            full_months[m] = v
        full_months.index = [get_month_name(i) for i in full_months.index]

        st.bar_chart(full_months)

        # 全年備忘（只顯示無法歸類的）
        if yearly_uncategorized:
            st.divider()
            st.subheader("📝 全年備忘（未歸類）")
            for memo in yearly_uncategorized:
                date_parts = memo["date"].split("-")
                display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"

                if manage_mode:
                    col_memo, col_del = st.columns([10, 1])
                    with col_memo:
                        st.markdown(f"• **{display_date}** {memo['content']}")
                    with col_del:
                        if st.button("❌", key=f"del_yearly_memo_{memo['id']}"):
                            db.delete_memo(memo["id"])
                            st.rerun()
                else:
                    st.markdown(f"• **{display_date}** {memo['content']}")


# ========== 查詢功能 ==========

st.divider()
st.subheader("🔍 費用查詢")

with st.expander("展開查詢", expanded=False):
    query_col1, query_col2, query_col3 = st.columns(3)

    with query_col1:
        query_person = st.selectbox(
            "人員",
            options=["全部"] + person_names,
            key="query_person"
        )

    with query_col2:
        query_category = st.selectbox(
            "類別",
            options=["全部"] + CATEGORY_ORDER,
            key="query_category"
        )

    with query_col3:
        query_amount = st.number_input(
            "金額（0=不限）",
            min_value=0,
            value=0,
            step=10,
            key="query_amount"
        )

    if st.button("查詢", key="do_query"):
        # 取得所有資料
        all_expenses = db.get_expenses(year=year)
        if all_expenses:
            query_df = pd.DataFrame(all_expenses)
            query_df["total"] = query_df["amount"] * query_df["quantity"]

            # 篩選
            if query_person != "全部":
                query_df = query_df[query_df["person"] == query_person]
            if query_category != "全部":
                query_df = query_df[query_df["category"] == query_category]
            if query_amount > 0:
                query_df = query_df[query_df["total"] == query_amount]

            if query_df.empty:
                st.warning("查無資料")
            else:
                st.success(f"找到 {len(query_df)} 筆記錄")

                # 顯示結果
                result_df = query_df.copy()
                result_df["類別"] = result_df["category"].map(lambda c: CATEGORY_DISPLAY.get(c, c))
                result_df = result_df.sort_values("date").rename(
                    columns={"date": "日期", "person": "人員", "amount": "單價", "quantity": "數量", "total": "小計"}
                )[["日期", "人員", "類別", "單價", "數量", "小計"]]
                st.dataframe(
                    result_df,
                    hide_index=True,
                    width='stretch',
                    column_config={
                        "單價": st.column_config.NumberColumn(format="$%d"),
                        "數量": st.column_config.NumberColumn(format="%g"),
                        "小計": st.column_config.NumberColumn(format="$%.0f"),
                    },
                )
        else:
            st.info("該年度無資料")


# ========== 匯出功能 ==========

st.divider()
st.subheader("匯出資料")

# 取得當前篩選的資料
if report_type == "年度統計":
    export_expenses = db.get_expenses(year=year)
else:
    export_expenses = db.get_expenses(year=year, month=month)

if export_expenses:
    export_df = pd.DataFrame(export_expenses)
    export_df["total"] = export_df["amount"] * export_df["quantity"]

    col1, col2 = st.columns(2)

    with col1:
        # CSV 匯出
        csv = export_df.to_csv(index=False, encoding="utf-8-sig")
        filename = f"expenses_{year}_{'all' if report_type == '年度統計' else month}.csv"
        st.download_button(
            label="📥 匯出 CSV",
            data=csv,
            file_name=filename,
            mime="text/csv"
        )

    with col2:
        # HTML 報表
        if report_type == "年度統計":
            export_memos = db.get_memos(year=year)
            month_label = f"{year} 全年"
        else:
            export_memos = db.get_memos(year=year, month=month)
            month_label = f"{year} {get_month_name(month)}"
        export_person_memos, export_uncategorized_memos = categorize_memos_by_person(export_memos, person_names)

        card_htmls = []
        for person in person_names:
            person_df = export_df[export_df["person"] == person]
            person_memo_list = export_person_memos.get(person, [])
            if not person_df.empty or person_memo_list:
                category_totals = (
                    person_df.groupby("category")["total"].sum().to_dict()
                    if not person_df.empty else {}
                )
                category_details = _build_category_details(person_df) if not person_df.empty else {}
                card_htmls.append(_build_card_html(person, category_totals, month_label, person_memo_list, category_details))

        if export_uncategorized_memos:
            rows = ""
            for memo in export_uncategorized_memos:
                date_parts = memo["date"].split("-")
                d = f"{int(date_parts[1])}/{int(date_parts[2])}"
                who = memo.get("person") or ""
                rows += f'    <tr><td class="memo-date">{d}</td><td class="memo-who">{who}</td><td colspan="3">{memo["content"]}</td></tr>\n'
            card_htmls.append(
                f'<div class="report">\n  <div class="rp-name">備忘（未歸類）</div>\n  <table>\n{rows}  </table>\n</div>'
            )

        report_css = _REPORT_CSS

        cards_html = "\n".join(f'<div class="card-wrap">{c}</div>' for c in card_htmls)
        full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8">
  <title>{month_label} 月結報表</title>
  <style>
    body {{ background: #FBFCF9; color: #1E2A38; font-family: sans-serif; padding: 2rem; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 1.5rem; }}
    .card-wrap {{ flex: 0 0 280px; }}
{report_css}
  </style>
</head>
<body>
  <h1>{month_label} 月結報表</h1>
  <div class="cards">
    {cards_html}
  </div>
</body>
</html>"""

        filename = f"report_{year}_{'all' if report_type == '年度統計' else month}.html"
        st.download_button(
            label="📄 匯出 HTML 報表",
            data=full_html.encode("utf-8"),
            file_name=filename,
            mime="text/html"
        )
