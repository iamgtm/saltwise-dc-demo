"""Read-only access to the trusted data service's evidence snapshots (provider-data mode).

The dashboard never fetches weather: this module opens the service's SQLite store read-only, sends no request, and
rebuilds the provider payload shapes that saltwise_contract.build_view() already understands (nws_hourly,
xweather_roadweather) from the stored, normalized evidence. Three location statuses stay separate: geographic
verification (DCGIS), provider road-name matching (Xweather metadata) and confirmation of bridge-specific modeling.
Pavement is used only when the point is geographically verified AND the provider road matched; otherwise it is withheld
with a reason. Missing evidence is reported, never filled, substituted or turned into "no treatment", and every
location stays in assumed service.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent          # demo build: every path stays inside this package
XW_ATTRIBUTION = {"text": "Powered by Vaisala Xweather", "url": "https://www.xweather.com/"}
NWS_ATTRIBUTION = {"text": "National Weather Service (api.weather.gov)", "url": "https://www.weather.gov/"}
PRECIP_WEATHER = {"rain", "rain_showers", "drizzle", "freezing_rain", "freezing_drizzle", "snow", "snow_showers", "sleet",
                  "thunderstorms", "hail", "ice_pellets"}
FRESHNESS_PENDING = {"_status": "PENDING USER REVIEW - no age limit applied; only periods whose valid time has ended are withheld",
                     "nws_air_forecast_max_age_hours": None, "xweather_pavement_max_age_hours": None,
                     "rwis_observation_max_age_minutes": None}
FRESHNESS_NOTE = ("Freshness limits are pending user review, so no age limit is applied: only periods whose valid time has "
                  "ended are withheld. Retrieval age is not forecast age.")
GEO = {"verified": "Verified on DCGIS", "partial": "Partial (needs review)"}
ROAD = {"matched": "Matched", "mismatch": "Mismatch", "unresolved": "Unresolved", "not_checked": "Not checked"}
BRIDGE = {"unconfirmed": "Unconfirmed", "not_applicable": "Not applicable", "confirmed": "Confirmed"}
DROP_KEYS = {"request", "url_redacted", "params", "body_redacted", "headers"}


def store_path():
    return Path(os.environ.get("SALTWISE_STORE") or ROOT / "data" / "store" / "saltwise.sqlite")


def registry_path():
    return Path(os.environ.get("SALTWISE_REGISTRY") or ROOT / "data" / "locations" / "registry.json")


def now_utc():
    """Current time. SALTWISE_SNAPSHOT_NOW (ISO 8601) replays saved snapshots at a fixed time for tests and reviews."""
    s = os.environ.get("SALTWISE_SNAPSHOT_NOW")
    return _dt(s) if s else datetime.now(timezone.utc)


def _dt(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(d):
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def store_token():
    """Changes whenever the trusted service writes (main file or WAL) or the registry changes; no provider polling."""
    p = store_path()
    return (str(p),) + tuple((q.stat().st_mtime_ns, q.stat().st_size) if q.exists() else None
                             for q in (p, Path(str(p) + "-wal"), registry_path()))


def _latest(con, provider, lid):
    cur = con.execute("SELECT id, status, retrieved_utc, issued_utc, valid_from_utc, valid_to_utc, evidence_json, meta_json, sha256 "
                      "FROM snapshots WHERE provider=? AND location_id=? AND status IN ('ok','ok_partial') ORDER BY id DESC LIMIT 1",
                      (provider, lid))
    r = cur.fetchone()
    if not r:
        return None
    d = dict(zip([c[0] for c in cur.description], r))
    d["evidence"], m = json.loads(d.pop("evidence_json")), json.loads(d.pop("meta_json"))
    # The Xweather refresh stores its whole result; the parsed metadata (road match, coverage) sits under "meta".
    d["meta"] = {**m["meta"], "headers": m.get("headers")} if isinstance(m.get("meta"), dict) else m
    return d


def read_all():
    """Latest usable Xweather and NWS snapshot per registry location. Read-only; never creates the store."""
    out = {"store_status": "available", "registry_generated_utc": None, "locations": {}}
    try:
        reg = json.loads(registry_path().read_text())
    except (OSError, ValueError) as e:
        out["store_status"] = f"unavailable (location registry unreadable: {type(e).__name__})"
        return out
    out["registry_generated_utc"] = reg.get("generated_utc")
    con, p = None, store_path()
    if not p.exists():
        out["store_status"] = "unavailable (no snapshot store yet; the trusted refresh has not run)"
    else:
        try:
            con = sqlite3.connect(f"file:{quote(str(p))}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error as e:
            out["store_status"] = f"unavailable ({type(e).__name__})"
    try:
        for loc in reg.get("locations", []):
            snaps = {"xweather": None, "nws": None}
            for prov in snaps:
                if con is not None:
                    try:
                        snaps[prov] = _latest(con, prov, loc["id"])
                    except sqlite3.Error as e:
                        out["store_status"] = f"unavailable ({type(e).__name__})"
            out["locations"][loc["id"]] = {"registry": loc, **snaps}
    finally:
        if con is not None:
            con.close()
    return out


def statuses(loc, xw=None):
    v = loc.get("verification") or {}
    reg_rm = loc.get("provider_road_match") or {}
    snap_rm = ((xw or {}).get("meta") or {}).get("road_match") or {}
    geo = (v.get("geographic_verification") or {}).get("status") or loc.get("geographic_status") or "unknown"
    road = (v.get("provider_road_matching") or {}).get("status") or reg_rm.get("status") or "not_checked"
    if snap_rm.get("status") == "mismatch" or (road == "matched" and xw is not None and snap_rm.get("status") != "matched"):
        road = snap_rm.get("status") or "unresolved"          # the stored response must agree before pavement is used
    bridge = (v.get("bridge_specific_modeling") or {}).get("status") or ("unconfirmed" if loc.get("bridge") else "not_applicable")
    prov_road = snap_rm.get("provider_road") or reg_rm.get("provider_road")
    prov_type = snap_rm.get("provider_road_type") or reg_rm.get("provider_road_type")
    keep = " The road stays in assumed service."
    if geo != "verified":
        reason, short = "Pavement withheld: the location is only partially verified on DCGIS, so no provider request was made." + keep, "location review"
    elif road == "mismatch":
        reason, short = (f"Pavement withheld: unavailable (road match). Xweather matched this point to '{prov_road}', not "
                         f"{loc['name']}." + keep), "road match"
    elif road != "matched":
        reason, short = "Pavement withheld: the provider road match is not confirmed." + keep, "road match"
    elif xw is None:
        reason, short = "Pavement unavailable: no Xweather snapshot is stored for this point yet." + keep, "no snapshot"
    elif (xw.get("meta") or {}).get("geographic_check") != "consistent":
        reason, short = "Pavement withheld: the provider's returned coordinates do not match the requested point." + keep, "coordinates"
    else:
        reason, short = None, None
    return {"geo": geo, "road": road, "bridge": bridge, "is_bridge": bool(loc.get("bridge")),
            "geo_label": GEO.get(geo, geo.title()), "road_label": ROAD.get(road, road), "bridge_label": BRIDGE.get(bridge, bridge),
            "provider_road": prov_road, "provider_road_type": prov_type, "pavement_reason": reason, "pavement_short": short}


def air_reason(geo, nw):
    if geo != "verified":
        return "Air forecast not requested: the location is only partially verified on DCGIS."
    if nw is None:
        return "Air forecast unavailable: no NWS snapshot is stored for this point yet."
    return None


def _xw_payload(xw):
    by = {}
    for e in xw["evidence"]:
        by.setdefault(e["valid_from_utc"], {})[e["variable"]] = e
    periods = []
    for t in sorted(by, key=_dt):
        temp = (by[t].get("pavement_temperature") or {}).get("value")
        cond = (by[t].get("road_surface_condition") or {}).get("value")
        rs = None if temp is None else {"condition": cond, "tempC": temp, "tempF": round(temp * 9 / 5 + 32, 2)}
        periods.append({"timestamp": int(_dt(t).timestamp()), "dateTimeISO": t, "roadSurface": rs})
    m = xw["meta"]
    rc, rm = m.get("returned_coordinates") or {}, m.get("road_match") or {}
    return {"success": True, "response": [{"loc": {"lat": rc.get("lat"), "long": rc.get("lon")},
                                           "road": {"name": rm.get("provider_road"), "type": rm.get("provider_road_type")},
                                           "periods": periods}]}


def _precip_desc(weather, start):
    """Precipitation words from the structured gridpoint weather items covering this period (no text parsing)."""
    s, parts = _dt(start), []
    for a, b, items in weather:
        if a <= s < b:
            for i in items:
                if i.get("weather") in PRECIP_WEATHER:
                    label = i["weather"].replace("_", " ").capitalize() + (f" ({i['coverage'].replace('_', ' ')})" if i.get("coverage") else "")
                    if label not in parts:
                        parts.append(label)
    return ", ".join(parts)


def _nws_payload(nw):
    hourly, weather = {}, []
    for e in nw["evidence"]:
        if e["variable"] == "weather_type":
            weather.append((_dt(e["valid_from_utc"]), _dt(e["valid_to_utc"]), e["value"] or []))
        else:
            hourly.setdefault((e["valid_from_utc"], e["valid_to_utc"]), {})[e["variable"]] = e
    structured = nw["meta"].get("weather_layer_status") == "provided"
    periods = []
    for (s, en), d in sorted(hourly.items(), key=lambda kv: _dt(kv[0][0])):
        t = (d.get("air_temperature") or {}).get("value")
        if t is None:
            continue                                     # missing temperature stays a gap; never filled
        periods.append({"startTime": s, "endTime": en, "temperature": round(t * 9 / 5 + 32, 2), "temperatureUnit": "F",
                        "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": (d.get("precipitation_probability") or {}).get("value")},
                        "shortForecast": _precip_desc(weather, s) if structured else ""})
    return {"properties": {"updateTime": nw["meta"].get("update_time"), "generatedAt": nw["meta"].get("generated_at"), "periods": periods}}


def _counts(snap, var, now):
    ev = [e for e in snap["evidence"] if e["variable"] == var]
    return sum(_dt(e["valid_to_utc"]) <= now for e in ev), sum(_dt(e["valid_to_utc"]) > now for e in ev)


def _age(snap, now):
    return None if snap is None else round((now - _dt(snap["retrieved_utc"])).total_seconds() / 60)


def provenance(loc, s, xw, nw, now):
    v = loc.get("verification") or {}
    pav = {"status": "no snapshot stored", "used_in_view": False, "withheld_reason": s["pavement_reason"]}
    if xw is not None:
        m, (n_end, n_cur) = xw["meta"], _counts(xw, "pavement_temperature", now)
        pav = {"provider": "Xweather Road Weather Conditions", "kind": "provider-modeled pavement forecast (not a sensor observation)",
               "used_in_view": s["pavement_reason"] is None, "withheld_reason": s["pavement_reason"],
               "retrieved_utc": xw["retrieved_utc"], "issued_utc": xw["issued_utc"], "issue_time": xw["issued_utc"] or "not supplied by provider",
               "returned_coverage_utc": m.get("coverage_utc"), "returned_coverage_hours": m.get("coverage_hours"),
               "periods_ended_before_evaluation": n_end, "periods_current": n_cur, "geographic_check": m.get("geographic_check"),
               "returned_distance_m": m.get("distance_m"), "fields_present": m.get("fields_present"),
               "cost_tokens": (m.get("headers") or {}).get("X-Cost-Tokens"), "snapshot_sha256": xw["sha256"], "attribution": XW_ATTRIBUTION}
    air = {"status": "no snapshot stored", "used_in_view": False, "withheld_reason": s.get("air_reason")}
    if nw is not None:
        m, (n_end, n_cur) = nw["meta"], _counts(nw, "air_temperature", now)
        air = {"provider": "NWS api.weather.gov", "kind": "provider atmospheric forecast (air temperature; not pavement)",
               "used_in_view": s.get("air_reason") is None, "withheld_reason": s.get("air_reason"),
               "retrieved_utc": nw["retrieved_utc"], "issued_utc": nw["issued_utc"], "issue_time": m.get("update_time") or "not supplied by provider",
               "generated_at": m.get("generated_at"), "grid": m.get("grid"), "shared_grid_with": m.get("shared_grid_with"),
               "points_cache": m.get("points_cache"), "forecast_hourly_url": m.get("forecast_hourly_url"),
               "weather_layer": m.get("weather_layer_status"), "returned_coverage_utc": m.get("coverage_utc"),
               "returned_coverage_hours": m.get("coverage_hours"), "periods_ended_before_evaluation": n_end, "periods_current": n_cur,
               "precipitation_type_source": "NWS gridpoint weather layer (structured fields); forecast text is not parsed",
               "units": "stored in degC; converted for display", "snapshot_sha256": nw["sha256"], "attribution": NWS_ATTRIBUTION}
    return sanitize({
        "location_id": loc["id"], "name": loc["name"], "evaluated_at_utc": iso(now),
        "statuses": {"geographic_verification": {"status": s["geo"], "label": s["geo_label"], "basis": (v.get("geographic_verification") or {}).get("basis")},
                     "provider_road_matching": {"status": s["road"], "label": s["road_label"], "provider_road": s["provider_road"],
                                                "provider_road_type": s["provider_road_type"], "basis": (v.get("provider_road_matching") or {}).get("basis")},
                     "bridge_specific_modeling": {"status": s["bridge"], "label": s["bridge_label"], "basis": (v.get("bridge_specific_modeling") or {}).get("basis")}},
        "open_questions": loc.get("open_questions") or [],
        "assumed_service": "included: missing or withheld evidence never removes a road from assumed service",
        "treatment_decision": None, "pavement": pav, "air": air, "freshness": FRESHNESS_NOTE,
        "retrieval_age_minutes": {"pavement": _age(xw, now), "air": _age(nw, now)}})


def fixture(snap, location_id, now):
    """(contract input, statuses) for one location, evaluated at `now`."""
    entry = snap["locations"][location_id]
    loc, xw, nw = entry["registry"], entry.get("xweather"), entry.get("nws")
    s = statuses(loc, xw)
    s["air_reason"] = air_reason(s["geo"], nw)
    fx = {"location": {"location_id": location_id, "name": loc["name"], "requested_lat": loc["lat"], "requested_lon": loc["lon"],
                       "coordinates_verified": s["geo"] == "verified", "validation_status": s["geo_label"]},
          "evaluation_time": iso(now)}
    if s["pavement_reason"] is None:
        fx["xweather_roadweather"], fx["retrieved_at"] = _xw_payload(xw), xw["retrieved_utc"]
    else:
        fx["pavement_withheld_reason"] = s["pavement_reason"]
        fx["road_match"] = {"status": {"matched": "match"}.get(s["road"], s["road"]), "returned_name": s["provider_road"],
                            "returned_type": s["provider_road_type"], "note": s["pavement_reason"]}
    if s["air_reason"] is None:
        fx["nws_hourly"] = _nws_payload(nw)
    else:
        fx["air_unavailable_reason"] = s["air_reason"]
    fx["provenance"] = provenance(loc, s, xw, nw, now)
    fx["evidence_ids"] = evidence_index(xw if s["pavement_reason"] is None else None, nw if s["air_reason"] is None else None)
    cur = fx["provenance"]["pavement"].get("periods_current", 0)
    s["pavement_badge"] = (f"Pavement withheld · {s['pavement_short']}" if s["pavement_reason"]
                           else "Pavement: Xweather modeled" if cur else "Pavement: no current periods")
    return fx, s


def sanitize(obj):
    """Drop request/header/body fields and anything that looks like a credentialed URL."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items() if k not in DROP_KEYS}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, str) and ("client_secret" in obj or "client_id" in obj):
        return "[removed: credentialed request URL]"
    return obj


