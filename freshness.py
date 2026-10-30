"""Shared freshness policy for every view: Road Weather, Storm Outlook, review briefings, Storm Lab snapshots and exports.

No policy is active until the user approves one in run_config.json data_policy.freshness_limits: an explicit user decision
with a real calendar date, bound to this policy version and a hash of its exact settings (validate_limits). Until then
ages are shown, not judged. Kept apart: provider issue time (NWS updateTime; Xweather supplies none), retrieval time, the
first time unchanged forecast content was seen, valid periods and coverage. Retrieval and first-seen ages are lower bounds
on forecast age, never proof that a forecast is recent.

Under every policy, periods whose valid time has ended are withheld, and a policy only adds restrictions. A limit of N
hours accepts exactly N hours. Beyond a hard limit, values are excluded from current views and review inputs (kept and
labelled in withheld records and exports). A timestamp without a UTC offset, an issue or retrieval time later than the
evaluation time beyond the clock tolerance, or an issue time later than the retrieval time is inconsistent: excluded from
current decision inputs with an explanation, with or without an approved policy. Future VALID times are normal and are
not checked here.
"""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = next((d for d in Path(__file__).resolve().parents if (d / "run_config.json").exists()), Path.cwd())
NOT_ASSESSED = "not_assessed"
VERSION = "proposal-2026-10-26.3"
CLOCK_TOLERANCE_MIN = 5          # ENGINEERING ASSUMPTION: clock skew allowed between this machine and the providers
RANK = {"within_policy": 0, "unconfirmed": 1, "warn": 2, "inconsistent": 3, "exceeds_withhold": 4}
OVER_LIMIT = "excluded from current views and review inputs; kept, labelled, in withheld details and exports"
PROPOSAL = {
    "policy_id": "saltwise-freshness", "version": VERSION, "approved": False,
    "status": "PROPOSED - not approved and not active; evaluated only as a labeled preview",
    "clock_tolerance_minutes": CLOCK_TOLERANCE_MIN,
    "sources": {
        "nws_air": {"issue_age_warn_h": 6, "issue_age_withhold_h": 12, "retrieval_age_warn_h": None, "retrieval_age_withhold_h": 12,
                    "over_limit": OVER_LIMIT},
        "xweather_pavement": {"issue_age_warn_h": None, "issue_age_withhold_h": None, "retrieval_age_warn_h": 2,
                              "retrieval_age_withhold_h": 6, "over_limit": OVER_LIMIT},
    },
    "age_from": {"nws_air": "NWS updateTime; retrieval or first-seen time only as a lower bound when updateTime is missing",
                 "xweather_pavement": "first time this forecast content was seen (else last retrieval): a lower bound; issue time unknown"},
    "issue_time_missing": ("Status 'unconfirmed': the evidence stays visible with that label and is never described as fresh. "
                           "Retrieval age is used only as a lower bound on forecast age: it can show that evidence is old, never that it is new."),
    "coverage": "Valid-time coverage is reported separately (hours remaining and the unsupported part of the selected window); it is not an age.",
    "always": "Periods whose valid time has ended are withheld under every policy; a policy can only add restrictions.",
    "timestamps": "Missing offset, later than the evaluation time beyond the clock tolerance, or issue after retrieval: 'inconsistent', excluded.",
    "basis": ("proposals/freshness_policy_v2/POLICY.md. Pilot assumptions for user review, not provider or agency limits. NWS documents "
              "no maximum age or update cadence; age runs from NWS updateTime, never generatedAt or retrieval. Xweather documents a 6 h "
              "update interval (15 min for the first 2 h) and supplies no issue time, so its age is only a lower bound."),
}
SETTING_KEYS = ("policy_version", "units", "nws_air_forecast_warn_age_hours", "nws_air_forecast_max_age_hours",
                "xweather_pavement_warn_age_hours", "xweather_pavement_max_age_hours", "rwis_observation_max_age_minutes",
                "clock_tolerance_minutes")
