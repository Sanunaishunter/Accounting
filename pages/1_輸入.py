"""輸入頁面 - 校對：點右邊的日期，左邊顯示該天的原始資料與魔法整理後的資料"""
import calendar
from datetime import datetime

import streamlit as st

import database as db
from dayinput import find_raw, raw_input_days
from normalizer import DEFAULT_CATEGORIES, normalize_day
from parser import ParseStatus, parse_accounting_text
from ui import (apply_theme, cn_date, cn_int, cn_year, diff_marks, edict_end, edict_head, edict_idle, is_mobile,
                pane_label, pill, stamp)


st.set_page_config(page_title="輸入記帳", page_icon="📝", layout="wide")
apply_theme()
MOBILE = is_mobile()

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]  # 中文星期（週一開始）

if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "selected_ym" not in st.session_state:
    st.session_state.selected_ym = None


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


def magic_day(date_str: str, header: str) -> None:
    """「來點魔法」callback：原始資料 -> 魔法整理後"""
    result = normalize_day(st.session_state[f"raw_{date_str}"], header, **normalize_options())
    st.session_state[f"magic_{date_str}"] = result.text
    st.session_state[f"res_{date_str}"] = result
    st.session_state[f"snap_{date_str}"] = st.session_state[f"raw_{date_str}"]


def load_day(date_str: str, year: int, month: int, day: int, header: str) -> None:
    """第一次看這天時，載入已儲存的資料；沒存過就找原文並自動魔法一次"""
    if f"raw_{date_str}" in st.session_state:
        return
    saved = db.get_day_input(date_str)
    result = None
    if saved:
        raw, magic, source = saved["raw_text"], saved["magic_text"], "已儲存"
        # 重算一次只為了拿到「需要確認」的提示；內容和存的不一樣就不顯示
        recomputed = normalize_day(raw, header, **normalize_options())
        result = recomputed if recomputed.text.strip() == magic.strip() else None
    else:
        found = find_raw(year, month, day)
        raw, source = found if found else ("", "沒有找到原始資料")
        magic = ""
        if raw.strip():
            result = normalize_day(raw, header, **normalize_options())
            magic = result.text
    st.session_state[f"raw_{date_str}"] = raw
    st.session_state[f"magic_{date_str}"] = magic
    st.session_state[f"res_{date_str}"] = result
    st.session_state[f"snap_{date_str}"] = raw
    st.session_state[f"src_{date_str}"] = source
    st.session_state[f"saved_{date_str}"] = bool(saved)
    st.session_state[f"reviewed_{date_str}"] = bool(saved and saved["reviewed"])


def toggle_review(date_str: str, header: str) -> None:
    """「閱」章 callback：沒蓋就儲存並蓋章；已經蓋了就收回章（資料不動）"""
    if st.session_state[f"reviewed_{date_str}"]:
        db.set_day_reviewed(date_str, False)
        st.toast(f"{header} 收回閱章", icon="↩️")
    else:
        try:
            save_day(date_str, st.session_state[f"raw_{date_str}"], st.session_state[f"magic_{date_str}"], True)
        except Exception as e:
            st.toast(f"儲存失敗：{e}", icon="⚠️")
            return
        st.toast(f"{header} 閱", icon="🈶")
    forget_day(date_str)


def forget_day(date_str: str) -> None:
    for prefix in ("raw", "magic", "res", "snap", "src", "saved", "reviewed"):
        st.session_state.pop(f"{prefix}_{date_str}", None)


def save_day(date_str: str, raw: str, magic: str, reviewed: bool | None = None) -> dict:
    """儲存：用「魔法整理後」（空的話用原始資料）取代這天已入帳的資料，並記下兩邊的文字"""
    text = magic if magic.strip() else raw
    parsed = parse_accounting_text(text, target_date=date_str)
    db.delete_day_data(date_str)
    parsed = parse_accounting_text(text, target_date=date_str)  # 刪掉舊資料後重解析，才不會被當成重複
    result = {"success": 0, "pending": 0, "memo": 0}
    for exp in parsed.expenses:
        if exp.status == ParseStatus.SUCCESS:
            db.add_expense(date=exp.date, category=exp.category, person=exp.person,
                           amount=exp.amount, quantity=exp.quantity, note=exp.note)
            result["success"] += 1
    for item in parsed.pending:
        db.add_pending_review(raw_text=item["raw_text"], source_line=item["source_line"], date=item["date"])
        result["pending"] += 1
    for memo in parsed.memos:
        db.add_memo(memo.date, memo.content, memo.person)
        result["memo"] += 1
    db.save_day_input(date_str, raw, magic, reviewed)
    return result


