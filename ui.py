"""共用介面樣式與小元件（各頁在 set_page_config 之後呼叫 apply_theme）

視覺概念「聖旨」：深褐背景上攤開一卷明黃絹布，兩側青藍祥雲紋、上下木軸；
頂端導覽就是上軸。原稿與整理後的文字寫在烏絲欄上，批改用硃砂紅，蓋「閱」章收尾。
"""
import difflib
import html as _html
import re
from urllib.parse import quote

import streamlit as st

# 絹黃、硃砂、墨
INK = "#2B2118"
RED = "#C8261B"
GREEN = "#2F6B4A"
AMBER = "#9A6212"


def _svg(body: str, w: int, h: int) -> str:
    """把 SVG 轉成可放進 CSS url() 的 data URI"""
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{body}</svg>"
    return "data:image/svg+xml," + quote(svg)


# 祥雲紋（直條：聖旨左右兩側；橫條：月曆上下）
_CLOUD_V = _svg(
    "<rect width='44' height='64' fill='#2B5F7E'/>"
    "<rect width='3' height='64' fill='#C79A2B'/><rect x='41' width='3' height='64' fill='#C79A2B'/>"
    "<g fill='none' stroke-linecap='round'>"
    "<path d='M9 30c-6 0-7-9 0-9 0-6 9-7 11-1 6-3 12 3 8 8-2 3-7 2-9 2z' stroke='#F3D98A' stroke-width='1.8'/>"
    "<path d='M15 24c3-3 7-1 6 2' stroke='#F3D98A' stroke-width='1.5'/>"
    "<path d='M22 56c-6 0-7-8 0-8 0-6 9-6 11-1 6-2 10 3 7 7-2 3-7 2-9 2z' stroke='#F4EFE0' stroke-width='1.6'/>"
    "<path d='M28 51c3-3 7-1 6 2' stroke='#F4EFE0' stroke-width='1.4'/></g>"
    "<circle cx='36' cy='12' r='3.2' fill='#C8261B'/><circle cx='8' cy='44' r='2.6' fill='#C8261B'/>"
    "<circle cx='36' cy='38' r='1.6' fill='#F3D98A'/>", 44, 64)
