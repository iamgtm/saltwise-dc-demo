"""DC Storm Outlook: NWS api.weather.gov atmospheric forecast for one reference point, plus active DC alerts.

Provider forecast only (evidence kind "provider_forecast"). It is not a pavement forecast and it is not assigned to the
demonstration roads, whose coordinates are unverified. Requests are made only when a person presses Load or Refresh:
no polling, no retries. Every attempt, including failures, is logged and counted against the weather-request caps
before it is sent. Freshness limits are unresolved, so ages are shown, never judged.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REF_POINT = (38.8945, -77.0426)
REF_LABEL = "Washington, DC reference-point forecast"
REF_NOTE = ("NWS forecasts cover a grid area around this one reference point (38.8945, -77.0426). This is not citywide "
            "coverage and is not assigned to the five demonstration roads, whose coordinates are not yet validated.")
USER_AGENT = "SaltWiseDC/0.1 (student research prototype)"
API = "https://api.weather.gov"
POINTS_URL = f"{API}/points/{REF_POINT[0]},{REF_POINT[1]}"
ALERTS_URL = f"{API}/alerts/active?area=DC"
OUTLOOK_HOURS = 72
SOURCE = "NWS api.weather.gov"
KIND = "provider_forecast"
TIMEOUT_S = 15

import demo_config  # noqa: E402  (live weather requests disabled in the demo build)
ROOT = Path(__file__).resolve().parent          # demo build: every path stays inside this package
DEFAULT_LOG = ROOT / "logs" / "weather_requests.jsonl"


def _caps():
    try:
        w = json.loads((ROOT / "run_config.json").read_text())["caps"]["weather_requests"]
        return {"per_run": int(w["all_providers_max_per_run"]), "per_day": int(w["all_providers_max_per_day"])}
    except (OSError, ValueError, KeyError):
        return {"per_run": 20, "per_day": 100}


CAPS = _caps()

# Precipitation words matched only when NWS text states them explicitly. Order matters: freezing rain before rain.
PRECIP = [("freezing rain", r"freezing rain"), ("freezing drizzle", r"freezing drizzle"), ("sleet", r"sleet"),
          ("snow", r"snow"), ("rain", r"(?<!freezing )rain")]


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(s):
    try:
        t = datetime.fromisoformat(s)
        return t if t.tzinfo else None
    except (TypeError, ValueError):
        return None


class RequestBudget:
    """Counts NWS attempts in a JSONL log (shared with the evaluator's --weather-log check) and refuses past the caps."""

    def __init__(self, log_path=None, run_id=None, caps=CAPS):
        self.path = Path(log_path or os.environ.get("SALTWISE_WEATHER_LOG") or DEFAULT_LOG)
        self.run_id = run_id or os.environ.get("SALTWISE_RUN_ID") or f"app-{os.getpid()}"
        self.caps = caps

    def _rows(self):
        try:
            return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]
        except (OSError, ValueError):
            return []

    def counts(self, at=None):
        today = (at or now_utc()).astimezone(ET).date().isoformat()
        rows = self._rows()
        return {"run": sum(1 for r in rows if r.get("run_id") == self.run_id),
                "day": sum(1 for r in rows if r.get("day_et") == today)}

    def reserve(self, url, at=None):
        """Record the attempt before sending it. Returns None if allowed, or the reason it was refused."""
        c = self.counts(at)
        if c["run"] >= self.caps["per_run"]:
            return f"weather-request cap reached for this run ({self.caps['per_run']}); no request sent"
        if c["day"] >= self.caps["per_day"]:
            return f"daily weather-request cap reached ({self.caps['per_day']}, America/New_York day); no request sent"
        t = at or now_utc()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": t.isoformat(), "day_et": t.astimezone(ET).date().isoformat(), "provider": "nws",
                                "run_id": self.run_id, "url": url}) + "\n")
        return None


class HttpCache:
    """Per-URL cache. Within Cache-Control max-age the stored response is reused without a request; after that the
    request carries If-None-Match / If-Modified-Since so an unchanged response comes back as 304 and is reused."""

    def __init__(self):
        self.entries = {}

    def fresh(self, url, at):
        e = self.entries.get(url)
        return e if e and e["expires_at"] and at < e["expires_at"] else None


def _max_age(headers):
    m = re.search(r"max-age=(\d+)", headers.get("Cache-Control", "") or "")
    return int(m.group(1)) if m else 0


