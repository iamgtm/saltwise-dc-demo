"""First returned pavement forecast period at or below the freezing reference (a physical reference, not a policy).

Reads only the evidence view: pavement points of kind "modeled" with a value, in the displayed units. Simulated periods
and periods beyond the returned horizon are never used, and no crossing time is interpolated: the marker names the
period the provider (or the synthetic scenario) returned. It is a forecast reference, not a treatment instruction.
"""
import pandas as pd

NOTE = "Forecast reference, not a treatment instruction."


def find(view):
    """Status and period for the first pavement forecast period at or below the freezing reference.

    status: "reached" (an earlier period is above), "starts_at_or_below" (the first available period already is),
    "not_reached" (no returned period is), or "no_values" (no returned pavement values in this window).
    missing_before counts periods with no value before the marked period (all of them when none is marked).
    """
    ref = view["freezing_reference"]["value"]
    pts = sorted((p for s in view["series"] if s["quantity"] == "pavement_temperature" and s["kind"] == "modeled"
                  for p in s["points"] if p.get("kind", s["kind"]) in ("modeled", "unavailable")),
                 key=lambda p: pd.Timestamp(p["valid_start"]))
    valued = [p for p in pts if p.get("kind") != "unavailable" and p.get("value") is not None]
    out = {"status": "no_values", "reference": ref, "unit": view["freezing_reference"]["unit"], "period": None,
           "missing_before": sum(p.get("value") is None for p in pts),
           "checked_through": max((p["valid_end"] for p in valued), key=pd.Timestamp, default=None)}
    if not valued:
        return out
    first = next((p for p in valued if p["value"] <= ref), None)
    if first is None:
        out["status"] = "not_reached"
        return out
    out.update(status="starts_at_or_below" if first is valued[0] else "reached",
               period={k: first[k] for k in ("valid_start", "valid_end", "value")},
               missing_before=sum(p.get("value") is None and pd.Timestamp(p["valid_start"]) < pd.Timestamp(first["valid_start"])
                                  for p in pts))
    return out


def describe(m, fmt):
    """Plain-language sentence for the marker (text, not color only). fmt formats an ISO time for display."""
    ref = f"{m['reference']:g}°{m['unit']}"
    if m["status"] == "no_values":
        text = f"No returned pavement forecast values in this window, so no period at or below {ref} is marked."
    elif m["status"] == "not_reached":
        text = (f"No returned pavement forecast period in this window is at or below {ref} (returned periods end "
                f"{fmt(m['checked_through'])}). Later periods are unknown; this does not mean treatment is unnecessary.")
    else:
        p = m["period"]
        lead = ("Pavement forecast is already at or below" if m["status"] == "starts_at_or_below" and not m["missing_before"]
                else "First pavement forecast period at or below")
        text = (f"{lead} {ref}: period starting {fmt(p['valid_start'])} ({p['value']:.1f}°{m['unit']}). "
                "This is the returned period, not an exact crossing time.")
    if m["missing_before"]:
        n = m["missing_before"]
        text += (f" {n} earlier period{'s have' if n != 1 else ' has'} no pavement value, so an earlier period at or "
                 "below the reference cannot be ruled out." if m["period"] else
                 f" {n} period{'s have' if n != 1 else ' has'} no pavement value.")
    return f"{text} {NOTE}"


def chart_label(m, fmt):
    """Short on-chart label next to the marker, or None when no period is marked."""
    if not m["period"]:
        return None
    return f"◇ First ≤{m['reference']:g}°{m['unit']} period · {fmt(m['period']['valid_start'])}"
