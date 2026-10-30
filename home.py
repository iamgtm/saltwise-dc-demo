"""Home page: five-slide showcase (showcase.py), then How it works, Why sustainability matters, What's available today.

Never contacts a weather provider. Every number shown comes from saltwise_contract on synthetic data and is labeled.
"""
from datetime import timedelta

import pandas as pd
import streamlit as st

import saltwise_contract as sc
import scenarios
import closing
import dc_showcase
import showcase
from data import get_view
from theme import TOKENS


def _go(page_key):
    import nav
    st.switch_page(nav.PAGES[page_key])


def default_plans():
    """The Storm Lab's default illustrative plans: baseline treats every point twice; scenario treats flagged points once."""
    E = pd.Timestamp(scenarios.SCENARIO_TIME)
    t0, t3 = E.isoformat(), (E + timedelta(hours=6)).isoformat()
    flagged = {lid for lid, *_ in scenarios.LOCATIONS
               if any(f["id"] in ("treatment_review", "refreeze_review")
                      for f in (get_view(lid, "F", "overnight", 0)[1]["flags"] or []))}
    return {"baseline": {lid: {"initial": t0, "later": [t3]} for lid, *_ in scenarios.LOCATIONS},
            "scenario": {lid: {"initial": t0 if lid in flagged else None, "later": []} for lid, *_ in scenarios.LOCATIONS}}


def default_comparison(use_submitted=True):
    """Default illustrative comparison (or the last submitted Storm Lab assumptions when use_submitted)."""
    E = pd.Timestamp(scenarios.SCENARIO_TIME)
    inp = st.session_state.get("storm_inputs") if use_submitted else None
    if inp:
        hours = {"overnight": 12, "24h": 24}[inp["window_key"]]
        plans, lm, rate, source = inp["plans"], inp["lane_miles"], inp["rate"], "your last submitted Storm Lab assumptions"
    else:
        hours, rate, source = 12, 200.0, "default illustrative assumptions"
        plans, lm = default_plans(), {lid: 1.0 for lid, *_ in scenarios.LOCATIONS}
    window = {"start": E.isoformat(), "end": (E + timedelta(hours=hours)).isoformat()}
    return sc.compare_plans(plans["baseline"], plans["scenario"], lm, rate, window), source


STATUS = [
    ("simulated", "Demo interface", "Atmospheric weather view; live forecasts and alerts are disabled in this public demo.",
     [("Open Storm Outlook", "outlook", "home_outlook")]),
    ("simulated", "Simulated", "Five-road pavement scenarios, illustrative review flags and treatment and material comparisons.",
     [("Open Road Weather", "weather", "home_explore_weather"), ("Open Storm Lab", "storm", "home_open_storm")]),
    ("planned", "Pilot next", "Partner validation of forecast accuracy, treatment policies and required road service.",
     [("See Evidence", "evidence", "home_evidence")]),
]

HOME_CSS = f"""<style>
.sw-notice {{ display:flex; flex-wrap:wrap; gap:.4rem .8rem; align-items:center; margin:0 0 .9rem 0; font-size:13.5px; color:{TOKENS['muted']}; }}
.sw-lower {{ margin-top:5.5rem; padding-bottom:1.6rem; border-bottom:1px solid #D9E0E6; margin-bottom:0; }}
.sw-lower .sw-h2 {{ font-size:40px; line-height:1.2; letter-spacing:-.03em; font-weight:300; max-width:820px; }}
.sw-lede {{ font-size:18px; line-height:1.6; color:{TOKENS['muted']}; max-width:720px; margin:.2rem 0 1rem 0; }}
.sw-unmeasured {{ display:inline-block; margin:.2rem 0 0 0; font-size:15px; color:#7A3108; border-left:3px solid {TOKENS['accent']};
  padding:.45rem .8rem; background:#FFF4EC; border-radius:6px; }}
.sw-status-card {{ background:{TOKENS['panel']}; border:1px solid {TOKENS['border']}; border-radius:18px; padding:1.2rem 1.25rem; min-height:150px; margin-bottom:.7rem; }}
.sw-status-card.planned {{ border-style:dashed; background:#FFFFFF; }}
.sw-status-k {{ font-family:ui-monospace, Menlo, monospace; letter-spacing:.14em; font-size:12px; text-transform:uppercase; margin-bottom:.6rem; }}
.sw-status-card.connected .sw-status-k {{ color:{TOKENS['accent_text']}; }}
.sw-status-card.simulated .sw-status-k {{ color:{TOKENS['air']}; }}
.sw-status-card.planned .sw-status-k {{ color:{TOKENS['muted']}; }}
.sw-status-card p {{ font-size:16px; line-height:1.55; color:{TOKENS['text']}; margin:0; }}
.sw-foot {{ margin-top:5rem; padding:1.6rem 0 .6rem; border-top:1px solid {TOKENS['border']}; display:flex; flex-wrap:wrap; gap:.4rem 1.2rem;
  align-items:baseline; color:{TOKENS['muted']}; font-size:14px; }}
.sw-foot b {{ color:{TOKENS['text']}; font-size:16px; }}
@media (prefers-reduced-motion: no-preference) {{
  @supports (animation-timeline: view()) {{
    .sw-reveal {{ animation: sw-rise linear both; animation-timeline: view(); animation-range: entry 0% entry 40%; }}
    @keyframes sw-rise {{ from {{ opacity:.35; transform: translateY(14px); }} to {{ opacity:1; transform:none; }} }}
  }}
}}
@media (max-width: 760px) {{
  .sw-lower {{ margin-top:3.6rem; }}
  .sw-lower .sw-h2 {{ font-size:29px; }}
}}
</style>"""


def render():
    st.markdown(HOME_CSS, unsafe_allow_html=True)
    target = showcase.render()
    if target:
        _go(target)
    # "Make every treatment count": the sustainability story, told as four scroll-driven chapters
    st.markdown('<div class="sw-lower"><div class="sw-section">SUSTAINABILITY</div>'
                '<h2 class="sw-h2">Make every treatment count.</h2>'
                '<p class="sw-lede">Use salt where it helps and reduce avoidable use, while keeping winter access and '
                'required road service. Four ideas sit behind every SaltWise comparison.</p>'
                '<div class="sw-unmeasured">Actual salt reductions, financial savings and environmental benefits have '
                'not yet been measured.</div></div>', unsafe_allow_html=True)
    target = dc_showcase.render()
    if target:
        _go(target)

    # ---------------- What's available today ----------------
    st.markdown('<div class="sw-lower sw-reveal"><div class="sw-section">WHAT’S AVAILABLE TODAY</div>'
                '<h2 class="sw-h2">What works now, what is simulated, and what is planned.</h2></div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for col, (cls, label, desc, links) in zip(cols, STATUS):
        with col:
            st.markdown(f'<div class="sw-status-card {cls}"><div class="sw-status-k">{label}</div><p>{desc}</p></div>',
                        unsafe_allow_html=True)
            for text, page, key in links:
                if st.button(text, key=key):
                    _go(page)

    # ---------------- sustainability closing + footer ----------------
    target = closing.render()
    if target:
        _go(target)
