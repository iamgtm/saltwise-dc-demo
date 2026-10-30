"""SaltWise DC - Stage D dashboard: air/pavement views, illustrative review flags, the Storm Lab, and the DC Storm Outlook.

The weather/review view and Storm Lab render exclusively from synthetic scenarios via saltwise_contract.build_view().
Only the DC Storm Outlook view contacts a provider (NWS api.weather.gov), and only when a person presses Load or Refresh.
No credentials are loaded.
"""
import html
import json
import sys
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import demo_config  # noqa: E402  (public demo build settings)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import briefing  # noqa: E402
import dpw_feedback  # noqa: E402
import freezing_marker  # noqa: E402
import review_items  # noqa: E402
import road_map  # noqa: E402
import saltwise_contract as sc  # noqa: E402
import scenarios  # noqa: E402
from theme import CSS, TOKENS  # noqa: E402

from data import PROVIDER_WINDOWS, WINDOWS, fmt_time, fmt_time_exact, get_provider_view, get_view  # noqa: E402
import evidence_snapshot  # noqa: E402

# NAV: this script is running as the "Road Weather" page inside main.py's top navigation. Standalone (streamlit run
# app.py, and the evaluator's harness) it remains the complete single-page dashboard with its own view switch.
NAV = bool(st.session_state.get("_saltwise_nav"))
if not NAV:
    st.set_page_config(page_title="SaltWise DC", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

UNITS = {"F": "°F", "C": "°C"}
LOC_IDS = [x[0] for x in scenarios.LOCATIONS]
SHORT = {x[0]: x[2] for x in scenarios.LOCATIONS}


# ---------- header (standalone only; the Road Weather page opens with road_maintenance's copy beside the photo) ----------
if not NAV:
    st.markdown(
    '<div class="sw-eyebrow"><span class="sw-chip">D</span> SALTWISE DC · STAGE D · REVIEW &amp; STORM LAB</div>'
    '<h1 class="sw-title">Salt<span class="sw-accent">Wise</span> DC</h1>'
    '<p class="sw-sub">Reduce avoidable salt use while keeping required road service. '
    'SaltWise shows the evidence; people make every treatment decision.</p>', unsafe_allow_html=True)
SYNTHETIC_BANNER = (
    '<div class="sw-banner">SYNTHETIC SCENARIO · ILLUSTRATIVE WEATHER — the weather, pavement and Storm Lab views use '
    'synthetic data and nothing in them is a real forecast. Only the DC Storm Outlook view requests live NWS forecasts, '
    'and only when you press Load.</div>')
PROVIDER_BANNER = (
    '<div class="sw-banner">PROVIDER DATA · SAVED SNAPSHOTS — air: NWS hourly forecast; pavement: Xweather modeled forecast '
    '(a provider model, not a sensor observation). Read-only snapshots from the trusted data service: this page sends no '
    'weather request. Review rules remain illustrative; people make every treatment decision.</div>')
# The data-mode switch is below the view switch; session state already holds its current value at the top of each rerun.
_provider_page = st.session_state.get("data_mode") == "provider" and (NAV or st.session_state.get("view", "weather") == "weather")
st.markdown(PROVIDER_BANNER if _provider_page else SYNTHETIC_BANNER, unsafe_allow_html=True)

if "reload_count" not in st.session_state:
    st.session_state.reload_count = 0

# ---------- view switch (Storm Lab code runs only when selected) ----------
VIEWS = {"weather": "Weather & review", "storm": "Storm Lab", "outlook": "DC Storm Outlook"}
view_key = "weather" if NAV else st.radio("View", list(VIEWS), format_func=lambda k: VIEWS[k], horizontal=True,
                                          key="view", label_visibility="collapsed")
if view_key == "storm":
    import storm_lab_view
    from data import storm_get_view
    storm_lab_view.render(storm_get_view)
    st.stop()
if view_key == "outlook":
    import outlook_view
    outlook_view.render()
    st.stop()

# ---------- opening: one set of selectors and the selected-road readout (left), DC street photo (right) ----------
import road_maintenance as rm  # noqa: E402
if NAV:
    left, right = st.columns([1, 1.08], gap="large", vertical_alignment="top")
    with right:
        rm.photo()
else:
    left = st.container()
with left:
    if NAV:
        rm.opening_copy()
    # data mode (explicit; the simulated scenario stays the default)
    DATA_MODES = {"simulated": "Simulated scenario", "provider": "Provider data · saved snapshots"}
    st.session_state.setdefault("data_mode", "simulated")
    if demo_config.DEMO_BUILD:
        st.session_state["data_mode"] = "simulated"          # provider snapshots are not part of the demo package
    data_mode = st.radio("Data mode", list(DATA_MODES), format_func=lambda k: DATA_MODES[k], horizontal=True, key="data_mode",
                         disabled=demo_config.DEMO_BUILD,
                         help=("Demo build: saved provider snapshots are not included, so only the simulated scenario is available."
                               if demo_config.DEMO_BUILD else
                               "Provider data reads the trusted data service's saved NWS and Xweather snapshots. It sends no request."))
    PROVIDER = data_mode == "provider"
    st.session_state.setdefault("location", "michigan_ave_ne_bridge")    # default via state so it persists across pages
    location_id = st.radio("Location", LOC_IDS, format_func=lambda i: SHORT[i], horizontal=True, key="location",
                           label_visibility="visible" if NAV else "collapsed")
    window_key = st.radio("Time window", list(WINDOWS), format_func=lambda k: PROVIDER_WINDOWS[k] if PROVIDER else WINDOWS[k][0], horizontal=True, key="window")
    c2, c3 = st.columns([1, 1.4])
    units = c2.radio("Units", list(UNITS), format_func=lambda u: UNITS[u], horizontal=True, key="units")
    with c3:
        if PROVIDER:
            if st.button("Re-read snapshots", key="reload", help="Re-reads the trusted service's saved snapshots. It sends no weather request."):
                st.session_state.reload_count += 1
            st.caption("Re-reads saved snapshots — sends no weather request.")
        else:
            if st.button("Reload scenario", key="reload", help="Re-reads the synthetic scenario file. It does not fetch newly issued weather."):
                st.session_state.reload_count += 1
            st.caption("Reloads the synthetic scenario — not new weather.")
    summary_slot = st.container()          # filled once the inspected time is known (below), from the same view as the chart
    if NAV and st.button("Storm Lab handoff →", key="rm_open_storm", help="Opens Storm Lab, which compares all five demonstration points in °F and pounds. The road and units selected here are not carried over."):
        import nav
        st.switch_page(nav.PAGES["storm"])
AIR_L, PAV_L = ("Air · NWS forecast", "Pavement · Xweather modeled") if PROVIDER else ("Air temperature", "Pavement temperature")

# ---------- location overview: the one map, then the five point cards ----------
st.markdown('<div class="sw-section">DEMONSTRATION POINTS</div>', unsafe_allow_html=True)
map_slot = st.container()                 # filled after the selected period is known (below); the map reads existing views only
map_entries = []
cols = st.columns(5)
for col, (lid, name, short, road, profile) in zip(cols, scenarios.LOCATIONS):
    sel = " sw-card-selected" if lid == location_id else ""
    if PROVIDER:
        _, v_card, s_card = get_provider_view(lid, units, window_key, st.session_state.reload_count)
    else:
        _, v_card = get_view(lid, units, window_key, st.session_state.reload_count)
    map_entries.append((lid, short, v_card, s_card if PROVIDER else None))
    n_rev = len(v_card["flags"] or [])
    rev_badge = (f'<div class="sw-review-count">▲ {n_rev} review flag{"s" if n_rev != 1 else ""}</div>' if n_rev
                 else '<div class="sw-review-none">No review flags in window</div>')
    if PROVIDER:      # three separate statuses: DCGIS geography, provider road name, bridge-specific modeling
        meta = (f'Location: {s_card["geo_label"]} · Road match: {s_card["road_label"]}'
                + (f' · Bridge modeling: {s_card["bridge_label"]}' if s_card["is_bridge"] else ""))
        col.markdown(
            f'<div class="sw-card{sel}"><div class="sw-card-title">{name}</div>'
            f'<div class="sw-card-meta">{meta}</div>{rev_badge}'
            f'<div class="sw-badge">{s_card["pavement_badge"]}</div></div>', unsafe_allow_html=True)
    else:
        col.markdown(
            f'<div class="sw-card{sel}"><div class="sw-card-title">{name}</div>'
            f'<div class="sw-card-meta">Scenario: {scenarios.PROFILE_LABEL[profile]}</div>{rev_badge}'
            f'<div class="sw-badge">Location not yet validated</div></div>', unsafe_allow_html=True)
    if NAV:   # the whole card is a button (CSS overlay): same shared handler as the map markers
        col.button(f"Select {name}", key=f"rwcard_{lid}", on_click=road_map.select_location, args=(lid,))


if PROVIDER:
    fx, view, loc_status = get_provider_view(location_id, units, window_key, st.session_state.reload_count)
else:
    fx, view = get_view(location_id, units, window_key, st.session_state.reload_count)
    loc_status = None
U = UNITS[units]
E = pd.Timestamp(fx["evaluation_time"])
w_end = E + timedelta(hours=WINDOWS[window_key][1])

# ---------- chart data from the evidence view ----------
rows = []
for s in view["series"]:
    if s["quantity"] not in ("air_temperature", "pavement_temperature"):
        continue
    label = AIR_L if s["quantity"] == "air_temperature" else PAV_L
    for p in s["points"]:
        rows.append({"time": pd.Timestamp(p["valid_start"]), "end": pd.Timestamp(p["valid_end"]), "value": p["value"], "series": label,
                     "kind": p.get("kind", s["kind"]), "surface": p.get("surface_condition") or "—"})
df = pd.DataFrame(rows, columns=["time", "end", "value", "series", "kind", "surface"])
cov = view["coverage"]["pavement"].get("last_period_start")
pav_end = pd.Timestamp(cov) + timedelta(hours=1) if cov else E
GAP_LABEL = "Pavement series ends · later periods unavailable"
if PROVIDER:      # shade from the end of the current pavement values (never extended), labeled with the reason
    pav_ends = [pd.Timestamp(p["valid_end"]) for s in view["series"] if s["quantity"] == "pavement_temperature"
                for p in s["points"] if p["value"] is not None]
    pav_end = max(pav_ends) if pav_ends else E
    if loc_status["pavement_short"]:
        GAP_LABEL = f"No pavement values · withheld ({loc_status['pavement_short']})"
    elif loc_status.get("freshness_short"):
        GAP_LABEL = f"No pavement values · withheld ({loc_status['freshness_short']})"
    elif not pav_ends:
        GAP_LABEL = "No current pavement values · ended periods withheld"
times = sorted(df["time"].unique()) if not df.empty else [E]
slider_labels = [(fmt_time_exact if PROVIDER else fmt_time)(t) for t in times]

name = view["location"]["name"]
title = f"{name} ({U})"
subtitle = ("Air: NWS hourly forecast · Pavement: Xweather modeled forecast, not a sensor · saved provider snapshots" if PROVIDER
            else "Air vs. pavement temperature · synthetic scenario, illustrative")
x0 = min([E] + list(df["time"])) if PROVIDER and not df.empty else E      # provider periods can start before this minute
colors = alt.Scale(domain=[AIR_L, PAV_L], range=[TOKENS["air"], TOKENS["accent"]])
base = alt.Chart(df).encode(x=alt.X("time:T", title=None, scale=alt.Scale(domain=[x0, w_end]),
                                    axis=alt.Axis(format="%a %-I %p", labelColor=TOKENS["muted"], tickCount=8)))
ref_val = view["freezing_reference"]["value"]
vals = [v for v in df["value"].dropna()] + [ref_val]
y_dom = [min(vals) - 4, max(vals) + 4]
lines = base.mark_line(strokeWidth=3, interpolate="monotone").encode(
    y=alt.Y("value:Q", title=f"Temperature ({U})", scale=alt.Scale(domain=y_dom, zero=False), axis=alt.Axis(titleColor=TOKENS["muted"], labelColor=TOKENS["muted"])),
    color=alt.Color("series:N", scale=colors, legend=alt.Legend(orient="top", title=None, labelColor=TOKENS["text"], **({"labelLimit": 320} if PROVIDER else {}))),
    strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=[AIR_L, PAV_L],
                                                          range=[[6, 3], [1, 0]]), legend=None),
    tooltip=[alt.Tooltip("series:N"), alt.Tooltip("time:T", format="%a %-I %p"),
             alt.Tooltip("value:Q", title=f"Value ({U})", format=".1f"), alt.Tooltip("surface:N", title="Surface")])
