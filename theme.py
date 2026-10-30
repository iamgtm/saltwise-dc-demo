"""SaltWise DC design tokens: white and very light gray surfaces, dark text, orange accent.

User-directed appearance change (2026-10-15, supervised run 2026-10-15_004803_light-theme-story) replaces the
earlier near-black direction. `accent` is the graphics/button orange (>= 3:1 on white); `accent_text` is the
orange used for text (>= 4.5:1 on white and on panels).
"""
import base64
from pathlib import Path

_LOGO = (Path(__file__).resolve().parent / "assets" / "saltwise_logo.svg").read_text()
# light wordmark for the dark hero: same file, only the wordmark text recolored (orange mark kept)
LOGO_LIGHT_URI = "data:image/svg+xml;base64," + base64.b64encode(_LOGO.replace('<tspan fill="#15171C"', '<tspan fill="#F2F4F6"').encode()).decode()

TOKENS = {
    "bg": "#FFFFFF",          # page
    "panel": "#F5F6F8",       # very light gray surface
    "border": "#E3E6EA",
    "text": "#15171C",
    "muted": "#4F5561",
    "inactive": "#6B717C",    # inactive scroll chapters (4.9:1 on white)
    "accent": "#D2560A",      # orange: pavement series, buttons, highlights (4.1:1 on white)
    "accent_text": "#A3420A", # orange for text (6.3:1 on white)
    "air": "#3D6A96",         # blue-gray air series (5.7:1 on white)
    "grid": "#ECEEF1",
    "unavailable": "#D9DDE3",
    "min_font_px": 15,
}