def _cov(x):
    c = x.get("returned_coverage_utc") or {}
    return f"{c.get('from')} to {c.get('to')} ({x.get('returned_coverage_hours')} h)" if c.get("from") else "none"


def details_markdown(prov, checks=()):
    """Markdown for the Road Weather evidence panel: statuses, times, coverage, reasons and attribution."""
    s, p, a = prov["statuses"], prov["pavement"], prov["air"]

    def status_line(key, title):
        x = s[key]
        return f"**{title}:** {x['label']}" + (f" — {x['basis']}" if x.get("basis") else "")

    lines = ["**Data mode:** provider data from saved snapshots (read-only; this page sends no weather request)",
             f"**Evaluated at (UTC):** {prov['evaluated_at_utc']}",
             status_line("geographic_verification", "Geographic verification (DCGIS)"),
             status_line("provider_road_matching", "Provider road-name match (Xweather)"),
             status_line("bridge_specific_modeling", "Bridge-specific modeling")]
    if p.get("used_in_view"):
        lines.append(f"**Pavement · {p['kind']}:** retrieved {p['retrieved_utc']}; issue time {p['issue_time']}; returned coverage "
                     f"{_cov(p)}; {p['periods_ended_before_evaluation']} ended period(s) withheld, {p['periods_current']} current.")
    else:
        lines.append(f"**Pavement:** {p.get('withheld_reason') or 'unavailable'}"
                     + (f" (stored snapshot retrieved {p['retrieved_utc']} is not shown)" if p.get("retrieved_utc") else ""))
    if a.get("used_in_view"):
        g = a.get("grid") or {}
        lines.append(f"**Air · {a['kind']}:** retrieved {a['retrieved_utc']}; NWS updateTime {a['issue_time']}; grid {g.get('office')} "
                     f"{g.get('x')},{g.get('y')} (shared with: {', '.join(a.get('shared_grid_with') or [])}); returned coverage {_cov(a)}; "
                     f"precipitation type: {a.get('weather_layer')} from structured gridpoint fields.")
    else:
        lines.append(f"**Air:** {a.get('withheld_reason') or 'unavailable'}")
    ages = prov["retrieval_age_minutes"]
    lines.append(f"**Freshness:** {FRESHNESS_NOTE} Retrieval age: pavement {ages['pavement']} min, air {ages['air']} min.")
    lines += [f"**Data check:** {c['message']}" for c in checks]
    lines += [f"**Open question:** {q}" for q in prov["open_questions"]]
    lines.append("**Attribution:** " + " · ".join(f"[{x['attribution']['text']}]({x['attribution']['url']})"
                                                  for x in (p, a) if x.get("used_in_view")) if (p.get("used_in_view") or a.get("used_in_view")) else "**Attribution:** no provider values shown")
    return "  \n".join(lines)