_CLOUD_H = _svg(
    "<rect width='64' height='18' fill='#2B5F7E'/><g fill='none' stroke-linecap='round'>"
    "<path d='M10 14c-6 0-6-8 0-8 0-5 9-5 10 0 5-2 9 3 6 7z' stroke='#F3D98A' stroke-width='1.6'/>"
    "<path d='M40 14c-6 0-6-8 0-8 0-5 9-5 10 0 5-2 9 3 6 7z' stroke='#F4EFE0' stroke-width='1.5'/></g>"
    "<circle cx='30' cy='9' r='2.2' fill='#C8261B'/>", 64, 18)

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=LXGW+WenKai+TC:wght@400;700&display=swap');
:root {{
  --silk: #F3DA8C; --silk2: #F8E8B0;
  --paper: #FFF8E2;
  --wash: #F1DE9B;
  --grid: #D9BF6E;
  --rule: rgba(160,120,40,.38);
  --ink: {INK};
  --ink2: #6E5A42;
  --line: #D8BF78;
  --red: {RED}; --red2: #9E1F16;
  --green: {GREEN};
  --amber: {AMBER};
  --gold: #C79A2B; --gold2: #E8C763;
  --acc: {RED};
  --soft: var(--wash);
  --radius: 5px;
  --sans: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", "Noto Sans CJK TC", system-ui, sans-serif;
  --ming: "LXGW WenKai TC", "AR PL UKai TW", "BiauKai", "Kaiti TC", "KaiTi", serif;
  --kai: "LXGW WenKai TC", "AR PL UKai TW", "BiauKai", "Kaiti TC", "KaiTi", serif;
  --padx: 74px; --rod: 30px; --bw: 44px; --bh: 64px; --bx: 10px;
  --cap: linear-gradient(180deg, #8a6414 0, #f0cf6a 35%, #b98b24 65%, #6d4c0e 100%);
  --wood: linear-gradient(180deg, #1d0f06 0, #7c5030 32%, #5a381d 62%, #1d0f06 100%);
  --rod-bg: var(--cap) left center / 22px 100% no-repeat, var(--cap) right center / 22px 100% no-repeat, var(--wood);
  --silk-bg:
    url("{_CLOUD_V}") var(--bx) 0 / var(--bw) var(--bh) repeat-y,
    url("{_CLOUD_V}") calc(100% - var(--bx)) 0 / var(--bw) var(--bh) repeat-y,
    repeating-linear-gradient(90deg, rgba(150,110,30,.05) 0 1px, transparent 1px 4px),
    repeating-linear-gradient(0deg, rgba(150,110,30,.05) 0 1px, transparent 1px 4px),
    linear-gradient(90deg, #E9C867 0, var(--silk) 9%, #F8E4A0 50%, var(--silk) 91%, #E9C867 100%);
}}

/* ---- 背景與版面：深褐背景上攤開一卷絹布 ---- */
html, body, [data-testid="stAppViewContainer"] {{ font-family: var(--sans); -webkit-font-smoothing: antialiased; }}
[data-testid="stApp"] {{ background: radial-gradient(ellipse at 50% 12%, #4A2A20 0, #2A1A15 75%) fixed; }}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{
  position: relative; max-width: 1400px; width: calc(100% - 56px); margin: 0 auto 44px; padding: 0 var(--padx) 4.5rem;
  background: var(--silk-bg); box-shadow: 0 14px 30px rgba(0,0,0,.45); color: var(--ink);
}}
/* 下軸 */
[data-testid="stMainBlockContainer"]::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: var(--rod); background: var(--rod-bg); box-shadow: 0 -2px 8px rgba(0,0,0,.35); }}
/* 輸入頁：背景不鋪絹布，絹布只在左邊那一卷（.st-key-scroll）和右邊月曆 */
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) {{ --padx: 28px; width: 100%; max-width: 1440px; background: none; box-shadow: none; padding-bottom: 4rem; margin-bottom: 0; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll)::after {{ display: none; }}
#MainMenu, footer, [data-testid="stDecoration"], .stDeployButton, [data-testid="stHeader"] {{ display: none !important; }}
/* 只放 <style> 的區塊不佔位 */
[data-testid="stElementContainer"]:has(style) {{ display: none; }}

/* ---- 標題 ---- */
h1, h2, h3 {{ font-family: var(--ming) !important; letter-spacing: .04em; font-weight: 700 !important; color: var(--ink); }}
h2 {{ font-size: 1.5rem !important; padding-top: .6rem !important; }}
h3 {{ font-size: 1.2rem !important; }}
hr {{ border-color: var(--line) !important; margin: 1.6rem 0 !important; opacity: 1; }}
.pg-head {{ margin: 1.8rem 0 1.4rem; padding-bottom: .7rem; border-bottom: 3px double var(--gold); }}
.pg-title {{ font-family: var(--ming); font-size: 2.5rem; font-weight: 700; line-height: 1.15; letter-spacing: .08em; color: var(--red2); }}
.pg-sub {{ color: var(--ink2); font-size: .95rem; margin-top: .35rem; }}

/* ---- 頂端導覽：就是聖旨的上軸 ---- */
.st-key-topnav {{ align-items: center; gap: 2.2rem !important; height: 56px; width: calc(100% + 2 * var(--padx)) !important; max-width: none !important; margin: 0 calc(-1 * var(--padx)); padding: 0 calc(22px + 1.6rem); background: var(--rod-bg); box-shadow: 0 4px 10px rgba(0,0,0,.5); flex-wrap: nowrap !important; overflow-x: auto; scrollbar-width: none; position: relative; z-index: 3; }}
.st-key-topnav::-webkit-scrollbar {{ display: none; }}
.st-key-topnav > [data-testid="stElementContainer"], .st-key-topnav > [data-testid="stPageLink"] {{ flex: 0 0 auto; width: auto; }}
.st-key-topnav > *:has([data-testid="stPopover"]) {{ margin-left: auto; }}
.brand {{ display: flex; align-items: center; gap: .6rem; font-family: var(--kai); font-weight: 700; font-size: 1.35rem; color: var(--gold2); white-space: nowrap; }}
.brand .seal {{ width: 32px; height: 32px; background: var(--red); color: #FFE9B0; display: grid; place-items: center; border: 2px solid var(--gold2); border-radius: 4px; font-family: var(--kai); font-size: 1.15rem; transform: rotate(-4deg); }}
.st-key-topnav [data-testid="stPageLink-NavLink"] {{ padding: .5rem .1rem; background: none !important; border-radius: 0; position: relative; color: #E9D6A8; }}
.st-key-topnav [data-testid="stPageLink-NavLink"] * {{ color: inherit !important; }}
.st-key-topnav [data-testid="stPageLink-NavLink"] p {{ font-family: var(--kai); font-size: 1.05rem; font-weight: 500; color: inherit !important; }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"] {{ color: #FFE9A0; }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"] p {{ font-weight: 700; }}
.st-key-topnav [data-testid="stPageLink-NavLink"][aria-current="page"]::after {{ content: ""; position: absolute; left: -4px; right: -4px; bottom: -3px; height: 3px; border-radius: 2px; background: var(--gold2); }}
.st-key-topnav [data-testid="stPopover"] button {{ border: none !important; background: none !important; color: #C7B183 !important; box-shadow: none; padding: 0 .2rem; min-height: 0; }}
.st-key-topnav [data-testid="stPopover"] button p {{ color: #C7B183; }}

/* ---- 功能列（年月、人員、動作按鈕）：絹布頁是一條絹底，輸入頁是硃紅綢帶 ---- */
.st-key-toolbar {{ border: none !important; border-top: 1px solid var(--gold) !important; border-bottom: 2px solid var(--gold) !important; border-radius: 0 !important; background: rgba(255,248,226,.55); margin: 0 0 1.6rem; padding: .9rem 1.2rem !important; gap: 1.4rem !important; }}
.st-key-toolbar [data-testid="stSelectbox"] [data-baseweb="select"] > div {{ border: none; border-bottom: 1.5px solid var(--ink); border-radius: 0; background: transparent; font-weight: 600; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar {{ width: 100% !important; margin: 0 !important; background: linear-gradient(180deg, #B52B1F, #8F1D14); border-top: 2px solid var(--gold) !important; border-bottom: 2px solid var(--gold) !important; padding: .7rem 40px !important; box-shadow: 0 6px 12px rgba(0,0,0,.35); position: relative; z-index: 2; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar [data-testid="stWidgetLabel"] p {{ color: #F6DFA4; font-family: var(--kai); font-size: .95rem; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar [data-testid="stSelectbox"] [data-baseweb="select"] > div {{ background: #FFF3CC; border: 1.5px solid var(--gold2); border-radius: 5px; color: var(--ink); }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar [data-testid="stSelectbox"] svg {{ color: var(--ink2); fill: var(--ink2); }}
/* 綢帶上的按鈕 */
.st-key-toolbar [class*="st-key-magic_btn"] button:not(:disabled) {{ background: transparent; border-color: var(--gold2); color: #FFE9B0; }}
.st-key-toolbar [class*="st-key-magic_btn"] button:not(:disabled) p {{ color: #FFE9B0; }}
.st-key-toolbar [class*="st-key-magic_btn"] button:not(:disabled):hover {{ background: rgba(255,233,176,.15) !important; border-color: #FFE9B0 !important; color: #FFE9B0 !important; }}
.st-key-toolbar button[data-testid="stBaseButton-primary"] {{ background: linear-gradient(180deg, #F3D879, #D5A93A); border-color: #F3D879; color: #3A1E0C; }}
.st-key-toolbar button[data-testid="stBaseButton-primary"]:not(:disabled) p {{ color: #3A1E0C; }}
.st-key-toolbar button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ background: linear-gradient(180deg, #F8E48F, #E0B646) !important; color: #3A1E0C !important; }}
.st-key-toolbar .st-key-day_next button {{ background: #FFF3CC; border-color: #FFF3CC; color: var(--red2); }}
.st-key-toolbar .st-key-day_next button:hover:not(:disabled) {{ background: #fff !important; color: var(--red2); }}
.st-key-toolbar .st-key-day_cancel button {{ background: transparent; border-color: transparent; color: #EBC9A0; }}
.st-key-toolbar .st-key-day_cancel button:hover:not(:disabled) {{ background: rgba(255,233,176,.12); color: #FFE9B0; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar button:disabled {{ background: transparent !important; border-color: rgba(232,199,99,.35) !important; }}
[data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar button:disabled p {{ color: rgba(255,233,176,.45) !important; }}

/* ---- 按鈕 ---- */
.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"], [data-testid="stPopover"] > button {{
  border-radius: 5px; font-weight: 600; border: 1.5px solid var(--ink); background: var(--paper); color: var(--ink);
  transition: background .12s ease, border-color .12s ease;
}}
.stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled) {{ background: var(--wash); border-color: var(--ink); color: var(--ink); }}
button[data-testid="stBaseButton-primary"] {{ background: var(--red2); border-color: var(--red2); color: #FFE9B0; }}
button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ background: #B52B1F !important; color: #FFE9B0 !important; }}
button[data-testid="stBaseButton-primary"]:not(:disabled) p {{ color: #FFE9B0; }}
button:disabled {{ background: var(--wash) !important; color: var(--ink2) !important; border-color: var(--line) !important; opacity: 1 !important; }}
button:disabled p {{ color: var(--ink2) !important; }}

/* ---- 卡片：有邊框的容器、指標、展開區 ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--line) !important; border-radius: var(--radius); background: var(--paper); }}
[data-testid="stMetric"] {{ border: none; border-left: 3px solid var(--gold); border-radius: 0; padding: .1rem .9rem; background: none; }}
[data-testid="stMetricLabel"] {{ color: var(--ink2); font-size: .82rem; }}
[data-testid="stMetricValue"] {{ font-weight: 700; font-variant-numeric: tabular-nums; font-size: 1.9rem; }}
[data-testid="stExpander"] {{ border: 1px solid var(--line); border-radius: var(--radius); background: var(--paper); }}
[data-testid="stExpander"] summary {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: var(--radius); border: 1px solid var(--line); }}

/* ---- 烏絲欄稿紙：文字框畫成有橫線的稿紙，原稿與整理後都用楷體 ---- */
[data-testid="stTextAreaRootElement"] {{ background: var(--paper) !important; border: 3px double #D2B35E !important; border-radius: 3px; }}
[data-testid="stTextArea"] textarea {{
  background-color: transparent;
  background-image:
    linear-gradient(90deg, transparent 26px, rgba(200,38,27,.45) 26px, rgba(200,38,27,.45) 27px, transparent 27px),
    repeating-linear-gradient(transparent 0 31px, var(--rule) 31px 32px);
  background-attachment: local;
  background-position: 0 0, 0 7px;
  font-family: var(--kai);
  font-size: 1.1rem;
  line-height: 32px;
  padding: 7px 14px 7px 38px;
  border-radius: 3px;
}}
[data-testid="stTextArea"] textarea::placeholder {{ opacity: .45; }}
[class*="st-key-magic_20"] [data-testid="stTextAreaRootElement"] {{ background: #FFFAE8 !important; border: 3px double #B78A24 !important; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 600; font-size: .88rem; }}

/* ---- 自訂小元件 ---- */
.pill {{
  display: inline-flex; align-items: center; gap: .35rem;
  padding: .1rem .65rem; border-radius: 999px;
  font-size: .76rem; font-weight: 600; line-height: 1.6; white-space: nowrap;
  border: 1px solid transparent;
}}
.pill-neutral {{ background: rgba(255,255,255,.4); border-color: var(--gold); color: var(--ink2); }}
.pill-accent {{ background: rgba(200,38,27,.08); color: var(--red2); border-color: rgba(200,38,27,.5); }}
.pill-ok {{ background: rgba(47,107,74,.12); color: var(--green); border-color: rgba(47,107,74,.5); }}
.pill-warn {{ background: rgba(154,98,18,.12); color: var(--amber); border-color: rgba(154,98,18,.5); }}
.pane-label {{ display: flex; align-items: center; justify-content: space-between; margin: 0 0 .35rem; min-height: 2.6rem; }}
.pane-label span.t {{ font-family: var(--kai); font-size: 1.2rem; font-weight: 700; letter-spacing: .12em; }}
.stamp {{ display: inline-block; border: 2.5px solid var(--red); color: var(--red); border-radius: 5px; padding: 0 .6rem; font-family: var(--kai); font-weight: 700; font-size: 1rem; letter-spacing: .1em; transform: rotate(-7deg); opacity: .9; }}
.day-head {{ display: flex; align-items: center; gap: .7rem; margin-bottom: .55rem; }}
.day-head .d {{ font-family: var(--kai); font-size: 1.35rem; font-weight: 700; }}
.day-title {{ font-family: var(--kai); font-size: 2.9rem; font-weight: 700; line-height: 1.1; letter-spacing: .04em; display: flex; align-items: baseline; flex-wrap: wrap; gap: .5rem .8rem; margin: 0 0 .9rem; }}
.day-title small {{ font-family: var(--kai); font-size: .95rem; font-weight: 400; color: var(--ink2); letter-spacing: 0; }}
.steps {{ display: flex; gap: .5rem; flex-wrap: wrap; margin: .2rem 0 1rem; align-items: center; }}
.step {{ display: inline-flex; align-items: center; gap: .5rem; color: var(--ink2); font-size: .88rem; }}
.step b {{ display: inline-grid; place-items: center; width: 1.45rem; height: 1.45rem; border-radius: 50%; border: 1.5px solid var(--line); font-size: .75rem; }}
.step + .step::before {{ content: "—"; color: var(--line); margin-right: .5rem; }}
.step.on {{ color: var(--ink); font-weight: 600; }}
.step.on b {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
.step.done b {{ background: var(--green); color: #fff; border-color: var(--green); }}
.card-link {{ border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.2rem; height: 100%; background: var(--paper); }}
.card-link .ic {{ font-size: 1.3rem; }}
.card-link .tt {{ font-family: var(--kai); font-weight: 700; font-size: 1.15rem; margin: .35rem 0 .2rem; }}
.card-link .ds {{ color: var(--ink2); font-size: .88rem; line-height: 1.55; }}
.rv-raw {{ font-family: var(--kai); font-size: 1.6rem; font-weight: 700; margin: .1rem 0 .55rem; word-break: break-all; }}
.rv-meta {{ display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; font-size: .85rem; margin-bottom: .5rem; }}
.rv-meta .mut {{ color: var(--ink2); }}
.rel-row {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }}
.rel-row .arrow {{ color: var(--red); }}
.rel-note {{ color: var(--ink2); font-size: .85rem; margin-top: .35rem; }}
.empty {{ text-align: center; border: 1.5px dashed var(--gold); border-radius: var(--radius); background: rgba(255,255,255,.35); padding: 2.4rem 1rem; margin: .5rem 0 1rem; }}
.empty .ic {{ font-size: 2rem; }}
.empty .tt {{ font-family: var(--kai); font-weight: 700; font-size: 1.1rem; margin: .45rem 0 .2rem; }}
.empty .ds {{ color: var(--ink2); font-size: .9rem; }}

/* ---- 輸入頁：左邊那一卷聖旨（上下木軸、左右祥雲紋） ---- */
.st-key-scroll {{ position: relative; margin: 34px 0 34px; padding: 28px 70px 34px !important; background: var(--silk-bg); box-shadow: 0 14px 30px rgba(0,0,0,.45); }}
.st-key-scroll::before, .st-key-scroll::after {{ content: ""; position: absolute; left: -14px; right: -14px; height: var(--rod); border-radius: 6px; background: var(--rod-bg); box-shadow: 0 4px 10px rgba(0,0,0,.5); z-index: 2; }}
.st-key-scroll::before {{ top: calc(-1 * var(--rod) + 2px); }}
.st-key-scroll::after {{ bottom: calc(-1 * var(--rod) + 2px); }}
.edict-head {{ text-align: center; font-family: var(--kai); font-size: 1.9rem; letter-spacing: .35em; color: var(--red2); font-weight: 700; padding-bottom: .6rem; border-bottom: 1px solid var(--gold); position: relative; margin-bottom: .6rem; }}
.edict-head::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: -5px; border-bottom: 1px solid var(--gold); }}
.edict-idle {{ text-align: center; padding: 1.6rem 0 1rem; }}
.edict-idle .tt {{ font-family: var(--kai); font-size: 2rem; font-weight: 700; letter-spacing: .1em; }}
.edict-idle .ds {{ margin-top: .5rem; color: var(--ink2); line-height: 1.8; }}
.edict-end {{ position: relative; height: 128px; margin-top: .4rem; }}
.edict-end .ks {{ position: absolute; right: 130px; top: 34px; font-family: var(--kai); font-weight: 700; font-size: 2.3rem; letter-spacing: .3em; }}
.edict-end .dt {{ position: absolute; right: 130px; top: 88px; font-family: var(--kai); font-size: .95rem; color: var(--ink2); }}
.seal-big, .seal-slot {{ position: absolute; right: 6px; top: 8px; width: 104px; height: 104px; display: grid; place-items: center; transform: rotate(-6deg); }}
.seal-big {{ background: rgba(200,38,27,.92); color: #FFE9B0; font-family: var(--kai); font-weight: 700; font-size: 4.4rem; border: 3px solid #7d150e; outline: 3px solid rgba(200,38,27,.92); outline-offset: -10px; mix-blend-mode: multiply; }}
.seal-slot {{ border: 2px dashed rgba(200,38,27,.5); color: rgba(200,38,27,.55); font-family: var(--kai); font-size: 1.1rem; letter-spacing: .2em; }}

/* ---- 閱章：像皇帝批奏摺，按下去蓋章 ---- */
.st-key-pane_head {{ gap: .5rem !important; min-height: 2.6rem; margin-bottom: .35rem; position: relative; }}
.st-key-pane_head .pane-label {{ margin: 0; min-height: 0; }}
.st-key-yue_off button, .st-key-yue_on button {{
  width: 2.9rem; min-height: 2.9rem; height: 2.9rem; padding: 0; border: 2.5px solid var(--red) !important; border-radius: 2px;
  background: transparent; color: var(--red) !important; transform: rotate(5deg);
  transition: transform .15s ease, background .15s ease;
}}
.st-key-yue_off button p, .st-key-yue_on button p {{ font-family: var(--kai); font-size: 1.7rem; font-weight: 700; color: var(--red) !important; line-height: 1; }}
.st-key-yue_off button:hover:not(:disabled) {{ background: rgba(200,38,27,.12) !important; transform: rotate(5deg) scale(1.08); }}
.st-key-yue_on button {{ background: var(--red) !important; border-color: #7d150e !important; outline: 2px solid var(--red); outline-offset: -6px; box-shadow: 0 2px 0 #7d150e; }}
.st-key-yue_on button p {{ color: #FFE9B0 !important; }}
.st-key-yue_off button:disabled {{ border-color: var(--line) !important; background: transparent !important; }}
.st-key-yue_off button:disabled p {{ color: var(--line) !important; }}

/* ---- 批改紀錄：原稿 → 批改後 ---- */
.marks {{ border: 1px solid var(--line); border-radius: 4px; background: var(--paper); padding: .55rem .9rem .6rem; margin: .7rem 0 .2rem; }}
.marks .mt {{ font-size: .8rem; font-weight: 700; color: var(--red); margin-bottom: .15rem; }}
.mk-row {{ display: grid; grid-template-columns: 1fr auto 1fr; gap: .7rem; align-items: start; font-size: .95rem; line-height: 1.9; padding: .3rem 0; border-top: 1px dashed var(--line); }}
.mk-row:first-of-type {{ border-top: none; }}
.mk-new {{ width: fit-content; max-width: 100%; }}
.mk-old {{ font-family: var(--kai); font-size: 1.05rem; color: var(--ink2); text-decoration: line-through; text-decoration-color: rgba(200,38,27,.6); }}
.mk-arrow {{ color: var(--red); }}
.mk-new {{ text-decoration: underline wavy var(--red); text-underline-offset: 5px; text-decoration-thickness: 1.2px; }}
.mk-none {{ color: var(--ink2); font-size: .9rem; }}

/* ---- 保持橫排的區塊（月曆、年月選擇、按鈕列）：用 st.container(key=...) 標記 ---- */
.st-key-calendar [data-testid="stHorizontalBlock"],
.st-key-actions [data-testid="stHorizontalBlock"],
.st-key-ymbar [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .3rem !important; }}
.st-key-calendar [data-testid="stHorizontalBlock"] {{ gap: 0 !important; }}
.st-key-calendar {{ gap: 0 !important; border-top: 2px solid var(--ink); }}
.st-key-calendar [data-testid="stColumn"],
.st-key-actions [data-testid="stColumn"],
.st-key-ymbar [data-testid="stColumn"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
.st-key-calendar .stButton > button {{ min-height: 4rem; padding: .3rem .5rem !important; border: none; border-bottom: 1px solid rgba(160,120,40,.45); border-right: 1px solid rgba(160,120,40,.45); border-radius: 0; background: transparent; justify-content: flex-start; align-items: flex-start; position: relative; }}
.st-key-calendar .stButton > button [data-testid="stMarkdownContainer"] {{ width: 100%; }}
.st-key-calendar .stButton > button p {{ font-size: .95rem; white-space: nowrap; text-align: left; line-height: 1.35; }}
.st-key-calendar .stButton > button:hover:not(:disabled) {{ background: rgba(255,248,226,.7); border-color: rgba(160,120,40,.45); }}
.cal-wd {{ text-align: center; padding: .4rem 0; font-family: var(--kai); font-size: .95rem; color: var(--red2); border-bottom: 1px solid var(--gold); }}
.cal-month {{ font-family: var(--kai); font-size: 2rem; font-weight: 700; letter-spacing: .06em; margin: .3rem 0 0; display: flex; align-items: baseline; flex-wrap: wrap; gap: .3rem .8rem; }}
.cal-month small {{ font-family: var(--sans); font-size: .8rem; font-weight: 400; color: var(--ink2); letter-spacing: 0; }}
.cal-legend {{ display: flex; gap: 1.1rem; margin-top: .8rem; font-size: .8rem; color: var(--ink2); flex-wrap: wrap; }}
.cal-legend i {{ display: inline-block; width: .8rem; height: .8rem; vertical-align: -1px; margin-right: .35rem; }}
.cal-total {{ margin-top: 1rem; padding-top: .8rem; border-top: 1px solid var(--gold); display: flex; justify-content: space-between; align-items: baseline; color: var(--ink2); font-size: .88rem; }}
.cal-total b {{ font-family: var(--kai); font-size: 2.3rem; color: var(--ink); font-variant-numeric: tabular-nums; }}
/* 月曆這一張絹，上下各一條祥雲邊 */
.st-key-calwrap {{ position: relative; margin-top: 4px; padding: 38px 26px 30px !important; background: linear-gradient(90deg, #E9C867, #F6E2A0 12%, #F8E8B0 50%, #F6E2A0 88%, #E9C867); box-shadow: 0 14px 30px rgba(0,0,0,.45); }}
.st-key-calwrap::before, .st-key-calwrap::after {{ content: ""; position: absolute; left: 0; right: 0; height: 18px; background: url("{_CLOUD_H}") repeat-x; border-top: 3px solid var(--gold); border-bottom: 3px solid var(--gold); box-sizing: content-box; }}
.st-key-calwrap::before {{ top: 0; }}
.st-key-calwrap::after {{ bottom: 0; }}

/* ---- 桌面：月曆欄跟著捲動（輸入區很長時，月曆仍在視窗內） ---- */
@media (min-width: 641px) {{
  [data-testid="stColumn"]:has(.st-key-calwrap) {{ align-self: flex-start; position: sticky; top: 1rem; }}
}}

/* ---- 手機寬度 ---- */
@media (max-width: 640px) {{
  :root {{ --padx: 30px; --rod: 24px; --bw: 16px; --bh: 23px; --bx: 6px; }}
  [data-testid="stMainBlockContainer"] {{ width: calc(100% - 16px); padding-bottom: 4rem; }}
  [data-testid="stMainBlockContainer"]:has(.st-key-scroll) {{ --padx: 8px; width: 100%; }}
  .st-key-topnav {{ padding: 0 calc(22px + .6rem); gap: 1.3rem !important; height: 48px; }}
  .brand .nm {{ display: none; }}
  .st-key-toolbar {{ margin: 0 0 1rem; padding: .7rem .8rem !important; }}
  [data-testid="stMainBlockContainer"]:has(.st-key-scroll) .st-key-toolbar {{ width: 100% !important; margin: 0 !important; padding: .6rem .85rem !important; }}
  .st-key-scroll {{ margin: 28px 0 28px; padding: 20px 28px 28px !important; }}
  .st-key-scroll::before, .st-key-scroll::after {{ left: -6px; right: -6px; }}
  .st-key-calwrap {{ padding: 34px 12px 26px !important; }}
  .edict-head {{ font-size: 1.3rem; letter-spacing: .2em; }}
  .edict-end .ks {{ right: 100px; font-size: 1.8rem; }}
  .edict-end .dt {{ right: 100px; font-size: .8rem; }}
  .seal-big, .seal-slot {{ width: 84px; height: 84px; font-size: 3.4rem; }}
  .pg-head {{ margin: 1rem 0 .9rem; }}
  .pg-title {{ font-size: 1.8rem; }}
  .pg-sub {{ font-size: .88rem; }}
  .day-title {{ font-size: 2rem; }}
  .cal-month {{ font-size: 1.5rem; }}
  .cal-total b {{ font-size: 1.8rem; }}
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
  .st-key-calendar .stButton > button {{ min-height: 3.3rem; padding: .2rem .3rem !important; }}
  .st-key-calendar .stButton > button p {{ font-size: .85rem; }}
  .st-key-actions .stButton > button {{ padding: .2rem .25rem; }}
  .st-key-actions .stButton > button p {{ font-size: .82rem; white-space: normal; line-height: 1.25; }}
  .steps {{ gap: .35rem; }}
  .step {{ font-size: .78rem; }}
  .card-link {{ padding: .9rem 1rem; }}
  .pane-label span.t {{ font-size: 1rem; }}
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


_CN = "〇一二三四五六七八九"
_STEMS, _BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"


def cn_int(n: int) -> str:
    """1~99 轉中文數字：9→九、10→十、15→十五、20→二十、31→三十一"""
    if n < 10:
        return _CN[n]
    if n < 20:
        return "十" + (_CN[n - 10] if n > 10 else "")
    return _CN[n // 10] + "十" + (_CN[n % 10] if n % 10 else "")


def cn_year(year: int) -> str:
    """2026 → 二〇二六年"""
    return "".join(_CN[int(c)] for c in str(year)) + "年"


def cn_date(month: int, day: int) -> str:
    """9, 9 → 九月九日"""
    return f"{cn_int(month)}月{cn_int(day)}日"


def ganzhi_year(year: int) -> str:
    """2026 → 丙午年"""
    return _STEMS[(year - 4) % 10] + _BRANCHES[(year - 4) % 12] + "年"


def edict_head() -> None:
    st.html('<div class="edict-head">奉天承運　記帳詔曰</div>')


def edict_idle() -> None:
    """還沒選日期：聖旨捲著，等你點日期"""
    st.html('<div class="edict-idle"><div class="tt">聖旨待展</div>'
            '<div class="ds">點選日曆上的日期，就會展開那天的原奏與魔法聖旨</div></div>')


def edict_end(year: int, month: int, day: int, reviewed: bool) -> str:
    """聖旨結尾：欽此、日期，蓋了閱章就多一個大紅印，還沒蓋就留一個待用印的空位"""
    seal = '<div class="seal-big">閱</div>' if reviewed else '<div class="seal-slot">待用印</div>'
    status = "批閱" if reviewed else "待批閱"
    return (f'<div class="edict-end"><div class="ks">欽　此</div>'
            f'<div class="dt">{ganzhi_year(year)}　{cn_date(month, day)}　{status}</div>{seal}</div>')


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
