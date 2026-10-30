"""輸入頁面 - 月曆模式"""
import calendar
import streamlit as st
from datetime import datetime

import database as db
from parser import parse_accounting_text, ParseStatus
import html

from ui import apply_theme, diff_marks, is_mobile, pane_label, pill, stamp, steps
from normalizer import DEFAULT_CATEGORIES, normalize_day, normalize_text, split_days


st.set_page_config(page_title="輸入記帳", page_icon="📝", layout="wide")
apply_theme()
MOBILE = is_mobile()

# 中文星期
WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]

# 初始化 session state
if "calendar_data" not in st.session_state:
    st.session_state.calendar_data = {}  # {day: text} 當月每日的輸入文字
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "batch_mode" not in st.session_state:
    st.session_state.batch_mode = False
if "batch_log" not in st.session_state:
    st.session_state.batch_log = []
if "bulk_awaiting_confirm" not in st.session_state:
    st.session_state.bulk_awaiting_confirm = False
if "bulk_safe_items" not in st.session_state:
    st.session_state.bulk_safe_items = []
if "bulk_conflict_items" not in st.session_state:
    st.session_state.bulk_conflict_items = []
if "bulk_pending_items" not in st.session_state:
    st.session_state.bulk_pending_items = []
if "bulk_memos" not in st.session_state:
    st.session_state.bulk_memos = []
if "bulk_gen" not in st.session_state:
    st.session_state.bulk_gen = 0  # 每次重新拆格 +1，讓各格的 widget key 換新
if "bulk_cells" not in st.session_state:
    st.session_state.bulk_cells = []  # 各格標題（日期行）；文字存在各格的 widget key 裡


def get_weekday_name(year: int, month: int, day: int) -> str:
    """取得星期幾的中文名稱"""
    weekday = calendar.weekday(year, month, day)
    return WEEKDAYS[weekday]


def format_date_title(year: int, month: int, day: int) -> str:
    """格式化日期標題，如「1/19（一）」"""
    weekday_name = get_weekday_name(year, month, day)
    return f"{month}/{day}（{weekday_name}）"


def normalize_options() -> dict:
    """整理格式要用的已知人名（含別名、代理關鍵字）與類別"""
    names = []
    for p in db.get_all_persons():
        names.append(p["name"])
        if p["aliases"]:
            names.extend(a.strip() for a in p["aliases"].split(",") if a.strip())
    persons = list(names)  # 真正的人員與別名（代理關鍵字不算），用來判斷「阿鵰點心+70」這類獨立行
    names.extend(db.get_person_proxy_mappings().keys())
    categories = list(dict.fromkeys([*DEFAULT_CATEGORIES, *db.get_all_category_prices().keys()]))
    return {"names": names, "categories": categories, "persons": persons}


def select_day(day: int) -> None:
    """月曆點日期 callback"""
    st.session_state.selected_date = day


def magic_single_day(day: int, header: str) -> None:
    """單日編輯區「來點魔法」callback：左邊原始資料 -> 右邊整理後"""
    src = st.session_state.get(f"input_{day}", st.session_state.calendar_data.get(day, ""))
    result = normalize_day(src, header, **normalize_options())
    st.session_state[f"magic_{day}"] = result.text
    st.session_state[f"magic_src_{day}"] = src
    st.session_state[f"magic_res_{day}"] = result


def bulk_key(i: int) -> str:
    return f"bulk_{st.session_state.bulk_gen}_{i}"


def split_bulk_text() -> None:
    """整月大格貼上後：依日期行拆成一天一格（左邊填原始資料，右邊清空）"""
    old_prefix = f"bulk_{st.session_state.bulk_gen}_"
    for k in [k for k in st.session_state if k.startswith(old_prefix)]:
        del st.session_state[k]

    cells = split_days(st.session_state.bulk_input_text)
    st.session_state.bulk_gen += 1
    st.session_state.bulk_cells = [c["title"] for c in cells]
    for i, c in enumerate(cells):
        st.session_state[f"{bulk_key(i)}_src"] = c["text"]
        st.session_state[f"{bulk_key(i)}_out"] = ""

    # 舊文字算出的待確認項目已失效
    st.session_state.bulk_awaiting_confirm = False
    st.session_state.bulk_safe_items = []
    st.session_state.bulk_conflict_items = []
    st.session_state.bulk_pending_items = []
    st.session_state.bulk_memos = []


def load_raw_input(text: str) -> None:
    """把手機傳來的原文原封不動放進大格，並依日期行拆成一天一格"""
    st.session_state.bulk_input_text = text
    split_bulk_text()


