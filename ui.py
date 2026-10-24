"""共用介面樣式與小元件（各頁在 set_page_config 之後呼叫 apply_theme）"""
import re

import streamlit as st

# 主色與狀態色；背景與邊框一律用半透明，深色／淺色主題都適用
ACCENT = "#4F6BED"
OK = "#1F9D6B"
WARN = "#D9822B"
DANGER = "#D64545"

_CSS = f"""
<style>
:root {{
  --acc: {ACCENT};
  --ok: {OK};
  --warn: {WARN};
  --danger: {DANGER};
  --line: rgba(128, 133, 149, .28);
  --soft: rgba(128, 133, 149, .08);
  --radius: 12px;
}}

/* ---- 版面 ---- */
html, body, [data-testid="stAppViewContainer"] {{
  font-family: "Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}}
[data-testid="stMainBlockContainer"] {{
  max-width: 1280px;
  padding-top: 2.2rem;
  padding-bottom: 5rem;
}}
#MainMenu, footer, [data-testid="stDecoration"], .stDeployButton {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
/* 只放 <style> 的區塊不佔位 */
[data-testid="stElementContainer"]:has(style) {{ display: none; }}

/* ---- 標題 ---- */
h1, h2, h3 {{ letter-spacing: -.01em; font-weight: 650 !important; }}
h2 {{ font-size: 1.35rem !important; padding-top: .6rem !important; }}
h3 {{ font-size: 1.1rem !important; }}
hr {{ border-color: var(--line) !important; margin: 1.6rem 0 !important; opacity: .7; }}
.pg-head {{ margin: 0 0 1.4rem; }}
.pg-eyebrow {{ font-size: .72rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--acc); }}
.pg-title {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.25; margin: .15rem 0 .25rem; }}
.pg-sub {{ opacity: .62; font-size: .95rem; }}

/* ---- 按鈕 ---- */
.stButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {{
  border-radius: 9px;
  font-weight: 550;
  letter-spacing: .01em;
  border: 1px solid var(--line);
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
}}
.stButton > button:hover:not(:disabled) {{
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(79, 107, 237, .18);
  border-color: var(--acc);
}}
[data-testid="stBaseButton-primary"] {{
  background: var(--acc);
  border-color: var(--acc);
  box-shadow: 0 1px 2px rgba(79, 107, 237, .35);
}}
[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ filter: brightness(1.08); }}

/* ---- 卡片：有邊框的容器、指標、展開區 ---- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  border-radius: var(--radius);
}}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--line) !important; }}
[data-testid="stMetric"] {{
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem 1.15rem;
  background: var(--soft);
}}
[data-testid="stMetricLabel"] {{ opacity: .65; font-size: .8rem; font-weight: 550; }}
[data-testid="stMetricValue"] {{ font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }}
[data-testid="stExpander"] {{ border: 1px solid var(--line); border-radius: var(--radius); background: transparent; }}
[data-testid="stExpander"] summary {{ font-weight: 550; }}
[data-testid="stAlert"] {{ border-radius: var(--radius); border: 1px solid var(--line); }}

/* ---- 輸入框 ---- */
[data-testid="stTextArea"] textarea {{
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", "Noto Sans Mono CJK TC", "Noto Sans TC", Menlo, Consolas, monospace;
  font-size: .9rem;
  line-height: 1.65;
  border-radius: 10px;
}}
[data-testid="stTextArea"] textarea::placeholder {{ opacity: .4; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 550; font-size: .88rem; }}

/* ---- 側邊欄 ---- */
[data-testid="stSidebar"] {{ border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ font-size: .78rem !important; letter-spacing: .1em; text-transform: uppercase; opacity: .6; }}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; }}

/* ---- 自訂小元件 ---- */
.pill {{
  display: inline-flex; align-items: center; gap: .35rem;
  padding: .12rem .65rem; border-radius: 999px;
  font-size: .76rem; font-weight: 600; line-height: 1.6; white-space: nowrap;
  border: 1px solid transparent;
}}
.pill-neutral {{ background: var(--soft); border-color: var(--line); }}
.pill-accent {{ background: rgba(79,107,237,.14); color: var(--acc); border-color: rgba(79,107,237,.35); }}
.pill-ok {{ background: rgba(31,157,107,.14); color: var(--ok); border-color: rgba(31,157,107,.35); }}
.pill-warn {{ background: rgba(217,130,43,.15); color: var(--warn); border-color: rgba(217,130,43,.4); }}
.pane-label {{ display: flex; align-items: center; justify-content: space-between; margin: 0 0 .35rem; }}
.pane-label span.t {{ font-size: .8rem; font-weight: 650; opacity: .75; letter-spacing: .04em; }}
.day-head {{ display: flex; align-items: center; gap: .6rem; margin-bottom: .55rem; }}
.day-head .d {{ font-size: 1.05rem; font-weight: 700; letter-spacing: -.01em; }}
.steps {{ display: flex; gap: .5rem; flex-wrap: wrap; margin: .2rem 0 1rem; }}
.step {{ display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .8rem .35rem .4rem; border-radius: 999px;
         border: 1px solid var(--line); font-size: .85rem; font-weight: 550; }}
.step b {{ display: inline-grid; place-items: center; width: 1.45rem; height: 1.45rem; border-radius: 50%;
           background: var(--soft); font-size: .75rem; border: 1px solid var(--line); }}
.step.on {{ border-color: var(--acc); }}
.step.on b {{ background: var(--acc); color: #fff; border-color: var(--acc); }}
.step.done b {{ background: var(--ok); color: #fff; border-color: var(--ok); }}
.card-link {{ border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.2rem; height: 100%; background: var(--soft); }}
.card-link .ic {{ font-size: 1.3rem; }}
.card-link .tt {{ font-weight: 650; margin: .35rem 0 .2rem; }}
.card-link .ds {{ opacity: .65; font-size: .88rem; line-height: 1.55; }}
.rv-raw {{ font-size: 1.3rem; font-weight: 700; letter-spacing: -.01em; margin: .1rem 0 .55rem; word-break: break-all; }}
.rv-meta {{ display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; font-size: .85rem; margin-bottom: .5rem; }}
.rv-meta .mut {{ opacity: .55; }}
.rel-row {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }}
.rel-row .arrow {{ opacity: .4; }}
.rel-note {{ opacity: .6; font-size: .85rem; margin-top: .35rem; }}
.empty {{ text-align: center; border: 1px dashed var(--line); border-radius: var(--radius); padding: 2.4rem 1rem; margin: .5rem 0 1rem; }}
.empty .ic {{ font-size: 2rem; }}
.empty .tt {{ font-weight: 650; margin: .45rem 0 .2rem; }}
.empty .ds {{ opacity: .6; font-size: .9rem; }}

/* ---- 保持橫排的區塊（月曆、年月選擇、按鈕列）：用 st.container(key=...) 標記 ---- */
.st-key-calendar [data-testid="stHorizontalBlock"],
.st-key-actions [data-testid="stHorizontalBlock"],
.st-key-ymbar [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .35rem !important; }}
.st-key-calendar [data-testid="stColumn"],
.st-key-actions [data-testid="stColumn"],
.st-key-ymbar [data-testid="stColumn"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
.st-key-calendar .stButton > button {{ padding: 0 !important; }}
.st-key-calendar .stButton > button p {{ font-size: .85rem; white-space: nowrap; }}

/* ---- 手機寬度 ---- */
@media (max-width: 640px) {{
  /* 上方留白給左上角的選單按鈕，不要壓到頁首 */
  [data-testid="stMainBlockContainer"] {{ padding: 3.2rem .85rem 4rem; }}
  .pg-head {{ margin-bottom: 1rem; }}
  .pg-title {{ font-size: 1.5rem; }}
  .pg-sub {{ font-size: .88rem; }}
  h2 {{ font-size: 1.2rem !important; }}
  hr {{ margin: 1.1rem 0 !important; }}
  /* 指標卡：一排兩個 */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{ flex-wrap: wrap !important; gap: .6rem !important; }}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 1 1 calc(50% - .6rem) !important; min-width: calc(50% - .6rem) !important; }}
  [data-testid="stMetric"] {{ padding: .7rem .85rem; }}
  [data-testid="stMetricValue"] {{ font-size: 1.55rem; }}
  /* 好按的尺寸；輸入框 16px 以上，iPhone 才不會在聚焦時自動放大 */
  .stButton > button, .stDownloadButton > button, [data-testid^="stBaseButton"] {{ min-height: 2.75rem; }}
  input, textarea, [data-baseweb="select"] * {{ font-size: 16px !important; }}
  [data-testid="stTextArea"] textarea {{ line-height: 1.6; }}
  .st-key-calendar .stButton > button {{ min-height: 2.6rem; }}
  .st-key-actions .stButton > button {{ padding: .2rem .25rem; }}
  .st-key-actions .stButton > button p {{ font-size: .82rem; white-space: normal; line-height: 1.25; }}
  .steps {{ gap: .35rem; }}
  .step {{ font-size: .78rem; padding-right: .6rem; }}
  .report {{ padding: 1rem 1rem; }}
  .card-link {{ padding: .9rem 1rem; }}
  .pane-label span.t {{ font-size: .78rem; }}
}}
</style>
"""