CSS = f"""
<style>
html, body, [data-testid="stAppViewContainer"] {{
  background: radial-gradient(ellipse 60% 30% at 50% -8%, rgba(210,86,10,0.07), rgba(210,86,10,0) 70%), {TOKENS['bg']};
  color: {TOKENS['text']}; font-size: {TOKENS['min_font_px']}px;
}}
[data-testid="stHeader"] {{ height: 68px; background: rgba(242,244,246,.86); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid #D9E0E6; transition: background-color .3s ease, border-color .3s ease; }}
/* The header overlays the stMain scroller: keep focused or scrolled-to content below it (WCAG 2.4.11). Layout unchanged. */
[data-testid="stMain"] {{ scroll-padding-top: 76px; }}
html.sw-over-hero [data-testid="stHeader"] {{ background: rgba(6,10,14,.16) !important; border-bottom-color: rgba(255,255,255,.16) !important; }}
html.sw-over-hero [data-testid="stTopNavLink"], html.sw-over-hero [data-testid="stTopNavLink"] * {{ color: #F2F4F6 !important; }}
html.sw-over-hero [data-testid="stHeaderLogo"], html.sw-over-hero [data-testid="stSidebarLogo"] {{ content: url("{LOGO_LIGHT_URI}"); }}
html.sw-over-hero [data-testid="stExpandSidebarButton"] {{ background: rgba(255,255,255,.12) !important; border-color: rgba(255,255,255,.7) !important; }}
html.sw-over-hero [data-testid="stExpandSidebarButton"], html.sw-over-hero [data-testid="stExpandSidebarButton"] *, html.sw-over-hero [data-testid="stExpandSidebarButton"]::after {{ color: #FFFFFF !important; fill: #FFFFFF !important; }}
html.sw-home .block-container {{ padding-top: 0 !important; padding-bottom: 0 !important; max-width: 1960px !important; padding-left: 48px !important; padding-right: 48px !important; }}
@media (max-width: 640px) {{ html.sw-home .block-container {{ padding-left: 16px !important; padding-right: 16px !important; }} }}
html.sw-home [data-testid="stMain"], html.sw-home [data-testid="stAppViewContainer"] {{ overflow-x: hidden; }}
.block-container {{ padding-top: 4.2rem; max-width: 1920px; padding-left: clamp(16px, 3.4vw, 56px) !important; padding-right: clamp(16px, 3.4vw, 56px) !important; }}
html:not(.sw-home) .block-container [data-testid="stMarkdownContainer"] p {{ max-width: 82ch; }}   /* readable lines on the wider pages */
.sw-eyebrow {{ font-family: ui-monospace, Menlo, monospace; letter-spacing: .18em; font-size: 12px; color: {TOKENS['muted']}; }}
.sw-chip {{ border: 1px solid {TOKENS['accent']}; color: {TOKENS['accent_text']}; border-radius: 6px; padding: 1px 6px; margin-right: 6px; }}
.sw-title {{ font-size: 46px; font-weight: 600; letter-spacing: -0.02em; margin: .25rem 0 .2rem 0; color: {TOKENS['text']}; }}
.sw-accent {{ color: {TOKENS['accent_text']}; }}
.sw-sub {{ color: {TOKENS['muted']}; font-size: 17px; max-width: 760px; }}
.sw-banner {{ display: inline-block; margin: .4rem 0 1.2rem 0; padding: .45rem .9rem; border-radius: 18px;
  border: 1px solid rgba(210,86,10,.40); background: #FFF4EC; color: #7A3108; font-size: 13px; }}
/* Demo build: an 18px radius keeps one-line labels pill-shaped; wrapped labels become rounded rectangles, not ellipses. */
@media (max-width: 640px) {{ .sw-banner {{ display: block; padding: .65rem 1rem; line-height: 1.5; }} }}
.sw-section {{ font-family: ui-monospace, Menlo, monospace; letter-spacing: .16em; font-size: 12px; color: {TOKENS['muted']}; margin: .6rem 0 .3rem 0; }}
.sw-card {{ background: {TOKENS['panel']}; border: 1px solid {TOKENS['border']}; border-radius: 16px; padding: .85rem .9rem; min-height: 158px; }}
.sw-card-selected {{ border-color: {TOKENS['accent']}; box-shadow: 0 0 0 3px rgba(210,86,10,.12); background: #FFFFFF; }}
.sw-card-title {{ font-weight: 600; font-size: 15px; color: {TOKENS['text']}; line-height: 1.3; }}
.sw-card-meta {{ color: {TOKENS['muted']}; font-size: 14px; margin-top: .35rem; }}
.sw-badge {{ display: inline-block; margin-top: .5rem; font-size: 12px; color: {TOKENS['muted']}; border: 1px dashed #C4C9D0;
  border-radius: 999px; padding: 1px 8px; background: #FFFFFF; }}
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{ background: #FFFFFF; border: 1px solid {TOKENS['border']};
  border-radius: 18px; padding: 14px 10px 6px 10px; }}
div[role="radiogroup"] label {{ background: #FFFFFF; border: 1px solid {TOKENS['border']}; border-radius: 999px;
  padding: 4px 12px; margin-right: 6px; }}
div[role="radiogroup"] label:has(input:checked) {{ border-color: {TOKENS['accent']}; background: #FFF4EC; }}
.stButton button, .stDownloadButton button {{ border-radius: 999px; border: 1px solid #D5D9DF; background: #FFFFFF; color: {TOKENS['text']}; }}
.stButton button:hover, .stDownloadButton button:hover {{ border-color: {TOKENS['accent']}; color: {TOKENS['text']}; }}
[data-testid="stMetric"] {{ background: {TOKENS['panel']}; border: 1px solid {TOKENS['border']}; border-radius: 16px; padding: .7rem 1rem; }}
[data-testid="stExpander"] {{ background: {TOKENS['panel']}; border-radius: 16px; }}
@media (max-width: 640px) {{ .sw-card:not(.sw-card-selected) {{ display: none; }} .sw-card {{ min-height: 0; }} .sw-title {{ font-size: 38px; }} }}
.sw-review-count {{ margin-top: .45rem; font-size: 13px; color: {TOKENS['accent_text']}; font-weight: 600; }}
.sw-review-none {{ margin-top: .45rem; font-size: 13px; color: {TOKENS['muted']}; }}
.sw-rule-note {{ color: {TOKENS['muted']}; font-size: 14px; margin-bottom: .6rem; }}
.sw-flag {{ background: {TOKENS['panel']}; border: 1px solid {TOKENS['border']}; border-left: 3px solid {TOKENS['accent']};
  border-radius: 14px; padding: .8rem 1rem; margin-bottom: .6rem; }}
.sw-flag-none {{ border-left-color: #C4C9D0; color: {TOKENS['muted']}; }}
.sw-flag-head {{ display: flex; flex-wrap: wrap; gap: .6rem; align-items: baseline; margin-bottom: .3rem; }}
.sw-flag-title {{ font-weight: 600; color: {TOKENS['text']}; font-size: 16px; }}
.sw-flag-time {{ color: {TOKENS['muted']}; font-size: 14px; }}
.sw-chip-ill {{ font-family: ui-monospace, Menlo, monospace; letter-spacing: .12em; font-size: 11px; color: {TOKENS['muted']};
  border: 1px dashed #C4C9D0; border-radius: 999px; padding: 1px 8px; background: #FFFFFF; }}
.sw-flag-reason {{ color: {TOKENS['text']}; font-size: 15px; line-height: 1.5; }}
.sw-flag-next {{ color: {TOKENS['muted']}; font-size: 14px; margin-top: .35rem; }}
.sw-h2 {{ font-size: 26px; font-weight: 600; color: {TOKENS['text']}; margin: .2rem 0 .6rem 0; letter-spacing: -0.01em; }}
.sw-muted {{ color: {TOKENS['muted']}; font-size: 13px; }}
.sw-table {{ width: 100%; border-collapse: collapse; margin: .4rem 0 .8rem 0; font-size: 14px; background: #FFFFFF; }}
.sw-table th {{ text-align: left; color: {TOKENS['muted']}; font-weight: 600; border-bottom: 1px solid {TOKENS['border']}; padding: .45rem .5rem; background: {TOKENS['panel']}; }}
.sw-table td {{ color: {TOKENS['text']}; border-bottom: 1px solid {TOKENS['grid']}; padding: .45rem .5rem; vertical-align: top; }}
@media (max-width: 640px) {{
  .sw-table thead {{ display: none; }}
  .sw-table tr {{ display: block; border: 1px solid {TOKENS['border']}; border-radius: 12px; margin-bottom: .5rem; padding: .3rem .2rem; }}
  .sw-table td {{ display: flex; gap: .6rem; border: none; padding: .2rem .5rem; }}
  .sw-table td::before {{ content: attr(data-label); color: {TOKENS['muted']}; min-width: 7.5rem; flex-shrink: 0; }}
}}
.sw-later {{ margin-top: 1.2rem; padding: .8rem 1rem; border-radius: 14px; border: 1px dashed #C4C9D0; color: {TOKENS['muted']}; font-size: 14px; }}
/* ---- accessibility: slider value contrast, radio focus, chart-toolbar focus ---- */
[data-testid$="ThumbValue"] {{ color: {TOKENS['accent_text']} !important; }}
[data-testid="stRadioOption"]:has(input:focus-visible) {{ outline: 3px solid {TOKENS['accent_text']} !important; outline-offset: 2px; border-radius: 8px; }}
[data-testid="stElementToolbar"]:focus-within {{ opacity: 1 !important; visibility: visible !important; }}
[data-testid="stElementToolbar"] button:focus-visible {{ outline: 3px solid {TOKENS['accent_text']} !important; outline-offset: 1px; }}
/* ---- home, navigation, focus ---- */
:focus-visible, button:focus-visible, a:focus-visible, [role="radio"]:focus-visible, [role="tab"]:focus-visible, [role="link"]:focus-visible {{
  outline: 2px solid {TOKENS['accent']} !important; outline-offset: 2px; }}
[data-testid="stBaseButton-primary"] {{ background: {TOKENS['accent']} !important; border-color: {TOKENS['accent']} !important;
  color: #1A0B02 !important; font-weight: 600; box-shadow: 0 4px 14px rgba(210,86,10,.18); }}
[data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.06); }}
[data-testid="stBaseButton-primary"] p {{ color: #1A0B02 !important; }}
[data-testid="stBaseButton-primaryFormSubmit"] {{ background: {TOKENS['accent']} !important; border-color: {TOKENS['accent']} !important; color: #1A0B02 !important; font-weight: 600; }}
[data-testid="stBaseButton-primaryFormSubmit"] p {{ color: #1A0B02 !important; }}
[data-baseweb="tag"] {{ background: #FFE3CF !important; border: 1px solid rgba(210,86,10,.45) !important; }}
[data-baseweb="tag"], [data-baseweb="tag"] *, [data-testid="stMultiSelect"] span, [data-testid="stMultiSelect"] [data-baseweb="tag"] * {{ color: #3A1803 !important; fill: #3A1803 !important; }}
.sw-status {{ display: inline-block; font-family: ui-monospace, Menlo, monospace; letter-spacing: .12em; font-size: 11.5px;
  color: #7A3108; border: 1px solid rgba(210,86,10,.40); background: #FFF4EC; border-radius: 999px; padding: 4px 12px; }}
.sw-brand {{ font-size: 20px; font-weight: 700; margin: 1.6rem 0 .4rem 0; color: {TOKENS['text']}; letter-spacing: -0.01em; }}
.sw-hero {{ font-size: 52px; line-height: 1.06; font-weight: 650; letter-spacing: -0.025em; color: {TOKENS['text']};
  margin: .2rem 0 1rem 0; padding: 0; }}
.sw-hero-sub {{ font-size: 19px; line-height: 1.5; color: {TOKENS['muted']}; max-width: 560px; margin-bottom: 1.4rem; }}
.sw-hero-note {{ font-size: 14px; color: {TOKENS['muted']}; margin-top: .6rem; }}
.sw-frame-head {{ display: flex; justify-content: space-between; align-items: center; gap: .6rem; flex-wrap: wrap;
  font-size: 13px; color: {TOKENS['muted']}; margin: .2rem 0 .4rem 0; }}
.sw-caption {{ font-size: 13px; color: {TOKENS['muted']}; margin-top: .5rem; }}
.sw-home-section {{ margin-top: 3.2rem; }}
.sw-h3 {{ font-size: 22px; font-weight: 600; color: {TOKENS['text']}; margin: .8rem 0 .5rem 0; padding: 0; }}
.sw-body {{ font-size: 16px; line-height: 1.55; color: {TOKENS['muted']}; }}
.sw-list {{ color: {TOKENS['text']}; font-size: 15px; line-height: 1.7; padding-left: 1.1rem; margin-bottom: 1rem; }}
.sw-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .9rem; margin: .4rem 0 1rem 0; }}
.sw-card2 {{ background: {TOKENS['panel']}; border: 1px solid {TOKENS['border']}; border-radius: 16px; padding: 1rem 1.1rem;
  color: {TOKENS['text']}; font-size: 15px; line-height: 1.5; }}
.sw-card2-k {{ font-family: ui-monospace, Menlo, monospace; letter-spacing: .12em; font-size: 11.5px; color: {TOKENS['accent_text']};
  margin-bottom: .45rem; text-transform: uppercase; }}
.sw-card2-planned {{ border-style: dashed; color: {TOKENS['muted']}; background: #FFFFFF; }}
.sw-card2-planned .sw-card2-k {{ color: {TOKENS['muted']}; }}
.sw-close {{ margin-top: 3rem; padding-top: 1.6rem; border-top: 1px solid {TOKENS['border']}; }}
.sw-footer {{ margin: 2.4rem 0 1rem 0; font-size: 13px; color: {TOKENS['muted']}; }}
@media (max-width: 640px) {{
  .sw-hero {{ font-size: 36px; }}
  .sw-hero-sub {{ font-size: 17px; }}
  .sw-home-section {{ margin-top: 2.2rem; }}
}}
[data-testid="stExpandSidebarButton"] {{ border: 1px solid {TOKENS['accent']} !important; border-radius: 999px !important;
  color: {TOKENS['text']} !important; padding: 2px 12px 2px 8px !important; background: #FFF4EC !important; }}
[data-testid="stExpandSidebarButton"]::after {{ content: "Menu"; font-size: 14px; margin-left: 4px; color: {TOKENS['text']}; }}
[data-testid="stTopNavLink"] p {{ font-size: 15px; }}
[data-testid="stHeaderLogo"], [data-testid="stSidebarLogo"] {{ height: 34px !important; max-width: 200px !important; cursor: pointer; border-radius: 6px; }}
.st-key-sw_logo_link {{ display: none !important; }}
@media (max-width: 640px) {{ [data-testid="stHeaderLogo"], [data-testid="stSidebarLogo"] {{ height: 28px !important; max-width: 164px !important; }} }}
[data-testid="stTooltipContent"], [data-baseweb="tooltip"] div {{ background: #FFFFFF !important; color: {TOKENS['text']} !important; }}
</style>
"""
