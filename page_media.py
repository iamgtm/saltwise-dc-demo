"""Storm Outlook and Storm Lab media: a split opening (the page's own heading and controls beside a photograph) and one
broad media band between existing sections, built on the Road Weather zoom_media component (enters enlarged and settles
into its final framing inside a clipped frame as it scrolls in; videos muted, looping and inline, with posters; reduced
motion shows the final framing). Decorative and illustrative only: never current conditions, an observation, a forecast,
a simulation result or DC practice. Sources, original dimensions and licenses: static/media/SOURCES.json, also listed on
the Evidence page. Everything runs in the browser: no reruns, model calls or weather requests.
"""
import html

import streamlit as st

import media
from road_maintenance import zoom_media

CSS = """<style>
[class*="st-key-pm_split_"] { border-bottom: 1px solid #D9E0E6; padding-bottom: clamp(18px, 2.2vw, 30px); margin-bottom: 6px; }
[class*="st-key-pm_band_"] { margin: 34px 0 8px; }
.sw-pm-note { font-size: 12.5px; color: #6B7280; line-height: 1.45; margin: 8px 0 0; }
.sw-pm-credits { font-size: 12.5px; color: #6B7280; line-height: 1.5; margin: 28px 0 0; padding-top: 10px; border-top: 1px solid #E5E9EE; max-width: 110ch; }
</style>"""


def split(slot, alt, key, note, ratio="16 / 10", scale=1.15, pos=None):
    """Returns the left column for the page's heading and controls; the photograph sits beside it (below it on phones)."""
    st.markdown(CSS, unsafe_allow_html=True)
    with st.container(key=f"pm_split_{key}"):
        left, right = st.columns([1, 1.05], gap="large", vertical_alignment="center")
        with right:
            zoom_media(slot, alt, ratio=ratio, scale=scale, key=key, pos=pos)
            st.markdown(f'<p class="sw-pm-note">{html.escape(note)}</p>', unsafe_allow_html=True)
    return left


def band(slot, alt, key, note, ratio="21 / 9", scale=1.2, pos=None):
    """Full-width media between two existing sections."""
    with st.container(key=f"pm_band_{key}"):
        zoom_media(slot, alt, ratio=ratio, scale=scale, key=key, full=True, pos=pos)
        st.markdown(f'<p class="sw-pm-note">{html.escape(note)}</p>', unsafe_allow_html=True)


def credits(slots):
    rec = {r["slot"]: r for r in media.records()}
    parts = "; ".join(f"{rec[s]['credit_label']}: {rec[s]['creator']}, {rec[s]['license']}" for s in slots)
    st.markdown(f'<p class="sw-pm-credits">Photographs and video on this page are illustrative scenery, not current conditions, observations, '
                f'forecasts, simulation results or DC practice. {html.escape(parts)}. All via Wikimedia Commons; sources, original dimensions '
                'and changes are listed on the Evidence page.</p>', unsafe_allow_html=True)