def location_rows(snap, now):
    rows = []
    for lid, e in snap["locations"].items():
        fx, s = fixture(snap, lid, now)
        p, a = fx["provenance"]["pavement"], fx["provenance"]["air"]
        rows.append({"Location": e["registry"]["name"], "Geographic verification": s["geo_label"],
                     "Provider road match": s["road_label"] + (f" (Xweather: {s['provider_road']})" if s["provider_road"] else ""),
                     "Bridge-specific modeling": s["bridge_label"] + (f" (road type '{s['provider_road_type']}' returned; no bridge attribute)"
                                                                      if s["bridge"] == "unconfirmed" and s["provider_road_type"] else ""),
                     "Pavement evidence": s["pavement_reason"] or f"Shown: {p['periods_current']} current period(s); {p['periods_ended_before_evaluation']} ended period(s) withheld",
                     "Air evidence": s["air_reason"] or f"Shown: {a['periods_current']} current period(s)"})
    return rows


def time_rows(snap, now):
    rows = []
    for lid, e in snap["locations"].items():
        _, s = fixture(snap, lid, now)
        for x, label, used in ((e["xweather"], "Xweather pavement (modeled)", s["pavement_reason"] is None),
                               (e["nws"], "NWS air (forecast)", s["air_reason"] is None)):
            if x is None:
                rows.append({"Location": e["registry"]["name"], "Source": label, "Shown": "No", "Retrieved (UTC)": "—", "Issued": "—",
                             "Returned coverage (UTC)": "No snapshot stored", "Retrieval age": "—"})
                continue
            cov = x["meta"].get("coverage_utc") or {}
            issued = x["issued_utc"] + (" (NWS updateTime)" if label.startswith("NWS") else "") if x["issued_utc"] else "Not supplied by provider"
            rows.append({"Location": e["registry"]["name"], "Source": label, "Shown": "Yes" if used else "No (withheld)",
                         "Retrieved (UTC)": x["retrieved_utc"][:16].replace("T", " "), "Issued": issued,
                         "Returned coverage (UTC)": f"{cov.get('from')} → {cov.get('to')} ({x['meta'].get('coverage_hours')} h)",
                         "Retrieval age": f"{_age(x, now)} min (not forecast age)"})
    return rows