ref = alt.Chart(pd.DataFrame({"y": [ref_val]})).mark_rule(strokeDash=[2, 4], color=TOKENS["text"], opacity=0.55).encode(y="y:Q")
ref_txt = alt.Chart(pd.DataFrame({"y": [ref_val], "x": [E]})).mark_text(
    align="left", dx=4, dy=-7, color=TOKENS["muted"], fontSize=12).encode(
    x="x:T", y="y:Q", text=alt.value(f"Freezing reference {ref_val:g}{U} (physical, not a policy)"))
layers = [ref, ref_txt, lines]
if pav_end < w_end:
    gap = pd.DataFrame({"start": [pav_end], "end": [w_end]})
    layers.insert(0, alt.Chart(gap).mark_rect(color=TOKENS["unavailable"], opacity=0.35).encode(x="start:T", x2="end:T"))
    layers.append(alt.Chart(gap).mark_rule(color=TOKENS["accent"], strokeDash=[5, 3]).encode(x="start:T"))
    layers.append(alt.Chart(gap).mark_text(align="left", dx=6, dy=14, color=TOKENS["accent"], fontSize=12).encode(
        x="start:T", y=alt.value(0), text=alt.value(GAP_LABEL)))
rev_rows = [{"time": pd.Timestamp(r["valid_start"]), "value": r["pavement"],
             "concerns": ", ".join(sc.FLAG_TITLES[c] for c in r["concerns"])}
            for r in view["review_periods"] if r["pavement"] is not None]
