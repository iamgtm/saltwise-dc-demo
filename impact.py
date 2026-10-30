"""Storm Lab impact comparison and one-way sensitivity (simulation; illustrative assumptions).

Built on the existing engine (saltwise_contract.plan_material / compare_plans): every application, including hypothetical
additional applications, is lane-miles x rate and counts only inside the same accounting window. This is scenario modeling,
not a prediction of operational savings, road service, safety or chloride runoff.
"""
import math
from datetime import timedelta

import saltwise_contract as sc
import scenarios

CALC_VERSION = "saltwise-storm-impact/1"
EXAMPLE_ID = "illustrative-comparison/1"
QUALIFICATION = "Illustrative material comparison. Equivalent road service has not been demonstrated."
OUTCOME_NOTE = "Salt reduction alone does not establish safety or environmental outcomes."
SENS_MIN_MAX, SENS_CAP = 3, 20
NO_ADDITIONAL = {"count": 0, "lane_miles_each": 1.0}
# Constructed example: which three locations receive the first application is registry order, chosen for the arithmetic only.
EXAMPLE_FIRST = [lid for lid, *_ in scenarios.LOCATIONS[:3]]
EXAMPLE_TEXT = [
    "Five demonstration locations; one assumed lane-mile each (placeholders, not measured road lengths).",
    "200 lb per lane-mile per application, an illustrative input only.",
    "Baseline: two applications at every location: 5 × 1 × 200 × 2 = 2,000 lb.",
    "Comparison: three locations receive the first application and all five receive the second: (3 + 5) × 1 × 200 = 1,600 lb.",
    "Two additional one-lane-mile applications bring the comparison to 2,000 lb (no difference); three bring it to 2,200 lb "
    "(200 lb more than the baseline).",
    "Constructed scenarios, not DC deployment records or demonstrated safe treatment plans. The three locations are taken in "
    "registry order for the arithmetic, not chosen by need.",
]


def lane_miles_text(x):
    return f"{x:g} lane-mile" + ("" if x == 1 else "s")


def additional_of(inp):
    return {**NO_ADDITIONAL, **(inp.get("additional") or {})}


def validate(inp):
    """Problems with applied inputs (negative values, a non-integer count). The page's controls do not allow them."""
    out, add = [], additional_of(inp)
    if inp["rate"] < 0:
        out.append("application rate is negative")
    out += [f"lane-miles for {lid} are negative" for lid, v in inp["lane_miles"].items() if v < 0]
    if (inp.get("price") or 0) < 0:
        out.append("salt price is negative")
    if add["count"] < 0 or add["count"] != int(add["count"]):
        out.append("additional applications must be a whole number, 0 or more")
    if add["lane_miles_each"] < 0:
        out.append("lane-miles per additional application are negative")
    return out


def additional_lb(count, lane_miles_each, rate, window):
    """Hypothetical additional applications through the same engine: no time is assumed; they count inside the window."""
    plan = {"additional": {"initial": None, "later": [window["start"]] * int(count)}}
    return sc.plan_material(plan, {"additional": lane_miles_each}, rate, window)["later_lb"]


def difference(baseline_lb, comparison_lb):
    """Comparison minus baseline (positive = the comparison uses more salt), with a percentage of the baseline."""
    d = round(comparison_lb - baseline_lb, 9)
    pct = round(100 * d / baseline_lb, 2) if baseline_lb > 0 else None
    p = "" if pct is None else f" ({abs(pct):.1f}%)"
    if d == 0:
        text = "No difference in total salt across the whole window"
    elif d < 0:
        text = f"Comparison uses {-d:,.0f} lb{p} less salt than the baseline"
    else:
        text = f"Comparison uses {d:,.0f} lb{p} MORE salt than the baseline"
    if pct is None and d != 0:
        text += " (the baseline is 0 lb, so no percentage)"
    return {"difference_lb": d, "difference_pct": pct, "text": text}


