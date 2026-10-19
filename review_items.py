"""Traceable review items: the existing illustrative review flags, each tied to its evidence by valid interval.

Built only from a computed view (saltwise_contract.build_view) and, in provider mode, the stored evidence IDs of the
snapshot the view came from. Each value is the one whose own valid interval contains the flagged time; nothing is
carried past the supported coverage (anything outside it is reported as missing). Geographic verification, provider
road-name matching and bridge-specific modeling stay separate, and every location stays in assumed service. No new
thresholds: the only temperature reference remains the physical freezing point inside the existing rules.
"""
import hashlib
import inspect
from datetime import timedelta, timezone

import freshness
import saltwise_contract as sc

RULE_BASIS = {
    "refreeze_review": "A wet, moist or slushy surface earlier in the window, then pavement at or below the physical freezing reference.",
    "rain_timing_review": "Forecast rain (without snow) before forecast snow, from the precipitation type of each period.",
    "treatment_review": "Pavement at or below the physical freezing reference with a wet, slushy, snowy or icy surface.",
    "evidence_review": "Missing, withheld or ended evidence, or a selected window that runs past the pavement series.",
}
RULE_CODE = hashlib.sha256(inspect.getsource(sc.review).encode()).hexdigest()[:10]   # version tracks the rule code


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def rule(fid):
    return {"rule_id": f"saltwise.review.{fid}", "rule_version": f"1.0+{RULE_CODE}", "basis": RULE_BASIS.get(fid, ""),
            "status": "illustrative - not approved operational policy",
            "temperature_reference": "physical freezing point only (32 °F / 0 °C); no treatment threshold"}


def _intervals(view):
    idx = {"air_temperature": [], "pavement_temperature": [], "precipitation": []}
    for s in view["series"]:
        if s["quantity"] in idx:
            idx[s["quantity"]] += [(sc.dt(p["valid_start"]), sc.dt(p["valid_end"]), p, s) for p in s["points"]]
    return idx


def _at(idx, q, t):
    """The point whose own valid interval contains t (never the nearest one)."""
    return next((h for h in idx[q] if h[0] <= t < h[1]), None)


def _statuses(fx, provider):
    if provider:
        return fx["provenance"]["statuses"]
    note = {"status": "not_applicable", "label": "Simulated scenario (synthetic road identity)"}
    return {"geographic_verification": note, "provider_road_matching": note, "bridge_specific_modeling": note}


def _coverage(view, E, w_end):
    out, hours = {}, (w_end - E).total_seconds() / 3600
    for q, key in (("air_temperature", "air"), ("pavement_temperature", "pavement")):
        pts = [p for s in view["series"] if s["quantity"] == q for p in s["points"] if p.get("value") is not None]
        if not pts:
            out[key] = {"supported_from": None, "supported_to": None, "unsupported_h": round(hours, 2), "window_end": iso(w_end)}
            continue
        a = max(min(sc.dt(p["valid_start"]) for p in pts), E)
        b = min(max(sc.dt(p["valid_end"]) for p in pts), w_end)
        out[key] = {"supported_from": iso(a), "supported_to": iso(b), "unsupported_h": round((w_end - b).total_seconds() / 3600, 2),
                    "window_end": iso(w_end)}
    return out


def _freshness(fx, provider, E, w_end):
    if not provider:
        return {"pavement": None, "air": None, "proposal_preview": None,
                "note": "Simulated scenario: scenario-only freshness settings; no approved policy applies."}
    p, a = fx["provenance"]["pavement"], fx["provenance"]["air"]

    def ev(policy):
        return {key: freshness.evaluate(policy, src, x.get("issued_utc"), x.get("retrieved_utc"),
                                        (x.get("returned_coverage_utc") or {}).get("to"), E, w_end) if x.get("used_in_view") else None
                for key, x, src in (("pavement", p, "xweather_pavement"), ("air", a, "nws_air"))}
    res = ev(freshness.active_policy())
    res["proposal_preview"] = {**ev(freshness.PROPOSAL),
                               "label": f"Preview of {freshness.PROPOSAL['policy_id']}@{freshness.PROPOSAL['version']}: proposed, not applied"}
    return res


def _precip(rec, idx, t, add, weather_id, sources, provider):
    hit = _at(idx, "precipitation", t)
    if not hit:
        return
    a, b, p, s = hit
    rec["precipitation"] = {"probability_pct": p.get("value"), "unit": "%", "type": p.get("description") or None,
                            "valid_from": iso(a), "valid_to": iso(b), "source": s["source"],
                            "type_source": "NWS gridpoint weather layer (structured)" if provider else "synthetic scenario text"}
    add("precipitation_probability", a)
    sources.add(s["source"])
    w = weather_id(t)
    if w:
        add(None, None, w)


