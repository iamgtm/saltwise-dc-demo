"""Shared data access for every page. Reading these never contacts a weather provider.

Simulated mode reads synthetic scenarios. Provider mode reads the trusted data service's saved snapshots through
evidence_snapshot (read-only SQLite); no page runs a second fetching system.
"""
import pandas as pd
import streamlit as st

import evidence_snapshot
import freshness
import saltwise_contract as sc
import scenarios

WINDOWS = {"overnight": ("Overnight · 9 p.m.–9 a.m.", 12), "24h": ("Next 24 h", 24), "72h": ("Next 72 h", 72)}
PROVIDER_WINDOWS = {"overnight": "Next 12 h", "24h": "Next 24 h", "72h": "Next 72 h"}   # provider mode starts now
HOURS_TO_KEY = {12: "overnight", 24: "24h", 72: "72h"}


@st.cache_data
def load_scenario(location_id, reload_count):
    """reload_count only busts the cache: reloading re-reads the synthetic scenario, never new weather."""
    return scenarios.scenario(location_id)


def get_view(location_id, units, window_key, reload_count):
    fx = load_scenario(location_id, reload_count)
    settings = {"units": units, "mode": "live", "source_mode": "synthetic_fixture",
                "evaluation_time": fx["evaluation_time"], "window_hours": WINDOWS[window_key][1],
                "freshness_limits": scenarios.SCENARIO_ONLY_FRESHNESS_LIMITS}
    return fx, sc.build_view(fx, settings)


def storm_get_view(lid, units, hours):
    """Adapter used by Storm Lab (it asks by window length in hours)."""
    return get_view(lid, units, HOURS_TO_KEY[hours], st.session_state.get("reload_count", 0))


def fmt_time(iso):
    return pd.Timestamp(iso).strftime("%a %-I %p").replace(" 0", " ")


@st.cache_resource(show_spinner=False)
def load_snapshots(store_token, reload_count):
    """Read-only snapshot read, shared and never mutated by callers. store_token changes when the trusted service writes;
    reload_count re-reads on request. No provider request."""
    return evidence_snapshot.read_all()


def get_provider_view(location_id, units, window_key, reload_count):
    """Provider-data view from saved snapshots, built by the same contract as the scenarios, evaluated at this minute."""
    now = evidence_snapshot.now_utc().replace(second=0, microsecond=0)
    fx, status = evidence_snapshot.fixture(load_snapshots(evidence_snapshot.store_token(), reload_count), location_id, now)
    settings = {"units": units, "mode": "live", "source_mode": "provider", "evaluation_time": fx["evaluation_time"],
                "window_hours": WINDOWS[window_key][1], "freshness_limits": freshness.contract_limits() or evidence_snapshot.FRESHNESS_PENDING}
    view = sc.build_view(fx, settings)
    view["export"]["data_mode"] = "provider_snapshot"
    view["export"]["provenance"] = fx["provenance"]
    return fx, view, evidence_snapshot.with_freshness_badge(status, view)


def fmt_time_exact(ts):
    """Provider periods can be 15 minutes long, so labels carry minutes (DC local time)."""
    return pd.Timestamp(ts).tz_convert("America/New_York").strftime("%a %-I:%M %p")
