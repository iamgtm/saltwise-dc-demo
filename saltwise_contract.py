"""SaltWise DC evidence functions (evaluator contract v1) - Stage B baseline.

The Streamlit app (app.py) renders exclusively from build_view(), the same function the evaluator
exercises against the frozen fixtures. Stage C adds illustrative review flags (review());
Stage D adds the Storm Lab material accounting (storm_lab(), compare_plans(), sensitivity()). Started from the evaluator's reference implementation and extended for
synthetic-scenario labeling, time windows, and unknown coordinates.
"""
import math
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import freshness as fp

CONTRACT_VERSION = "1"
CAPABILITIES = {"stage_b": True, "review_flags": True, "storm_lab": True}

NAMES = {
    "rhode_island_ave_nw_scott_circle": "Rhode Island Avenue NW near Scott Circle",
    "garfield_st_nw_34th_st_nw": "Garfield Street NW at 34th Street NW",
    "michigan_ave_ne_bridge": "Michigan Avenue NE bridge",
    "benning_rd_bridge": "Benning Road bridge",
    "mlk_jr_ave_se_alabama_ave_se": "Martin Luther King Jr. Avenue SE at Alabama Avenue SE",
}
TOKENS = {"rhode_island_ave_nw_scott_circle": ["rhode island"], "garfield_st_nw_34th_st_nw": ["garfield"],
          "michigan_ave_ne_bridge": ["michigan"], "benning_rd_bridge": ["benning"],
          "mlk_jr_ave_se_alabama_ave_se": ["martin luther king", "mlk"]}
WET = {"WET", "MOIST", "SLUSH"}
PRECIP_SURFACE = {"WET", "SLUSH", "SNOW", "ICE"}
XW_ATTRIBUTION = "Powered by Vaisala Xweather (https://www.xweather.com/)"
SOURCES = {
    "provider": {"air": "NWS forecast (api.weather.gov)", "pav": "Xweather Road Weather Conditions (modeled)"},
    "synthetic_fixture": {"air": "Synthetic scenario - NWS-shaped air forecast (illustrative)",
                          "pav": "Synthetic scenario - modeled-pavement shape (illustrative)"},
}


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def convert_c_to_f(c):
    return round(c * 9 / 5 + 32, 4)


def _disp(v_f, units):
    if v_f is None:
        return None
    return round(v_f, 2) if units == "F" else round((v_f - 32) * 5 / 9, 2)


def _km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _air(fx, settings, E, loc_id):
    units, lim = settings["units"], settings["freshness_limits"].get("nws_air_forecast_max_age_hours")
    rows, precip = [], []
    if fx.get("nws_hourly"):
        props = fx["nws_hourly"]["properties"]
        update, source_unit = props.get("updateTime"), "F (NWS temperatureUnit)"
        for p in props["periods"]:
            s, e = dt(p["startTime"]), dt(p["endTime"])
            tf = p["temperature"] if p.get("temperatureUnit", "F") == "F" else convert_c_to_f(p["temperature"])
            rows.append((s, e, tf))
            precip.append((s, e, (p.get("probabilityOfPrecipitation") or {}).get("value"), p.get("shortForecast", "")))
    elif fx.get("nws_griddata"):
        props = fx["nws_griddata"]["properties"]
        update, t = props.get("updateTime"), props["temperature"]
        source_unit = t["uom"]
        for v in t["values"]:
            start, dur = v["validTime"].split("/")
            s = dt(start)
            e = s + timedelta(hours=int(re.match(r"PT(\d+)H", dur).group(1)))
            rows.append((s, e, convert_c_to_f(v["value"]) if "degC" in source_unit else v["value"]))
    else:
        return None, None, None
    # Shared policy (freshness.py). No settings: not assessed, ages shown. Inconsistent timestamps or an age beyond the hard
    # limit: values excluded from current views and review inputs, kept in the withheld record. Ended periods always drop.
    a = fp.evaluate(fp.policy_from_limits(settings["freshness_limits"]), "nws_air", update, fx.get("nws_retrieved_at"), None, E,
                    first_seen_utc=fx.get("nws_content_first_seen"), provider_record=settings.get("source_mode") == "provider")
    fresh, cut = a["contract_status"], a["exclude"]
    keep = lambda s, e: e > E and s < E + timedelta(hours=72)  # noqa: E731
    src = SOURCES[settings.get("source_mode", "provider")]["air"]
    pts = [{"valid_start": s.isoformat(), "valid_end": e.isoformat(), "value": _disp(tf, units),
            "kind": "provider_forecast", "freshness": fresh} for s, e, tf in rows if keep(s, e)]
    ppts = [{"valid_start": s.isoformat(), "valid_end": e.isoformat(), "value": pop, "description": d,
             "kind": "provider_forecast", "freshness": fresh} for s, e, pop, d in precip if keep(s, e)]
    air = {"location_id": loc_id, "quantity": "air_temperature", "source": src,
           "kind": "provider_forecast", "unit": units, "source_unit": source_unit, "style": "solid-air",
           "points": [] if cut else pts}
    pr = None
    if precip:
        pr = {"location_id": loc_id, "quantity": "precipitation", "source": src,
              "kind": "provider_forecast", "unit": "%", "source_unit": "wmoUnit:percent", "style": "bars",
              "points": [] if cut else ppts}
    kind = "approved" if settings.get("source_mode") == "provider" else "fixture-only"
    if a["reason_code"] == "over_hard_limit":
        msg = f"Air forecast last updated {update}; older than the {lim} h {kind} freshness limit, so its values are excluded."
    elif a["reason_code"] == "not_assessed":
        msg = ((f"Air forecast updated {update} (NWS updateTime)." if update else "Air forecast issue time not supplied by provider.")
               + " Freshness limits are pending review: age is shown, not judged.")
    else:
        msg = fp.describe(a, "Air forecast")
    fr = {"quantity": "air_temperature", "status": fresh, "message": msg, "reason_code": a["reason_code"], "assessment": a}
    if cut:
        fr["excluded"] = {"quantity": "air_temperature", "status": fresh, "reason_code": a["reason_code"], "expired_after": None,
                          "reason": msg + " Values are excluded from current charts, summaries and review inputs; the road stays "
                                          "in assumed service.", "excluded_points": pts, "excluded_precipitation_points": ppts}
    return air, pr, fr