if rev_rows:
    layers.append(alt.Chart(pd.DataFrame(rev_rows)).mark_point(shape="triangle-up", size=120, filled=True, color=TOKENS["accent"],
                                                               stroke=TOKENS["bg"], strokeWidth=1).encode(
        x="time:T", y="value:Q", tooltip=[alt.Tooltip("time:T", format="%a %-I %p"), alt.Tooltip("concerns:N", title="Needs review")]))
# First returned pavement forecast period at or below the freezing reference: the period itself, never an interpolated crossing.
tfmt = fmt_time_exact if PROVIDER else fmt_time
frz = freezing_marker.find(view)
frz_label = freezing_marker.chart_label(frz, tfmt)
if frz_label:
    fp = frz["period"]
    f_t = pd.Timestamp(fp["valid_start"])
    f_df = pd.DataFrame({"time": [f_t], "value": [fp["value"]], "label": [frz_label], "period": [f"{tfmt(fp['valid_start'])} – {tfmt(fp['valid_end'])}"]})
    # The label sits in the bottom strip (y_dom pads 4 units below every value, so no line reaches it), joined to the
    # diamond by a dotted rule; near either edge it aligns inward so it stays inside the plot at narrow widths.
    f_frac = (f_t - x0) / (w_end - x0)
    f_align = "left" if f_frac < 0.25 else "right" if f_frac > 0.75 else "center"
    layers.append(alt.Chart(f_df).mark_rule(strokeDash=[1, 3], color=TOKENS["text"], opacity=0.6).encode(
        x="time:T", y="value:Q", y2=alt.datum(y_dom[0])))
    layers.append(alt.Chart(f_df).mark_point(shape="diamond", size=280, filled=False, strokeWidth=2.5, color=TOKENS["text"]).encode(
        x="time:T", y="value:Q", tooltip=[alt.Tooltip("label:N", title="Forecast reference"), alt.Tooltip("period:N", title="Returned period"),
                                          alt.Tooltip("value:Q", title=f"Pavement ({U})", format=".1f")]))
    layers.append(alt.Chart(f_df).mark_text(align=f_align, dx={"left": -4, "right": 4, "center": 0}[f_align], dy=-10,
                                            color=TOKENS["text"], fontSize=12, fontWeight="bold").encode(
        x="time:T", y=alt.datum(y_dom[0]), text="label:N"))