def build(view, fx, data_mode):
    """Review items for one location's view. data_mode: 'provider' (saved snapshots) or 'simulated'."""
    provider = data_mode == "provider"
    loc, U = view["location"], view["units"]
    lid = loc["location_id"]
    E = sc.dt(view["export"]["evaluation_time"])
    w_end = E + timedelta(hours=view.get("window_hours") or 24)
    idx, ev = _intervals(view), (fx.get("evidence_ids") or {}) if provider else None

    def eid(variable, start):
        k = iso(start)
        return ev.get("by_start", {}).get((variable, k)) if provider else f"syn:{lid}:{k}:{variable}"

    def weather_id(t):
        return next((i for a, b, i in ev.get("weather", []) if sc.dt(a) <= t < sc.dt(b)), None) if provider else None
    statuses, cov, fr = _statuses(fx, provider), _coverage(view, E, w_end), _freshness(fx, provider, E, w_end)
    unc = []
    if provider:
        if statuses["geographic_verification"]["status"] != "verified":
            unc.append("Location only partially verified on DCGIS.")
        if statuses["provider_road_matching"]["status"] != "matched":
            unc.append(f"Provider road match: {statuses['provider_road_matching']['label']}.")
        if statuses["bridge_specific_modeling"]["status"] == "unconfirmed":
            unc.append("Bridge-specific modeling unconfirmed: it is not confirmed that the provider models this point as a bridge deck.")
        pv = fx["provenance"]["pavement"]
        if pv.get("used_in_view") and not pv.get("issued_utc"):
            unc.append("Xweather issue time not supplied, so the pavement forecast's age is unknown.")
        if any(x and x["status"] == freshness.NOT_ASSESSED for x in (fr["pavement"], fr["air"])):
            unc.append("Freshness not assessed: no approved freshness policy.")
    else:
        unc.append("Simulated scenario: illustrative values, not a forecast or an observation.")
    if cov["pavement"]["supported_to"] and cov["pavement"]["unsupported_h"] > 0:
        unc.append(f"Pavement evidence covers the window only until {sc._when(cov['pavement']['supported_to'])}; "
                   f"the last {cov['pavement']['unsupported_h']:g} h are unsupported.")
    conflicts = [c["message"] for c in view.get("data_checks") or [] if c.get("status") == "warn"]
    by_flag = {}
    for r in view["review_periods"]:
        for c in r["concerns"]:
            by_flag.setdefault(c, []).append(r)
    items = []
    for f in view["flags"] or []:
        rows = sorted(by_flag.get(f["id"], []), key=lambda r: sc.dt(r["valid_start"]))
        support, ids, missing, sources, lost = [], [], [], set(), []

        def add(variable, start, known=None):
            i = known or eid(variable, start)
            if i:
                ids.append(i)
            elif provider:
                lost.append(f"No stored evidence ID for {variable} at {iso(start)}.")
        for r in rows:
            t = sc.dt(r["valid_start"])
            rec = {"valid_time": iso(t)}
            hit = _at(idx, "pavement_temperature", t)
            if hit and hit[2].get("value") is not None:
                a, b, p, s = hit
                rec["pavement"] = {"value": p["value"], "unit": U, "surface": p.get("surface_condition"), "valid_from": iso(a),
                                   "valid_to": iso(b), "source": s["source"], "kind": "modeled" if provider else "simulation"}
                add("pavement_temperature", a)
                add("road_surface_condition", a)
                sources.add(s["source"])
            else:
                missing.append(f"No pavement value covers {sc._when(iso(t))}.")
            hit = _at(idx, "air_temperature", t)
            if hit:
                a, b, p, s = hit
                rec["air"] = {"value": p["value"], "unit": U, "valid_from": iso(a), "valid_to": iso(b), "source": s["source"],
                              "kind": "provider_forecast" if provider else "simulation"}
                add("air_temperature", a)
                sources.add(s["source"])
            else:
                missing.append(f"No air forecast period covers {sc._when(iso(t))}.")
            _precip(rec, idx, t, add, weather_id, sources, provider)
            support.append(rec)
        for e in f.get("evidence") or []:
            if e.get("kind") == "provider_forecast" and e.get("valid_start"):      # periods the rule itself cites
                t = sc.dt(e["valid_start"])
                rec = {"valid_time": iso(t), "cited_by_rule": True}
                _precip(rec, idx, t, add, weather_id, sources, provider)
                support.append(rec)
            if e.get("kind") == "unavailable":
                missing += [i[:1].upper() + i[1:] + "." for i in e.get("issues", [])]
        ends = [sc.dt(x[k]["valid_to"]) for x in support for k in ("pavement", "air", "precipitation") if k in x]
        start = min([sc.dt(x["valid_time"]) for x in support] or [E])
        items.append({"item_id": f"{lid}:{f['id']}:{iso(start)}", "title": f["title"], "rule": rule(f["id"]),
                      "location": {"location_id": lid, "name": loc["name"], "statuses": statuses, "assumed_service": True},
                      "window": {"start": iso(start), "end": iso(max(ends) if ends else w_end), "n_periods": len(rows)},
                      "evidence_ids": sorted(set(ids)), "supporting": support, "sources": sorted(sources),
                      "missing": list(dict.fromkeys(missing)), "conflicting": conflicts + lost, "uncertain": unc,
                      "explanation": f["reason"], "next_step": f["next_step"], "treatment_decision": None,
                      "decision_by": "people (SaltWise never approves or cancels treatment)"})
    return {"location": {"location_id": lid, "name": loc["name"], "statuses": statuses, "assumed_service": True},
            "data_mode": data_mode, "evaluated_at": iso(E), "window": {"start": iso(E), "end": iso(w_end)}, "coverage": cov,
            "freshness": fr, "location_uncertainty": unc, "conflicting": conflicts, "items": items}