LIMIT_KEYS = ("nws_air_forecast_max_age_hours", "xweather_pavement_max_age_hours", "rwis_observation_max_age_minutes")
CAPS_H = {"nws_air_forecast": 72, "xweather_pavement": 24}      # NWS display window; Xweather documented horizon
CONTENT_FIELDS = ("variable", "valid_from_utc", "valid_to_utc", "value", "unit")
CONTENT_NOTE = ("Content first seen = the earliest retrieval in an unbroken run of stored responses in which every forecast value "
                "(variable, valid period, value) of the latest response already appeared unchanged. Re-fetching unchanged content "
                "never resets that age. Identical content shows only that the forecast did not change between checks: it does not "
                "prove a sensor or provider failure and does not reveal an issue time. Changed content does not verify an issue time either.")
_CONTRACT = {"inconsistent": ("unknown", True, "inconsistent_timestamps"), "exceeds_withhold": ("stale", True, "over_hard_limit"),
             "warn": ("current", False, "warning"), "unconfirmed": ("current", False, "issue_time_unknown"),
             "within_policy": ("current", False, "within_policy"), NOT_ASSESSED: ("unknown", False, "not_assessed")}


def _dt(s):
    """UTC datetime, or None when the timestamp has no UTC offset (never guessed from the machine's local zone)."""
    d = s if isinstance(s, datetime) else datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return None if d.tzinfo is None else d.astimezone(timezone.utc)


def settings_sha256(lim):
    """Hash of the exact settings an approval covers: version, units, every limit and the clock tolerance."""
    return hashlib.sha256(json.dumps({k: lim.get(k) for k in SETTING_KEYS}, sort_keys=True).encode()).hexdigest()


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _calendar_date(s):
    try:
        return isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None and bool(date.fromisoformat(s))
    except ValueError:
        return False


def validate_limits(lim):
    """Problems that keep run_config.json limits inert; an empty list means a valid, explicitly approved policy."""
    p = []
    if lim.get("policy_version") != VERSION:
        p.append(f"policy_version must be {VERSION}")
    if lim.get("units") != "hours":
        p.append("units must be 'hours' (keys ending in _minutes are minutes)")
    for src, cap in CAPS_H.items():
        w, m = lim.get(f"{src}_warn_age_hours"), lim.get(f"{src}_max_age_hours")
        if not (_num(m) and 0 < m <= cap):
            p.append(f"{src}_max_age_hours must be a number above 0 and at most {cap}")
        elif not (_num(w) and 0 < w < m):
            p.append(f"{src}_warn_age_hours must be a number above 0 and below {src}_max_age_hours")
    if lim.get("rwis_observation_max_age_minutes") is not None:
        p.append("rwis_observation_max_age_minutes must stay null: RWIS is not integrated")
    t = lim.get("clock_tolerance_minutes")
    if not (_num(t) and 0 <= t <= 15):
        p.append("clock_tolerance_minutes must be a number from 0 to 15")
    d = lim.get("user_decision") or {}
    if d.get("approved") is not True or d.get("decided_by") != "user":
        p.append("no explicit user approval (user_decision.approved true and decided_by user)")
    if not _calendar_date(d.get("date")):
        p.append("user_decision.date must be a real calendar date (YYYY-MM-DD)")
    if d.get("policy_version") != lim.get("policy_version"):
        p.append("user_decision.policy_version does not match policy_version")
    if d.get("settings_sha256") != settings_sha256(lim):
        p.append("user_decision.settings_sha256 does not match these exact settings")
    return p