slider_label =st.session_state.get("slider") if st.session_state.get("slider") in slider_labels else slider_labels[0]
sel_time = times[slider_labels.index(slider_label)]
layers.append(alt.Chart(pd.DataFrame({"t": [sel_time]})).mark_rule(color=TOKENS["text"], opacity=0.35).encode(x="t:T"))
chart = alt.layer(*layers).properties(height=380, title=alt.Title(title, subtitle=subtitle, color=TOKENS["text"], subtitleColor=TOKENS["muted"], fontSize=17,
                                       subtitleFontSize=13, anchor="start")) \
    .configure_view(strokeWidth=0).configure(background="transparent") \
    .configure_axis(gridColor=TOKENS["grid"], domainColor=TOKENS["grid"])

st.markdown('<div id="sw-rw-chart" class="sw-rm-anchor"></div>', unsafe_allow_html=True)
st.markdown('<div class="sw-panel-start"></div>', unsafe_allow_html=True)
st.vega_lite_chart(spec=chart.to_dict(validate=False), width="stretch")  # skip ~60 ms schema validation (profiled)
if PROVIDER:
    fresh_note = evidence_snapshot.pavement_freshness_html(view)   # pavement policy status and its own explanation
    if fresh_note:
        st.markdown(fresh_note, unsafe_allow_html=True)
    st.caption("Solid orange: pavement, Xweather modeled forecast (a provider model, not a sensor observation). Dashed: air, "
               "NWS hourly forecast. The pavement line stops where the returned forecast stops and is never extended; air "
               "never stands in for pavement. Shaded: no pavement values. ▲ Triangles: periods that need human review "
               "(illustrative rules, not policy).")
    for msg in [g["reason"] for g in view["gaps"] if g.get("valid_start") is None] + [w["reason"] for w in view["withheld"]]:
        st.markdown(f'<div class="sw-flag sw-flag-none">{html.escape(msg)}</div>', unsafe_allow_html=True)
    src = []
    if any(s["quantity"] == "air_temperature" and s["points"] for s in view["series"]):
        src.append('Air data: <a href="https://www.weather.gov/" target="_blank" rel="noopener">National Weather Service</a> (api.weather.gov)')
    if view["attribution"]:
        src.append('Pavement data: <a href="https://www.xweather.com/" target="_blank" rel="noopener">Powered by Vaisala Xweather</a>')
    if src:
        st.markdown('<div class="sw-rule-note">' + " · ".join(src) + "</div>", unsafe_allow_html=True)