_MOBILE_UA = re.compile(r"Mobi|Android|iPhone|iPod", re.I)  # iPad 當桌面，靠響應式 CSS 即可
VIEW_OPTIONS = ["自動", "手機版", "桌面版"]
_VIEW_QUERY = {"mobile": "手機版", "desktop": "桌面版"}


def is_mobile() -> bool:
    """目前是否使用手機版面：手動選擇優先，否則看 User-Agent"""
    mode = st.session_state.get("view_mode_sel", "自動")
    if mode == "手機版":
        return True
    if mode == "桌面版":
        return False
    try:
        agent = st.context.headers.get("User-Agent", "") or ""
    except Exception:  # 舊版 Streamlit 或沒有請求資訊（測試環境）
        agent = ""
    return bool(_MOBILE_UA.search(agent))


def apply_theme() -> None:
    """注入共用樣式與「顯示設定」；每頁在 st.set_page_config 之後呼叫一次"""
    # 這版 st.html 會濾掉 <style>，所以用 st.markdown
    st.markdown(_CSS, unsafe_allow_html=True)

    # 網址帶 ?view=mobile / ?view=desktop 可直接指定版面（第一次進來時生效）
    if "view_mode_sel" not in st.session_state:
        preset = _VIEW_QUERY.get(str(st.query_params.get("view", "")).lower())
        if preset:
            st.session_state["view_mode_sel"] = preset
    with st.sidebar:
        with st.expander("顯示設定"):
            st.radio("版面", VIEW_OPTIONS, key="view_mode_sel", horizontal=True,
                     help="自動：依裝置判斷；手機連線會用手機版面")