def magic_bulk_cells(indexes: list, opts: dict = None) -> None:
    """對指定的格子「來點魔法」"""
    opts = opts or normalize_options()
    for i in indexes:
        key = bulk_key(i)
        src = st.session_state[f"{key}_src"]
        result = normalize_text(src, **opts)
        st.session_state[f"{key}_out"] = result.text
        st.session_state[f"{key}_snap"] = src
        st.session_state[f"{key}_res"] = result


def magic_bulk_all() -> None:
    magic_bulk_cells(range(len(st.session_state.bulk_cells)))


def render_magic_report(result, stale: bool) -> None:
    """顯示魔法結果：檢查通過／問題、需要確認的推測"""
    if stale:
        st.html(pill("原稿已修改，右邊是舊的批改結果，請重新「來點魔法」", "warn"))
    if result is None:
        return
    if result.ok:
        st.html(pill("✓ 自動檢查通過", "ok"))
    else:
        st.warning("⚠️ 自動檢查發現 {} 個問題，請先確認：\n\n".format(len(result.problems))
                   + "\n".join(f"- {p}" for p in result.problems))
    if result.flags:
        with st.expander(f"需要你確認的 {len(result.flags)} 處"):
            for flag in result.flags:
                st.text(flag)


def text_height(text: str) -> int:
    """依行數決定文字框高度"""
    return max(100, min(420, 26 * (text.count("\n") + 1) + 40))


def process_bulk_text(text: str, year: int) -> dict:
    """解析整段多日記帳文字（parser 自動從日期行分組）

    Args:
        text: 包含多個日期行的原始記帳文字
        year: 年份（用於補足日期格式）

    Returns:
        {
            "success_count": int,
            "pending_count": int,
            "duplicate_count": int,
            "memo_count": int,
            "dates": set[str],       # 解析到的日期集合
            "pending_items": list,   # 待審核原始項目
        }
    """
    result = {
        "success_count": 0,
        "pending_count": 0,
        "duplicate_count": 0,
        "memo_count": 0,
        "dates": set(),
        "pending_items": [],
    }

    if not text.strip():
        return result

    parse_result = parse_accounting_text(text, target_date=None, year=year)

    for exp in parse_result.expenses:
        if exp.status == ParseStatus.SUCCESS:
            db.add_expense(
                date=exp.date,
                category=exp.category,
                person=exp.person,
                amount=exp.amount,
                quantity=exp.quantity,
                note=exp.note,
            )
            result["success_count"] += 1
            result["dates"].add(exp.date)
        elif exp.status == ParseStatus.DUPLICATE:
            result["duplicate_count"] += 1

    for item in parse_result.pending:
        db.add_pending_review(
            raw_text=item["raw_text"],
            source_line=item["source_line"],
            date=item["date"],
        )
        result["pending_count"] += 1
        result["pending_items"].append(item)

    for memo in parse_result.memos:
        db.add_memo(memo.date, memo.content, memo.person)
        result["memo_count"] += 1
        result["dates"].add(memo.date)

    return result


def process_single_day(year: int, month: int, day: int, text: str) -> dict:
    """處理單日資料，回傳處理結果"""
    date_str = f"{year}-{month:02d}-{day:02d}"
    result = {
        "date": date_str,
        "success_count": 0,
        "pending_count": 0,
        "duplicate_count": 0,
        "memo_count": 0,
        "status": "success",
        "message": ""
    }

    if not text.strip():
        result["status"] = "skipped"
        result["message"] = "無資料"
        return result

    # 解析文字
    parse_result = parse_accounting_text(text, target_date=date_str)

    # 儲存成功的支出
    for exp in parse_result.expenses:
        if exp.status == ParseStatus.SUCCESS:
            db.add_expense(
                date=exp.date,
                category=exp.category,
                person=exp.person,
                amount=exp.amount,
                quantity=exp.quantity,
                note=exp.note
            )
            result["success_count"] += 1

    # 儲存待審核
    for item in parse_result.pending:
        db.add_pending_review(
            raw_text=item["raw_text"],
            source_line=item["source_line"],
            date=item["date"]
        )
        result["pending_count"] += 1

    # 儲存備忘
    for memo in parse_result.memos:
        db.add_memo(memo.date, memo.content, memo.person)
        result["memo_count"] += 1

    # 重複數量
    result["duplicate_count"] = len(parse_result.duplicates)

    # 設定狀態
    if result["pending_count"] > 0:
        result["status"] = "warning"
        result["message"] = f"{result['success_count']} 筆成功，{result['pending_count']} 筆待審核"
    elif result["success_count"] > 0:
        result["status"] = "success"
        result["message"] = f"{result['success_count']} 筆成功"
    else:
        result["status"] = "skipped"
        result["message"] = "無有效資料"

    if result["duplicate_count"] > 0:
        result["message"] += f"（{result['duplicate_count']} 筆重複跳過）"

    return result