else:
    st.caption(f"Solid orange: pavement (synthetic modeled shape). Dashed grey: air (synthetic NWS shape). "
               f"Shaded: no pavement values. Gaps in the line: missing pavement values. "
               f"▲ Triangles: periods that need human review (illustrative rules). All weather is illustrative.")
st.markdown(f'<div class="sw-rule-note" data-testid="freezing-marker-note">◇ {html.escape(freezing_marker.describe(frz, tfmt))}</div>',
            unsafe_allow_html=True)

# ---------- time readout ----------
if st.session_state.get("slider") not in slider_labels:
    st.session_state.pop("slider", None)          # options changed (data mode or snapshot): drop the stale selection
slider_label = st.select_slider("Inspect a time", options=slider_labels, value=slider_label, key="slider")
sel_time = times[slider_labels.index(slider_label)]
# Provider pavement has 15-minute steps while air is hourly: read the period that contains the selected time.
at = df[(df["time"] <= sel_time) & (df["end"] > sel_time)] if PROVIDER else df[df["time"] == sel_time]


def reading(series_name):
    r = at[at["series"] == series_name]
    if r.empty or pd.isna(r["value"].iloc[0]):
        return "Unavailable", ""
    return f"{r['value'].iloc[0]:.1f}{U}", r["surface"].iloc[0]


air_v, _ = reading(AIR_L)
pav_v, surf = reading(PAV_L)
m1, m2, m3 = st.columns(3)
m1.metric("Air temperature", air_v)
m2.metric("Pavement temperature", pav_v)
m3.metric("Pavement surface", surf if pav_v != "Unavailable" else "Unavailable")
with map_slot:      # same views, units, window and selected period as the chart; a marker click sets st.session_state.location
    road_map.render(road_map.map_data(map_entries, location_id, units, pd.Timestamp(sel_time), PROVIDER, tfmt))