def _current(x, now, variables):
    return [{"id": e["id"], "variable": e["variable"], "value": e["value"], "unit": e["unit"], "kind": e["kind"],
             "valid_from_utc": e["valid_from_utc"], "valid_to_utc": e["valid_to_utc"]}
            for e in (x or {}).get("evidence", []) if e["variable"] in variables and _dt(e["valid_to_utc"]) > now]


def export_all(snap, now):
    """Sanitized evidence export: statuses, provenance and current (never ended) evidence values with their IDs."""
    locs = []
    for lid, e in snap["locations"].items():
        fx, s = fixture(snap, lid, now)
        p = dict(fx["provenance"])
        p["pavement_periods"] = [] if s["pavement_reason"] else _current(e["xweather"], now, ("pavement_temperature", "road_surface_condition"))
        p["air_periods"] = [] if s["air_reason"] else _current(e["nws"], now, ("air_temperature", "precipitation_probability", "weather_type"))
        locs.append(p)
    return sanitize({"schema": "saltwise.evidence_snapshot_export.v1", "data_mode": "provider_snapshot", "generated_at_utc": iso(now),
                     "store_status": snap["store_status"], "registry_generated_utc": snap.get("registry_generated_utc"),
                     "freshness": FRESHNESS_NOTE, "treatment_decision": None,
                     "note": "Provider forecasts and provider-modeled pavement values, not sensor observations. Review rules are "
                             "illustrative; people make every treatment decision.",
                     "attribution": [XW_ATTRIBUTION, NWS_ATTRIBUTION], "locations": locs})


def evidence_index(xw, nw):
    """Stored evidence IDs by (variable, valid_from) plus structured-weather intervals, for traceable review items.
    Only sources actually used in the view are indexed, so withheld evidence is never cited."""
    by, weather = {}, []
    for snapx in (xw, nw):
        for e in (snapx or {}).get("evidence", []):
            if e["variable"] == "weather_type":
                weather.append((e["valid_from_utc"], e["valid_to_utc"], e["id"]))
            else:
                by[(e["variable"], e["valid_from_utc"])] = e["id"]
    return {"by_start": by, "weather": weather}
