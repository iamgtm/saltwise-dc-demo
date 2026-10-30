"""DC Storm Outlook view: next 72 hours of NWS atmospheric forecast for one DC reference point, plus official alerts.

Rendered only when selected. No request is sent until a person presses Load or Refresh.
"""
import json

import altair as alt
import pandas as pd
import streamlit as st

import demo_config  # noqa: E402  (public demo build settings)

import page_media

import nws_outlook as nws
import scenarios
from storm_lab_view import chart, html_table
from theme import TOKENS


def et(iso, fmt="%a %-I %p"):
    if not iso:
        return "not supplied"
    return pd.Timestamp(iso).tz_convert(nws.ET).strftime(fmt)


def age(iso, now):
    if not iso:
        return "unknown"
    m = int((now - pd.Timestamp(iso).to_pydatetime()).total_seconds() // 60)
    return f"{m} min" if m < 120 else f"{m // 60} h {m % 60} min"


@st.cache_resource
def http_cache():
    """Process-wide, so a page reload reuses or revalidates the stored response instead of re-requesting it."""
    return nws.HttpCache()


def _load():
    st.session_state["nws_outlook"] = nws.load_outlook(nws.RequestBudget(), http_cache())


def _open_storm_lab(ctx):
    st.session_state["forecast_context"] = ctx
    st.session_state["view"] = "storm"            # standalone app.py view switch
    st.session_state["_goto_storm"] = True        # top navigation (main.py): switch page on this rerun


def _download(outlook, fresh, now):
    st.download_button("Download NWS outlook (JSON)", json.dumps(nws.export_record(outlook, fresh, now), indent=2, default=str),
                       file_name="saltwise_nws_outlook.json", mime="application/json", key="outlook_download")


def _groups(periods, kind):
    """Consecutive periods whose NWS text names `kind`, as (start, end) ranges. No arrival time is inferred."""
    out, cur = [], None
    for p in periods:
        if kind in p["precip_types"]:
            if cur and cur[1] == p["start"]:
                cur[1] = p["end"]
            else:
                cur = [p["start"], p["end"]]
                out.append(cur)
    return out


def render():
    _render_body()
    page_media.credits(["outlook_dc_storm", "outlook_clouds"])


def _media_band():
    page_media.band("outlook_clouds", "Time-lapse of clouds moving over the Grand Canyon, Arizona (not DC)", key="ol_media_clouds",
                    note="Illustrative time-lapse: clouds over the Grand Canyon, Arizona, November 2025 (not DC). Not a forecast, "
                         "radar or satellite view, and not conditions at any SaltWise location.", scale=1.18, pos="50% 35%")


def _render_body():
    budget = nws.RequestBudget()
    c = budget.counts()
    outlook = st.session_state.get("nws_outlook")
    # Opening: heading, forecast status and the load control stay at the top, beside an illustrative photograph.
    with page_media.split("outlook_dc_storm", "16th Street NW in Washington, DC, during the January 25, 2026 snowstorm", key="ol_photo_storm",
                          note="Illustrative photograph: 16th Street NW, Washington, DC, during the January 25, 2026 storm. Not current "
                               "conditions and not a forecast for any road or SaltWise location.", pos="50% 58%"):
        st.markdown(
            '<div class="sw-section">DC STORM OUTLOOK · NEXT 72 HOURS · NWS ATMOSPHERIC FORECAST</div>'
            f'<h2 class="sw-h2">{nws.REF_LABEL}</h2>'
            f'<div class="sw-banner">NWS PROVIDER FORECAST · AIR, NOT PAVEMENT — {nws.REF_NOTE}</div>',
            unsafe_allow_html=True)
        st.button("Refresh NWS forecast" if outlook else "Load NWS forecast", key="nws_load", type="primary", on_click=_load,
                  disabled=not demo_config.LIVE_WEATHER_REQUESTS,
                  help=None if demo_config.LIVE_WEATHER_REQUESTS else "Disabled in this demo build: live weather requests are turned off.")
        st.caption(f"Requests go to {nws.SOURCE} only when you press this button: no automatic polling or retries. "
               f"Weather requests logged — this app process: {c['run']} of {budget.caps['per_run']}; "
               f"today (America/New_York): {c['day']} of {budget.caps['per_day']}, failed attempts included.")
    if not outlook:
        st.info("Not loaded. No NWS request has been sent from this page yet." if demo_config.LIVE_WEATHER_REQUESTS else
                "Demo build: live NWS forecast loading is disabled, so no outlook is shown and no request can be sent. "
                "In the full app, the forecast is fetched only when a person presses Load.")
        _media_band()
        return
    now = nws.now_utc()
    outlook, fresh = nws.assess(outlook, now)
    h, meta = outlook["hourly"], outlook["hourly_meta"]

    # ---- source times ----
    grid = outlook.get("grid") or {}
    if h:
        st.markdown(
            f'<div class="sw-rule-note">Grid {grid.get("office")} {grid.get("x")},{grid.get("y")} · '
            f'NWS generated {et(h["generated_at"], "%a %-I:%M %p")} (age {age(h["generated_at"], now)}) · '
            f'NWS update time {et(h["update_time"], "%a %-I:%M %p")} (age {age(h["update_time"], now)}) · '
            f'retrieved {et(meta["retrieved_at"], "%a %-I:%M %p")} ({meta["cache"]}). '
            f'{nws.freshness.describe(fresh, "Freshness")}</div>', unsafe_allow_html=True)

    # ---- official alerts, separate from SaltWise review flags ----
    st.markdown('<div class="sw-section">OFFICIAL NWS ALERTS · DC · NOT SALTWISE REVIEW FLAGS</div>', unsafe_allow_html=True)
    if outlook["alerts_error"]:
        st.error(f"Alerts unavailable: {outlook['alerts_error']}. Active alerts are unknown, not absent.")
    elif not outlook["alerts"]["alerts"]:
        st.markdown(f'<div class="sw-flag sw-flag-none">NWS returned no active alerts for DC '
                    f'(retrieved {et(outlook["alerts_meta"]["retrieved_at"], "%a %-I:%M %p")}). This does not mean '
                    'hazardous weather is impossible.</div>', unsafe_allow_html=True)
    for a in (outlook["alerts"] or {}).get("alerts", []):
        st.markdown(
            f'<div class="sw-flag"><div class="sw-flag-head"><span class="sw-flag-title">{a["event"] or "Alert"}</span>'
            f'<span class="sw-chip-ill">OFFICIAL NWS ALERT</span></div>'
            f'<div class="sw-flag-reason">{a["headline"] or "No headline supplied"}</div>'
            f'<div class="sw-flag-next">Onset {et(a["onset"] or a["effective"])} · ends {et(a["ends"])} · expires '
            f'{et(a["expires"])} · {a["sender"] or ""} · <a href="{a["link"]}" target="_blank">NWS source</a></div></div>',
            unsafe_allow_html=True)
    for a in (outlook["alerts"] or {}).get("withheld", []):
        st.caption(f"Withheld alert ({a['event']}): {a['reason']}.")

    # ---- hourly forecast ----
    st.markdown('<div class="sw-section">HOURLY FORECAST · AIR TEMPERATURE · PRECIPITATION PROBABILITY · WIND</div>',
                unsafe_allow_html=True)
    if outlook["hourly_error"] or not h:
        st.error(f"Hourly forecast unavailable: {outlook['hourly_error']}. No simulated forecast is shown in its place.")
        _download(outlook, fresh, now)
        return
    periods = h["periods"]
    if not periods:
        st.warning("NWS returned no current or future hourly periods. Nothing is shown.")
        _download(outlook, fresh, now)
        return
    cov = h["coverage_hours"]
    st.markdown(f"**Coverage:** {len(periods)} hourly periods, {et(periods[0]['start'])} – {et(periods[-1]['end'])} "
                f"({cov:g} h of the next {nws.OUTLOOK_HOURS} h)"
                + ("" if cov >= nws.OUTLOOK_HOURS else f". NWS returned only {cov:g} h of usable current and future periods.")
                + (f" {len(h['withheld'])} past or invalid period(s) withheld." if h["withheld"] else ""))

    df = pd.DataFrame([{"time": pd.Timestamp(p["start"]).tz_convert(nws.ET).tz_localize(None), "air": p["air_temperature"],
                        "pop": p["precip_probability_pct"]} for p in periods])
    unit = periods[0]["air_temperature_unit"] or "?"
    base = alt.Chart(df).encode(x=alt.X("time:T", title=None, axis=alt.Axis(format="%a %-I %p", labelColor=TOKENS["muted"])))
    air = base.mark_line(color=TOKENS["air"], strokeWidth=2.5).encode(
        y=alt.Y("air:Q", title=f"Air · NWS forecast (°{unit})", scale=alt.Scale(zero=False),
                axis=alt.Axis(labelColor=TOKENS["muted"], titleColor=TOKENS["air"])),
        tooltip=[alt.Tooltip("time:T", format="%a %-I %p"), alt.Tooltip("air:Q", title=f"Air °{unit}")])
    pop = base.mark_bar(color=TOKENS["accent"], opacity=0.55).encode(
        y=alt.Y("pop:Q", title="Precipitation probability · NWS (%)", scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(labelColor=TOKENS["muted"], titleColor=TOKENS["accent"])),
        tooltip=[alt.Tooltip("time:T", format="%a %-I %p"), alt.Tooltip("pop:Q", title="Probability %")])
    chart(alt.vconcat(air.properties(height=170, width="container", title=alt.Title(
        "Air temperature · NWS (not pavement)", color=TOKENS["text"], anchor="start")),
        pop.properties(height=110, width="container", title=alt.Title(
            "Precip. probability · NWS forecast", color=TOKENS["text"], anchor="start")))
        .configure(background="transparent").configure_view(strokeWidth=0).configure_axis(gridColor=TOKENS["grid"]))
    n_pop_missing = sum(1 for p in periods if p["precip_probability_pct"] is None)
    if n_pop_missing:
        st.caption(f"{n_pop_missing} period(s) have no precipitation probability from NWS; shown as unavailable, not 0%.")

    lines = []
    for kind, _ in nws.PRECIP:
        g = _groups(periods, kind)
        if g:
            lines.append(f"<li><b>{kind.capitalize()}</b> named in NWS text: "
                         + "; ".join(f"{et(s)} – {et(e)}" for s, e in g) + "</li>")
    st.markdown('<div class="sw-flag sw-flag-none"><b>Precipitation types named by NWS</b>'
                + (f"<ul>{''.join(lines)}</ul>" if lines else
                   "<br>No rain, snow, sleet or freezing rain is named in the NWS hourly text for these periods.")
                + '<span class="sw-muted">Matched only where the NWS short forecast names the type. Probabilities are '
                  'as supplied; no amounts, severity or arrival times are added.</span></div>', unsafe_allow_html=True)

    with st.expander(f"Hourly periods ({len(periods)})"):
        st.markdown(html_table([{"Time (ET)": et(p["start"]),
                                 "Air (NWS forecast)": "Unavailable" if p["air_temperature"] is None
                                 else f"{p['air_temperature']:g} °{p['air_temperature_unit']}",
                                 "Precip. probability": "Unavailable" if p["precip_probability_pct"] is None
                                 else f"{p['precip_probability_pct']:g}%",
                                 "Wind": " ".join(x for x in (p["wind_direction"], p["wind_speed"]) if x) or "Unavailable",
                                 "NWS text": p["short_forecast"] or "Unavailable"} for p in periods],
                               ["Time (ET)", "Air (NWS forecast)", "Precip. probability", "Wind", "NWS text"]),
                    unsafe_allow_html=True)
    if h["withheld"]:
        with st.expander(f"Withheld periods ({len(h['withheld'])})"):
            for w in h["withheld"]:
                st.markdown(f"- {w['start'] or 'no start time'}: {w['reason']}")

    _media_band()

    # ---- handoff to Storm Lab ----
    st.markdown('<div class="sw-section">USE A FORECAST WINDOW IN STORM LAB · READ-ONLY CONTEXT</div>', unsafe_allow_html=True)
    bounds = [p["start"] for p in periods] + [periods[-1]["end"]]
    default_end = bounds[min(12, len(bounds) - 1)]
    start, end = st.select_slider("Forecast window", bounds, value=(bounds[0], default_end), format_func=et,
                                  key="outlook_window")
    if start == end:
        st.caption("Choose a window of at least one hour.")
    ctx = nws.window_context(outlook, start, end)
    st.caption("Storm Lab shows this window as read-only context beside its synthetic scenario. It does not change "
               "treatment locations, rates or application counts, and the synthetic pavement scenario is not shifted "
               "to these dates. People make every treatment decision.")
    st.button("Open Storm Lab with this forecast window", key="open_storm_lab", disabled=start == end,
              on_click=_open_storm_lab, args=(ctx,))
    if st.session_state.pop("_goto_storm", False) and st.session_state.get("_saltwise_nav"):
        import nav
        st.switch_page(nav.PAGES["storm"])

    _download(outlook, fresh, now)
    st.session_state["outlook_state"] = {"n_periods": len(periods), "coverage_hours": cov, "window": [start, end],
                                         "n_alerts": len((outlook["alerts"] or {}).get("alerts", []))}


def context_panel(ctx):
    """Read-only forecast context shown in Storm Lab."""
    rng = ctx["air_temperature_range"]
    pop = ctx["highest_precip_probability_pct"]
    types = ", ".join(f"{t} ({v['n_periods']} h, {et(v['first'])} – {et(v['last'])} start)"
                      for t, v in ctx["precip_types_reported"].items()) or "none named in NWS text"
    alerts = (", ".join(ctx["active_alerts"]) or "none returned") if ctx["alerts_available"] else "unavailable (request failed)"
    rows = [
        {"Item": "Forecast window (real dates)", "NWS forecast context":
            f"{et(ctx['window']['start'], '%a %b %-d, %-I %p')} – {et(ctx['window']['end'], '%a %b %-d, %-I %p')} ET · "
            f"{ctx['n_periods']} hourly periods"},
        {"Item": "Storm Lab scenario below", "NWS forecast context":
            f"Synthetic, dated {pd.Timestamp(scenarios.SCENARIO_TIME).strftime('%a %b %-d, %Y')}; not shifted to the forecast dates"},
        {"Item": "Air temperature range", "NWS forecast context":
            f"{rng[0]:g}–{rng[1]:g} °{ctx['air_temperature_unit']} (air, not pavement)" if rng else "Unavailable"},
        {"Item": "Highest precipitation probability", "NWS forecast context":
            (f"{pop:g}%" if pop is not None else "Unavailable")
            + (f" · {ctx['periods_missing_precip_probability']} period(s) unavailable" if ctx["periods_missing_precip_probability"] else "")},
        {"Item": "Precipitation types", "NWS forecast context": types},
        {"Item": "Official NWS alerts (DC)", "NWS forecast context": alerts},
        {"Item": "Source times", "NWS forecast context":
            f"NWS update {et(ctx['issued']['update_time'], '%a %-I:%M %p')} · retrieved {et(ctx['retrieved_at'], '%a %-I:%M %p')}"},
    ]
    st.markdown('<div class="sw-section">NWS FORECAST CONTEXT · READ-ONLY · ' + ctx["label"].upper() + '</div>',
                unsafe_allow_html=True)
    st.markdown(html_table(rows, ["Item", "NWS forecast context"]), unsafe_allow_html=True)
    st.markdown(f'<div class="sw-rule-note">{ctx["note"]} The Storm Lab below still uses its synthetic scenario '
                'and its own accounting window.</div>', unsafe_allow_html=True)
