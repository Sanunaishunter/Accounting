"""輸入頁面 - 月曆模式"""
import calendar
import streamlit as st
from datetime import datetime

import database as db
from parser import parse_accounting_text, ParseStatus


st.set_page_config(page_title="輸入記帳", page_icon="📝", layout="wide")
st.title("📝 輸入記帳資料")

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


def get_weekday_name(year: int, month: int, day: int) -> str:
    """取得星期幾的中文名稱"""
    weekday = calendar.weekday(year, month, day)
    return WEEKDAYS[weekday]


def format_date_title(year: int, month: int, day: int) -> str:
    """格式化日期標題，如「1/19（一）」"""
    weekday_name = get_weekday_name(year, month, day)
    return f"{month}/{day}（{weekday_name}）"


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


# ========== 側邊欄：年月選擇 ==========

with st.sidebar:
    st.subheader("選擇年月")

    current_year = datetime.now().year
    current_month = datetime.now().month

    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox(
            "年份",
            options=list(range(current_year - 2, current_year + 2)),
            index=2,
            key="select_year"
        )
    with col2:
        month = st.selectbox(
            "月份",
            options=list(range(1, 13)),
            index=current_month - 1,
            key="select_month"
        )

    st.divider()

    # 人員列表
    st.subheader("人員列表")
    persons = db.get_all_persons()
    if persons:
        for p in persons:
            st.text(f"• {p['name']}")
    else:
        st.info("尚未建立人員")

    # 新增人員
    with st.expander("新增人員"):
        new_name = st.text_input("姓名", key="new_person_name")
        new_aliases = st.text_input("別名", key="new_person_aliases")
        if st.button("新增"):
            if new_name:
                try:
                    db.add_person(new_name, new_aliases)
                    st.success(f"已新增：{new_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗：{e}")

    st.divider()

    # 清除月份資料
    with st.expander("🗑️ 清除月份資料"):
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
                st.success(
                    f"已清除 {clear_year}/{clear_month}："
                    f"{result['expenses']} 筆支出、"
                    f"{result['pending']} 筆待審核、"
                    f"{result['memos']} 筆備忘"
                )
            else:
                st.info(f"{clear_year}/{clear_month} 無資料")
            st.rerun()


# ========== 月曆顯示 ==========

# 取得該月資訊
cal = calendar.Calendar(firstweekday=0)  # 週一開始
month_days = cal.monthdayscalendar(year, month)
dates_with_data = db.get_dates_with_data(year, month)

st.subheader(f"{year} 年 {month} 月")

# 顯示星期標題
header_cols = st.columns(7)
for i, day_name in enumerate(WEEKDAYS):
    header_cols[i].markdown(f"**{day_name}**")

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

                # 決定按鈕樣式
                if has_data:
                    button_label = f"🟢 {day}"
                elif has_input:
                    button_label = f"📝 {day}"
                else:
                    button_label = str(day)

                if st.button(button_label, key=f"day_{day}", width='stretch'):
                    st.session_state.selected_date = day


# ========== 日期輸入對話框 ==========

if st.session_state.selected_date:
    day = st.session_state.selected_date
    date_title = format_date_title(year, month, day)
    date_str = f"{year}-{month:02d}-{day:02d}"

    st.divider()
    st.subheader(f"📅 {date_title}")

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

    # 輸入區域
    current_text = st.session_state.calendar_data.get(day, "")
    input_text = st.text_area(
        "輸入記帳資料",
        value=current_text,
        height=200,
        key=f"input_{day}",
        placeholder=f"""範例（日期行會被忽略）：
{month}/{day}（{get_weekday_name(year, month, day)}）
早餐：小明、小華
中餐：阿鵰、泰禎
點心：阿鵰點心+60
晚餐：傑森*2
牛奶*1.5：小明"""
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 暫存", width='stretch'):
            st.session_state.calendar_data[day] = input_text
            st.success("已暫存")

    with col2:
        if st.button("✅ 儲存並關閉", type="primary", width='stretch'):
            if input_text.strip():
                result = process_single_day(year, month, day, input_text)
                if result["status"] == "success":
                    st.success(result["message"])
                elif result["status"] == "warning":
                    st.warning(result["message"])
                # 清除暫存
                if day in st.session_state.calendar_data:
                    del st.session_state.calendar_data[day]
            st.session_state.selected_date = None
            st.rerun()

    with col3:
        if st.button("❌ 取消", width='stretch'):
            st.session_state.selected_date = None
            st.rerun()

    # 即時預覽
    if input_text.strip():
        st.divider()
        st.write("**預覽解析結果：**")
        preview_result = parse_accounting_text(input_text, target_date=date_str)

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
st.caption("直接貼入整個月的原始文字，parser 會自動依日期行分組處理")

bulk_text = st.text_area(
    "貼入記帳文字（需包含日期行，如 `3/1（日）`）",
    height=300,
    key="bulk_input_text",
    placeholder="""範例：
3/1（日）
早餐：小明、小華
晚餐：阿鵰*2、泰禎

3/2（一）
早餐：小明
牛奶*1.5：阿鵰、泰禎"""
)

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
    if st.button("✅ 解析並儲存整月資料", type="primary", disabled=not bulk_text.strip(), key="bulk_save"):
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
