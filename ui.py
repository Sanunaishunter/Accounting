"""共用介面樣式與小元件（各頁在 set_page_config 之後呼叫 apply_theme）

視覺概念「紅筆批改」：稿紙白底＋淡綠格線，原稿用楷體、整理後用黑體；
紅色只留給「魔法／批改記號」，其餘用墨藍黑。
"""
import difflib
import html as _html
import re

import streamlit as st

# 墨色、批改紅、稿紙綠
INK = "#1E2A38"
RED = "#D23B2E"
GREEN = "#2F7D5B"
AMBER = "#B9741F"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;700&family=LXGW+WenKai+TC:wght@400;700&display=swap');
:root {{
  --paper: #FBFCF9;
  --wash: #EDF5EF;
  --grid: #CDE2D6;
  --ink: {INK};
  --ink2: #5E6D7C;
  --line: #D6DED8;
  --red: {RED};
  --green: {GREEN};
  --amber: {AMBER};
  --acc: {RED};
  --soft: var(--wash);
  --radius: 6px;
  --sans: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", "Noto Sans CJK TC", system-ui, sans-serif;
  --ming: "Noto Serif TC", "AR PL UMing TW", "PMingLiU", "Songti TC", serif;
  --kai: "LXGW WenKai TC", "AR PL UKai TW", "BiauKai", "Kaiti TC", "KaiTi", serif;
}}

/* ---- 版面 ---- */
html, body, [data-testid="stAppViewContainer"] {{ font-family: var(--sans); -webkit-font-smoothing: antialiased; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1400px; padding: 0 2.5rem 5rem; }}
#MainMenu, footer, [data-testid="stDecoration"], .stDeployButton, [data-testid="stHeader"] {{ display: none !important; }}
/* 只放 <style> 的區塊不佔位 */
[data-testid="stElementContainer"]:has(style) {{ display: none; }}

/* ---- 標題 ---- */
h1, h2, h3 {{ font-family: var(--ming) !important; letter-spacing: .01em; font-weight: 700 !important; color: var(--ink); }}
h2 {{ font-size: 1.45rem !important; padding-top: .6rem !important; }}
h3 {{ font-size: 1.2rem !important; }}
hr {{ border-color: var(--line) !important; margin: 1.6rem 0 !important; opacity: 1; }}
.pg-head {{ margin: 1.6rem 0 1.2rem; }}
.pg-title {{ font-family: var(--ming); font-size: 2.4rem; font-weight: 700; line-height: 1.15; }}
.pg-sub {{ color: var(--ink2); font-size: .95rem; margin-top: .35rem; }}

