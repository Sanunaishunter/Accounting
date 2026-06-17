"""關係表管理頁面 - 管理備忘關鍵字與人員的代理對應關係"""
import streamlit as st

import database as db


st.set_page_config(page_title="關係表", page_icon="🔗", layout="wide")
st.title("🔗 關係表管理")
st.caption("設定備忘關鍵字與人員的對應關係。解析 ⚠️ 備忘時，內容包含關鍵字則自動掛到對應人員下。")

# ========== 現有對應列表 ==========

proxies = db.get_person_proxies()
persons = db.get_all_persons()
person_names = [p["name"] for p in persons]

st.subheader("現有對應")

if not proxies:
    st.info("尚無對應關係，請在下方新增。")
else:
    for proxy in proxies:
        with st.container(border=True):
            col_info, col_edit, col_del = st.columns([4, 4, 1])

            with col_info:
                st.markdown(f"**{proxy['keyword']}** → `{proxy['proxy_for']}`")
                if proxy["note"]:
                    st.caption(proxy["note"])

            with col_edit:
                with st.expander("編輯"):
                    new_keyword = st.text_input(
                        "關鍵字",
                        value=proxy["keyword"],
                        key=f"kw_{proxy['id']}",
                    )
                    new_proxy_for = st.selectbox(
                        "代理人員",
                        options=person_names,
                        index=person_names.index(proxy["proxy_for"]) if proxy["proxy_for"] in person_names else 0,
                        key=f"pf_{proxy['id']}",
                    )
                    new_note = st.text_input(
                        "說明",
                        value=proxy["note"] or "",
                        key=f"note_{proxy['id']}",
                    )
                    if st.button("更新", key=f"upd_{proxy['id']}"):
                        db.update_person_proxy(proxy["id"], new_keyword, new_proxy_for, new_note)
                        st.success("已更新")
                        st.rerun()

            with col_del:
                st.write("")  # 對齊用
                if st.button("❌", key=f"del_{proxy['id']}", help="刪除此對應"):
                    db.delete_person_proxy(proxy["id"])
                    st.warning(f"已刪除「{proxy['keyword']}」")
                    st.rerun()


# ========== 新增對應 ==========

st.divider()
st.subheader("新增對應")

with st.form("add_proxy_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        new_keyword = st.text_input("關鍵字", placeholder="例：外婆")
    with col2:
        new_proxy_for = st.selectbox("代理人員", options=[""] + person_names)
    with col3:
        new_note = st.text_input("說明（選填）", placeholder="例：崴崴的外婆")

    submitted = st.form_submit_button("新增", type="primary")
    if submitted:
        if not new_keyword or not new_proxy_for:
            st.error("關鍵字與代理人員皆為必填")
        else:
            try:
                db.add_person_proxy(new_keyword, new_proxy_for, new_note)
                st.success(f"已新增：「{new_keyword}」→ {new_proxy_for}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ========== 側邊欄說明 ==========

with st.sidebar:
    st.subheader("使用說明")
    st.write("**格式範例：**")
    st.code("⚠️台北媽媽家檯燈1499⚠️", language=None)
    st.write("若「台北媽媽」已設為牧恩的關鍵字，此備忘會自動掛到牧恩的報表下。")
    st.divider()
    st.write("**目前關鍵字數量：**", len(proxies))
    if proxies:
        for p in proxies:
            st.text(f"• {p['keyword']} → {p['proxy_for']}")
