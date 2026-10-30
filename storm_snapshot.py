"""Explicit evidence snapshot for Storm Lab: chosen by a person, recorded with an identifier, never refreshed silently.

The record keeps imported provider evidence apart from Storm Lab's editable assumptions (rates, lane-miles and
application times). Lane-miles and route lengths are never inferred from demonstration points. Reading sends no
weather request.
"""
import hashlib
import json
from datetime import timedelta

import evidence_snapshot as es
import freshness
import saltwise_contract as sc


def _ceil_hour(t):
    f = t.replace(minute=0, second=0, microsecond=0)
    return f if f == t else f + timedelta(hours=1)


def _part(x, reason):
    if not x.get("provider"):
        return {"used": False, "snapshot_sha256": None, "retrieved_utc": None, "issue_time": None, "coverage_utc": None,
                "withheld_reason": reason or "no snapshot stored"}
    return {"used": bool(x.get("used_in_view")), "snapshot_sha256": x.get("snapshot_sha256"), "retrieved_utc": x.get("retrieved_utc"),
            "issue_time": x.get("issue_time"), "coverage_utc": x.get("returned_coverage_utc"), "withheld_reason": x.get("withheld_reason")}


def select(now=None):
    """Record the trusted service's saved snapshots as they are now. Returns (record, snapshot data)."""
    now = (now or es.now_utc()).replace(second=0, microsecond=0)
    snap = es.read_all()
    locs = []
    for lid, e in snap["locations"].items():
        fx, s = es.fixture(snap, lid, now)
        p = fx["provenance"]
        unresolved = [r for r in (s["pavement_reason"], s["air_reason"]) if r]
        if s["bridge"] == "unconfirmed":
            unresolved.append("Bridge-specific modeling unconfirmed.")
        if p["pavement"].get("used_in_view") and not p["pavement"].get("issued_utc"):
            unresolved.append("Xweather issue time not supplied.")
        locs.append({"location_id": lid, "name": e["registry"]["name"], "statuses": {k: v["status"] for k, v in p["statuses"].items()},
                     "pavement": _part(p["pavement"], s["pavement_reason"]), "air": _part(p["air"], s["air_reason"]),
                     "unresolved": list(dict.fromkeys(unresolved + p["open_questions"]))})
    basis = json.dumps([[l["location_id"], l["pavement"]["snapshot_sha256"], l["air"]["snapshot_sha256"]] for l in locs] + [es.iso(now)])
    rec = {"snapshot_id": "snap-" + hashlib.sha256(basis.encode()).hexdigest()[:12], "selected_at_utc": es.iso(now),
           "window_start_utc": es.iso(_ceil_hour(now)), "store_status": snap["store_status"], "locations": locs,
           "freshness": es.FRESHNESS_NOTE,
           "note": "Imported provider evidence (read-only). It never changes rates, lane-miles or application times."}
    return rec, snap


def views(rec, snap, units, hours, start=None):
    """Provider views of the recorded snapshot, evaluated at its window start (the next whole hour after selection)."""
    at = es._dt(rec["window_start_utc"])
    out = {}
    for lid in snap["locations"]:
        fx, _ = es.fixture(snap, lid, at)
        out[lid] = sc.build_view(fx, {"units": units, "mode": "live", "source_mode": "provider", "evaluation_time": fx["evaluation_time"],
                                      "window_hours": hours, "freshness_limits": freshness.contract_limits() or es.FRESHNESS_PENDING})
    return out


def coverage_vs_window(rec, window):
    """Supported and unsupported hours of the accounting window per location and source (returned coverage only)."""
    w0, w1 = sc.dt(window["start"]), sc.dt(window["end"])
    total = (w1 - w0).total_seconds() / 3600
    rows = []
    for l in rec["locations"]:
        row = {"location_id": l["location_id"], "name": l["name"]}
        for k in ("pavement", "air"):
            x, cov = l[k], l[k].get("coverage_utc") or {}
            if not x["used"] or not cov.get("to"):
                row[k] = {"supported_h": 0.0, "unsupported_h": round(total, 2), "unsupported_from": es.iso(w0),
                          "reason": x.get("withheld_reason") or "no supported values"}
                continue
            a, b = max(w0, es._dt(cov["from"])), min(w1, es._dt(cov["to"]))
            sup = max(0.0, (b - a).total_seconds() / 3600)
            gap = round(total - sup, 2)
            row[k] = {"supported_h": round(sup, 2), "unsupported_h": gap,
                      "unsupported_from": None if gap <= 0 else (es.iso(max(w0, b)) if sup > 0 else es.iso(w0)),
                      "reason": "beyond the returned forecast coverage (never extended)" if gap > 0 else None}
        rows.append(row)
    return rows


def rows(rec):
    selected = es._dt(rec["selected_at_utc"])

    def cell(x):
        if not x["used"]:
            return x.get("withheld_reason") or "Not used"
        end = (x.get("coverage_utc") or {}).get("to")
        to = (end or "?")[:16].replace("T", " ")
        text = f"Retrieved {x['retrieved_utc'][:16].replace('T', ' ')} UTC · issue time {x['issue_time']} · covers until {to} UTC"
        if end and es._dt(end) <= selected:          # every returned period ended before this snapshot was selected
            text += " · historical: ended before this snapshot, so no usable coverage for a current window"
        return text

    def sentence(t):
        # One sentence per item, ending in exactly one terminal mark (no ".;" or "..").
        t = str(t).strip()
        core = t.rstrip(" .;,:!?")
        if not core:
            return ""
        tail = t[len(core):]
        return core + ("?" if "?" in tail else "!" if "!" in tail else ".")
    out = []
    for l in rec["locations"]:
        s = l["statuses"]
        out.append({"Location": l["name"],
                    "Location statuses": (f"Geographic: {s['geographic_verification']} · Road match: {s['provider_road_matching']} · "
                                          f"Bridge modeling: {s['bridge_specific_modeling']}").replace("_", " "),
                    "Pavement (Xweather modeled)": cell(l["pavement"]), "Air (NWS forecast)": cell(l["air"]),
                    "Unresolved": " ".join(filter(None, map(sentence, l["unresolved"]))) or "—"})
    return out