def compare(inp, window):
    """Baseline vs. comparison over the whole accounting window: initial, later and additional applications."""
    bad = validate(inp)
    if bad:
        raise ValueError("; ".join(bad))
    add = additional_of(inp)
    res = sc.compare_plans(inp["plans"]["baseline"], inp["plans"]["scenario"], inp["lane_miles"], inp["rate"], window)
    a_lb = additional_lb(add["count"], add["lane_miles_each"], inp["rate"], window)
    b, s = res["baseline"], res["scenario"]
    totals = {"baseline": {"initial_lb": b["initial_lb"], "later_lb": b["later_lb"], "additional_lb": 0.0, "total_lb": b["total_lb"]},
              "comparison": {"initial_lb": s["initial_lb"], "later_lb": s["later_lb"], "additional_lb": a_lb,
                             "total_lb": s["total_lb"] + a_lb}}
    price, cost = inp.get("price") or None, None
    if price:                                           # same formula and source as compare_plans: a user-entered assumption
        bt, ct = totals["baseline"]["total_lb"], totals["comparison"]["total_lb"]
        cost = {"price_per_short_ton": float(price), "source": "user-entered assumption (not a DC price)",
                "baseline_cost": bt / sc.LB_PER_SHORT_TON * price, "comparison_cost": ct / sc.LB_PER_SHORT_TON * price,
                "cost_difference": (bt - ct) / sc.LB_PER_SHORT_TON * price, "cost_difference_meaning": "baseline cost - comparison cost"}
    return {"calculation_version": CALC_VERSION, "totals": totals, "additional": {**add, "lb": a_lb},
            **difference(totals["baseline"]["total_lb"], totals["comparison"]["total_lb"]), "cost": cost,
            "outside_window": b["outside_window"] + s["outside_window"], "engine_results": res}


def sensitivity(inp, window):
    """One-way: vary only the number of additional applications (each lane_miles_each x rate); hold every other input fixed."""
    add = additional_of(inp)
    base = compare({**inp, "additional": {**add, "count": 0}}, window)
    per = additional_lb(1, add["lane_miles_each"], inp["rate"], window)
    reduction = -base["difference_lb"]                  # material below the baseline before any additional application
    if reduction <= 0:
        zero, note = None, ("The comparison already uses at least as much salt as the baseline with no additional applications, "
                            "so there is no reduction to erase.")
    elif per == 0:
        zero, note = None, "Additional applications add no material at the entered lane-miles and rate, so the reduction is never erased here."
    else:
        zero = round(reduction / per, 6)
        note = (f"The reduction is erased at {zero:g} additional application{'' if zero == 1 else 's'}; beyond that the comparison "
                "uses more salt than the baseline." if zero == int(zero) else
                f"The reduction is erased between {math.floor(zero)} and {math.ceil(zero)} additional applications ({zero:g} "
                "applications' worth of material); beyond that the comparison uses more salt than the baseline.")
    top = min(SENS_CAP, max(SENS_MIN_MAX, int(add["count"]), math.ceil(zero) + 1 if zero is not None else 0))
    points = []
    for n in range(top + 1):
        r = compare({**inp, "additional": {**add, "count": n}}, window)
        points.append({"additional_applications": n, "additional_lb": r["additional"]["lb"],
                       "comparison_total_lb": r["totals"]["comparison"]["total_lb"], "baseline_total_lb": r["totals"]["baseline"]["total_lb"],
                       "difference_lb": r["difference_lb"], "difference_pct": r["difference_pct"], "text": r["text"]})
    return {"calculation_version": CALC_VERSION, "method": "one-way: additional applications varied, every other applied input held fixed",
            "varied": "additional applications (count)", "range": [0, top],
            "per_additional_application": {"lane_miles": add["lane_miles_each"], "rate_lb_per_lane_mile": inp["rate"], "lb": per},
            "held_fixed": ["lane-miles", "application rate", "baseline plan", "comparison initial and later applications",
                           "accounting window"],
            "reduction_before_additional_lb": reduction, "zero_difference_at": zero, "zero_difference_note": note, "points": points}


