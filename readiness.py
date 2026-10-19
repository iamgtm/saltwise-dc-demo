"""Deterministic readiness check for the Storm Lab scenario (demonstration points only).

Every operational value is supplied by a person and labeled an unverified assumption; nothing is defaulted. Missing
values, or units without a conversion, make the result "incomplete". Application rounds share trucks and loaders, so
a round that starts while an earlier one is still running waits for it (overlapping activities are queued). This is
not a citywide completion time, and it does not approve or schedule treatment.
"""
import math
from datetime import timedelta

import saltwise_contract as sc

LB_PER_SHORT_TON = 2000.0
UNIT_CHOICES = {"mass": ["short tons", "lb", "other (no conversion)"],
                "rate_mass": ["short tons per hour", "lb per hour", "other (no conversion)"],
                "time": ["hours", "minutes", "other (no conversion)"]}
FACTORS = {"short tons": 1.0, "lb": 1 / LB_PER_SHORT_TON, "short tons per hour": 1.0, "lb per hour": 1 / LB_PER_SHORT_TON,
           "hours": 1.0, "minutes": 1 / 60}
FIELDS = [("inventory", "mass", True, "Material on hand at the first round"),
          ("production_rate", "rate_mass", False, "Production or resupply rate"),
          ("loaders", "count", True, "Loaders available"),
          ("loading_rate", "rate_mass", True, "Loading rate per loader"),
          ("trucks", "count", True, "Trucks available"),
          ("truck_capacity", "mass", True, "Material per truck load"),
          ("route_time", "time", True, "Route time per load (out, spreading and back)"),
          ("deadline", "time", True, "Deadline after each round starts")]
POSITIVE = ("loaders", "loading_rate", "trucks", "truck_capacity")
SCOPE = ("Scope: the scenario's applications at the demonstration points only, under the values you supply. Every value is "
         "an unverified assumption; this is not a citywide completion time and it does not approve or schedule treatment.")
METHOD = ("Rounds = scenario applications grouped by start time inside the accounting window; material = lane-miles × rate "
          "(Storm Lab assumptions). Loads = ceil(material / truck load). Duration = max(waves of trucks × (load time + route "
          "time), loads × load time / loaders + route time). A round starts when it is scheduled or when the previous round "
          "finishes, whichever is later (shared trucks and loaders). Material on hand grows by the production rate between rounds.")


def rounds_from_plan(plan, lane_miles, rate, window):
    w0, w1 = sc.dt(window["start"]), sc.dt(window["end"])
    by = {}
    for loc, p in plan.items():
        for t in ([p["initial"]] if p.get("initial") else []) + list(p.get("later", [])):
            if w0 <= sc.dt(t) <= w1:
                r = by.setdefault(sc.dt(t), {"start": t, "material_lb": 0.0, "locations": []})
                r["material_lb"] += float(lane_miles.get(loc, 0.0)) * float(rate)
                r["locations"].append(loc)
    return [by[k] for k in sorted(by)]


def _convert(inputs):
    vals, missing = {}, []
    labels = {n: lab for n, _, _, lab in FIELDS}
    for name, kind, required, label in FIELDS:
        x = inputs.get(name) or {}
        v, u = x.get("value"), x.get("unit")
        if v is None:
            if required:
                missing.append(f"{label}: no value supplied")
            continue
        if kind == "count":
            vals[name] = float(v)
        elif u in FACTORS and u in UNIT_CHOICES[kind]:
            vals[name] = float(v) * FACTORS[u]
        else:
            missing.append(f"{label}: unit '{u}' has no conversion")
    missing += [f"{labels[n]}: must be greater than zero" for n in POSITIVE if n in vals and vals[n] <= 0]
    return vals, missing


def assess(rounds, inputs):
    vals, missing = _convert(inputs)
    assumptions = {n: {"value": (inputs.get(n) or {}).get("value"), "unit": (inputs.get(n) or {}).get("unit"),
                       "label": "verified" if (inputs.get(n) or {}).get("verified") else "assumption (unverified)"} for n, *_ in FIELDS}
    base = {"scope": SCOPE, "method": METHOD, "assumptions": assumptions, "rounds": []}
    if not rounds:
        missing.append("The scenario plan has no applications inside the accounting window.")
    if missing:
        return {**base, "status": "incomplete", "missing": missing}
    load_h, route_h, prod = vals["truck_capacity"] / vals["loading_rate"], vals["route_time"], vals.get("production_rate", 0.0)
    stock, prev_finish, last, ok, out = vals["inventory"], None, sc.dt(rounds[0]["start"]), True, []
    for r in rounds:
        start = sc.dt(r["start"])
        stock += prod * max(0.0, (start - last).total_seconds() / 3600)
        last = start
        tons = r["material_lb"] / LB_PER_SHORT_TON
        loads = math.ceil(tons / vals["truck_capacity"] - 1e-9) if tons > 0 else 0
        begin = max(start, prev_finish) if prev_finish else start
        dur_h = max(math.ceil(loads / vals["trucks"]) * (load_h + route_h), loads * load_h / vals["loaders"] + route_h) if loads else 0.0
        finish, deadline = begin + timedelta(hours=dur_h), start + timedelta(hours=vals["deadline"])
        enough = stock + 1e-9 >= tons
        stock -= tons
        result = "insufficient material" if not enough else ("on time" if finish <= deadline else "late")
        ok = ok and result == "on time"
        out.append({"start": r["start"], "locations": r["locations"], "material_short_tons": round(tons, 3), "truck_loads": loads,
                    "queued_behind_previous": bool(prev_finish and prev_finish > start), "work_starts": begin.isoformat(),
                    "work_finishes": finish.isoformat(), "deadline": deadline.isoformat(),
                    "material_on_hand_after_short_tons": round(stock, 3), "result": result})
        prev_finish = finish
    return {**base, "status": "ready under supplied assumptions" if ok else "not ready under supplied assumptions",
            "missing": [], "rounds": out}