# ========== 頂端功能列：年月、人員、清除月份、動作按鈕 ==========

current_year = datetime.now().year
current_month = datetime.now().month

# 桌面：一條橫列，年月／人員／清除在左，動作按鈕（選了日期才能按）在右。
# 手機：年月＋「⋯」一列，動作按鈕改放在日期編輯區上方。
if MOBILE:
    tb_year, tb_month, tb_more = st.container(key="ymbar").columns(3, vertical_alignment="bottom")
    toolbar = None
else:
    toolbar = st.container(horizontal=True, vertical_alignment="bottom", key="toolbar")
    tb_year = tb_month = toolbar

with tb_year:
    year = st.selectbox(
        "年份",
        options=list(range(current_year - 2, current_year + 2)),
        index=2,
        key="select_year",
        width="stretch" if MOBILE else 110,
    )
with tb_month:
    month = st.selectbox(
        "月份",
        options=list(range(1, 13)),
        index=current_month - 1,
        key="select_month",
        width="stretch" if MOBILE else 90,
    )

if MOBILE:
    people_box = tb_more.popover("⋯", help="人員、清除月份", width="stretch")
    clear_box = people_box.expander("🗑️ 清除月份資料")
else:
    people_box = toolbar.popover("👥 人員")
    clear_box = toolbar.popover("🗑️ 清除月份資料")