if NAV:
    with summary_slot:  # the same card as the map's detail, for the same road, units, window and inspected time
        rm.summary(road_map.location_card(location_id, SHORT[location_id], view, loc_status, road_map.registry_points().get(location_id),
                                          pd.Timestamp(sel_time), units, PROVIDER, tfmt), PROVIDER)

# ---------- review (stage C) ----------
flags = view["flags"] or []
if NAV:
    rm.pair()          # "Every road stays in service": after the chart and readout, before the review section
st.markdown('<div id="sw-rw-review" class="sw-rm-anchor"></div><div class="sw-section">WHICH PERIODS NEED HUMAN REVIEW?</div>'
            '<div class="sw-rule-note">Illustrative review rules — not approved operational policy. '
            'Flags prompt a person to look closer; people make every treatment decision.</div>', unsafe_allow_html=True)
if not flags:
    st.markdown('<div class="sw-flag sw-flag-none">No review flags in the selected window for this scenario. '
                'This is not a statement that treatment is unnecessary; conditions beyond the shown evidence are unknown.</div>',
                unsafe_allow_html=True)
for f in flags:
    st.markdown(
        f'<div class="sw-flag"><div class="sw-flag-head"><span class="sw-flag-title">▲ {f["title"]}</span>'
        f'<span class="sw-flag-time">{sc._when(f["valid_time"])}</span><span class="sw-chip-ill">ILLUSTRATIVE RULE</span></div>'
        f'<div class="sw-flag-reason">{f["reason"]}</div>'
        f'<div class="sw-flag-next"><b>Next step:</b> {f["next_step"]}</div>'
        + (f'<div class="sw-flag-reason" data-testid="evidence-qualification"><b>Evidence status:</b> '
           f'{html.escape(f["evidence_qualification"])}</div>' if f.get("evidence_qualification") else "")
        + (f'<div class="sw-flag-reason">{dpw_feedback.RAIN_NOTE}</div>' if f["id"] == "rain_timing_review" else "")
        + '</div>', unsafe_allow_html=True)
changing = dpw_feedback.changing_conditions(view) if flags else None
if changing:
    st.markdown(f'<div class="sw-rule-note" data-testid="changing-conditions-note">{html.escape(changing)}</div>',
                unsafe_allow_html=True)
if view["review_periods"]:
    cols_rp = ["Time", "Pavement", "Surface", "Forecast", "Concerns (can overlap)"]
    rp = [{"Time": sc._when(r["valid_start"]),
           "Pavement": f"{r['pavement']:.1f}{U}" if r["pavement"] is not None else "Unavailable",
           "Surface": r["surface"] or "Unavailable",
           "Forecast": f"{r['precipitation']} ({r['precipitation_pct']}%)" if r["precipitation"] else "—",
           "Concerns (can overlap)": ", ".join(sc.FLAG_TITLES[c] for c in r["concerns"])} for r in view["review_periods"]]
    # Responsive HTML table: on narrow screens each period becomes a labeled stacked row, so Concerns stay visible.
    st.markdown('<table class="sw-table"><thead><tr>' + "".join(f"<th>{c}</th>" for c in cols_rp) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f'<td data-label="{c}">{r[c]}</td>' for c in cols_rp) + "</tr>" for r in rp)
                + "</tbody></table>", unsafe_allow_html=True)

# ---------- traceable review items and the deterministic planner briefing ----------
review_pack = review_items.build(view, fx, "provider" if PROVIDER else "simulated")
planner_brief = briefing.build([review_pack], view["export"]["evaluation_time"], "provider_snapshot" if PROVIDER else "synthetic_fixture")
view["export"].update(review_items=review_pack["items"], briefing=planner_brief,
                      review_context={k: review_pack[k] for k in ("coverage", "freshness", "location_uncertainty", "conflicting")})
with st.expander(f"Planner briefing · Python-generated · {len(review_pack['items'])} traceable review item(s)", expanded=False):
    st.markdown(planner_brief["text"])