def schedules(inp, window):
    """Application schedules as applied: every location in both plans, plus the comparison's additional applications."""
    w0, w1, add = sc.dt(window["start"]), sc.dt(window["end"]), additional_of(inp)

    def plan(p):
        out = {}
        for lid, *_ in scenarios.LOCATIONS:
            x, lm = p.get(lid) or {"initial": None, "later": []}, inp["lane_miles"].get(lid, 0.0)
            apps = ([("initial", x["initial"])] if x["initial"] else []) + [("later", t) for t in x["later"]]
            out[lid] = {"lane_miles": lm, "applications": [{"kind": k, "time": t, "lb": lm * inp["rate"],
                                                            "counted": w0 <= sc.dt(t) <= w1} for k, t in apps]}
        return out
    return {"baseline": plan(inp["plans"]["baseline"]), "comparison": plan(inp["plans"]["scenario"]),
            "comparison_additional": {"count": add["count"], "lane_miles_each": add["lane_miles_each"],
                                      "lb_each": add["lane_miles_each"] * inp["rate"], "location": "not assigned",
                                      "time": "not specified; counted inside the accounting window"}}


def input_status(inp, window, anchored, snapshot_id=None):
    """Applied inputs with units, and whether each is an assumption or supported by project evidence."""
    add, lm = additional_of(inp), inp["lane_miles"]
    A = "assumed"
    return [
        {"input": "Locations", "value": len(scenarios.LOCATIONS), "unit": "demonstration points", "status": "project evidence",
         "note": "Points in the project location registry, not measured road segments; every location stays in assumed service"},
        {"input": "Lane-miles", "value": lm, "unit": "lane-miles per location", "status": A,
         "note": "Placeholders, not measured road lengths"},
        {"input": "Application rate", "value": inp["rate"], "unit": "lb per lane-mile per application", "status": A,
         "note": "Illustrative input, not an approved DC rate"},
        {"input": "Baseline plan", "value": "see schedules", "unit": "applications", "status": A,
         "note": "Illustrative reference, not DC practice"},
        {"input": "Comparison plan", "value": "see schedules", "unit": "applications", "status": A, "note": "Editable scenario"},
        {"input": "Additional applications", "value": add["count"], "unit": f"applications of {lane_miles_text(add['lane_miles_each'])}",
         "status": A, "note": "Hypothetical later treatment, counted inside the same accounting window"},
        {"input": "Accounting window", "value": window, "unit": "ISO 8601", "status": A,
         "note": f"Starts at the evidence snapshot time ({snapshot_id})" if anchored else "Starts at the synthetic scenario time"},
        {"input": "Review flags", "value": f"evidence snapshot {snapshot_id}" if anchored else "synthetic scenario", "unit": None,
         "status": "project evidence (read-only snapshot)" if anchored else "simulation",
         "note": "Shown for context; flags never change the totals"},
        {"input": "Salt price", "value": inp.get("price") or None, "unit": "USD per US short ton", "status": A if inp.get("price") else "not given",
         "note": "Optional; cost stays unavailable without it"},
        {"input": "Required road service", "value": "all locations", "unit": None, "status": "constraint",
         "note": "Not traded away; missing evidence never removes a location from assumed service"},
    ]


def example_inputs(E, window_key="overnight", anchor="scenario"):
    """The constructed illustrative comparison (EXAMPLE_TEXT), timed from window start E; a repeat 6 h later."""
    t0, t6 = E.isoformat(), (E + timedelta(hours=6)).isoformat()
    ids = [lid for lid, *_ in scenarios.LOCATIONS]
    return {"window_key": window_key, "rate": 200.0, "price": 0.0, "anchor": anchor, "lane_miles": {lid: 1.0 for lid in ids},
            "plans": {"baseline": {lid: {"initial": t0, "later": [t6]} for lid in ids},
                      "scenario": {lid: {"initial": t0 if lid in EXAMPLE_FIRST else None, "later": [t6]} for lid in ids}},
            "additional": dict(NO_ADDITIONAL)}


def matches_example(inp, E):
    """True while the applied inputs are the illustrative example (any additional count or price)."""
    ex = example_inputs(E)
    norm = lambda p: {k: {lid: {"initial": x["initial"] and sc.dt(x["initial"]), "later": [sc.dt(t) for t in x["later"]]}  # noqa: E731
                          for lid, x in v.items()} for k, v in p.items()}
    return (inp["rate"] == ex["rate"] and inp["lane_miles"] == ex["lane_miles"] and norm(inp["plans"]) == norm(ex["plans"])
            and additional_of(inp)["lane_miles_each"] == 1.0)
