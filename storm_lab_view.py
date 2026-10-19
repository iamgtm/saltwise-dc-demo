"""Storm Lab view (stage D): how does changing treatment timing affect total salt use across the whole storm?

Imported and rendered only when the Storm Lab view is selected. Every input is an editable simulation
assumption - not a measured DC road length, an approved application rate, or a description of DC practice.
"""
import json
from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

import readiness
import saltwise_contract as sc
import scenarios
import storm_snapshot
from theme import TOKENS

WINDOWS = {"overnight": ("Overnight · 9 p.m.–9 a.m.", 12), "24h": ("Next 24 h", 24)}
NONE = "None"


def _fmt(ts):
    return pd.Timestamp(ts).strftime("%a %-I %p")


def html_table(rows, columns):
    """Responsive table: columns on desktop, labeled stacked rows on narrow screens (see theme .sw-table)."""
    head = "".join(f"<th>{c}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f'<td data-label="{c}">{r.get(c, "")}</td>' for c in columns) + "</tr>" for r in rows)
    return f'<table class="sw-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def chart(spec_chart):
    # Build the Vega-Lite spec without Altair's JSON-schema validation (about 60 ms per chart in profiling);
    # the chart content is unchanged.
    st.vega_lite_chart(spec=spec_chart.to_dict(validate=False), width="stretch")


def _init(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


# Widget keys whose values main.py carries across page changes (Streamlit drops state of widgets not rendered).
PERSIST_PREFIXES = ("sl_", "lm_", "bi_", "bl_", "si_", "rd")


def _views(units, window_hours, get_view, snap=None, start=None):
    """Synthetic scenario views, or provider views of an explicitly chosen evidence snapshot (never a live read)."""
    if snap:
        return storm_snapshot.views(snap[0], snap[1], units, window_hours, start)
    return {lid: get_view(lid, units, window_hours)[1] for lid, *_ in scenarios.LOCATIONS}


BASELINE_NOTE = ("Illustrative baseline (editable): every point treated at the start of the window plus one repeat at "
                 "3 a.m. This is a comparison reference, not DC practice.")


def _count(plan):
    """Initial and later application counts across locations."""
    return (sum(1 for p in plan.values() if p["initial"]), sum(len(p["later"]) for p in plan.values()))


def assumption_rows(inp, window, b, s_, views, data_label="Synthetic fixtures; results are a simulation"):
    """The applied inputs behind the comparison, one row each, so they read beside the results."""
    lm = inp["lane_miles"]
    vals = sorted(set(lm.values()))
    lm_text = (f"{sum(lm.values()):g} total · {vals[0]:g} per location" if len(vals) == 1
               else f"{sum(lm.values()):g} total · {vals[0]:g}–{vals[-1]:g} per location (see breakdown)")
    bi, bl = _count(inp["plans"]["baseline"])
    si, sl = _count(inp["plans"]["scenario"])
    missing = sum(1 for v in views.values() if any(f["id"] == "evidence_review" for f in (v["flags"] or [])))
    return [
        {"Assumption": "Accounting window", "In this comparison":
            f"{_fmt(window['start'])} – {_fmt(window['end'])}, every later / catch-up application inside it",
         "Kind": "Editable"},
        {"Assumption": "Application rate", "In this comparison": f"{inp['rate']:g} lb per lane-mile",
         "Kind": "Editable · not an approved DC rate"},
        {"Assumption": "Lane-miles", "In this comparison": lm_text, "Kind": "Editable · not measured"},
        {"Assumption": "Baseline plan", "In this comparison":
            f"{bi} initial + {bl} later · start of window + a repeat 6 h later",
         "Kind": "Illustrative reference · not DC practice"},
        {"Assumption": "Scenario plan", "In this comparison": f"{si} initial + {sl} later / catch-up",
         "Kind": "Editable"},
        {"Assumption": "Salt price", "In this comparison":
            f"${inp['price']:,.0f} per US short ton" if inp["price"] else "Not given, so cost is unavailable",
         "Kind": "Editable"},
        {"Assumption": "Required road service", "In this comparison":
            f"All {len(views)} locations stay in assumed service" + (f", including {missing} with missing evidence" if missing else ""),
         "Kind": "Constraint · not traded away"},
        {"Assumption": "Data", "In this comparison": data_label, "Kind": "Simulation"},
    ]


def render(get_view, window_key_default="overnight"):
    st.markdown(
        '<div class="sw-section">STORM LAB · SIMULATION · ILLUSTRATIVE ASSUMPTIONS</div>'
        '<h2 class="sw-h2">How does changing treatment timing affect total salt use across the whole storm?</h2>'
        '<div class="sw-banner">SIMULATION — every input below is an editable assumption, not a measured DC road length, '
        'an approved application rate, or DC practice. Results do not predict safety, chloride runoff, or deployment '
        'outcomes. Required road service and access are constraints the plan must still meet.</div>',
        unsafe_allow_html=True)

    ctx = st.session_state.get("forecast_context")
    if ctx:
        import outlook_view
        outlook_view.context_panel(ctx)
        st.button("Clear forecast context", key="clear_forecast_context",
                  on_click=lambda: st.session_state.pop("forecast_context", None))

    if "storm_inputs" not in st.session_state:
        st.session_state.storm_inputs = None
    applied_anchor = (st.session_state.storm_inputs or {}).get("anchor", "scenario")
    rec = _snapshot_panel(applied_anchor)
    snap = (rec, st.session_state.get("_storm_snapshot_data")) if rec else None
    anchored = applied_anchor == "snapshot" and snap is not None
    E = _anchor_time("snapshot" if anchored else "scenario", rec)
    if st.session_state.pop("_sl_reset_plan_keys", False):          # plans were re-timed to a new window start
        for lid, *_ in scenarios.LOCATIONS:
            for p in ("bi", "bl", "si", "sl"):
                st.session_state.pop(f"{p}_{lid}", None)

    # Comparison and its assumptions render first; the editing form renders below them. The form still runs
    # first so a submit updates the results in the same rerun.
    top = st.container()

    st.markdown('<div class="sw-section">EDIT ASSUMPTIONS · APPLIED WHEN YOU PRESS UPDATE</div>', unsafe_allow_html=True)
    # Form fields start from the last submitted assumptions (or the defaults), set through session state rather than
    # widget defaults, so they come back unchanged after visiting another page.
    applied = st.session_state.storm_inputs or {}
    _init("sl_window", applied.get("window_key", "overnight"))
    _init("sl_rate", applied.get("rate", 200.0))
    _init("sl_price", applied.get("price", 0.0))
    with st.form("storm_form", border=False):
        g1, g2, g3 = st.columns(3)
        win = g1.selectbox("Accounting window (same for baseline and scenario)", list(WINDOWS),
                           format_func=lambda k: WINDOWS[k][0], key="sl_window")
        rate = g2.number_input("Assumed application rate (lb per lane-mile)", min_value=0.0, step=10.0,
                               key="sl_rate", help="Illustrative assumption, not an approved DC rate.")
        price = g3.number_input("Salt price per US short ton (optional)", min_value=0.0, step=5.0, key="sl_price",
                                help="Leave at 0 to keep financial results unavailable.")
        anchor_opts = ["scenario"] + (["snapshot"] if rec else [])
        _init("sl_anchor", applied.get("anchor", "scenario"))
        if st.session_state["sl_anchor"] not in anchor_opts:
            st.session_state["sl_anchor"] = "scenario"
        anchor = st.selectbox("Accounting window starts at", anchor_opts, key="sl_anchor", format_func=lambda k: _anchor_label(k, rec),
                              help="An assumption, applied when you press Update. Application times keep their offsets from the window start.")
        hours = WINDOWS[win][1]
        times = [(E + timedelta(hours=h)).isoformat() for h in range(hours + 1)]
        views = _views("F", hours, get_view, snap if anchored else None, E)
        flagged = {lid for lid, v in views.items()
                   if any(f["id"] in ("treatment_review", "refreeze_review") for f in (v["flags"] or []))}
        st.markdown(f'<div class="sw-rule-note">{BASELINE_NOTE} The default scenario treats only points with review flags '
                    'at the start; add later or catch-up applications as needed.</div>', unsafe_allow_html=True)
        plans = {"baseline": {}, "scenario": {}}
        lane_miles = {}
        three_am = (E + timedelta(hours=6)).isoformat()
        with st.expander(f"Lane-miles and application times for each location ({len(scenarios.LOCATIONS)} locations)"):
            for lid, name, short, road, profile in scenarios.LOCATIONS:
                ab = applied.get("plans", {}).get("baseline", {}).get(lid)
                asc = applied.get("plans", {}).get("scenario", {}).get(lid)
                _init(f"lm_{lid}", applied.get("lane_miles", {}).get(lid, 1.0))
                _init(f"bi_{lid}", (ab["initial"] or NONE) if ab else times[0])
                _init(f"bl_{lid}", list(ab["later"]) if ab else [three_am])
                _init(f"si_{lid}", (asc["initial"] or NONE) if asc else (times[0] if lid in flagged else NONE))
                _init(f"sl_{lid}", list(asc["later"]) if asc else [])
                with st.container(border=True):
                    c0, c1, c2, c3, c4, c5 = st.columns([2.2, 1.2, 1.4, 2, 1.4, 2])
                    c0.markdown(f"**{name}**  \n<span class='sw-muted'>Synthetic road {road} · not validated</span>",
                                unsafe_allow_html=True)
                    lane_miles[lid] = c1.number_input("Lane-miles", min_value=0.0, step=0.5, key=f"lm_{lid}",
                                                      help="Assumed, not a measured DC road length.")
                    opts = [NONE] + times
                    b_init = c2.selectbox("Baseline initial", opts,
                                          format_func=lambda t: t if t == NONE else _fmt(t), key=f"bi_{lid}")
                    b_later = c3.multiselect("Baseline later / repeat", times, format_func=_fmt,
                                             key=f"bl_{lid}")
                    s_init = c4.selectbox("Scenario initial", opts,
                                          format_func=lambda t: t if t == NONE else _fmt(t), key=f"si_{lid}")
                    s_later = c5.multiselect("Scenario later / catch-up", times, format_func=_fmt,
                                             key=f"sl_{lid}")
                    plans["baseline"][lid] = {"initial": None if b_init == NONE else b_init, "later": list(b_later)}
                    plans["scenario"][lid] = {"initial": None if s_init == NONE else s_init, "later": list(s_later)}
        submitted = st.form_submit_button("Update Storm Lab", type="primary")
    if submitted or st.session_state.storm_inputs is None:
        new = {"window_key": win, "rate": rate, "price": price, "lane_miles": lane_miles, "plans": plans, "anchor": anchor}
        if st.session_state.storm_inputs is not None and anchor != applied_anchor:
            # The window start is an assumption: re-time every application by the same offset, then redraw the form.
            new_e = _anchor_time(anchor, rec)
            new["plans"] = _shift_plans(plans, new_e - E, new_e)
            st.session_state.storm_inputs = new
            st.session_state["_sl_reset_plan_keys"] = True
            st.rerun()
        st.session_state.storm_inputs = new
    inp = st.session_state.storm_inputs
    hours = WINDOWS[inp["window_key"]][1]
    window = {"start": E.isoformat(), "end": (E + timedelta(hours=hours)).isoformat()}
    res = sc.compare_plans(inp["plans"]["baseline"], inp["plans"]["scenario"], inp["lane_miles"], inp["rate"], window,
                           inp["price"] or None)
    views = _views("F", hours, get_view, snap if anchored else None, E)
    unresolved = sc.unresolved_requirements(inp["plans"]["scenario"], views)
    one_round = sum(inp["lane_miles"].get(lid, 0) * inp["rate"] for lid in
                    {lid for lid, v in views.items() if any(f["id"] in ("treatment_review", "refreeze_review") for f in (v["flags"] or []))})
    sens = sc.sensitivity(res["baseline"]["total_lb"], res["scenario"]["initial_lb"], one_round)

    b, s_, av = res["baseline"], res["scenario"], res["material_avoided_lb"]
    with top:
        st.markdown(f'<div class="sw-section">RESULTS · ACCOUNTING WINDOW {_fmt(window["start"])} – {_fmt(window["end"])}</div>',
                    unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Baseline total", f"{b['total_lb']:,.0f} lb", help="Initial + later applications, illustrative baseline")
        m1.caption(f"Initial {b['initial_lb']:,.0f} lb · later {b['later_lb']:,.0f} lb")
        m2.metric("Scenario total", f"{s_['total_lb']:,.0f} lb")
        m2.caption(f"Initial {s_['initial_lb']:,.0f} lb · later {s_['later_lb']:,.0f} lb")
        m3.metric("MATERIAL AVOIDED", f"{av:,.0f} lb",
                  help="Baseline total minus scenario total. Negative means the scenario uses more material.")
        if unresolved:
            m3.caption(f"INCOMPLETE: {len(unresolved)} later need(s) not included yet — see below and the sensitivity cases.")
        m3.caption("Scenario uses MORE material than the baseline." if av < 0 else
                   ("No difference in total material." if av == 0 else f"{res['material_avoided_short_tons']:.2f} US short tons (simulated)"))
        if res["cost"]:
            m4.metric("Cost difference", f"${res['cost']['cost_difference']:,.0f}")
            m4.caption(f"At an assumed ${res['cost']['price_per_short_ton']:,.0f} per short ton")
        else:
            m4.metric("Cost difference", "Unavailable")
            m4.caption("Enter a salt price to calculate.")

        st.markdown('<div class="sw-section">ASSUMPTIONS IN THIS COMPARISON · LAST APPLIED</div>', unsafe_allow_html=True)
        rows = assumption_rows(inp, window, b, s_, views, _data_label(rec if anchored else None))
        for col, half in zip(st.columns(2), (rows[:4], rows[4:])):
            col.markdown(html_table(half, ["Assumption", "In this comparison", "Kind"]), unsafe_allow_html=True)

        if unresolved:
            items = "".join(f"<li><b>{next(x[1] for x in scenarios.LOCATIONS if x[0] == u['location_id'])}</b> — "
                            f"{u['kind']}: {u['detail']}</li>" for u in unresolved)
            st.markdown(f'<div class="sw-flag"><div class="sw-flag-title">▲ Comparison incomplete — later need not yet included</div>'
                        f'<div class="sw-flag-reason">A deferred application is not a permanent reduction. Review flags still '
                        f'show possible treatment need after the scenario\'s last application, or evidence is missing:'
                        f'<ul>{items}</ul>Add later or catch-up applications under Edit assumptions below, or read the '
                        f'sensitivity cases.</div></div>', unsafe_allow_html=True)
        if res["baseline"]["outside_window"] or res["scenario"]["outside_window"]:
            st.warning("Some applications fall outside the accounting window and are not counted: "
                       + ", ".join(f"{o['location_id']} {o['kind']} {_fmt(o['time'])}"
                                   for o in res["baseline"]["outside_window"] + res["scenario"]["outside_window"]))

        bars = pd.DataFrame([{"plan": p, "part": part, "lb": res[k][f"{part}_lb"]}
                             for p, k in (("Baseline (illustrative)", "baseline"), ("Scenario", "scenario"))
                             for part in ("initial", "later")])
        chart(alt.Chart(bars).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("plan:N", title=None, sort=["Baseline (illustrative)", "Scenario"], axis=alt.Axis(labelColor=TOKENS["text"])),
            x=alt.X("sum(lb):Q", title="Material over the whole window (lb, simulated)",
                    axis=alt.Axis(labelColor=TOKENS["muted"], titleColor=TOKENS["muted"])),
            color=alt.Color("part:N", scale=alt.Scale(domain=["initial", "later"], range=[TOKENS["accent"], TOKENS["air"]]),
                            legend=alt.Legend(orient="bottom", title=None, labelColor=TOKENS["text"],
                                              labelExpr="datum.label == 'initial' ? 'Initial applications' : 'Later / repeat / catch-up'")),
            tooltip=["plan:N", "part:N", alt.Tooltip("lb:Q", format=",.0f")])
            .properties(height=alt.Step(44), width="container",
                        title=alt.Title("Baseline vs. scenario — total material", color=TOKENS["text"], anchor="start"))
            .configure(background="transparent").configure_view(strokeWidth=0).configure_axis(gridColor=TOKENS["grid"]))

    st.markdown('<div class="sw-section">SENSITIVITY · INITIAL PLAN HELD FIXED, LATER NEED VARIED (HYPOTHETICAL)</div>',
                unsafe_allow_html=True)
    srows = [{"Case": c["case"], "Initial": f"{c['initial_lb']:,.0f} lb", "Later": f"{c['later_lb']:,.0f} lb",
              "Scenario total": f"{c['scenario_total_lb']:,.0f} lb", "Material avoided": f"{c['material_avoided_lb']:,.0f} lb"}
             for c in sens]
    st.markdown(html_table(srows, ["Case", "Initial", "Later", "Scenario total", "Material avoided"]), unsafe_allow_html=True)
    chart(alt.Chart(pd.DataFrame([{"case": c["case"].split(" (")[0], "avoided": c["material_avoided_lb"]} for c in sens]))
          .mark_bar(cornerRadiusEnd=4, color=TOKENS["accent"]).encode(
              y=alt.Y("case:N", sort=None, title=None, axis=alt.Axis(labelColor=TOKENS["text"], labelLimit=260)),
              x=alt.X("avoided:Q", title="Material avoided vs. baseline (lb; negative = more material)",
                      axis=alt.Axis(labelColor=TOKENS["muted"], titleColor=TOKENS["muted"])),
              tooltip=["case:N", alt.Tooltip("avoided:Q", format=",.0f")])
          .properties(height=alt.Step(36), width="container").configure(background="transparent").configure_view(strokeWidth=0)
          .configure_axis(gridColor=TOKENS["grid"]))

    prow = [{"Location": name,
             "Lane-miles (assumed)": f"{inp['lane_miles'][lid]:g}",
             "Baseline": f"{b['per_location'][lid]['initial_lb']:,.0f} + {b['per_location'][lid]['later_lb']:,.0f} lb",
             "Scenario": f"{s_['per_location'][lid]['initial_lb']:,.0f} + {s_['per_location'][lid]['later_lb']:,.0f} lb",
             "Evidence": "Missing evidence — still in assumed service"
             if any(f["id"] == "evidence_review" for f in (views[lid]["flags"] or [])) else "See review flags"}
            for lid, name, *_ in scenarios.LOCATIONS]
    with st.expander("Per-location breakdown (initial + later)"):
        st.markdown(html_table(prow, ["Location", "Lane-miles (assumed)", "Baseline", "Scenario", "Evidence"]), unsafe_allow_html=True)
    cov = storm_snapshot.coverage_vs_window(rec, window) if rec else None
    if rec:
        _coverage_panel(cov, anchored)
    rd = _readiness_panel(inp, window)

    export = {"schema": "saltwise-storm-lab/1", "source_mode": "synthetic_fixture", "labels": sc.STORM_LABELS,
              "accounting_window": window, "assumptions": {"rate_lb_per_lane_mile": inp["rate"], "lane_miles": inp["lane_miles"],
                                                           "salt_price_per_short_ton": inp["price"] or None,
                                                           "baseline_note": "illustrative editable baseline, not DC practice"},
              "plans": inp["plans"], "results": res, "sensitivity": sens, "unresolved_requirements": unresolved,
              "formulas": {"material_per_application": "lane_miles x rate", "total": "sum of applications in window",
                           "material_avoided": "baseline total - scenario total"},
              "disclaimer": "Simulation only; does not predict safety, chloride runoff, or deployment outcomes.",
              "evidence_snapshot": rec, "window_anchor": inp.get("anchor", "scenario"), "coverage_vs_window": cov,
              "flags_source": f"evidence snapshot {rec['snapshot_id']}" if anchored else "synthetic scenario", "readiness": rd,
              "forecast_context": ctx or None,
              "forecast_context_note": "NWS atmospheric forecast shown as read-only context; it did not change the "
                                       "synthetic pavement scenario, locations, rates, application counts or results."}
    st.download_button("Download Storm Lab inputs and results (JSON)", json.dumps(export, indent=2),
                       file_name="saltwise_storm_lab.json", mime="application/json", key="storm_download")
    st.session_state["storm_state"] = {"baseline_total": b["total_lb"], "scenario_total": s_["total_lb"],
                                       "scenario_initial": s_["initial_lb"], "scenario_later": s_["later_lb"],
                                       "avoided": av, "cost": res["cost"], "unresolved": len(unresolved),
                                       "sensitivity_avoided": [c["material_avoided_lb"] for c in sens],
                                       "window_hours": hours, "export": export, "anchor": inp.get("anchor", "scenario"),
                                       "snapshot_id": rec["snapshot_id"] if rec else None, "readiness_status": rd["status"]}



def _anchor_time(anchor, rec):
    if anchor == "snapshot" and rec:
        return pd.Timestamp(rec["window_start_utc"]).tz_convert("America/New_York")
    return pd.Timestamp(scenarios.SCENARIO_TIME)


def _anchor_label(k, rec):
    if k == "snapshot" and rec:
        return f"Evidence snapshot time ({_fmt(_anchor_time('snapshot', rec))} · {rec['snapshot_id']})"
    return f"Synthetic scenario start ({_fmt(scenarios.SCENARIO_TIME)}, Dec 15)"


def _shift_plans(plans, shift, new_e):
    def mv(t):
        return None if t is None else (pd.Timestamp(t) + shift).tz_convert(new_e.tz).isoformat()
    return {k: {lid: {"initial": mv(p["initial"]), "later": [mv(t) for t in p["later"]]} for lid, p in v.items()} for k, v in plans.items()}


def _data_label(rec):
    if rec is None:
        return "Synthetic fixtures; results are a simulation"
    return f"Review flags from evidence snapshot {rec['snapshot_id']} (provider forecasts, read-only); material totals remain a simulation"


def _snapshot_panel(applied_anchor):
    """Explicit, person-chosen evidence snapshot: recorded once, never refreshed silently, never changes assumptions."""
    st.markdown('<div class="sw-section">EVIDENCE SNAPSHOT · IMPORTED ONLY WHEN YOU CHOOSE</div>', unsafe_allow_html=True)
    locked = applied_anchor == "snapshot" and st.session_state.get("storm_snapshot") is not None
    c1, c2 = st.columns(2)
    if c1.button("Use this evidence snapshot", key="use_snapshot", disabled=locked,
                 help="Records the trusted service's saved NWS and Xweather snapshots as they are now. Read-only; no weather request."):
        st.session_state["storm_snapshot"], st.session_state["_storm_snapshot_data"] = storm_snapshot.select()
    rec = st.session_state.get("storm_snapshot")
    if rec and c2.button("Stop using the snapshot", key="clear_snapshot", disabled=locked):
        st.session_state.pop("storm_snapshot", None)
        st.session_state.pop("_storm_snapshot_data", None)
        rec = None
    if locked:
        st.caption("The accounting window starts at the snapshot time. Switch it back to the scenario start under Edit assumptions "
                   "before replacing or removing the snapshot.")
    if not rec:
        st.caption("No evidence snapshot in use: Storm Lab review flags come from the synthetic scenario. Choosing a snapshot never "
                   "changes rates, lane-miles or application times.")
        return None
    st.markdown(f'<div class="sw-rule-note"><b>EVIDENCE SNAPSHOT IN USE · {rec["snapshot_id"]}</b> · selected {rec["selected_at_utc"]} · '
                'imported evidence only (read-only). Rates, lane-miles and application times stay editable assumptions; lane-miles '
                'and route lengths are never inferred from demonstration points.</div>', unsafe_allow_html=True)
    st.markdown(html_table(storm_snapshot.rows(rec), ["Location", "Location statuses", "Pavement (Xweather modeled)", "Air (NWS forecast)",
                                                      "Unresolved"]), unsafe_allow_html=True)
    return rec


def _coverage_panel(cov, anchored):
    st.markdown('<div class="sw-section">EVIDENCE COVERAGE VS ACCOUNTING WINDOW</div>', unsafe_allow_html=True)
    if not anchored:
        st.caption("The accounting window starts at the synthetic scenario date, which the evidence snapshot does not cover, so the "
                   "whole window is unsupported by provider evidence. To compare against the snapshot, set the window start to the "
                   "snapshot time under Edit assumptions.")

    def cell(x):
        if x["supported_h"] == 0:
            return f"Unsupported for the whole window ({x['unsupported_h']:g} h): {x['reason']}"
        if x["unsupported_h"] == 0:
            return f"Covered for the whole window ({x['supported_h']:g} h)"
        return (f"Covered {x['supported_h']:g} h; unsupported {x['unsupported_h']:g} h from "
                f"{_fmt(pd.Timestamp(x['unsupported_from']).tz_convert('America/New_York'))} ({x['reason']})")
    rows = [{"Location": r["name"], "Pavement (returned horizon only)": cell(r["pavement"]), "Air (NWS forecast)": cell(r["air"])} for r in cov]
    st.markdown(html_table(rows, ["Location", "Pavement (returned horizon only)", "Air (NWS forecast)"]), unsafe_allow_html=True)


def _readiness_panel(inp, window):
    """Small deterministic readiness check from values a person supplies; incomplete until every needed value and unit is given."""
    rounds = readiness.rounds_from_plan(inp["plans"]["scenario"], inp["lane_miles"], inp["rate"], window)
    with st.expander("Readiness check · deterministic · your supplied assumptions only"):
        st.caption(readiness.SCOPE)
        with st.form("readiness_form", border=False):
            cols, vals = st.columns(2), {}
            for i, (name, kind, required, label) in enumerate(readiness.FIELDS):
                c = cols[i % 2]
                v = c.number_input(label + ("" if required else " (optional)"), min_value=0.0, value=None, key=f"rd_{name}",
                                   help="Unverified assumption; nothing is filled in for you.")
                u = "count" if kind == "count" else c.selectbox(f"Unit · {label.lower()}", readiness.UNIT_CHOICES[kind], key=f"rdu_{name}")
                vals[name] = {"value": v, "unit": u, "verified": False}
            go = st.form_submit_button("Check readiness")
        if go:
            st.session_state["readiness_inputs"] = vals
        res = readiness.assess(rounds, st.session_state.get("readiness_inputs") or {})
        if res["status"] == "incomplete":
            st.markdown('<div class="sw-flag sw-flag-none"><b>Readiness: incomplete.</b> ' + "; ".join(res["missing"]) + "</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="sw-flag"><b>Readiness: {res["status"]}.</b> Every value above is an unverified assumption.</div>',
                        unsafe_allow_html=True)
            st.markdown(html_table([{"Round starts": _fmt(r["start"]), "Material (short tons)": f"{r['material_short_tons']:g}",
                                     "Truck loads": r["truck_loads"], "Work starts": _fmt(r["work_starts"]), "Work finishes": _fmt(r["work_finishes"]),
                                     "Deadline": _fmt(r["deadline"]), "Waited for an earlier round": "Yes" if r["queued_behind_previous"] else "No",
                                     "Material on hand after": f"{r['material_on_hand_after_short_tons']:g} short tons", "Result": r["result"]}
                                    for r in res["rounds"]],
                                   ["Round starts", "Material (short tons)", "Truck loads", "Work starts", "Work finishes", "Deadline",
                                    "Waited for an earlier round", "Material on hand after", "Result"]), unsafe_allow_html=True)
        st.caption(readiness.METHOD)
    return res