/* ---- 頂端導覽 ---- */
.st-key-topnav {{ align-items: center; gap: 2.2rem !important; height: 60px; border-bottom: 1px solid var(--line); margin: 0 -2.5rem; padding: 0 2.5rem; flex-wrap: nowrap !important; overflow-x: auto; scrollbar-width: none; }}
.st-key-topnav::-webkit-scrollbar {{ display: none; }}
.st-key-topnav > [data-testid="stElementContainer"], .st-key-topnav > [data-testid="stPageLink"] {{ flex: 0 0 auto; width: auto; }}
.st-key-topnav > *:has([data-testid="stPopover"]) {{ margin-left: auto; }}
.brand {{ display: flex; align-items: center; gap: .6rem; font-weight: 700; font-size: 1.05rem; white-space: nowrap; }}
.brand .seal {{ width: 30px; height: 30px; background: var(--red); color: #fff; display: grid; place-items: center; border-radius: 4px; font-family: var(--ming); font-size: 1.1rem; transform: rotate(-5deg); }}
.st-key-topnav [data-testid="stPageLink-NavLink"] {{ padding: .5rem .1rem; background: none !important; border-radius: 0; position: relative; color: var(--ink2); }}
.st-key-topnav [data-testid="stPageLink-NavLink"] p {{ font-size: .98rem; font-weight: 500; }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"] {{ color: var(--ink); }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"] p {{ font-weight: 700; }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"]::after {{ content: ""; position: absolute; left: -2px; right: -2px; bottom: -8px; height: 4px; border-radius: 4px; background: var(--red); transform: rotate(-.8deg); }}
.st-key-topnav [data-testid="stPopover"] button {{ border: none; background: none; color: var(--ink2); box-shadow: none; padding: 0 .2rem; min-height: 0; }}

/* ---- 功能列（年月、人員、動作按鈕） ---- */
.st-key-toolbar {{ border: none !important; border-bottom: 1px solid var(--line) !important; border-radius: 0 !important; background: #fff; margin: 0 -2.5rem 1.6rem; padding: .9rem 2.5rem !important; gap: 1.4rem !important; }}
.st-key-toolbar [data-testid="stSelectbox"] [data-baseweb="select"] > div {{ border: none; border-bottom: 1.5px solid var(--ink); border-radius: 0; background: transparent; font-weight: 600; }}

/* ---- 按鈕 ---- */
.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"], [data-testid="stPopover"] > button {{
  border-radius: 6px; font-weight: 600; border: 1.5px solid var(--ink); background: #fff; color: var(--ink);
  transition: background .12s ease, border-color .12s ease;
}}
.stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled) {{ background: var(--wash); border-color: var(--ink); color: var(--ink); }}
button[data-testid="stBaseButton-primary"] {{ background: var(--ink); border-color: var(--ink); color: #fff; }}
button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ background: #2C3B4E !important; color: #fff !important; }}
button[data-testid="stBaseButton-primary"]:not(:disabled) p {{ color: #fff; }}
button:disabled {{ background: var(--wash) !important; color: var(--ink2) !important; border-color: var(--line) !important; opacity: 1 !important; }}
button:disabled p {{ color: var(--ink2) !important; }}
/* 紅筆＝來點魔法 */
[class*="st-key-magic_btn"] button:not(:disabled), .st-key-bulk_magic_all button:not(:disabled), [class*="st-key-bulk_"][class*="_btn"] button:not(:disabled) {{ background: var(--red); border-color: var(--red); color: #fff; }}
[class*="st-key-magic_btn"] button:not(:disabled):hover, .st-key-bulk_magic_all button:not(:disabled):hover, [class*="st-key-bulk_"][class*="_btn"] button:not(:disabled):hover {{ background: #B93225 !important; border-color: #B93225 !important; color: #fff !important; }}
[class*="st-key-magic_btn"] button:not(:disabled) p, .st-key-bulk_magic_all button:not(:disabled) p, [class*="st-key-bulk_"][class*="_btn"] button:not(:disabled) p {{ color: #fff; }}

/* ---- 卡片：有邊框的容器、指標、展開區 ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--line) !important; border-radius: var(--radius); background: #fff; }}
[data-testid="stMetric"] {{ border: none; border-left: 3px solid var(--grid); border-radius: 0; padding: .1rem .9rem; background: none; }}
[data-testid="stMetricLabel"] {{ color: var(--ink2); font-size: .82rem; }}
[data-testid="stMetricValue"] {{ font-weight: 700; font-variant-numeric: tabular-nums; font-size: 1.9rem; }}
[data-testid="stExpander"] {{ border: 1px solid var(--line); border-radius: var(--radius); background: #fff; }}
[data-testid="stExpander"] summary {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: var(--radius); border: 1px solid var(--line); }}

/* ---- 稿紙：文字框畫成有橫線的稿紙，原稿用楷體 ---- */
[data-testid="stTextArea"] [data-baseweb="textarea"], [data-testid="stTextArea"] [data-baseweb="base-input"] {{ background: #fff !important; border: 1px solid var(--line); border-radius: 4px; }}
[data-testid="stTextArea"] textarea {{
  background-color: transparent;
  background-image:
    linear-gradient(90deg, transparent 22px, rgba(210,59,46,.35) 22px, rgba(210,59,46,.35) 23px, transparent 23px),
    repeating-linear-gradient(transparent 0 29px, var(--grid) 29px 30px);
  background-attachment: local;
  background-position: 0 0, 0 8px;
  font-family: var(--sans);
  font-size: 1rem;
  line-height: 30px;
  padding: 8px 14px 8px 34px;
  border-radius: 4px;
}}
[data-testid="stTextArea"] textarea::placeholder {{ opacity: .4; }}
[class*="st-key-raw_"] textarea {{ font-family: var(--kai); font-size: 1.15rem; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 600; font-size: .88rem; }}

/* ---- 自訂小元件 ---- */
.pill {{
  display: inline-flex; align-items: center; gap: .35rem;
  padding: .1rem .65rem; border-radius: 999px;
  font-size: .76rem; font-weight: 600; line-height: 1.6; white-space: nowrap;
  border: 1px solid transparent;
}}
.pill-neutral {{ background: var(--wash); border-color: var(--line); color: var(--ink2); }}
.pill-accent {{ background: rgba(210,59,46,.1); color: var(--red); border-color: rgba(210,59,46,.35); }}
.pill-ok {{ background: rgba(47,125,91,.12); color: var(--green); border-color: rgba(47,125,91,.35); }}
.pill-warn {{ background: rgba(185,116,31,.12); color: var(--amber); border-color: rgba(185,116,31,.4); }}
.pane-label {{ display: flex; align-items: center; justify-content: space-between; margin: 0 0 .35rem; min-height: 1.6rem; }}
.pane-label span.t {{ font-size: .88rem; font-weight: 700; }}
.stamp {{ display: inline-block; border: 2px solid var(--red); color: var(--red); border-radius: 4px; padding: 0 .55rem; font-family: var(--ming); font-weight: 700; font-size: .9rem; letter-spacing: .1em; transform: rotate(-6deg); }}
.day-head {{ display: flex; align-items: center; gap: .7rem; margin-bottom: .55rem; }}
.day-head .d {{ font-family: var(--ming); font-size: 1.35rem; font-weight: 700; }}
.day-title {{ font-family: var(--ming); font-size: 2.3rem; font-weight: 700; line-height: 1.1; display: flex; align-items: baseline; gap: .8rem; margin: 0 0 .9rem; }}
.day-title small {{ font-family: var(--sans); font-size: .95rem; font-weight: 400; color: var(--ink2); }}
.steps {{ display: flex; gap: .5rem; flex-wrap: wrap; margin: .2rem 0 1rem; align-items: center; }}
.step {{ display: inline-flex; align-items: center; gap: .5rem; color: var(--ink2); font-size: .88rem; }}
.step b {{ display: inline-grid; place-items: center; width: 1.45rem; height: 1.45rem; border-radius: 50%; border: 1.5px solid var(--line); font-size: .75rem; }}
.step + .step::before {{ content: "—"; color: var(--line); margin-right: .5rem; }}
.step.on {{ color: var(--ink); font-weight: 600; }}
.step.on b {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
.step.done b {{ background: var(--green); color: #fff; border-color: var(--green); }}
.card-link {{ border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.2rem; height: 100%; background: #fff; }}
.card-link .ic {{ font-size: 1.3rem; }}
.card-link .tt {{ font-family: var(--ming); font-weight: 700; font-size: 1.1rem; margin: .35rem 0 .2rem; }}
.card-link .ds {{ color: var(--ink2); font-size: .88rem; line-height: 1.55; }}
.rv-raw {{ font-family: var(--kai); font-size: 1.6rem; font-weight: 700; margin: .1rem 0 .55rem; word-break: break-all; }}
.rv-meta {{ display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; font-size: .85rem; margin-bottom: .5rem; }}
.rv-meta .mut {{ color: var(--ink2); }}
.rel-row {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }}
.rel-row .arrow {{ color: var(--red); }}
.rel-note {{ color: var(--ink2); font-size: .85rem; margin-top: .35rem; }}
.empty {{ text-align: center; border: 1.5px dashed var(--grid); border-radius: var(--radius); background: var(--wash); padding: 2.4rem 1rem; margin: .5rem 0 1rem; }}
.empty .ic {{ font-size: 2rem; }}
.empty .tt {{ font-family: var(--ming); font-weight: 700; margin: .45rem 0 .2rem; }}
.empty .ds {{ color: var(--ink2); font-size: .9rem; }}

/* ---- 批改紀錄：原稿 → 批改後 ---- */
.marks {{ border: 1px solid var(--line); border-radius: 4px; background: #fff; padding: .55rem .9rem .6rem; margin: .7rem 0 .2rem; }}
.marks .mt {{ font-size: .8rem; font-weight: 700; color: var(--red); margin-bottom: .15rem; }}
.mk-row {{ display: grid; grid-template-columns: 1fr auto 1fr; gap: .7rem; align-items: start; font-size: .95rem; line-height: 1.9; padding: .3rem 0; border-top: 1px dashed var(--line); }}
.mk-row:first-of-type {{ border-top: none; }}
.mk-new {{ width: fit-content; max-width: 100%; }}
.mk-old {{ font-family: var(--kai); font-size: 1.05rem; color: var(--ink2); text-decoration: line-through; text-decoration-color: rgba(210,59,46,.55); }}
.mk-arrow {{ color: var(--red); }}
.mk-new {{ text-decoration: underline wavy var(--red); text-underline-offset: 5px; text-decoration-thickness: 1.2px; }}
.mk-none {{ color: var(--ink2); font-size: .9rem; }}

/* ---- 保持橫排的區塊（月曆、年月選擇、按鈕列）：用 st.container(key=...) 標記 ---- */
.st-key-calendar [data-testid="stHorizontalBlock"],
.st-key-actions [data-testid="stHorizontalBlock"],
.st-key-ymbar [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .3rem !important; }}
.st-key-calendar [data-testid="stColumn"],
.st-key-actions [data-testid="stColumn"],
.st-key-ymbar [data-testid="stColumn"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
.st-key-calendar .stButton > button {{ min-height: 3.6rem; padding: .3rem .5rem !important; border: 1px solid var(--line); background: #fff; justify-content: flex-start; align-items: flex-start; position: relative; }}
.st-key-calendar .stButton > button [data-testid="stMarkdownContainer"] {{ width: 100%; }}
.st-key-calendar .stButton > button p {{ font-size: .95rem; white-space: nowrap; text-align: left; line-height: 1.35; }}
.st-key-calendar .stButton > button:hover:not(:disabled) {{ background: var(--wash); border-color: var(--grid); }}
.cal-month {{ font-family: var(--ming); font-size: 1.7rem; font-weight: 700; margin-bottom: .6rem; }}
.cal-legend {{ display: flex; gap: 1.1rem; margin-top: .6rem; font-size: .8rem; color: var(--ink2); flex-wrap: wrap; }}
.cal-legend i {{ display: inline-block; width: .8rem; height: .8rem; vertical-align: -1px; margin-right: .35rem; border: 1px solid var(--line); background: #fff; }}
.cal-total {{ margin-top: 1rem; padding-top: .8rem; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: baseline; color: var(--ink2); font-size: .88rem; }}
.cal-total b {{ font-size: 1.8rem; color: var(--ink); font-variant-numeric: tabular-nums; }}

/* ---- 桌面：月曆欄跟著捲動（輸入區很長時，月曆仍在視窗內） ---- */
@media (min-width: 641px) {{
  [data-testid="stColumn"]:has(.st-key-calwrap) {{ align-self: flex-start; position: sticky; top: 1rem; }}
}}

/* ---- 手機寬度 ---- */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding: 0 .85rem 4rem; }}
  .st-key-topnav {{ margin: 0 -.85rem; padding: 0 .85rem; gap: 1.3rem !important; height: 52px; }}
  .brand .nm {{ display: none; }}
  .st-key-toolbar {{ margin: 0 -.85rem 1rem; padding: .7rem .85rem !important; }}
  .pg-head {{ margin: 1rem 0 .9rem; }}
  .pg-title {{ font-size: 1.7rem; }}
  .pg-sub {{ font-size: .88rem; }}
  .day-title {{ font-size: 1.8rem; }}
  .cal-month {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.25rem !important; }}
  hr {{ margin: 1.1rem 0 !important; }}
  /* 指標：一排兩個 */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{ flex-wrap: wrap !important; gap: .6rem !important; }}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 1 1 calc(50% - .6rem) !important; min-width: calc(50% - .6rem) !important; }}
  [data-testid="stMetricValue"] {{ font-size: 1.5rem; }}
  /* 好按的尺寸；輸入框 16px 以上，iPhone 才不會在聚焦時自動放大 */
  .stButton > button, .stDownloadButton > button, [data-testid^="stBaseButton"] {{ min-height: 2.75rem; }}
  input, textarea, [data-baseweb="select"] * {{ font-size: 16px !important; }}
  .st-key-calendar .stButton > button {{ min-height: 3.1rem; padding: .2rem .3rem !important; }}
  .st-key-calendar .stButton > button p {{ font-size: .85rem; }}
  .st-key-actions .stButton > button {{ padding: .2rem .25rem; }}
  .st-key-actions .stButton > button p {{ font-size: .82rem; white-space: normal; line-height: 1.25; }}
  .steps {{ gap: .35rem; }}
  .step {{ font-size: .78rem; }}
  .card-link {{ padding: .9rem 1rem; }}
  .pane-label span.t {{ font-size: .8rem; }}
  .mk-row {{ grid-template-columns: 1fr; gap: .1rem; }}
  .mk-arrow {{ transform: rotate(90deg); width: fit-content; }}
}}
</style>
"""


_MOBILE_UA = re.compile(r"Mobi|Android|iPhone|iPod", re.I)  # iPad 當桌面，靠響應式 CSS 即可
VIEW_OPTIONS = ["自動", "手機版", "桌面版"]
_VIEW_QUERY = {"mobile": "手機版", "desktop": "桌面版"}

# (檔案, 標籤)；標籤盡量短，手機版導覽才排得下
_NAV = [
    ("app.py", "總覽"),
    ("pages/1_輸入.py", "輸入"),
    ("pages/2_審核.py", "審核"),
    ("pages/3_報表.py", "報表"),
    ("pages/4_關係表.py", "關係表"),
]


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


def top_nav() -> None:
    """頂端導覽列：品牌、五個頁面、顯示設定"""
    with st.container(horizontal=True, vertical_alignment="center", wrap=False, key="topnav"):
        st.html('<div class="brand"><div class="seal">帳</div><span class="nm">家計帳</span></div>')
        for path, label in _NAV:
            st.page_link(path, label=label)
        with st.popover("顯示", help="切換手機／桌面版面"):
            st.radio("版面", VIEW_OPTIONS, key="view_mode_sel", horizontal=True,
                     help="自動：依裝置判斷；手機連線會用手機版面")


def apply_theme() -> None:
    """注入共用樣式與頂端導覽；每頁在 st.set_page_config 之後呼叫一次"""
    # 這版 st.html 會濾掉 <style>，所以用 st.markdown
    st.markdown(_CSS, unsafe_allow_html=True)

    # 網址帶 ?view=mobile / ?view=desktop 可直接指定版面（第一次進來時生效）
    if "view_mode_sel" not in st.session_state:
        preset = _VIEW_QUERY.get(str(st.query_params.get("view", "")).lower())
        if preset:
            st.session_state["view_mode_sel"] = preset
    top_nav()


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    """頁首：大標題＋一行說明（eyebrow 保留參數相容，不再顯示）"""
    sub = f'<div class="pg-sub">{subtitle}</div>' if subtitle else ""
    st.html(f'<div class="pg-head"><div class="pg-title">{title}</div>{sub}</div>')


def pill(text: str, kind: str = "neutral") -> str:
    """回傳標籤的 HTML 字串（kind: neutral / accent / ok / warn）"""
    return f'<span class="pill pill-{kind}">{text}</span>'


def stamp(text: str = "已整理") -> str:
    """回傳紅色印章的 HTML 字串"""
    return f'<span class="stamp">{text}</span>'


def pane_label(text: str, badge: str = "") -> None:
    st.html(f'<div class="pane-label"><span class="t">{text}</span>{badge}</div>')


def steps(active: int, done: int = 0) -> None:
    """三步驟指示：1 貼上 → 2 整理 → 3 寫入。active 為目前步驟，done 為已完成的步驟數"""
    labels = ["貼上原稿", "來點魔法", "寫入資料庫"]
    out = ""
    for i, label in enumerate(labels, 1):
        cls = "done" if i <= done else "on" if i == active else ""
        mark = "✓" if i <= done else str(i)
        out += f'<span class="step {cls}"><b>{mark}</b>{label}</span>'
    st.html(f'<div class="steps">{out}</div>')


def card(icon: str, title: str, desc: str) -> None:
    st.html(f'<div class="card-link"><div class="ic">{icon}</div><div class="tt">{title}</div><div class="ds">{desc}</div></div>')


def empty_state(icon: str, title: str, desc: str = "") -> None:
    st.html(f'<div class="empty"><div class="ic">{icon}</div><div class="tt">{title}</div><div class="ds">{desc}</div></div>')


def diff_marks(src: str, out: str) -> tuple[int, str]:
    """比對原稿與整理後的文字，回傳（修改處數, 批改紀錄 HTML）

    以「行」為單位，連續被改動的行算一處：左邊是原稿的行（畫刪除線），
    右邊是整理後的行（畫紅色波浪底線）。只有空白行或前後空白的差異不算修改。
    """
    a = [ln.strip() for ln in src.splitlines() if ln.strip()]
    b = [ln.strip() for ln in out.splitlines() if ln.strip()]
    blocks = [(a[i1:i2], b[j1:j2])
              for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
              if tag != "equal"]
    if not blocks:
        return 0, ""

    esc = _html.escape
    parts = []
    for olds, news in blocks:
        left = "".join(f'<div class="mk-old">{esc(x)}</div>' for x in olds) or '<div class="mk-old">（新增）</div>'
        right = "".join(f'<div class="mk-new">{esc(x)}</div>' for x in news) or '<div class="mk-none">（移除）</div>'
        parts.append(f'<div class="mk-row"><div>{left}</div><span class="mk-arrow">→</span><div>{right}</div></div>')
    return len(blocks), f'<div class="marks"><div class="mt">批改紀錄　{len(blocks)} 處</div>{"".join(parts)}</div>'
