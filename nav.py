"""Top-navigation pages for main.py. Only the selected page's code runs; Home never contacts a weather provider."""
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent


def _home():
    import home
    home.render()


def _outlook():
    import outlook_view
    outlook_view.render()


def _storm():
    import storm_lab_view
    from data import storm_get_view
    storm_lab_view.render(storm_get_view)


def _evidence():
    import evidence_view
    evidence_view.render()


PAGES = {
    "home": st.Page(_home, title="Home", url_path="home", default=True),
    "outlook": st.Page(_outlook, title="Storm Outlook", url_path="storm-outlook"),
    "weather": st.Page(HERE / "app.py", title="Road Weather", url_path="road-weather"),
    "storm": st.Page(_storm, title="Storm Lab", url_path="storm-lab"),
    "evidence": st.Page(_evidence, title="Evidence", url_path="evidence"),
}
ORDER = ["home", "outlook", "weather", "storm", "evidence"]