def fetch_json(url, budget, cache, get=None, at=None):
    """One attempt at most, no retries. Returns {'ok', 'data', 'retrieved_at', 'cache', 'error'}."""
    if not demo_config.LIVE_WEATHER_REQUESTS:            # demo build: refuse before any cache, log or network access
        return {"ok": False, "data": None, "retrieved_at": None, "cache": None, "error": "live weather requests are disabled in this demo build"}
    at = at or now_utc()
    e = cache.fresh(url, at)
    if e:
        return {"ok": True, "data": e["data"], "retrieved_at": e["retrieved_at"], "cache": "reused (within max-age; no request)",
                "error": None}
    refused = budget.reserve(url, at)
    if refused:
        return {"ok": False, "data": None, "retrieved_at": None, "cache": None, "error": refused}
    if get is None:
        import requests
        get = requests.get
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    old = cache.entries.get(url)
    if old and old.get("etag"):
        headers["If-None-Match"] = old["etag"]
    if old and old.get("last_modified"):
        headers["If-Modified-Since"] = old["last_modified"]
    try:
        r = get(url, headers=headers, timeout=TIMEOUT_S)
    except Exception as ex:                                          # network errors: report, never substitute
        return {"ok": False, "data": None, "retrieved_at": None, "cache": None,
                "error": f"request failed ({type(ex).__name__})"}
    h = dict(r.headers or {})
    if r.status_code == 304 and old:
        old["expires_at"] = at + timedelta(seconds=_max_age(h))
        return {"ok": True, "data": old["data"], "retrieved_at": old["retrieved_at"],
                "cache": f"revalidated at {at.isoformat(timespec='seconds')} (304 not modified; same response as before)",
                "error": None}
    if r.status_code != 200:
        return {"ok": False, "data": None, "retrieved_at": None, "cache": None, "error": f"NWS returned HTTP {r.status_code}"}
    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "data": None, "retrieved_at": None, "cache": None, "error": "NWS response was not valid JSON"}
    cache.entries[url] = {"data": data, "retrieved_at": at, "etag": h.get("ETag"), "last_modified": h.get("Last-Modified"),
                          "expires_at": at + timedelta(seconds=_max_age(h))}
    return {"ok": True, "data": data, "retrieved_at": at, "cache": "new response", "error": None}


def precip_types(text):
    t = (text or "").lower()
    return [name for name, pat in PRECIP if re.search(pat, t)]


def parse_hourly(data, now, hours=OUTLOOK_HOURS):
    """Keep current and future periods inside the next `hours`; withhold past or invalid ones with a reason."""
    props = (data or {}).get("properties") or {}
    kept, withheld = [], []
    horizon = now + timedelta(hours=hours)
    for p in props.get("periods") or []:
        s, e = parse_time(p.get("startTime")), parse_time(p.get("endTime"))
        if not s or not e or e <= s:
            withheld.append({"start": p.get("startTime"), "reason": "invalid or missing valid time"})
            continue
        if e <= now:
            withheld.append({"start": p.get("startTime"), "reason": "valid period already ended"})
            continue
        if s >= horizon:
            continue                                                  # beyond the 72 h outlook; not shown
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        temp = p.get("temperature")
        kept.append({"start": s.isoformat(), "end": e.isoformat(), "current": s <= now < e,
                     "air_temperature": temp if isinstance(temp, (int, float)) else None,
                     "air_temperature_unit": p.get("temperatureUnit"),
                     "precip_probability_pct": pop if isinstance(pop, (int, float)) else None,
                     "wind_speed": p.get("windSpeed") or None, "wind_direction": p.get("windDirection") or None,
                     "short_forecast": p.get("shortForecast") or None,
                     "precip_types": precip_types(p.get("shortForecast"))})
    kept.sort(key=lambda r: r["start"])
    covered = 0.0
    if kept:
        covered = (min(parse_time(kept[-1]["end"]), horizon) - max(parse_time(kept[0]["start"]), now)).total_seconds() / 3600
    return {"periods": kept, "withheld": withheld, "coverage_hours": round(max(covered, 0), 1),
            "generated_at": props.get("generatedAt"), "update_time": props.get("updateTime"),
            "valid_times": props.get("validTimes"), "units": props.get("units")}


