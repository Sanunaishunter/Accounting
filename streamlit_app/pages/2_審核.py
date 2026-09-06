"""審核頁面 - 處理待審核的項目"""
import streamlit as st

import database as db


st.set_page_config(page_title="審核", page_icon="🔍", layout="wide")
st.title("🔍 待審核項目")

# 取得待審核項目
pending_items = db.get_all_pending_reviews()
persons = db.get_all_persons()
person_names = [p["name"] for p in persons]

if not pending_items:
    st.success("沒有待審核的項目！")
    st.balloons()
else:
    st.info(f"共有 {len(pending_items)} 筆待審核項目")

    for item in pending_items:
        with st.container():
            st.divider()
            col1, col2 = st.columns([2, 3])

            with col1:
                st.write(f"**原始文字：** {item['raw_text']}")
                st.write(f"**來源行：** {item['source_line']}")
                st.write(f"**日期：** {item['date']}")
                st.caption(f"建立時間：{item['created_at']}")

            with col2:
                st.write("**處理選項：**")

                # 選項 1：是某人的別名
                if person_names:
                    selected_person = st.selectbox(
                        "選擇人員",
                        options=[""] + person_names,
                        key=f"person_select_{item['id']}",
                        label_visibility="collapsed"
                    )

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        if st.button(
                            f"是「{selected_person}」的別名",
                            key=f"alias_{item['id']}",
                            disabled=not selected_person
                        ):
                            # 找到該人員並新增別名
                            for p in persons:
                                if p["name"] == selected_person:
                                    db.add_alias_to_person(p["id"], item["raw_text"])
                                    break

                            # 刪除待審核項目
                            db.delete_pending_review(item["id"])
                            st.success(f"已將「{item['raw_text']}」加為「{selected_person}」的別名")
                            st.rerun()

                    with col_b:
                        if st.button("是新人員", key=f"new_person_{item['id']}"):
                            try:
                                db.add_person(item["raw_text"])
                                db.delete_pending_review(item["id"])
                                st.success(f"已新增人員：{item['raw_text']}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"新增失敗：{e}")

                    with col_c:
                        if st.button("忽略此項", key=f"ignore_{item['id']}"):
                            db.delete_pending_review(item["id"])
                            st.info("已忽略")
                            st.rerun()
                else:
                    st.warning("尚無人員資料，請先到輸入頁面新增人員")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("新增為人員", key=f"new_person_{item['id']}"):
                            try:
                                db.add_person(item["raw_text"])
                                db.delete_pending_review(item["id"])
                                st.success(f"已新增人員：{item['raw_text']}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"新增失敗：{e}")

                    with col_b:
                        if st.button("忽略", key=f"ignore_{item['id']}"):
                            db.delete_pending_review(item["id"])
                            st.info("已忽略")
                            st.rerun()

# 側邊欄：人員管理
with st.sidebar:
    st.subheader("人員列表")

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
                    st.success("已更新")
                    st.rerun()

                # 刪除人員
                if st.button("🗑️ 刪除人員", key=f"delete_person_{p['id']}"):
                    db.delete_person(p["id"])
                    st.warning(f"已刪除：{p['name']}")
                    st.rerun()
    else:
        st.info("尚無人員資料")

    st.divider()

    # 快速新增人員
    st.subheader("快速新增人員")
    quick_name = st.text_input("姓名", key="quick_add_name")
    quick_aliases = st.text_input("別名（選填）", key="quick_add_aliases")
    if st.button("新增", key="quick_add_btn"):
        if quick_name:
            try:
                db.add_person(quick_name, quick_aliases)
                st.success(f"已新增：{quick_name}")
                st.rerun()
            except Exception as e:
                st.error(f"新增失敗：{e}")