def page_header(title: str, subtitle: str = "", eyebrow: str = "記帳系統") -> None:
    sub = f'<div class="pg-sub">{subtitle}</div>' if subtitle else ""
    st.html(f'<div class="pg-head"><div class="pg-eyebrow">{eyebrow}</div><div class="pg-title">{title}</div>{sub}</div>')


def pill(text: str, kind: str = "neutral") -> str:
    """回傳標籤的 HTML 字串（kind: neutral / accent / ok / warn）"""
    return f'<span class="pill pill-{kind}">{text}</span>'


def pane_label(text: str, badge: str = "") -> None:
    st.html(f'<div class="pane-label"><span class="t">{text}</span>{badge}</div>')


def steps(active: int, done: int = 0) -> None:
    """三步驟指示：1 貼上 → 2 整理 → 3 寫入。active 為目前步驟，done 為已完成的步驟數"""
    labels = ["貼上原始文字", "來點魔法", "寫入資料庫"]
    html = ""
    for i, label in enumerate(labels, 1):
        cls = "done" if i <= done else "on" if i == active else ""
        mark = "✓" if i <= done else str(i)
        html += f'<span class="step {cls}"><b>{mark}</b>{label}</span>'
    st.html(f'<div class="steps">{html}</div>')


def card(icon: str, title: str, desc: str) -> None:
    st.html(f'<div class="card-link"><div class="ic">{icon}</div><div class="tt">{title}</div><div class="ds">{desc}</div></div>')


def empty_state(icon: str, title: str, desc: str = "") -> None:
    st.html(f'<div class="empty"><div class="ic">{icon}</div><div class="tt">{title}</div><div class="ds">{desc}</div></div>')