def parse_alerts(data, now):
    """Official alerts, kept verbatim. Alerts whose end/expiry has passed are withheld with a reason."""
    kept, withheld = [], []
    for f in (data or {}).get("features") or []:
        p = f.get("properties") or {}
        end = parse_time(p.get("ends")) or parse_time(p.get("expires"))
        rec = {"event": p.get("event"), "headline": p.get("headline"), "severity": p.get("severity"),
               "sent": p.get("sent"), "effective": p.get("effective"), "onset": p.get("onset"), "ends": p.get("ends"),
               "expires": p.get("expires"), "sender": p.get("senderName"), "area": p.get("areaDesc"),
               "link": p.get("@id") or f.get("id")}
        if end and end <= now:
            withheld.append({**rec, "reason": "alert end or expiry time has passed"})
        else:
            kept.append(rec)
    return {"alerts": kept, "withheld": withheld, "updated": (data or {}).get("updated")}


def load_outlook(budget, cache, get=None, at=None):
    """points -> forecastHourly, plus DC alerts. Failures are reported per part; nothing is simulated in their place."""
    at = at or now_utc()
    out = {"label": REF_LABEL, "note": REF_NOTE, "point": list(REF_POINT), "source": SOURCE, "kind": KIND,
           "loaded_at": at.isoformat(), "hourly": None, "hourly_error": None, "hourly_meta": {},
           "alerts": None, "alerts_error": None, "alerts_meta": {}, "grid": None}
    pts = fetch_json(POINTS_URL, budget, cache, get, at)
    hourly_url = None
    if pts["ok"]:
        pp = pts["data"].get("properties") or {}
        hourly_url = pp.get("forecastHourly")
        out["grid"] = {"office": pp.get("gridId"), "x": pp.get("gridX"), "y": pp.get("gridY")}
        if not hourly_url:
            out["hourly_error"] = "NWS /points response did not include an hourly forecast link"
    else:
        out["hourly_error"] = f"Could not resolve the forecast grid: {pts['error']}"
    if hourly_url:
        hr = fetch_json(hourly_url, budget, cache, get, at)
        if hr["ok"]:
            out["hourly"] = parse_hourly(hr["data"], at)
            out["hourly_meta"] = {"retrieved_at": hr["retrieved_at"].isoformat(), "cache": hr["cache"], "url": hourly_url}
        else:
            out["hourly_error"] = hr["error"]
    al = fetch_json(ALERTS_URL, budget, cache, get, at)
    if al["ok"]:
        out["alerts"] = parse_alerts(al["data"], at)
        out["alerts_meta"] = {"retrieved_at": al["retrieved_at"].isoformat(), "cache": al["cache"], "url": ALERTS_URL}
    else:
        out["alerts_error"] = al["error"]
    return out


def window_context(outlook, start_iso, end_iso):
    """Read-only summary of the selected forecast window, for Storm Lab. Only values NWS supplied; nothing derived
    beyond ranges, counts and the provider's own precipitation words."""
    rows = [p for p in (outlook.get("hourly") or {}).get("periods", []) if start_iso <= p["start"] < end_iso]
    temps = [p["air_temperature"] for p in rows if p["air_temperature"] is not None]
    pops = [p["precip_probability_pct"] for p in rows if p["precip_probability_pct"] is not None]
    types = {}
    for p in rows:
        for t in p["precip_types"]:
            types.setdefault(t, []).append(p["start"])
    return {"label": outlook["label"], "source": outlook["source"], "kind": outlook["kind"], "point": outlook["point"],
            "window": {"start": start_iso, "end": end_iso}, "n_periods": len(rows),
            "air_temperature_range": [min(temps), max(temps)] if temps else None,
            "air_temperature_unit": rows[0]["air_temperature_unit"] if rows else None,
            "highest_precip_probability_pct": max(pops) if pops else None,
            "periods_missing_precip_probability": sum(1 for p in rows if p["precip_probability_pct"] is None),
            "precip_types_reported": {t: {"first": v[0], "last": v[-1], "n_periods": len(v)} for t, v in types.items()},
            "active_alerts": [a["event"] for a in ((outlook.get("alerts") or {}).get("alerts") or [])],
            "alerts_available": outlook.get("alerts") is not None,
            "issued": {"generated_at": (outlook.get("hourly") or {}).get("generated_at"),
                       "update_time": (outlook.get("hourly") or {}).get("update_time")},
            "retrieved_at": outlook.get("hourly_meta", {}).get("retrieved_at"),
            "note": "NWS atmospheric forecast for a grid area; read-only context. It does not change Storm Lab locations, "
                    "rates or application counts, is not a pavement forecast, and does not establish treatment "
                    "effectiveness, road safety or actual material reductions."}