# ========== 頂端功能列：年月、動作按鈕 ==========

now = datetime.now()
if MOBILE:
    tb_year, tb_month, _ = st.container(key="ymbar").columns(3, vertical_alignment="bottom")
    toolbar = None
else:
    toolbar = st.container(horizontal=True, vertical_alignment="bottom", key="toolbar")
    tb_year = tb_month = toolbar

with tb_year:
    year = st.selectbox("年份", options=list(range(now.year - 2, now.year + 2)), index=2, key="select_year",
                        width="stretch" if MOBILE else 110)
with tb_month:
    month = st.selectbox("月份", options=list(range(1, 13)), index=now.month - 1, key="select_month",
                         width="stretch" if MOBILE else 90)

if st.session_state.selected_ym != (year, month):  # 換月份就不再停在上個月的某一天
    st.session_state.selected_ym = (year, month)
    st.session_state.selected_date = None


# ========== 版面：桌面 左 60% 校對／右 40% 月曆；手機 月曆在上、校對在下 ==========
# 先畫月曆（點日期會改 selected_date），再畫校對區

if MOBILE:
    cal_area = st.container()
    main_area = st.container()
else:
    main_area, cal_area = st.columns([6, 4], gap="large")

month_days = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
dates_with_data = db.get_dates_with_data(year, month)
daily_totals = db.get_daily_totals(year, month)
reviewed_days = db.get_reviewed_days(year, month)
waiting_days = sorted(set(raw_input_days(year, month)) - reviewed_days)  # 有原始資料、還沒蓋閱章的日子

with cal_area:
    with st.container(key="calwrap"):
        waiting_note = f"・待批閱 {len(waiting_days)} 天" if waiting_days else ""
        st.html(f'<div class="cal-month">{cn_year(year)}　{cn_int(month) + '月'}'
                f'<small>已入帳 {len(dates_with_data)} 天{waiting_note}</small></div>')
        with st.container(key="calendar"):
            header_cols = st.columns(7)
            for i, day_name in enumerate(WEEKDAYS):
                header_cols[i].html(f'<div class="cal-wd">{day_name}</div>')

            for week in month_days:
                cols = st.columns(7)
                for i, d in enumerate(week):
                    with cols[i]:
                        if d == 0:
                            st.write("")
                            continue
                        amount = daily_totals.get(d, 0)
                        label = f"**{d}**  \n:gray[:small[{amount:,.0f}]]" if d in dates_with_data and amount else f"**{d}**"
                        st.button(label, key=f"day_{d}", width="stretch", on_click=select_day, args=(d,))
        st.html(
            '<div class="cal-legend"><span><i style="background:rgba(232,199,99,.7)"></i>已入帳</span>'
            '<span><i style="border-radius:50%;border:1.5px solid var(--red)"></i>待批閱</span>'
            '<span><i style="background:var(--red)"></i>已閱</span>'
            '<span><i style="outline:2px solid var(--red);outline-offset:-2px"></i>展開中</span></div>'
            f'<div class="cal-total"><span>{cn_int(month) + '月'}已入帳合計</span>'
            f'<b>${sum(daily_totals.values()):,.0f}</b></div>'
        )

# 月曆格子的狀態樣式（依資料動態產生）：金底＝已入帳、紅圈＝待批閱、紅色「閱」章＝已閱、紅框＋摺角＝展開中
_css = "".join(f".st-key-day_{d} button{{background:rgba(232,199,99,.5)!important}}" for d in dates_with_data)
_css += "".join(f".st-key-day_{d} button::after{{content:'';position:absolute;right:8px;top:9px;width:7px;height:7px;"
                f"border-radius:50%;border:1.5px solid var(--red)}}" for d in waiting_days)
_css += "".join(f".st-key-day_{d} button::after{{content:'閱';position:absolute;right:5px;top:5px;width:19px;height:19px;"
                f"background:var(--red);color:#FFE9B0;font:700 13px/19px var(--kai);text-align:center;"
                f"transform:rotate(6deg);border-radius:2px}}" for d in reviewed_days)
