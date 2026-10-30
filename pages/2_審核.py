"""審核頁面 - 處理待審核的項目"""
import html

import streamlit as st

import database as db
from ui import apply_theme, empty_state, page_header, pill


st.set_page_config(page_title="審核", page_icon="🔍", layout="wide")
apply_theme()
page_header("待審核項目", "校對：處理無法自動辨識的人名，設為別名、新增人員或忽略")

# 取得待審核項目
pending_items = db.get_all_pending_reviews()
persons = db.get_all_persons()
person_names = [p["name"] for p in persons]

# 人員與別名管理（原本在側邊欄）
with st.container(horizontal=True, vertical_alignment="center", key="toolbar"):
    people_box = st.popover("👥 人員與別名")
    st.html(f'<span style="color:var(--ink2);font-size:.88rem">共 {len(persons)} 人；新增人員、編輯別名都在這裡</span>')

sum1, sum2, sum3 = st.columns(3)
sum1.metric("待審核", len(pending_items))
sum2.metric("人員數", len(persons))
sum3.metric("別名總數", sum(len([a for a in (p["aliases"] or "").split(",") if a.strip()]) for p in persons))
st.html("<div style='height:.6rem'></div>")

if not pending_items:
    empty_state("✅", "沒有待審核的項目", "所有無法辨識的名稱都已處理完畢")
else:
    for item in pending_items:
        with st.container(border=True):
            col1, col2 = st.columns([2, 3])

            with col1:
                st.html(
                    f'<div class="rv-raw">{html.escape(item["raw_text"])}</div>'
                    f'<div class="rv-meta">{pill(html.escape(str(item["date"])), "accent")}'
                    f'<span class="mut">建立於 {html.escape(str(item["created_at"])[:16].replace("T", " "))}</span></div>'
                )
                st.caption("來源行")
                st.code(item["source_line"], language=None)

            with col2:
                st.caption("處理方式")

                # 選項 1：是某人的別名
                if person_names:
                    selected_person = st.selectbox(
                        "選擇人員",
                        options=person_names,
                        index=None,
                        placeholder="選擇要設為別名的人員",
                        key=f"person_select_{item['id']}",
                        label_visibility="collapsed"
                    )

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        if st.button(
                            f"是「{selected_person}」的別名" if selected_person else "設為某人的別名",
                            key=f"alias_{item['id']}",
                            type="primary",
                            disabled=not selected_person
                        ):
                            # 找到該人員並新增別名
                            for p in persons:
                                if p["name"] == selected_person:
                                    db.add_alias_to_person(p["id"], item["raw_text"])
                                    break

                            # 刪除待審核項目
                            db.delete_pending_review(item["id"])
                            st.toast(f"已將「{item['raw_text']}」加為「{selected_person}」的別名")
                            st.rerun()

                    with col_b:
                        if st.button("是新人員", key=f"new_person_{item['id']}"):
                            try:
                                db.add_person(item["raw_text"])
                                db.delete_pending_review(item["id"])
                                st.toast(f"已新增人員：{item['raw_text']}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"新增失敗：{e}")

                    with col_c:
                        if st.button("忽略此項", key=f"ignore_{item['id']}"):
                            db.delete_pending_review(item["id"])
                            st.toast("已忽略")
                            st.rerun()
                else:
                    st.warning("尚無人員資料，請先到輸入頁面新增人員")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("新增為人員", key=f"new_person_{item['id']}"):
                            try:
                                db.add_person(item["raw_text"])
                                db.delete_pending_review(item["id"])
                                st.toast(f"已新增人員：{item['raw_text']}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"新增失敗：{e}")

                    with col_b:
                        if st.button("忽略", key=f"ignore_{item['id']}"):
                            db.delete_pending_review(item["id"])
                            st.toast("已忽略")
                            st.rerun()


# ========== 人員與別名（popover 內容） ==========

with people_box:
    if persons:
        for p in persons:
            with st.expander(p["name"]):
                st.write(f"**別名：** {p['aliases'] or '無'}")

                # 編輯別名
                new_aliases = st.text_input(
                    "編輯別名（逗號分隔）",
                    value=p["aliases"],
                    key=f"edit_alias_{p['id']}"
                )
                if st.button("更新別名", key=f"update_alias_{p['id']}"):
                    db.update_person_aliases(p["id"], new_aliases)
                    st.toast("已更新", icon="✅")
                    st.rerun()

                # 刪除人員
                if st.button("🗑️ 刪除人員", key=f"delete_person_{p['id']}"):
                    db.delete_person(p["id"])
                    st.toast(f"已刪除：{p['name']}", icon="🗑️")
                    st.rerun()
    else:
        st.info("尚無人員資料")

    st.divider()

    # 快速新增人員
    st.write("**快速新增人員**")
    quick_name = st.text_input("姓名", key="quick_add_name")
    quick_aliases = st.text_input("別名（選填）", key="quick_add_aliases")
    if st.button("新增", key="quick_add_btn"):
        if quick_name:
            try:
                db.add_person(quick_name, quick_aliases)
                st.toast(f"已新增：{quick_name}", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"新增失敗：{e}")
