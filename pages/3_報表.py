"""報表頁面 - 統計報表與匯出"""
import json
import re
from itertools import groupby
from pathlib import Path

import pandas as pd
import streamlit as st
from datetime import datetime

import database as db

MEMO_AMOUNT_RE = re.compile(r'[+＋$＄]\s*[$＄]?\s*(\d+(?:\.\d+)?)')

# ===== 對帳輔助 =====

_HISTORY_DIR = Path(__file__).parent.parent / "History"
_RAW_DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})[（(]')
_CAT_LINE_RE = re.compile(r'^([^：:]+)[：:](.+)$')
_ITEM_AMT_RE = re.compile(r'[+＋](\d+)')
_KNOWN_CATS = {"早餐", "中餐", "晚餐", "牛奶", "點心", "飲料", "文具", "電費"}


def _find_history_file(year: int, month: int) -> Path | None:
    candidate = _HISTORY_DIR / f"…{year}{month:02d}.txt"
    if candidate.exists():
        return candidate
    for f in _HISTORY_DIR.glob("*.txt"):
        if f"{year}{month:02d}" in f.name:
            return f
    return None


def _parse_history(year: int, month: int, persons: list[str]) -> dict:
    """Parse raw history file → {person: [{date, category, item_text, amount_str, key}]}"""
    path = _find_history_file(year, month)
    if not path:
        return {}

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

        if not current_date or "⚠" in line:
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
                ikey = f"{current_date}|{cat}|{item}"
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

_REPORT_CSS = """\
  .report { font-family: monospace; font-size: 14px; padding: 1.5rem; background: #1e1e1e; border-radius: 8px; color: #ddd; max-width: 360px; }
  .report table { width: 100%; border-collapse: collapse; }
  .report td { padding: 3px 6px; }
  .report .sym { text-align: right; width: 20px; color: #888; }
  .report .amt { text-align: right; width: 80px; }
  .report .divider td { border-top: 1px solid #444; padding-top: 6px; font-weight: bold; }
  .report .section-title { color: #888; font-size: 13px; padding-top: 1rem; padding-bottom: 4px; }
  .report .memo-date { width: 40px; color: #888; }
  .report .memo-who { width: 60px; color: #888; }
  .report .total-row td { font-weight: bold; padding-top: 6px; border-top: 2px solid #666; }
  .tooltip-container { position: relative; display: inline-block; cursor: pointer; }
  .tooltip-container .tooltip-text { visibility: hidden; background-color: #333; color: #fff; text-align: left; border-radius: 6px; padding: 8px 12px; position: absolute; z-index: 1000; left: 105%; top: 50%; transform: translateY(-50%); white-space: nowrap; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
  .tooltip-container:hover .tooltip-text { visibility: visible; }"""


st.set_page_config(page_title="報表", page_icon="📊", layout="wide")
st.title("📊 統計報表")

# Tooltip CSS 樣式
st.markdown("""
<style>
.tooltip-container {
    position: relative;
    display: inline-block;
    cursor: pointer;
    font-family: monospace;
    padding: 2px 5px;
    border-radius: 4px;
}
.tooltip-container:hover {
    background-color: #f0f2f6;
}
.tooltip-container .tooltip-text {
    visibility: hidden;
    background-color: #333;
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
.tooltip-text::before {
    content: "";
    position: absolute;
    top: 50%;
    right: 100%;
    margin-top: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: transparent #333 transparent transparent;
}
.report { font-family: monospace; font-size: 14px; padding: 1.5rem; background: #1e1e1e; border-radius: 8px; max-width: 360px; }
.report table { width: 100%; border-collapse: collapse; }
.report td { padding: 3px 6px; }
.report .sym { text-align: right; width: 20px; color: #888; }
.report .amt { text-align: right; width: 80px; }
.report .divider td { border-top: 1px solid #444; padding-top: 6px; font-weight: bold; }
.report .section-title { color: #888; font-size: 13px; padding-top: 1rem; padding-bottom: 4px; }
.report .memo-date { width: 40px; color: #888; }
.report .memo-who { width: 60px; color: #888; }
.report .total-row td { font-weight: bold; padding-top: 6px; border-top: 2px solid #666; }
</style>
""", unsafe_allow_html=True)

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
            rows += f'    <tr><td class="memo-date">{d}</td><td class="memo-who">{w}</td><td>{desc}</td><td class="sym">+$</td><td class="amt">{amt:,.0f}</td></tr>\n'
        rows += f'    <tr class="divider"><td colspan="3">備忘小計</td><td class="sym">+$</td><td class="amt">{memo_subtotal:,.0f}</td></tr>\n'
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
  <h3 style="margin-bottom:2px">{month_label}</h3>
  <div style="color:#aaa;font-size:16px;margin-bottom:0.5rem">{person}</div>
  <table>
{cat_rows}    <tr class="divider"><td>Sub Total</td><td class="sym">$</td><td class="amt">{subtotal:,.0f}</td></tr>
  </table>{memo_amt_table}{memo_no_amt_table}
  <table style="margin-top:1rem">
    <tr class="total-row"><td>Total</td><td class="sym">$</td><td class="amt">{total:,.0f}</td><td style="color:#888;font-size:13px;padding-left:12px">{pending_note}</td></tr>
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


# 側邊欄：篩選條件
with st.sidebar:
    st.subheader("篩選條件")

    # 取得可用年份
    available_years = db.get_expense_years()
    if not available_years:
        available_years = [datetime.now().year]

    year = st.selectbox("年份", options=available_years)

    # 取得該年份的月份
    available_months = db.get_expense_months(year) if year else []
    if not available_months:
        available_months = list(range(1, 13))

    month = st.selectbox(
        "月份",
        options=available_months,
        format_func=lambda x: f"{x}月"
    )

    st.divider()

    # 報表類型
    report_type = st.radio(
        "報表類型",
        options=["全員月報", "月份比較", "年度統計"],
        index=0
    )

    st.divider()

    # 管理模式
    manage_mode = st.toggle("🔧 管理模式", value=False, help="開啟後可刪除記錄")


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

        # DB lookup set for fast matching
        _db_set = {(e["date"], e["category"], e["person"]) for e in expenses}

        for person in person_names:
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
                f'  <style>\n    body {{ background: #111; color: #ddd; font-family: sans-serif; padding: 2rem; }}\n'
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
                _auto_match = sum(1 for it in person_raw if (it["date"], it["category"], person) in _db_set)
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
                            _in_db = (_it["date"], _it["category"], person) in _db_set
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

            st.divider()

        if not df.empty:
            st.metric("全體總計", f"${df['total'].sum():,.0f}")
        else:
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
            for i in range(0, len(compare_months), 3):
                cols = st.columns(3)
                batch = compare_months[i:i+3]

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
                    "總計": f"${total:,.0f}"
                })
            st.dataframe(pd.DataFrame(summary_data), hide_index=True, width='stretch')


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
        for i in range(0, len(person_names), 3):
            cols = st.columns(3)
            batch = person_names[i:i+3]

            for j, col in enumerate(cols):
                with col:
                    if j < len(batch):
                        person = batch[j]
                        person_df = yearly_df[yearly_df["person"] == person]

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
                        for cat in CATEGORY_ORDER:
                            amount = category_totals.get(cat, 0)
                            display_name = CATEGORY_DISPLAY.get(cat, cat)

                            if cat in category_details and category_details[cat]:
                                # 有明細，顯示 tooltip
                                tooltip_content = "<br>".join(category_details[cat])
                                html = f'''
                                <div class="tooltip-container">
                                    <span>{display_name}　${amount:,.0f}</span>
                                    <span class="tooltip-text">{tooltip_content}</span>
                                </div>
                                '''
                                st.markdown(html, unsafe_allow_html=True)
                            else:
                                st.text(f"{display_name}　${amount:,.0f}")

                            total_amount += amount

                        st.write("")
                        st.markdown(f"**Total ${total_amount:,.0f}**")

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
                for _, row in query_df.iterrows():
                    date_parts = row["date"].split("-")
                    display_date = f"{int(date_parts[1])}/{int(date_parts[2])}"
                    cat_display = CATEGORY_DISPLAY.get(row["category"], row["category"])
                    st.text(
                        f"📅 {row['date']} ({display_date}) | "
                        f"{row['person']} | {cat_display} | "
                        f"${row['amount']}×{row['quantity']}=${row['total']:.0f}"
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
                f'<div class="report">\n  <h3>備忘（未歸類）</h3>\n  <table>\n{rows}  </table>\n</div>'
            )

        report_css = _REPORT_CSS

        cards_html = "\n".join(f'<div class="card-wrap">{c}</div>' for c in card_htmls)
        full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8">
  <title>{month_label} 月結報表</title>
  <style>
    body {{ background: #111; color: #ddd; font-family: sans-serif; padding: 2rem; }}
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