def _config(config_path=None):
    try:
        return json.loads(Path(config_path or ROOT / "run_config.json").read_text())["data_policy"]["freshness_limits"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _identity(lim):
    """Policy identity from a validated run_config.json decision (version and approval date are read, never assumed)."""
    version, day = lim["policy_version"], lim["user_decision"]["date"]
    return {"_status": f"APPROVED by the user on {day} ({version})", "_policy_version": version, "_approved_date": day}


def approved_policy(config_path=None):
    """The approved policy from run_config.json, or None (no limits set, or the decision does not validate)."""
    lim = _config(config_path)
    if not lim or all(lim.get(k) is None for k in LIMIT_KEYS) or validate_limits(lim):
        return None
    return policy_from_limits({**lim, **_identity(lim)})


active_policy = approved_policy          # earlier name, still used by review_items and tests


def contract_limits(config_path=None):
    """Limits for the evidence contract from an approved run_config.json policy, or None (no age limit applied)."""
    if approved_policy(config_path) is None:
        return None
    lim = _config(config_path)
    return {**_identity(lim), **{k: lim.get(k) for k in SETTING_KEYS if k not in ("policy_version", "units")}}


def policy_from_limits(lim, version=None):
    """Policy from contract-style limits (approved run_config values or fixture-only test settings), or None. Limits from
    contract_limits carry the approved identity and are labelled with it; fixture-only settings keep the 'settings' label."""
    if not lim:
        return None
    nws, xw = lim.get("nws_air_forecast_max_age_hours"), lim.get("xweather_pavement_max_age_hours")
    if nws is None and xw is None:
        return None
    pv, day = lim.get("_policy_version"), lim.get("_approved_date")
    version = version or (f"{pv} (approved {day})" if pv and day else "settings")
    return {"policy_id": "saltwise-freshness", "version": version, "approved": True, "status": lim.get("_status") or "settings",
            "approved_policy_version": pv, "approved_date": day,
            "clock_tolerance_minutes": lim.get("clock_tolerance_minutes", CLOCK_TOLERANCE_MIN),
            "sources": {"nws_air": {"issue_age_warn_h": lim.get("nws_air_forecast_warn_age_hours"), "issue_age_withhold_h": nws,
                                    "retrieval_age_warn_h": None, "retrieval_age_withhold_h": nws, "over_limit": OVER_LIMIT},
                        "xweather_pavement": {"issue_age_warn_h": None, "issue_age_withhold_h": None,
                                              "retrieval_age_warn_h": lim.get("xweather_pavement_warn_age_hours"),
                                              "retrieval_age_withhold_h": xw, "over_limit": OVER_LIMIT}}}


def content_first_seen(history):
    """history: [(retrieved_utc, records)], newest first. When the newest forecast content was first seen (CONTENT_NOTE)."""
    if not history:
        return None
    key = lambda recs: frozenset(json.dumps({k: r.get(k) for k in CONTENT_FIELDS}, sort_keys=True) for r in recs or [])  # noqa: E731
    first, newest = history[0][0], key(history[0][1])
    for retrieved, records in history[1:]:
        if not newest or not newest <= key(records):
            break
        first = retrieved
    return first


# Missing versus invalid timestamps. A missing provider issue time alone leaves evidence usable but unconfirmed; a missing
# retrieval time never yields confirmed freshness; with no usable issue, retrieval or first-seen time the age cannot be bounded,
# so the values are excluded as unresolved. Malformed or offset-free timestamps are inconsistent (excluded) as before.
RANK.update(retrieval_unknown=RANK["unconfirmed"], age_unknown=RANK["inconsistent"])
_CONTRACT.update(retrieval_unknown=("current", False, "retrieval_time_unknown"), age_unknown=("unknown", True, "age_unknown"))


def evaluate(policy, source, issued_utc, retrieved_utc, coverage_to_utc, now, window_end=None, first_seen_utc=None,
             provider_record=True):
    """Freshness of one evidence source at `now` (policy None = no approved policy). Pure; inputs untouched.
    provider_record False (synthetic scenarios and test fixtures) skips the two missing-time rules, which apply to saved
    provider records only; a missing retrieval time never yields confirmed freshness either way."""
    now, problems, skew = _dt(now), [], []
    tol_min = (policy or {}).get("clock_tolerance_minutes", CLOCK_TOLERANCE_MIN)
    tol = tol_min / 60

    def age(x, what):
        if not x:
            return None
        try:
            d = _dt(x)
        except ValueError:
            problems.append(f"{what} {x} is not a valid timestamp")
            return None
        if d is None:
            problems.append(f"{what} {x} has no UTC offset")
            return None
        a = round((now - d).total_seconds() / 3600, 2)
        if a < -tol:
            problems.append(f"{what} {x} is later than the evaluation time")
            return None
        if a < 0:
            skew.append({"timestamp": what, "ahead_minutes": round(-a * 60, 1)})
        return max(a, 0.0)
    ia, ra, fa = age(issued_utc, "issue time"), age(retrieved_utc, "retrieval time"), age(first_seen_utc, "first-seen time")
    if ia is not None and ra is not None and ia < ra - tol:
        problems.append(f"issue time {issued_utc} is later than retrieval time {retrieved_utc}")
        ia = None
    if fa is not None and ra is not None and fa < ra - tol:
        problems.append(f"first-seen time {first_seen_utc} is later than retrieval time {retrieved_utc}")
        fa = None
    known = [x for x in (fa, ra) if x is not None]
    ca = max(known) if known else None                         # content age: a lower bound on forecast age
    cov = None
    try:
        cov = _dt(coverage_to_utc) if coverage_to_utc else None
    except ValueError:
        cov = None
    parts = [f"issued {issued_utc}" + (f" ({ia:g} h ago)" if ia is not None else "") if issued_utc else "issue time not supplied by the provider"]
    if first_seen_utc and first_seen_utc != retrieved_utc:
        parts.append(f"unchanged content first seen {first_seen_utc}" + (f" ({fa:g} h ago)" if fa is not None else ""))
    if retrieved_utc:
        parts.append(f"last retrieved {retrieved_utc}" + (f" ({ra:g} h ago)" if ra is not None else ""))
    if not issued_utc and known:
        parts.append("retrieval and first-seen ages are lower bounds on forecast age")
    if skew:
        parts.append("tolerated clock skew: " + ", ".join(f"{s['timestamp']} {s['ahead_minutes']:g} min ahead" for s in skew))
    out = {"source": source, "policy": None if policy is None else f"{policy['policy_id']}@{policy['version']}",
           "policy_active": bool(policy and policy.get("approved")),
           "approved_policy_version": (policy or {}).get("approved_policy_version"),
           "policy_approved_date": (policy or {}).get("approved_date"), "issue_time": issued_utc, "issue_age_h": ia,
           "retrieved_utc": retrieved_utc, "retrieval_age_h": ra, "first_seen_utc": first_seen_utc, "content_age_h": ca,
           "retrieval_age_note": "a lower bound on forecast age, not proof of it", "age_note": "; ".join(parts),
           "coverage_to": coverage_to_utc,
           "coverage_remaining_h": None if cov is None else max(0.0, round((cov - now).total_seconds() / 3600, 2)),
           "window_unsupported_h": None, "timestamp_problems": problems, "tolerated_skew": skew,
           "clock_tolerance_minutes": tol_min, "clock_tolerance_basis": "engineering assumption, not a provider value",
           "effect": "none (evaluation only; ended periods are withheld regardless)"}
    if window_end is not None:
        end = cov or now
        out["window_unsupported_h"] = max(0.0, round((_dt(window_end) - max(end, now)).total_seconds() / 3600, 2))
    if policy is None:
        why = ("Inconsistent timestamps (" + "; ".join(problems) + "): excluded from current decision inputs.") if problems \
            else "No approved freshness policy: ages are shown, not judged."
        out.update(status="inconsistent" if problems else NOT_ASSESSED, confirmed_fresh=False, reasons=[why])
        return _contract(out)
    rule, status, reasons = policy["sources"].get(source) or {}, "within_policy", []

    def raise_to(s, why):
        nonlocal status
        reasons.append(why)
        if RANK[s] > RANK[status]:
            status = s
    if problems:
        raise_to("inconsistent", "Inconsistent timestamps (" + "; ".join(problems) + "): freshness cannot be confirmed.")
    if ia is None and not issued_utc:
        raise_to("unconfirmed", "Provider issue time not supplied: freshness cannot be confirmed.")
    elif ia is not None and rule.get("issue_age_withhold_h") is not None and ia > rule["issue_age_withhold_h"]:
        raise_to("exceeds_withhold", f"Issued {ia:g} h ago (hard limit {rule['issue_age_withhold_h']} h).")
    elif ia is not None and rule.get("issue_age_warn_h") is not None and ia > rule["issue_age_warn_h"]:
        raise_to("warn", f"Issued {ia:g} h ago (warning after {rule['issue_age_warn_h']} h).")
    if provider_record and not problems and ia is None and ca is None:
        raise_to("age_unknown", "No usable issue, retrieval or first-seen time: the age cannot be bounded, so the values are "
                                "excluded from current decision inputs.")
    elif provider_record and not problems and ra is None:
        raise_to("retrieval_unknown", "Retrieval time not recorded: freshness cannot be confirmed.")
    what = "First seen" if fa is not None and fa > (ra or 0) else "Retrieved"
    if ca is not None and rule.get("retrieval_age_withhold_h") is not None and ca > rule["retrieval_age_withhold_h"]:
        raise_to("exceeds_withhold", f"{what} {ca:g} h ago, so the forecast is at least that old (hard limit {rule['retrieval_age_withhold_h']} h).")
    elif ca is not None and rule.get("retrieval_age_warn_h") is not None and ca > rule["retrieval_age_warn_h"]:
        raise_to("warn", f"{what} {ca:g} h ago, so the forecast is at least that old (warning after {rule['retrieval_age_warn_h']} h).")
    over = status in ("exceeds_withhold", "inconsistent", "age_unknown") and out["policy_active"]
    out.update(status=status, confirmed_fresh=status == "within_policy" and ia is not None and ra is not None, reasons=reasons,
               effect=rule.get("over_limit", OVER_LIMIT) if over else out["effect"])
    return _contract(out)


def _contract(out):
    """Contract status (current|stale|expired|unknown only) plus separate exclusion and reason fields."""
    cs, ex, code = _CONTRACT[out["status"]]
    out.update(contract_status=cs, exclude=ex, reason_code=code, reason=" ".join(out["reasons"]))
    return out


def describe(a, label):
    """One plain sentence for any page: the same wording on Road Weather, Storm Outlook, briefings and exports."""
    if a is None:
        return f"{label}: freshness limits are not yet set, so ages are shown, not judged."
    code = a["reason_code"]
    if code == "not_assessed":
        return f"{label}: freshness not assessed (no approved freshness policy); ages are shown, not judged ({a['age_note']})."
    if code in ("inconsistent_timestamps", "over_hard_limit", "age_unknown"):
        return f"{label}: {a['reason']} Values are excluded from current views and review inputs ({a['age_note']})."
    if code == "warning":
        return (f"{label}: warning. {a['reasons'][-1]} Values remain visible"
                + ("" if a["confirmed_fresh"] else " and are not confirmed fresh") + f" ({a['age_note']}).")
    if code == "issue_time_unknown":
        return f"{label}: within the freshness limits but not confirmed fresh ({a['age_note']})."
    if code == "retrieval_time_unknown":
        return f"{label}: not confirmed fresh because the retrieval time was not recorded ({a['age_note']})."
    return f"{label}: within the freshness policy ({a['age_note']})."


UNCONFIRMED_PROMPT = ("Precautionary review prompt: it uses modeled pavement values whose provider issue time is unknown, so they are "
                      "not confirmed fresh. It is never a no-treatment or safe-road conclusion; a person decides.")