if st.session_state.selected_date:
    _css += (f".st-key-day_{st.session_state.selected_date} button{{background:var(--paper)!important;"
             f"outline:2.5px solid var(--red);outline-offset:-2.5px;position:relative;z-index:2;"
             f"box-shadow:0 4px 10px rgba(120,60,20,.35)}}"
             f".st-key-day_{st.session_state.selected_date} button::before{{content:'';position:absolute;right:0;top:0;"
             f"border-style:solid;border-width:0 18px 18px 0;border-color:transparent var(--red) transparent transparent}}")
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)


# ========== 校對區：原始資料 | 魔法整理後 ==========

with main_area, st.container(key="scroll"):
    day = st.session_state.selected_date
    edict_head()

    if not day:
        edict_idle()
        if waiting_days:
            st.caption(f"{month} 月還有 {len(waiting_days)} 天待批閱（日期旁有紅圈）")
        if not MOBILE:
            toolbar.space("stretch")
            for label in ("✎ 來點魔法", "儲存", "儲存並看下一天", "取消"):
                toolbar.button(label, disabled=True, key=f"idle_{label}")
    else:
        date_str = f"{year}-{month:02d}-{day:02d}"
        weekday = WEEKDAYS[calendar.weekday(year, month, day)]
        header = f"{month}/{day}（{weekday}）"
        load_day(date_str, year, month, day, header)

        raw_now = st.session_state.get(f"raw_{date_str}", "")
        magic_now = st.session_state.get(f"magic_{date_str}", "")
        result = st.session_state.get(f"res_{date_str}")
        saved = st.session_state[f"saved_{date_str}"]
        reviewed = st.session_state[f"reviewed_{date_str}"]
        source = st.session_state[f"src_{date_str}"]
        stale = bool(magic_now.strip()) and st.session_state.get(f"snap_{date_str}") != raw_now

        # 標題＋狀態
        state_pill = (pill("✓ 已閱", "ok") if reviewed
                      else pill("已存檔・未閱", "warn") if saved else pill("尚未存檔", "warn"))
        st.html(
            f'<div class="day-title">{cn_date(month, day)}<small>星期{weekday}</small>'
            f'{state_pill}{pill(source, "neutral")}</div>'
        )

        # 動作按鈕：桌面在頂端功能列右側，手機在標題下方
        if MOBILE:
            slot_magic, slot_save, slot_next, slot_cancel = st.container(key="actions").columns(4)
            labels = ("✎魔法", "儲存", "下一天", "取消")
        else:
            toolbar.space("stretch")
            slot_magic = slot_save = slot_next = slot_cancel = toolbar
            labels = ("✎ 來點魔法", "儲存", "儲存並看下一天", "取消")
        btn_w = "stretch" if MOBILE else "content"

        # 批改紀錄用「目前」的兩邊文字比對（widget 狀態在腳本開跑前就已更新）
        n_marks, marks_html = diff_marks(raw_now, magic_now) if magic_now.strip() else (0, "")
        out_badge = (stamp("已整理") if result is not None and result.ok and magic_now.strip() and not stale
                     else pill(f"{n_marks} 處修改" if n_marks else "可手動修改", "accent"))

        raw_text_now = raw_now
        left, right = st.columns(2)
        with left:
            pane_label("原　奏", pill("可手動修改", "neutral"))
            raw_text = st.text_area("原始資料", key=f"raw_{date_str}", label_visibility="collapsed", height=360,
                                    placeholder="這天沒有找到原始資料，可以直接貼上或手打")
        with right:
            # 標題列：魔法整理後 ……… 已整理（印章）＋ 閱（按下去蓋章）
            with st.container(horizontal=True, vertical_alignment="center", key="pane_head"):
                st.html('<span class="pane-label"><span class="t">魔法聖旨</span></span>')
                st.space("stretch")
                st.html(out_badge)
                st.button("閱", key="yue_on" if reviewed else "yue_off", on_click=toggle_review,
                          args=(date_str, header), disabled=not (raw_text_now.strip() or magic_now.strip()),
                          help="收回閱章（資料不動）" if reviewed else "校對完了：儲存並蓋上「閱」章")
            magic_text = st.text_area("魔法整理後", key=f"magic_{date_str}", label_visibility="collapsed", height=360,
                                      placeholder="按「✎ 來點魔法」，整理後的文字會出現在這裡")

        slot_magic.button(labels[0], on_click=magic_day, args=(date_str, header), disabled=not raw_text.strip(),
                          key=f"magic_btn_{date_str}", width=btn_w,
                          help="把 ⚠️ 備忘整理成一品項一行（金額統一為 +$金額），並把類別行裡不是人名的項目拉成 ⚠️ 備忘")

        # 校對輔助：魔法檢查結果 → 批改紀錄
        if stale:
            st.html(pill("原始資料已修改，右邊是舊的整理結果，請重新「來點魔法」", "warn"))
        elif result is not None and magic_text.strip():
            if result.ok:
                st.html(pill("✓ 自動檢查通過", "ok"))
            else:
                st.warning("自動檢查發現 {} 個問題，請先確認：\n\n".format(len(result.problems))
                           + "\n".join(f"- {p}" for p in result.problems))
            if result.flags:
                with st.expander(f"需要你確認的 {len(result.flags)} 處", expanded=True):
                    for flag in result.flags:
                        st.text(flag)
        if marks_html:
            st.html(marks_html)

        # 儲存的內容：右邊有東西就用右邊，否則用左邊
        to_save = magic_text if magic_text.strip() else raw_text
        st.caption("儲存會用右邊的內容取代這天已入帳的資料；右邊留空則用左邊原始資料")

        # 預覽解析結果（儲存後會寫進資料庫的樣子）
        existing_expenses = db.get_expenses_by_date(date_str)
        existing_memos = db.get_memos_by_date(date_str)
        if to_save.strip():
            preview = parse_accounting_text(to_save, target_date=date_str)
            # 這天已入帳的項目會被解析成「重複」，但儲存會取代舊資料，所以一起列出
            ok_items = [e for e in preview.expenses if e.status == ParseStatus.SUCCESS] + list(preview.duplicates)
            pending_pill = pill(f"{len(preview.pending)} 筆無法辨識", "warn") if preview.pending else ""
            st.html(
                f'<div class="day-head">{pill(f"{len(ok_items)} 筆支出", "ok")}'
                f'{pill(f"{len(preview.memos)} 筆備忘", "neutral")}{pending_pill}</div>'
            )
            if ok_items:
                st.dataframe(
                    [{"類別": e.category, "人員": e.person, "單價": e.amount, "數量": e.quantity,
                      "小計": e.amount * e.quantity} for e in ok_items],
                    hide_index=True, width="stretch", height=min(36 * len(ok_items) + 40, 320), alt="解析後會寫入的支出",
                    column_config={"單價": st.column_config.NumberColumn(format="$%d"),
                                   "數量": st.column_config.NumberColumn(format="%g"),
                                   "小計": st.column_config.NumberColumn(format="$%.0f")},
                )
            for item in preview.pending:
                st.warning(f"無法辨識：「{item['raw_text']}」（儲存後會送到審核頁）")
        if existing_expenses or existing_memos:
            with st.expander(f"資料庫目前這天的內容（{len(existing_expenses)} 筆支出、{len(existing_memos)} 筆備忘）"):
                for exp in existing_expenses:
                    st.text(f"• {exp['category']} | {exp['person']} | ${exp['amount']} × {exp['quantity']}")
                for memo in existing_memos:
                    st.text(f"• 📝 {memo['content']}")
        st.html(edict_end(year, month, day, reviewed))

        # ===== 動作 =====
        def do_save(advance: bool) -> None:
            try:
                res = save_day(date_str, raw_text, magic_text, True if advance else None)
            except Exception as e:
                st.error(f"儲存失敗：{e}")
                return
            msg = f"{header} {'閱，' if advance else ''}已儲存：{res['success']} 筆支出、{res['memo']} 筆備忘"
            if res["pending"]:
                msg += f"，{res['pending']} 筆待審核"
            forget_day(date_str)
            others = [d for d in waiting_days if d != day]
            later = [d for d in others if d > day] or others
            if advance and later:
                st.session_state.selected_date = later[0]
                msg += f"；換到 {month}/{later[0]}"
            elif advance:
                st.session_state.selected_date = None
                msg += "；這個月沒有待批閱的日子了"
            st.toast(msg, icon="✅")
            st.rerun()

        if slot_save.button(labels[1], type="primary", width=btn_w, key="day_save"):
            do_save(advance=False)
        if slot_next.button(labels[2], width=btn_w, key="day_next"):
            do_save(advance=True)
        if slot_cancel.button(labels[3], width=btn_w, key="day_cancel"):
            forget_day(date_str)
            st.session_state.selected_date = None
            st.rerun()
