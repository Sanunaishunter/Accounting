"""記帳系統 - Streamlit 主程式"""
import streamlit as st
from datetime import datetime

import database as db


st.set_page_config(
    page_title="記帳系統",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💰 記帳系統")
st.write("解析半結構化中文記帳文字，產出統計報表")

# 顯示系統狀態
st.divider()

col1, col2, col3, col4 = st.columns(4)

# 統計資訊
persons = db.get_all_persons()
expenses = db.get_expenses()
pending = db.get_all_pending_reviews()
category_prices = db.get_all_category_prices()

with col1:
    st.metric("人員數", len(persons))

with col2:
    st.metric("支出記錄", len(expenses))

with col3:
    st.metric("待審核", len(pending))

with col4:
    if expenses:
        total = sum(e["amount"] * e["quantity"] for e in expenses)
        st.metric("總支出", f"${total:,.0f}")
    else:
        st.metric("總支出", "$0")


st.divider()

# 快速導覽
st.subheader("功能導覽")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("📝 **輸入頁面**\n\n月曆模式輸入，點擊日期輸入當日資料")

with col2:
    st.warning("🔍 **審核頁面**\n\n處理無法識別的人名，管理人員別名")

with col3:
    st.success("📊 **報表頁面**\n\n查看統計報表，匯出資料")


# 類別單價設定
st.divider()
st.subheader("類別單價設定")

with st.expander("編輯類別單價"):
    cols = st.columns(len(category_prices))
    for i, (category, price) in enumerate(category_prices.items()):
        with cols[i]:
            new_price = st.number_input(
                category,
                min_value=0,
                value=price,
                step=10,
                key=f"price_{category}"
            )
            if new_price != price:
                db.update_category_price(category, new_price)
                st.success(f"{category} 已更新為 ${new_price}")
                st.rerun()


# 最近記錄
if expenses:
    st.divider()
    st.subheader("最近記錄")

    # 取得最近的記錄（按日期排序）
    recent = sorted(expenses, key=lambda x: x["date"], reverse=True)[:10]

    for exp in recent:
        st.text(
            f"{exp['date']} | {exp['category']} | {exp['person']} | "
            f"${exp['amount']} × {exp['quantity']} = ${exp['amount'] * exp['quantity']}"
        )


# 側邊欄
with st.sidebar:
    st.header("記帳系統")
    st.caption(f"今天是 {datetime.now().strftime('%Y/%m/%d')}")

    st.divider()

    st.write("**支援的格式：**")
    st.code("""
1/19（一）
早餐：小明、小華
中餐：阿鵰、泰禎
點心：阿鵰點心+60
晚餐：傑森*2
牛奶*1.5：小明
⚠️ 備忘內容
    """, language=None)

    st.divider()

    st.write("**解析規則：**")
    st.write("- `類別：人名` 基本格式")
    st.write("- `人名+金額` 額外金額")
    st.write("- `人名*次數` 多次")
    st.write("- `類別*次數：` 預設次數")
    st.write("- `⚠️` 標記備忘")
