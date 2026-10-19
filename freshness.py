"""Versioned freshness-policy evaluation. No policy is active until the user approves one.

Keeps three things apart: provider issue age (only when the provider supplies an issue time), retrieval age (a lower
bound on forecast age, never proof that a forecast is recent) and valid-time coverage. Evaluation never changes saved
timestamps and never re-admits periods whose valid time has ended: those are withheld under every policy, and a
policy can only add restrictions.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # demo build: every path stays inside this package
NOT_ASSESSED = "not_assessed"
RANK = {"within_policy": 0, "unconfirmed": 1, "warn": 2, "exceeds_withhold": 3}
PROPOSAL = {
    "policy_id": "saltwise-freshness", "version": "proposal-2026-10-15.1", "approved": False,
    "status": "PROPOSED - not approved and not active; evaluated only as a labeled preview",
    "sources": {
        "nws_air": {"issue_age_warn_h": 2, "issue_age_withhold_h": 6, "retrieval_age_warn_h": None, "retrieval_age_withhold_h": None},
        "xweather_pavement": {"issue_age_warn_h": None, "issue_age_withhold_h": None, "retrieval_age_warn_h": 3, "retrieval_age_withhold_h": 6},
    },
    "issue_time_missing": ("Status 'unconfirmed': the evidence stays visible with that label and is never described as fresh. "
                           "Retrieval age is used only as a lower bound on forecast age: it can show that evidence is old, never that it is new."),
    "coverage": "Valid-time coverage is reported separately (hours remaining and the unsupported part of the selected window); it is not an age.",
    "always": "Periods whose valid time has ended are withheld under every policy; a policy can only add restrictions.",
    "basis": ("AUTOMATION_PLAN.md section 3 proposal: NWS warn 2 h / withhold 6 h after updateTime; Xweather warn 3 h / withhold 6 h "
              "after retrieval (provider update interval 6 h; no issue time supplied)."),
}


def _dt(s):
    return s if isinstance(s, datetime) else datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def active_policy(config_path=None):
    """The approved policy, or None. Built only from run_config.json data_policy.freshness_limits (all null today)."""
    try:
        lim = json.loads(Path(config_path or ROOT / "run_config.json").read_text())["data_policy"]["freshness_limits"]
    except (OSError, ValueError, KeyError):
        return None
    nws, xw = lim.get("nws_air_forecast_max_age_hours"), lim.get("xweather_pavement_max_age_hours")
    if nws is None and xw is None:
        return None
    return {"policy_id": "saltwise-freshness", "version": "run_config", "approved": True, "status": "approved in run_config.json",
            "sources": {"nws_air": {"issue_age_warn_h": None, "issue_age_withhold_h": nws, "retrieval_age_warn_h": None, "retrieval_age_withhold_h": None},
                        "xweather_pavement": {"issue_age_warn_h": None, "issue_age_withhold_h": None, "retrieval_age_warn_h": None,
                                              "retrieval_age_withhold_h": xw}}}


def evaluate(policy, source, issued_utc, retrieved_utc, coverage_to_utc, now, window_end=None):
    """Freshness of one evidence source at `now` under `policy` (None = no approved policy). Pure; inputs untouched."""
    now = _dt(now)

    def age(x):
        return None if not x else round((now - _dt(x)).total_seconds() / 3600, 2)
    out = {"source": source, "policy": None if policy is None else f"{policy['policy_id']}@{policy['version']}",
           "policy_active": bool(policy and policy.get("approved")), "issue_time": issued_utc, "issue_age_h": age(issued_utc),
           "retrieval_age_h": age(retrieved_utc), "retrieval_age_note": "a lower bound on forecast age, not proof of it",
           "coverage_to": coverage_to_utc,
           "coverage_remaining_h": None if not coverage_to_utc else max(0.0, round((_dt(coverage_to_utc) - now).total_seconds() / 3600, 2)),
           "window_unsupported_h": None, "effect": "none (evaluation only; ended periods are withheld regardless)"}
    if window_end is not None:
        end = _dt(coverage_to_utc) if coverage_to_utc else now
        out["window_unsupported_h"] = max(0.0, round((_dt(window_end) - max(end, now)).total_seconds() / 3600, 2))
    if policy is None:
        out.update(status=NOT_ASSESSED, confirmed_fresh=False, reasons=["No approved freshness policy: ages are shown, not judged."])
        return out
    rule, status, reasons = policy["sources"].get(source) or {}, "within_policy", []

    def raise_to(s, why):
        nonlocal status
        reasons.append(why)
        if RANK[s] > RANK[status]:
            status = s
    ia, ra = out["issue_age_h"], out["retrieval_age_h"]
    if ia is None:
        raise_to("unconfirmed", "Provider issue time not supplied: freshness cannot be confirmed.")
    elif rule.get("issue_age_withhold_h") is not None and ia >= rule["issue_age_withhold_h"]:
        raise_to("exceeds_withhold", f"Issued {ia:g} h ago (limit {rule['issue_age_withhold_h']} h).")
    elif rule.get("issue_age_warn_h") is not None and ia >= rule["issue_age_warn_h"]:
        raise_to("warn", f"Issued {ia:g} h ago (warning at {rule['issue_age_warn_h']} h).")
    if ra is not None and rule.get("retrieval_age_withhold_h") is not None and ra >= rule["retrieval_age_withhold_h"]:
        raise_to("exceeds_withhold", f"Retrieved {ra:g} h ago, so the forecast is at least that old (limit {rule['retrieval_age_withhold_h']} h).")
    elif ra is not None and rule.get("retrieval_age_warn_h") is not None and ra >= rule["retrieval_age_warn_h"]:
        raise_to("warn", f"Retrieved {ra:g} h ago, so the forecast is at least that old (warning at {rule['retrieval_age_warn_h']} h).")
    out.update(status=status, confirmed_fresh=status == "within_policy" and ia is not None, reasons=reasons,
               effect="would withhold this source" if status == "exceeds_withhold" and out["policy_active"] else out["effect"])
    return out
