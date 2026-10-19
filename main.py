"""SaltWise DC with top navigation: Home, Storm Outlook, Road Weather, Storm Lab, Evidence.

Launch: streamlit run main.py. (app.py also still runs on its own as the single-page dashboard.)
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nav  # noqa: E402
from storm_lab_view import PERSIST_PREFIXES  # noqa: E402
from theme import CSS  # noqa: E402
import logo_link  # noqa: E402
import demo_config  # noqa: E402  (shared review build settings)

st.set_page_config(page_title="SaltWise DC", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(demo_config.BANNER_HTML, unsafe_allow_html=True)   # demo build: simulation mode, live requests disabled
# Persistent identity: one local SVG logo in the navigation header on every page (clicking it opens Home).
LOGO = str(Path(__file__).resolve().parent / "assets" / "saltwise_logo.svg")
st.logo(LOGO, size="large", icon_image=LOGO)
logo_link.mount()
st.session_state["_saltwise_nav"] = True

# Streamlit discards a widget's value when its page is not rendered. Re-storing these keys every run keeps the
# selected location, units, window and Storm Lab form fields when people move between pages.
for k in list(st.session_state):
    if k in ("location", "units", "window", "data_mode") or (isinstance(k, str) and k.startswith(PERSIST_PREFIXES)):
        st.session_state[k] = st.session_state[k]

st.navigation([nav.PAGES[k] for k in nav.ORDER], position="top").run()