with people_box:
    persons = db.get_all_persons()
    if persons:
        for p in persons:
            st.text(f"• {p['name']}")
    else:
        st.info("尚未建立人員")

    with st.expander("新增人員"):
        new_name = st.text_input("姓名", key="new_person_name")
        new_aliases = st.text_input("別名", key="new_person_aliases")
        if st.button("新增"):
            if new_name:
                try:
                    db.add_person(new_name, new_aliases)
                    st.toast(f"已新增：{new_name}", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗：{e}")

with clear_box:
    clear_col1, clear_col2 = st.columns(2)
    with clear_col1:
        clear_year = st.selectbox(
            "年份",
            options=list(range(current_year - 2, current_year + 2)),
            index=2,
            key="clear_year"
        )
    with clear_col2:
        clear_month = st.selectbox(
            "月份",
            options=list(range(1, 13)),
            index=current_month - 1,
            key="clear_month"
        )
    st.caption(f"將清除 {clear_year}/{clear_month} 的支出、待審核、備忘")
    confirm = st.checkbox("確認清除", key="confirm_clear_month")
    if st.button("清除此月資料", disabled=not confirm):
        result = db.clear_month_data(clear_year, clear_month)
        total = result['expenses'] + result['pending'] + result['memos']
        if total > 0:
            st.toast(
                f"已清除 {clear_year}/{clear_month}："
                f"{result['expenses']} 筆支出、"
                f"{result['pending']} 筆待審核、"
                f"{result['memos']} 筆備忘",
                icon="🗑️",
            )
        else:
            st.toast(f"{clear_year}/{clear_month} 無資料", icon="ℹ️")
        st.rerun()


# ========== 版面：桌面 左 60% 輸入／右 40% 月曆；手機 月曆在上、輸入在下 ==========
# 先畫月曆（點日期會改 selected_date），再畫輸入區，所以腳本順序是月曆 → 輸入

if MOBILE:
    cal_area = st.container()
    main_area = st.container()
else:
    main_area, cal_area = st.columns([6, 4], gap="large")

cal = calendar.Calendar(firstweekday=0)  # 週一開始
month_days = cal.monthdayscalendar(year, month)
dates_with_data = db.get_dates_with_data(year, month)
daily_totals = db.get_daily_totals(year, month)

with cal_area:
    with st.container(key="calwrap"):
        st.html(f'<div class="cal-month">{year} 年 {month} 月</div>')

        with st.container(key="calendar"):
            # 顯示星期標題
            header_cols = st.columns(7)
            for i, day_name in enumerate(WEEKDAYS):
                header_cols[i].html(f'<div style="text-align:center;font-size:.8rem;font-weight:650;opacity:.6;letter-spacing:.08em">{day_name}</div>')

            # 顯示月曆格子
            for week in month_days:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    with cols[i]:
                        if day == 0:
                            st.write("")  # 空格
                        else:
                            has_data = day in dates_with_data
                            has_input = day in st.session_state.calendar_data

                            # 日期＋當日金額（有入帳的日子底色變綠、暫存的日子右上角畫紅圈，見下方 <style>）
                            amount = daily_totals.get(day, 0)
                            button_label = f"**{day}**  \n:gray[:small[{amount:,.0f}]]" if has_data and amount else f"**{day}**"

                            st.button(
                                button_label,
                                key=f"day_{day}",
                                width='stretch',
                                on_click=select_day,
                                args=(day,),
                            )
        st.html(
            '<div class="cal-legend"><span><i style="background:var(--wash)"></i>已入帳</span>'
            '<span><i style="border-radius:50%;border-color:var(--red)"></i>已暫存</span>'
            '<span><i style="border-radius:50%;border:2px solid var(--red)"></i>目前編輯</span></div>'
            f'<div class="cal-total"><span>{month} 月已入帳 {len(dates_with_data)} 天</span>'
            f'<b>${sum(daily_totals.values()):,.0f}</b></div>'
        )

# 月曆格子的狀態樣式（依資料動態產生）
_cal_css = "".join(
    f".st-key-day_{d} button{{background:var(--wash)!important;border-color:var(--grid)!important}}"
    for d in dates_with_data
)
_cal_css += "".join(
    f".st-key-day_{d} button::after{{content:'';position:absolute;right:8px;top:8px;width:7px;height:7px;"
    f"border-radius:50%;border:1.5px solid var(--red)}}"
    for d in st.session_state.calendar_data
)
if st.session_state.selected_date:
    _cal_css += (
        f".st-key-day_{st.session_state.selected_date} button{{background:#fff!important;"
        f"border:2px solid var(--red)!important;border-radius:46% 54% 50% 50% / 55% 45% 55% 45%!important}}"
    )
st.markdown(f"<style>{_cal_css}</style>", unsafe_allow_html=True)


# ========== 輸入區 ==========
with main_area:

    if st.session_state.selected_date:
        day = st.session_state.selected_date
        date_title = format_date_title(year, month, day)
        date_str = f"{year}-{month:02d}-{day:02d}"

        st.html(f'<div class="day-title">{month}月{day}日<small>星期{get_weekday_name(year, month, day)}</small></div>')

        # 動作按鈕的位置：桌面在頂端功能列右側，手機在日期標題下方（一列四顆）
        if MOBILE:
            slot_magic, slot_tmp, slot_save, slot_cancel = st.container(key="actions").columns(4)
        else:
            toolbar.space("stretch")
            slot_magic = slot_tmp = slot_save = slot_cancel = toolbar
        btn_w = "stretch" if MOBILE else "content"
        lbl_magic, lbl_tmp, lbl_save, lbl_cancel = (
            ("✎魔法", "暫存", "儲存", "取消") if MOBILE
            else ("✎ 來點魔法", "暫存", "儲存並關閉", "取消")
        )

        # 檢查是否已有資料（支出或備忘）
        existing_expenses = db.get_expenses_by_date(date_str)
        existing_memos = db.get_memos_by_date(date_str)

        if existing_expenses or existing_memos:
            st.info(f"此日期已有 {len(existing_expenses)} 筆支出、{len(existing_memos)} 筆備忘")
            with st.expander("查看現有資料"):
                for exp in existing_expenses:
                    st.text(f"• {exp['category']} | {exp['person']} | ${exp['amount']} × {exp['quantity']}")
                for memo in existing_memos:
                    st.text(f"• 📝 {memo['content']}")

            if st.button("🗑️ 清除此日資料", type="secondary"):
                result = db.delete_day_data(date_str)
                st.warning(f"已刪除 {result['expenses']} 筆支出、{result['memos']} 筆備忘")
                st.rerun()

        # 輸入區域：左邊原始資料、右邊魔法整理後
        current_text = st.session_state.calendar_data.get(day, "")
        # 批改紀錄用「目前」的兩邊文字比對（widget 狀態在腳本開跑前就已更新）
        src_now = st.session_state.get(f"input_{day}", current_text)
        out_now = st.session_state.get(f"magic_{day}", "")
        n_marks, marks_html = diff_marks(src_now, out_now) if out_now.strip() else (0, "")
        magic_res_now = st.session_state.get(f"magic_res_{day}")
        out_badge = (
            stamp("已整理") if out_now.strip() and magic_res_now is not None and magic_res_now.ok
            else pill(f"{n_marks} 處修改" if n_marks else "可手動修改", "accent")
        )
        left, right = st.columns(2)
        with left:
            pane_label("原稿", pill("貼上或手打", "neutral"))
            input_text = st.text_area(
                "原始資料",
                label_visibility="collapsed",
                value=current_text,
                height=240,
                key=f"input_{day}",
                placeholder=f"""範例（日期行可省略）：
{month}/{day}（{get_weekday_name(year, month, day)}）
早餐：小明、小華
中餐：阿鵰、泰禎
點心：阿鵰點心+60
晚餐：傑森*2
牛奶*1.5：小明"""
            )
        with right:
            pane_label("批改後", out_badge)
            magic_text = st.text_area(
                "魔法整理後",
                label_visibility="collapsed",
                height=240,
                key=f"magic_{day}",
                placeholder="按下「✎ 來點魔法」，批改後的文字會出現在這裡",
            )

        slot_magic.button(
            lbl_magic,
            on_click=magic_single_day,
            args=(day, date_title),
            disabled=not input_text.strip(),
            key=f"magic_btn_{day}",
            width=btn_w,
            help="把 ⚠️ 備忘整理成一品項一行（金額統一為 +$金額），並把類別行裡不是人名的項目拉成 ⚠️ 備忘",
        )
        magic_snapshot = st.session_state.get(f"magic_src_{day}")
        render_magic_report(
            st.session_state.get(f"magic_res_{day}") if magic_text.strip() else None,
            stale=bool(magic_text.strip()) and magic_snapshot is not None and magic_snapshot != input_text,
        )

        if marks_html:
            st.html(marks_html)

        # 實際儲存的內容：右邊有東西就用右邊，否則用左邊原稿
        input_text_to_save = magic_text if magic_text.strip() else input_text
        st.caption("儲存的是右邊批改後的文字；右邊留空則儲存左邊原稿")

        if slot_tmp.button(lbl_tmp, width=btn_w, key="day_tmp"):
            st.session_state.calendar_data[day] = input_text_to_save
            st.toast("已暫存", icon="💾")

        if slot_save.button(lbl_save, type="primary", width=btn_w, key="day_save"):
            if input_text_to_save.strip():
                result = process_single_day(year, month, day, input_text_to_save)
                if result["status"] == "success":
                    st.toast(result["message"], icon="✅")
                elif result["status"] == "warning":
                    st.toast(result["message"], icon="⚠️")
                # 清除暫存
                if day in st.session_state.calendar_data:
                    del st.session_state.calendar_data[day]
            for k in (f"input_{day}", f"magic_{day}", f"magic_src_{day}", f"magic_res_{day}"):
                st.session_state.pop(k, None)
            st.session_state.selected_date = None
            st.rerun()

        if slot_cancel.button(lbl_cancel, width=btn_w, key="day_cancel"):
            for k in (f"magic_{day}", f"magic_src_{day}", f"magic_res_{day}"):
                st.session_state.pop(k, None)
            st.session_state.selected_date = None
            st.rerun()

        # 即時預覽
        if input_text_to_save.strip():
            st.divider()
            st.write("**預覽解析結果：**")
            preview_result = parse_accounting_text(input_text_to_save, target_date=date_str)

            success_items = [e for e in preview_result.expenses if e.status == ParseStatus.SUCCESS]
            if success_items:
                st.success(f"✓ {len(success_items)} 筆可成功儲存")
                for exp in success_items[:5]:  # 最多顯示5筆
                    st.text(f"  • {exp.category} | {exp.person} | ${exp.amount} × {exp.quantity}")
                if len(success_items) > 5:
                    st.text(f"  ... 還有 {len(success_items) - 5} 筆")

            if preview_result.pending:
                st.warning(f"⚠️ {len(preview_result.pending)} 筆無法識別（將送審核）")
                for item in preview_result.pending[:3]:
                    st.text(f"  • 「{item['raw_text']}」")

            if preview_result.duplicates:
                st.info(f"🔄 {len(preview_result.duplicates)} 筆重複（將跳過）")


    else:
        st.caption("點選" + ("上方" if MOBILE else "右側") + "月曆的日期，開始輸入該天的記帳")
        if not MOBILE:
            toolbar.space("stretch")
            for label in ("✎ 來點魔法", "暫存", "儲存並關閉", "取消"):
                toolbar.button(label, disabled=True, key=f"idle_{label}")


    # ========== 批次輸入模式 ==========

    st.divider()
    st.subheader("批次輸入")

    # 顯示已暫存的資料
    if st.session_state.calendar_data:
        st.write(f"已暫存 **{len(st.session_state.calendar_data)}** 天的資料")
        with st.expander("查看暫存資料"):
            for day, text in sorted(st.session_state.calendar_data.items()):
                preview = text[:50] + "..." if len(text) > 50 else text
                st.text(f"• {month}/{day}：{preview}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🚀 開始批次輸入", type="primary", width='stretch'):
                st.session_state.batch_mode = True
                st.session_state.batch_log = []

        with col2:
            if st.button("🗑️ 清除所有暫存", width='stretch'):
                st.session_state.calendar_data = {}
                st.rerun()

    else:
        st.info("點擊月曆上的日期，輸入資料後按「暫存」，再使用批次輸入一次儲存所有資料")


    # 批次處理
    if st.session_state.batch_mode and st.session_state.calendar_data:
        st.divider()
        st.write("**批次處理進度：**")

        progress_bar = st.progress(0)
        status_container = st.container()

        total_days = len(st.session_state.calendar_data)
        processed = 0

        for day in sorted(st.session_state.calendar_data.keys()):
            text = st.session_state.calendar_data[day]
            result = process_single_day(year, month, day, text)

            # 更新 log
            if result["status"] == "success":
                icon = "✓"
            elif result["status"] == "warning":
                icon = "⚠️"
            else:
                icon = "⏭️"

            log_entry = f"{month}/{day} {icon} {result['message']}"
            st.session_state.batch_log.append(log_entry)

            processed += 1
            progress_bar.progress(processed / total_days)

        # 顯示結果
        with status_container:
            for log in st.session_state.batch_log:
                if "✓" in log:
                    st.success(log)
                elif "⚠️" in log:
                    st.warning(log)
                else:
                    st.info(log)

        st.success(f"批次輸入完成！共處理 {total_days} 天")

        # 清除狀態
        st.session_state.calendar_data = {}
        st.session_state.batch_mode = False
        st.session_state.batch_log = []

        if st.button("重新整理頁面"):
            st.rerun()


    # ========== 整月批次輸入 ==========

    st.divider()
    st.subheader("整月批次輸入")
    st.caption("在大格貼入整個月的原稿，點一下空白處（或按 Ctrl+Enter）就會自動依日期拆成一天一格。"
               "重新貼上會重新拆格並清除右邊的批改結果。")

    cells = st.session_state.bulk_cells
    _magic_done = any(st.session_state.get(f"{bulk_key(i)}_res") for i in range(len(cells)))
    if not cells:
        steps(active=1)
    elif not _magic_done:
        steps(active=2, done=1)
    else:
        steps(active=3, done=2)

    raw_inputs = db.get_recent_raw_inputs(10)
    if raw_inputs:
        with st.expander(f"📱 手機傳來的原文（最近 {len(raw_inputs)} 則）"):
            st.caption("按「載入」會把原文原封不動放進下方大格，並依日期行拆成一天一格（會取代大格目前的內容）。")
            for r in raw_inputs:
                days = "、".join(c["title"] for c in split_days(r["text"])) or "（無日期行）"
                c_info, c_btn = st.columns([5, 1])
                with c_info:
                    st.markdown(f"**{r['created_at'][:16].replace('T', ' ')}**　{days}")
                with c_btn:
                    st.button("載入", key=f"load_raw_{r['id']}", on_click=load_raw_input, args=(r["text"],),
                              width='stretch')

    st.text_area(
        "貼入記帳文字（需包含日期行，如 `3/1（日）`）",
        height=260,
        key="bulk_input_text",
        on_change=split_bulk_text,
        placeholder="""範例：
3/1（日）
早餐：小明、小華
晚餐：阿鵰*2、泰禎

3/2（一）
早餐：小明
牛奶*1.5：阿鵰、泰禎"""
    )


    def cell_status(key: str) -> str:
        """每格標題旁的狀態標籤（HTML）"""
        out_text = st.session_state.get(f"{key}_out", "")
        result = st.session_state.get(f"{key}_res")
        if not out_text.strip() or result is None:
            return pill("尚未整理", "neutral")
        snapshot = st.session_state.get(f"{key}_snap")
        if snapshot is not None and snapshot != st.session_state.get(f"{key}_src", ""):
            return pill("原稿已修改", "warn")
        if not result.ok:
            return pill(f"{len(result.problems)} 個問題", "warn")
        if result.flags:
            return pill(f"已批改 · {len(result.flags)} 處待確認", "accent")
        return pill("✓ 已批改", "ok")


    bulk_parts = []
    if cells:
        top1, top2, top3 = st.columns([1.2, 1.2, 3])
        with top1:
            st.button("✎ 全部來點魔法", on_click=magic_bulk_all, type="primary", key="bulk_magic_all", width='stretch')
        with top2:
            st.button("重新依日期拆格", on_click=split_bulk_text, key="bulk_resplit", width='stretch')
        with top3:
            st.html(f'<div style="padding-top:.55rem;opacity:.65;font-size:.9rem">共 <b>{len(cells)}</b> 天；'
                    '左邊是原稿，右邊是批改後的文字</div>')

        for i, title in enumerate(cells):
            key = bulk_key(i)
            src_text = st.session_state[f"{key}_src"]
            with st.container(border=True):
                st.html(f'<div class="day-head"><span class="d">{html.escape(title)}</span>{cell_status(key)}</div>')
                left, right = st.columns(2)
                with left:
                    pane_label("原稿", pill("貼上的內容", "neutral"))
                    src_text = st.text_area("原始資料", key=f"{key}_src", height=text_height(src_text),
                                            label_visibility="collapsed")
                with right:
                    out_now = st.session_state.get(f"{key}_out", "")
                    n_marks = diff_marks(st.session_state[f"{key}_src"], out_now)[0] if out_now.strip() else 0
                    pane_label("批改後", pill(f"{n_marks} 處修改" if n_marks else "可手動修改", "accent"))
                    out_text = st.text_area("魔法整理後", key=f"{key}_out", height=text_height(src_text),
                                            label_visibility="collapsed",
                                            placeholder="按「✎ 來點魔法」後出現在這裡")

                st.button("✎ 來點魔法", on_click=magic_bulk_cells, args=([i],), key=f"{key}_btn",
                          disabled=not src_text.strip())
                if out_text.strip():
                    marks_html = diff_marks(src_text, out_text)[1]
                    if marks_html:
                        st.html(marks_html)
                snapshot = st.session_state.get(f"{key}_snap")
                result = st.session_state.get(f"{key}_res") if out_text.strip() else None
                if result is not None and not result.ok:
                    st.warning("自動檢查發現問題，請先確認：\n\n" + "\n".join(f"- {p}" for p in result.problems))
                if result is not None and result.flags:
                    with st.expander(f"需要你確認的 {len(result.flags)} 處"):
                        for flag in result.flags:
                            st.text(flag)

                # 實際寫入的內容：右邊有東西就用右邊，否則用左邊原始資料
                bulk_parts.append(out_text if out_text.strip() else src_text)

    bulk_text = "\n\n".join(part for part in bulk_parts if part.strip())
    if cells:
        st.caption("寫入資料庫的是各格右邊批改後的文字；右邊留空的格子則寫入左邊原稿")
        st.html("<div style='height:.4rem'></div>")

    # 即時預覽
    if bulk_text.strip():
        preview_result = parse_accounting_text(bulk_text, target_date=None, year=year)
        success_items = [e for e in preview_result.expenses if e.status == ParseStatus.SUCCESS]
        duplicate_items = [e for e in preview_result.expenses if e.status == ParseStatus.DUPLICATE]

        preview_col1, preview_col2, preview_col3, preview_col4 = st.columns(4)
        with preview_col1:
            st.metric("可儲存", len(success_items))
        with preview_col2:
            st.metric("待審核", len(preview_result.pending))
        with preview_col3:
            st.metric("重複", len(duplicate_items))
        with preview_col4:
            st.metric("備忘", len(preview_result.memos))

        if success_items:
            with st.expander(f"預覽 {len(success_items)} 筆可儲存記錄"):
                for exp in success_items:
                    st.text(f"  {exp.date} | {exp.category} | {exp.person} | ${exp.amount} × {exp.quantity}")

        if preview_result.pending:
            with st.expander(f"⚠️ {len(preview_result.pending)} 筆無法識別"):
                for item in preview_result.pending:
                    st.text(f"  [{item['date']}] 「{item['raw_text']}」← {item['source_line']}")

        if duplicate_items:
            with st.expander(f"🔄 {len(duplicate_items)} 筆重複（儲存時會跳過）"):
                for exp in duplicate_items:
                    st.text(f"  {exp.date} | {exp.category} | {exp.person}")

    # 衝突確認 UI
    if st.session_state.bulk_awaiting_confirm:
        conflict_items = st.session_state.bulk_conflict_items
        st.warning(f"⚠️ 發現 {len(conflict_items)} 筆資料與資料庫中相同日期+金額的紀錄重複，請確認是否保留：")

        for i, conflict in enumerate(conflict_items):
            exp = conflict["exp"]
            existing = conflict["existing"]
            label = f"⚠️ {exp['date']} | {exp['category']} | {exp['person']} | ${exp['amount']} × {exp['quantity']}"
            with st.expander(label, expanded=True):
                st.write("**資料庫已存在（相同日期＋金額）：**")
                for ex in existing:
                    st.text(f"  • {ex['date']} | {ex['category']} | {ex['person']} | ${ex['amount']} × {ex['quantity']}")
                st.checkbox("保留此筆（插入資料庫）", key=f"bulk_conflict_keep_{i}", value=False)

        bulk_col1, bulk_col2 = st.columns(2)
        with bulk_col1:
            if st.button("✅ 確認儲存", type="primary", key="bulk_confirm_save"):
                saved_count = 0
                skipped_count = 0

                for item in st.session_state.bulk_safe_items:
                    db.add_expense(**item)
                    saved_count += 1

                for i, conflict in enumerate(st.session_state.bulk_conflict_items):
                    if st.session_state.get(f"bulk_conflict_keep_{i}", False):
                        db.add_expense(**conflict["exp"])
                        saved_count += 1
                    else:
                        skipped_count += 1

                pending_count = 0
                for item in st.session_state.bulk_pending_items:
                    db.add_pending_review(
                        raw_text=item["raw_text"],
                        source_line=item["source_line"],
                        date=item["date"],
                    )
                    pending_count += 1

                memo_count = 0
                for memo in st.session_state.bulk_memos:
                    db.add_memo(memo["date"], memo["content"], memo["person"])
                    memo_count += 1

                st.session_state.bulk_awaiting_confirm = False
                st.session_state.bulk_safe_items = []
                st.session_state.bulk_conflict_items = []
                st.session_state.bulk_pending_items = []
                st.session_state.bulk_memos = []

                msg = f"{saved_count} 筆支出、{memo_count} 筆備忘已儲存"
                if pending_count > 0:
                    msg += f"，{pending_count} 筆送審核"
                if skipped_count > 0:
                    msg += f"，{skipped_count} 筆重複略過"
                st.success(msg)
                st.rerun()

        with bulk_col2:
            if st.button("❌ 取消", key="bulk_cancel"):
                st.session_state.bulk_awaiting_confirm = False
                st.session_state.bulk_safe_items = []
                st.session_state.bulk_conflict_items = []
                st.session_state.bulk_pending_items = []
                st.session_state.bulk_memos = []
                st.rerun()

    else:
        if st.button("✅ 一次寫入資料庫", type="primary", disabled=not bulk_text.strip(), key="bulk_save"):
            parse_result = parse_accounting_text(bulk_text, target_date=None, year=year)
            safe_items = []
            conflict_items = []

            for exp in parse_result.expenses:
                if exp.status == ParseStatus.SUCCESS:
                    existing = db.find_expenses_by_date_and_amount(exp.date, exp.amount)
                    if existing:
                        conflict_items.append({
                            "exp": {
                                "date": exp.date,
                                "category": exp.category,
                                "person": exp.person,
                                "amount": exp.amount,
                                "quantity": exp.quantity,
                                "note": exp.note,
                            },
                            "existing": existing,
                        })
                    else:
                        safe_items.append({
                            "date": exp.date,
                            "category": exp.category,
                            "person": exp.person,
                            "amount": exp.amount,
                            "quantity": exp.quantity,
                            "note": exp.note,
                        })

            if conflict_items:
                st.session_state.bulk_awaiting_confirm = True
                st.session_state.bulk_safe_items = safe_items
                st.session_state.bulk_conflict_items = conflict_items
                st.session_state.bulk_pending_items = parse_result.pending
                st.session_state.bulk_memos = [
                    {"date": m.date, "content": m.content, "person": m.person}
                    for m in parse_result.memos
                ]
                st.rerun()
            else:
                # 無衝突，直接儲存
                saved_count = 0
                for item in safe_items:
                    db.add_expense(**item)
                    saved_count += 1

                pending_count = 0
                for item in parse_result.pending:
                    db.add_pending_review(
                        raw_text=item["raw_text"],
                        source_line=item["source_line"],
                        date=item["date"],
                    )
                    pending_count += 1

                memo_count = 0
                for memo in parse_result.memos:
                    db.add_memo(memo.date, memo.content, memo.person)
                    memo_count += 1

                duplicate_count = len([e for e in parse_result.expenses if e.status == ParseStatus.DUPLICATE])

                if saved_count > 0 or memo_count > 0:
                    msg = f"{saved_count} 筆支出、{memo_count} 筆備忘已儲存"
                    if pending_count > 0:
                        msg += f"，{pending_count} 筆送審核"
                    if duplicate_count > 0:
                        msg += f"，{duplicate_count} 筆重複跳過"
                    st.success(msg)
                elif pending_count > 0:
                    st.warning(f"0 筆儲存，{pending_count} 筆待審核")
                else:
                    st.info("無有效資料")

                if saved_count > 0:
                    st.rerun()