def _simulated(loc_id, units, start, hours, quantity="pavement_temperature"):
    pts = []
    for i in range(hours):
        s = start + timedelta(hours=i)
        tf = 33.0 + 3.0 * math.sin(i / 3.0)
        pts.append({"valid_start": s.isoformat(), "valid_end": (s + timedelta(hours=1)).isoformat(),
                    "value": _disp(tf, units), "kind": "simulation", "freshness": "unknown"})
    return {"location_id": loc_id, "quantity": quantity, "source": "SaltWise simulation (illustrative, not a forecast)",
            "kind": "simulation", "unit": units, "source_unit": "F", "style": "dashed-simulation", "points": pts}


def _pav_ids(fx, start):
    """Stored evidence ids for one pavement period (saved provider snapshots only; None for fixtures)."""
    by, t = (fx.get("evidence_ids") or {}).get("by_start") or {}, dt(start)
    return sorted(i for (var, s), i in by.items() if "road" in var.lower() and dt(s) == t) or None


def build_view(fx, settings):
    E, units, mode = dt(settings["evaluation_time"]), settings["units"], settings["mode"]
    source_mode = settings.get("source_mode", "provider")
    synthetic = source_mode == "synthetic_fixture"
    pav_src = SOURCES[source_mode]["pav"]
    loc = fx["location"]
    loc_id = loc["location_id"]
    series, gaps, withheld, freshness, checks, attribution, history, text = [], [], [], [], [], [], [], []
    coverage = {"pavement": {"last_period_start": None, "end_reason": None}, "air": {"last_period_start": None}}
    road_match = {"status": "unverified", "requested_name": loc["name"], "returned_name": None,
                  "returned_type": None, "distance_m": None}

    air, precip, fr = _air(fx, settings, E, loc_id)
    if air:
        series.append(air)
        freshness.append(fr)
        if fr.get("excluded"):
            withheld.append(fr.pop("excluded"))
        text.append(fr["message"])
        if air["points"]:
            coverage["air"]["last_period_start"] = air["points"][-1]["valid_start"]
    if precip:
        series.append(precip)
    if not air and fx.get("air_unavailable_reason"):
        gaps.append({"quantity": "air_temperature", "valid_start": None, "withheld": True, "reason": fx["air_unavailable_reason"]})

    pav_pts = []
    xw = fx.get("xweather_roadweather")
    if xw is not None:
        resp = xw.get("response") or []
        if not resp:
            series.append({"location_id": loc_id, "quantity": "pavement_temperature",
                           "source": pav_src, "kind": "unavailable",
                           "unit": units, "source_unit": "F/C", "style": "none", "points": []})
            gaps.append({"quantity": "pavement_temperature", "valid_start": None,
                         "reason": "Provider returned no pavement records for this location; pavement evidence unavailable."})
        else:
            rec = resp[0]
            road = rec.get("road")
            has_coords = loc.get("requested_lat") is not None and loc.get("requested_lon") is not None
            dist = _km(loc["requested_lat"], loc["requested_lon"], rec["loc"]["lat"], rec["loc"]["long"]) * 1000 \
                if has_coords else None
            toks = fx.get("expected_road_tokens") or TOKENS[loc_id]
            if synthetic or not has_coords or not road or not road.get("name"):
                status = "unverified"
            elif any(t in road["name"].lower() for t in toks) and dist <= 250:
                status = "match"
            else:
                status = "mismatch"
            road_match.update(status=status, returned_name=(road or {}).get("name"),
                              returned_type=(road or {}).get("type"),
                              distance_m=round(dist, 1) if dist is not None else None,
                              note="Synthetic road identity from the scenario; the real location has not been validated."
                              if synthetic else ("Requested coordinates not yet determined." if not has_coords else None))
            per = sorted(rec["periods"], key=lambda p: p["timestamp"])
            ends = [dt(per[i + 1]["dateTimeISO"]) if i + 1 < len(per) else dt(p["dateTimeISO"]) + timedelta(hours=1)
                    for i, p in enumerate(per)]
            last_start = dt(per[-1]["dateTimeISO"]) if per else None
            coverage["pavement"] = {"last_period_start": last_start.isoformat() if last_start else None,
                                    "end_reason": "Provider pavement forecast ends here (documented horizon up to 24 h); "
                                                  "later periods are unavailable, not extrapolated."}
            lim = settings["freshness_limits"].get("xweather_pavement_max_age_hours")
            pa = fp.evaluate(fp.policy_from_limits(settings["freshness_limits"]), "xweather_pavement", None, fx.get("retrieved_at"),
                             None, E, first_seen_utc=fx.get("pavement_content_first_seen"), provider_record=settings.get("source_mode") == "provider")
            current = [] if pa["exclude"] else [(p, e) for p, e in zip(per, ends) if e > E]
            n_ended = sum(1 for e in ends if e <= E)
            if current and n_ended:
                checks.append({"id": "ended_periods_withheld", "status": "info",
                               "message": f"{n_ended} pavement period(s) whose valid time had ended were withheld."})
            if per and not current:
                code = pa["reason_code"] if pa["exclude"] else "valid_period_ended"
                why = {"inconsistent_timestamps": f"Pavement forecast timestamps are inconsistent ({'; '.join(pa['timestamp_problems'])}). ",
                       "over_hard_limit": f"Pavement forecast is older than the {lim} h freshness limit ({pa['age_note']}). ",
                       "age_unknown": "Pavement forecast age cannot be bounded (no usable retrieval, first-seen or issue time). ",
                       "valid_period_ended": f"Pavement forecast expired: its valid periods ended at {max(ends).isoformat()}. "}[code]
                withheld.append({"quantity": "pavement_temperature", "expired_after": max(ends).isoformat(), "reason_code": code,
                                 "reason": why + "Withheld from the current view; the road stays in assumed service; refresh within "
                                                 "request caps."})
                if pa["exclude"]:
                    # Excluded periods (not yet ended) stay in the withheld record and export with valid times, evidence ids and
                    # the reason; they never enter current charts, readouts or review inputs.
                    withheld[-1].update(status=pa["contract_status"], source=pav_src, excluded_points=[
                        {"valid_start": p["dateTimeISO"], "valid_end": e.isoformat(), "unit": units, "kind": "modeled",
                         "value": _disp(p["roadSurface"]["tempF"], units) if (p.get("roadSurface") or {}).get("tempF") is not None else None,
                         "surface_condition": (p.get("roadSurface") or {}).get("condition"), "evidence_ids": _pav_ids(fx, p["dateTimeISO"]),
                         "freshness": pa["contract_status"], "reason_code": code} for p, e in zip(per, ends) if e > E])
                freshness.append({"quantity": "pavement_temperature", "message": withheld[-1]["reason"], "reason_code": code,
                                  "assessment": pa, "status": {"inconsistent_timestamps": "unknown", "over_hard_limit": "stale", "age_unknown": "unknown",
                                                               "valid_period_ended": "expired"}[code]})
                text.append(withheld[-1]["reason"])
            else:
                pts = []
                for p, e in current:
                    rs = p.get("roadSurface")
                    if rs is None:
                        pts.append({"valid_start": p["dateTimeISO"], "valid_end": e.isoformat(), "value": None,
                                    "kind": "unavailable", "freshness": "current"})
                        gaps.append({"quantity": "pavement_temperature", "valid_start": p["dateTimeISO"],
                                     "reason": "Provider returned no pavement value for this period."})
                        continue
                    if abs(convert_c_to_f(rs["tempC"]) - rs["tempF"]) > 0.2:
                        checks.append({"id": "unit_consistency", "status": "warn",
                                       "message": f"Provider tempC {rs['tempC']} and tempF {rs['tempF']} disagree at {p['dateTimeISO']}."})
                    pts.append({"valid_start": p["dateTimeISO"], "valid_end": e.isoformat(),
                                "value": _disp(rs["tempF"], units), "kind": "modeled", "freshness": pa["contract_status"],
                                "surface_condition": rs["condition"], "_f": rs["tempF"]})
                pav_pts = [dict(q) for q in pts if q["value"] is not None]
                for q in pts:
                    q.pop("_f", None)
                series.append({"location_id": loc_id, "quantity": "pavement_temperature",
                               "source": pav_src, "kind": "modeled",
                               "unit": units, "source_unit": "F/C (roadSurface.tempF/tempC)", "style": "solid-pavement",
                               "points": pts})
                freshness.append({"quantity": "pavement_temperature", "status": pa["contract_status"], "reason_code": pa["reason_code"],
                                  "message": fp.describe(pa, "Pavement forecast"), "assessment": pa})
                gaps.append({"quantity": "pavement_temperature", "valid_start": last_start.isoformat(),
                             "reason": "Beyond the provider's returned pavement horizon: unavailable (not extrapolated)."})
                text.append(coverage["pavement"]["end_reason"])
                if not synthetic and any(q["value"] is not None for q in pts):
                    attribution.append(XW_ATTRIBUTION)
                if mode == "demo":
                    window = fx.get("requested_window_hours", 24)
                    sim_start = max(ends)
                    hours = int((E + timedelta(hours=window) - sim_start).total_seconds() // 3600)
                    if hours > 0:
                        series.append(_simulated(loc_id, units, sim_start, hours))
                        text.append("Dashed periods are a SaltWise simulation (illustrative), not a provider forecast.")
    elif fx.get("pavement_withheld_reason"):
        # Location or provider road match not confirmed: pavement withheld with its reason; air is never substituted.
        series.append({"location_id": loc_id, "quantity": "pavement_temperature", "source": pav_src, "kind": "unavailable",
                       "unit": units, "source_unit": "F/C", "style": "none", "points": []})
        gaps.append({"quantity": "pavement_temperature", "valid_start": None, "withheld": True,
                     "reason": fx["pavement_withheld_reason"]})
        road_match.update(fx.get("road_match") or {})
    elif mode == "demo":
        series.append(_simulated(loc_id, units, E, 12, "air_temperature"))
        series.append(_simulated(loc_id, units, E, 12))
        text.append("Demo mode: all values are a SaltWise simulation (illustrative).")

    if fx.get("rwis_feature"):
        a = fx["rwis_feature"]["attributes"]
        history.append({"source": "DDOT RWIS (historical record)", "kind": "historical",
                        "observed_at": datetime.fromtimestamp(a["DATADATETIME"] / 1000, tz=timezone.utc).isoformat(),
                        "note": "Historical public record; not a current observation."})

    window_hours = settings.get("window_hours")
    if window_hours:
        w_end = E + timedelta(hours=window_hours)
        for s in series:
            s["points"] = [q for q in s["points"] if dt(q["valid_start"]) < w_end and dt(q["valid_end"]) > E]
        cov_last = coverage["pavement"].get("last_period_start")
        if cov_last and dt(cov_last) + timedelta(hours=1) < w_end:
            text.append(f"Pavement series ends at {cov_last}; the rest of the selected window is unavailable.")
    if synthetic:
        text.insert(0, "Synthetic scenario - illustrative weather, not a live forecast. No weather provider was contacted.")
    w_end_iso = (E + timedelta(hours=window_hours)).isoformat() if window_hours else None
    flags, review_periods, notes = review(series, gaps, withheld, freshness, units, coverage, settings["evaluation_time"], w_end_iso)
    pav_fr = next((f for f in freshness if f.get("quantity") == "pavement_temperature" and f.get("assessment")), None)
    if pav_fr and not pav_fr["assessment"]["confirmed_fresh"] and settings.get("source_mode") == "provider":
        # provider pavement with an unknown issue time: precautionary prompts only (synthetic scenarios have no issue time)
        for f in flags:
            if any(e.get("kind") == "modeled" for e in f.get("evidence") or []):
                f["evidence_qualification"] = fp.UNCONFIRMED_PROMPT
    for f in flags:
        text += [f["reason"], f["next_step"]]
    text += notes
    text += [f"Road match: {road_match['status']}", "Operational treatment thresholds are illustrative."] + attribution
    ref = {"value": 32.0 if units == "F" else 0.0, "unit": units,
           "label": "Physical reference: water freezes at 32 F / 0 C (physical, not a policy)"}
    location = {"location_id": loc_id, "name": loc["name"], "road_match": road_match,
                "verified": road_match["status"] == "match" and loc.get("coordinates_verified") is True}
    export = {"schema_version": "1", "source_mode": source_mode, "window_hours": window_hours,
              "location": location, "units": units, "evaluation_time": settings["evaluation_time"],
              "series": series, "gaps": gaps, "withheld": withheld, "freshness": freshness, "coverage": coverage,
              "flags": flags, "review_periods": review_periods, "data_checks": checks, "attribution": attribution}
    return {"source_mode": source_mode, "window_hours": window_hours,
            "location": location, "units": units, "freezing_reference": ref, "series": series, "coverage": coverage,
            "gaps": gaps, "withheld": withheld, "freshness": freshness, "data_checks": checks, "flags": flags,
            "review_periods": review_periods,
            "history": history, "treatment_decision": None, "location_in_assumed_service": True,
            "evidence_panel": {"location_id": loc_id, "sources": sorted({s["source"] for s in series})},
            "attribution": attribution, "text": text, "export": export}


FLAG_TITLES = {"refreeze_review": "Refreeze risk", "rain_timing_review": "Rain before snow",
               "treatment_review": "Treatment review", "evidence_review": "Evidence needed"}
RULE_TAIL = (" Illustrative review rule, not an approved operational policy; "
             "people make the treatment decision.")


DISPLAY_TZ = ZoneInfo("America/New_York")


def _when(iso):
    """DC local time, as on the chart: provider times are UTC; the synthetic fixtures already carry -05:00 (unchanged)."""
    d = dt(iso)
    return (d.astimezone(DISPLAY_TZ) if d.tzinfo else d).strftime("%a %-I:%M %p")


def review(series, gaps, withheld, freshness, units, coverage, now_iso, window_end_iso=None):
    """Stage C: which forecast periods need human review, and why (deterministic, illustrative).

    Uses only displayed values: modeled pavement temperature and surface state, forecast precipitation
    text and probability, and timestamps. The only temperature reference is the physical freezing point
    (32 F / 0 C); no treatment threshold is introduced. Missing evidence asks for evidence.
    """
    U = "F" if units == "F" else "C"
    ref = 32.0 if units == "F" else 0.0
    pav_series = [s for s in series if s["quantity"] == "pavement_temperature"]
    pav_src = pav_series[0]["source"] if pav_series else "pavement source"
    pav = sorted((p for s in pav_series if s["kind"] == "modeled" for p in s["points"] if p.get("value") is not None),
                 key=lambda p: dt(p["valid_start"]))
    pr_series = [s for s in series if s["quantity"] == "precipitation"]
    pr_src = pr_series[0]["source"] if pr_series else None
    precip = {dt(p["valid_start"]): p for s in pr_series for p in s["points"]}
    flags, periods, notes = [], {}, []
    step = "Review this location before morning travel and confirm surface conditions in the field."

    def pr_text(t):
        p = precip.get(dt(t))
        return f"; forecast {p['description'].lower()}, {p['value']}% chance of precipitation" if p and p.get("description") else ""

    def mark(p, fid):
        periods.setdefault(p["valid_start"], {"point": p, "concerns": set()})["concerns"].add(fid)

    def pav_ev(p):
        return {"source": pav_src, "kind": "modeled", "valid_start": p["valid_start"], "value": p["value"],
                "unit": U, "surface": p.get("surface_condition")}

    # 1. Refreeze: a wet surface earlier in the window, then pavement at or below the physical freezing point.
    wet_seen, first = False, None
    for p in pav:
        if p.get("surface_condition") in WET:
            wet_seen = True
        if wet_seen and p["value"] <= ref:
            first = first or p
            mark(p, "refreeze_review")
    if first:
        flags.append({"id": "refreeze_review", "title": FLAG_TITLES["refreeze_review"], "valid_time": first["valid_start"],
                      "illustrative": True, "evidence": [pav_ev(first)], "next_step": step,
                      "reason": f"After a wet surface, pavement reaches {first['value']:g} {U} "
                                f"({first.get('surface_condition', 'surface n/a')}) at {_when(first['valid_start'])}, at or below "
                                f"the {ref:g} {U} physical freezing reference{pr_text(first['valid_start'])}." + RULE_TAIL})
    # 2. Rain before snow, from the forecast text.
    ordered = [precip[t] for t in sorted(precip)]
    rain = next((p for p in ordered if "rain" in (p.get("description") or "").lower()
                 and "snow" not in (p.get("description") or "").lower()), None)
    snow = next((p for p in ordered if "snow" in (p.get("description") or "").lower()), None)
    if rain and snow and dt(rain["valid_start"]) < dt(snow["valid_start"]) and pr_src:
        for p in pav:
            if dt(rain["valid_start"]) <= dt(p["valid_start"]) <= dt(snow["valid_start"]):
                mark(p, "rain_timing_review")
        flags.append({"id": "rain_timing_review", "title": FLAG_TITLES["rain_timing_review"], "valid_time": snow["valid_start"],
                      "illustrative": True, "next_step": "Review the timing of any pre-treatment against the rain period. " + step,
                      "evidence": [{"source": pr_src, "kind": "provider_forecast", "valid_start": rain["valid_start"],
                                    "description": rain.get("description"), "probability_pct": rain.get("value")},
                                   {"source": pr_src, "kind": "provider_forecast", "valid_start": snow["valid_start"],
                                    "description": snow.get("description"), "probability_pct": snow.get("value")}],
                      "reason": f"Rain is forecast from {_when(rain['valid_start'])} ({rain['value']}% chance) before snow from "
                                f"{_when(snow['valid_start'])} ({snow['value']}% chance); rain may dilute or wash off "
                                "pre-treatment, a review consideration." + RULE_TAIL})
    # 3. Treatment review: at or below freezing with a wet, slushy, snowy, or icy surface.
    cold = [p for p in pav if p["value"] <= ref and p.get("surface_condition") in PRECIP_SURFACE]
    for p in cold:
        mark(p, "treatment_review")
    if cold:
        c = cold[0]
        flags.append({"id": "treatment_review", "title": FLAG_TITLES["treatment_review"], "valid_time": c["valid_start"],
                      "illustrative": True, "evidence": [pav_ev(c)], "next_step": step,
                      "reason": f"{len(cold)} period(s) from {_when(c['valid_start'])} show pavement at or below {ref:g} {U} with surface "
                                f"state {c['surface_condition']} (first: {c['value']:g} {U}){pr_text(c['valid_start'])}." + RULE_TAIL})
        notes.append("Below the freezing reference, how well de-icing material works varies with temperature; material "
                     "effectiveness is a review consideration. No threshold is applied (illustrative note).")
    # 4. Evidence needed: missing values, no records, expired or stale data, or a window past the pavement series.
    issues, times = [], []
    missing = [g for g in gaps if g["quantity"] == "pavement_temperature" and g.get("valid_start")
               and "no pavement value" in g["reason"].lower()]
    if missing:
        issues.append(f"pavement values missing for {len(missing)} period(s) ({', '.join(_when(g['valid_start']) for g in missing[:4])})")
        times += [g["valid_start"] for g in missing]
    for g in gaps:
        if g["quantity"] == "pavement_temperature" and g.get("valid_start") is None:
            issues.append(g["reason"].rstrip(".") if g.get("withheld") else "no pavement records were returned for this location")
            break
    issues += [g["reason"].rstrip(".") for g in gaps if g["quantity"] == "air_temperature" and g.get("withheld")]
    for w in withheld:
        q = "air" if w.get("quantity") == "air_temperature" else "pavement"
        issues.append({"over_hard_limit": f"the {q} forecast is older than the freshness setting, so its values are excluded",
                       "inconsistent_timestamps": f"the {q} forecast timestamps are inconsistent, so its values are excluded",
                       "age_unknown": f"the {q} forecast has no usable retrieval, first-seen or issue time, so its age cannot be "
                                      "bounded and its values are excluded"}
                      .get(w.get("reason_code")) or f"the pavement forecast expired at {_when(w['expired_after'])} and is withheld")
    cov_last = (coverage.get("pavement") or {}).get("last_period_start")
    if window_end_iso and cov_last and dt(cov_last) + timedelta(hours=1) < dt(window_end_iso):
        ends = [p["valid_end"] for x in series if x["quantity"] == "pavement_temperature" for p in x["points"]
                if p.get("value") is not None and p.get("valid_end")]          # the series' own end, as on the chart
        issues.append(f"the selected window runs past the pavement series, which ends {_when(max(ends, key=dt) if ends else cov_last)}")
    if issues:
        for t in times:
            periods.setdefault(t, {"point": {"valid_start": t, "value": None, "surface_condition": None},
                                   "concerns": set()})["concerns"].add("evidence_review")
        flags.append({"id": "evidence_review", "title": FLAG_TITLES["evidence_review"], "valid_time": times[0] if times else now_iso,
                      "illustrative": True, "evidence": [{"source": pav_src, "kind": "unavailable", "issues": issues}],
                      "next_step": "Obtain the missing evidence (refresh within request caps or check field observations) "
                                   "before deciding. Missing evidence does not mean treatment is unnecessary.",
                      "reason": "Evidence is incomplete: " + "; ".join(issues) + "." + RULE_TAIL})
    review_periods = [{"valid_start": t, "pavement": v["point"].get("value"), "unit": U,
                       "surface": v["point"].get("surface_condition"),
                       "precipitation": (precip.get(dt(t)) or {}).get("description"),
                       "precipitation_pct": (precip.get(dt(t)) or {}).get("value"),
                       "concerns": sorted(v["concerns"])} for t, v in sorted(periods.items(), key=lambda kv: dt(kv[0]))]
    return flags, review_periods, notes


def apply_action(state, action, fx, settings):
    state = dict(state or {"location_id": fx["location"]["location_id"], "units": settings["units"],
                           "window": ["21:00", "09:00"], "slider": None})
    key = {"select_location": "location_id", "set_window": "window", "toggle_units": "units", "move_slider": "slider"}
    state[key[action["action"]]] = action["value"]
    loc_id = state["location_id"]
    fx2 = {k: v for k, v in fx.items() if k not in ("ui_actions",)}
    fx2["location"] = {**fx["location"], "location_id": loc_id, "name": NAMES[loc_id]}
    state["view"] = build_view(fx2, {**settings, "units": state["units"], "mode": "demo"})
    return state


def handle_provider_error(fx, settings):
    err = fx["http_error"]
    secrets = [os.environ.get("XWEATHER_CLIENT_ID", ""), os.environ.get("XWEATHER_CLIENT_SECRET", "")]

    def redact(s):
        s = re.sub(r"(client_(?:id|secret)=)[^&\s]+", r"\1REDACTED", s)
        for v in secrets:
            if v:
                s = s.replace(v, "REDACTED")
        return s

    code = (err.get("body") or {}).get("error", {}).get("code", "error")
    msg = f"Xweather returned HTTP {err['status']} ({code}); pavement evidence unavailable for now."
    return {"ui_text": [msg + " Check the local credential configuration."],
            "logs": [redact(f"GET {err['url']} -> {err['status']}")],
            "exception_messages": [redact(f"ProviderAuthError: HTTP {err['status']} for {err['url']}")],
            "export_json": {"pavement": {"kind": "unavailable", "reason": msg}},
            "saved_urls": [redact(err["url"])], "reports": [msg],
            "pavement_kind": "unavailable", "probe_attempts": 1}


# ---------------------------------------------------------------------------
# Stage D - Storm Lab material accounting (deterministic simulation; every input is an assumption)
# ---------------------------------------------------------------------------
LB_PER_SHORT_TON = 2000.0
STORM_LABELS = ["SaltWise simulation", "illustrative assumptions: not measured DC road lengths, approved rates, or DC practice"]


def storm_lab(storm, settings):
    """Contract function (TC11): totals over the full accounting window, including catch-up applications."""
    w0, w1 = dt(storm["window"]["start"]), dt(storm["window"]["end"])
    a = storm["assumptions"]
    per_app = float(a["rate_lb_per_lane_mile"]) * float(a["lane_miles"])
    totals = {k: float(sum(per_app for t in v["applications"] if w0 <= dt(t) <= w1)) for k, v in storm["scenarios"].items()}
    change = {k: v - totals["baseline"] for k, v in totals.items() if k != "baseline"}
    outside = {k: [t for t in v["applications"] if not (w0 <= dt(t) <= w1)] for k, v in storm["scenarios"].items()}
    return {"totals_lb": totals, "change_vs_baseline_lb": change,
            "material_avoided_lb": {k: -v for k, v in change.items()},
            "applications_outside_window": outside,
            "shown": {"baseline": True, "assumptions": True, "required_service": True},
            "labels": STORM_LABELS,
            "text": [f"Totals cover the same full accounting window for every plan: {storm['window']['start']} to "
                     f"{storm['window']['end']}, including repeat and catch-up applications.",
                     "A deferred application is not a permanent reduction; later applications count in full.",
                     "Required road service and access are constraints: " + storm.get("required_service", "")]}


def plan_material(plan, lane_miles, rate, window):
    """plan: {location_id: {"initial": iso|None, "later": [iso, ...]}} -> per-location and total material (lb)."""
    w0, w1 = dt(window["start"]), dt(window["end"])
    rows, outside = {}, []
    for loc, p in plan.items():
        per_app = float(lane_miles.get(loc, 0.0)) * float(rate)
        times = ([("initial", p.get("initial"))] if p.get("initial") else []) + [("later", t) for t in p.get("later", [])]
        r = {"initial_lb": 0.0, "later_lb": 0.0, "applications": 0, "per_application_lb": per_app}
        for kind, t in times:
            if w0 <= dt(t) <= w1:
                r[f"{kind}_lb"] += per_app
                r["applications"] += 1
            else:
                outside.append({"location_id": loc, "time": t, "kind": kind})
        r["total_lb"] = r["initial_lb"] + r["later_lb"]
        rows[loc] = r
    tot = {k: sum(r[k] for r in rows.values()) for k in ("initial_lb", "later_lb", "total_lb")}
    return {"per_location": rows, **tot, "outside_window": outside}


def compare_plans(baseline_plan, scenario_plan, lane_miles, rate, window, price_per_short_ton=None):
    """Material avoided = baseline total - scenario total (negative when the scenario uses more)."""
    b = plan_material(baseline_plan, lane_miles, rate, window)
    sc_ = plan_material(scenario_plan, lane_miles, rate, window)
    avoided = b["total_lb"] - sc_["total_lb"]
    cost = None
    if price_per_short_ton:
        cost = {"price_per_short_ton": float(price_per_short_ton),
                "baseline_cost": b["total_lb"] / LB_PER_SHORT_TON * price_per_short_ton,
                "scenario_cost": sc_["total_lb"] / LB_PER_SHORT_TON * price_per_short_ton,
                "cost_difference": avoided / LB_PER_SHORT_TON * price_per_short_ton}
    return {"baseline": b, "scenario": sc_, "material_avoided_lb": avoided,
            "material_avoided_short_tons": avoided / LB_PER_SHORT_TON, "cost": cost, "labels": STORM_LABELS}


def sensitivity(baseline_total_lb, scenario_initial_lb, additional_lb):
    """Hold the initial plan fixed; vary the hypothetical later-treatment requirement."""
    deficit = max(baseline_total_lb - scenario_initial_lb, 0.0)
    cases = [("No catch-up (only if no later treatment is needed - not established)", 0.0),
             ("Partial catch-up (half of the gap)", 0.5 * deficit),
             ("Full catch-up (later treatment closes the gap)", deficit),
             ("Full catch-up plus one more application round", deficit + additional_lb)]
    return [{"case": name, "initial_lb": scenario_initial_lb, "later_lb": later,
             "scenario_total_lb": scenario_initial_lb + later,
             "material_avoided_lb": baseline_total_lb - (scenario_initial_lb + later)} for name, later in cases]


def unresolved_requirements(scenario_plan, views):
    """Review flags that still need treatment review after the scenario's last application, or missing evidence."""
    out = []
    for loc, v in views.items():
        p = scenario_plan.get(loc, {})
        times = [dt(t) for t in ([p["initial"]] if p.get("initial") else []) + list(p.get("later", []))]
        last = max(times) if times else None
        for f in v.get("flags") or []:
            if f["id"] in ("treatment_review", "refreeze_review"):
                periods = [dt(r["valid_start"]) for r in v.get("review_periods", []) if f["id"] in r["concerns"]]
                after = [t for t in periods if last is None or t > last]
                if after:
                    out.append({"location_id": loc, "kind": "later treatment may be required",
                                "detail": f"{FLAG_TITLES[f['id']]}: {len(after)} flagged period(s) after the scenario's last "
                                          f"application (first {_when(min(after).isoformat())})."})
            if f["id"] == "evidence_review":
                out.append({"location_id": loc, "kind": "requirement unknown (missing evidence)",
                            "detail": "Evidence is incomplete; the location stays in assumed service and its later need is unknown."})
    return out