# ---------- evidence ----------
gaps = [g for g in view["gaps"] if g["quantity"] == "pavement_temperature"]
with st.expander("Evidence details", expanded=False):
    if PROVIDER:
        import evidence_snapshot
        st.markdown(evidence_snapshot.details_markdown(fx["provenance"], view["data_checks"]))
    else:
        st.markdown(f"**Source mode:** synthetic fixture scenario — illustrative, not live weather  \n"
                f"**Scenario time:** {fx['evaluation_time']} · **Scenario issued:** {fx['nws_hourly']['properties']['updateTime']}  \n"
                f"**Location validation:** {fx['location']['validation_status']}  \n"
                f"**Road identity:** {view['location']['road_match']['returned_name']} — "
                f"status *{view['location']['road_match']['status']}*. {view['location']['road_match'].get('note') or ''}")
    st.caption(dpw_feedback.ROAD_CONTEXT)
    srows = [{"Series": s["quantity"].replace("_", " "), "Source": s["source"], "Kind": s["kind"], "Unit": s["unit"],
              "Periods in window": len(s["points"]),
              "First": s["points"][0]["valid_start"] if s["points"] else "—",
              "Last": s["points"][-1]["valid_start"] if s["points"] else "—"} for s in view["series"]]
    st.dataframe(pd.DataFrame(srows), hide_index=True, width="stretch")
    st.markdown(f"**Pavement coverage ends:** {cov or 'no pavement records'} — {view['coverage']['pavement'].get('end_reason') or ''}")
    st.markdown("**Missing or unavailable evidence:**")
    for g in gaps:
        st.markdown(f"- {g['valid_start'] or 'whole series'}: {g['reason']}")
    for w in view["withheld"]:
        st.markdown(f"- Withheld: {w['reason']}")
    st.caption("Missing evidence never means treatment is unnecessary and never removes a road from assumed service.")

export_json = json.dumps(view["export"], indent=2)
st.download_button("Download evidence (JSON)", export_json, file_name=f"saltwise_{'provider_' if PROVIDER else ''}{location_id}_{units}_{window_key}.json",
                   mime="application/json", key="download")

if NAV:
    import nav
    rm.workflow()
    rm.plow()
    rm.whole_storm()
    _, right_b = st.columns([1, 1.35], gap="large")                   # buttons sit under the whole-storm text
    with right_b:
        b1, b2 = st.columns([1.55, 1])
        if b1.button("Compare full-storm material use in Storm Lab", key="to_storm_lab"):
            st.switch_page(nav.PAGES["storm"])
        if b2.button("How evidence is labeled →", key="rm_evidence"):
            st.switch_page(nav.PAGES["evidence"])
    rm.landscape()
st.markdown('<div class="sw-later">Storm Lab (stage D) — open the Storm Lab view to compare total material use over the '
            'whole storm window, including later applications, under editable simulation assumptions. Operational '
            'treatment thresholds are illustrative; the freezing line is a physical reference.</div>', unsafe_allow_html=True)

# Machine-readable state for the evaluator's interaction tests (no credentials).
st.session_state["saltwise_state"] = {
    "location_id": location_id, "units": units, "window": window_key, "slider": slider_label,
    "chart_title": title, "series_locations": sorted({s["location_id"] for s in view["series"]}),
    "n_air": int((df["series"] == AIR_L).sum()), "n_pavement": int((df["series"] == PAV_L).sum()),
    "readout": {"air": air_v, "pavement": pav_v}, "export_location": view["export"]["location"]["location_id"],
    "export_units": view["export"]["units"], "source_mode": view["source_mode"], "reload_count": st.session_state.reload_count,
    "flag_ids": sorted(f["id"] for f in flags), "n_review_periods": len(view["review_periods"]),
    "data_mode": data_mode, "pavement_withheld": bool(loc_status and loc_status["pavement_reason"]),
    "n_review_items": len(review_pack["items"]),
    "freezing_marker": {"status": frz["status"], "valid_start": frz["period"] and frz["period"]["valid_start"]},
    "changing_conditions": bool(changing),
}
st.session_state["saltwise_export_json"] = export_json
