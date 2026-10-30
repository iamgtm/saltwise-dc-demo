"""Operational context notes (public demo build).

The full SaltWise app keeps user-supplied stakeholder correspondence here, traceable and separate from evidence. The public
demo does not include that correspondence: the topic rows and named sources are empty and the notes below are neutral.
Nothing in this module is a threshold, a rule or a value used in any calculation.
"""
from datetime import datetime

SOURCE = "Stakeholder correspondence is not included in the public demo."
ROWS = []
AGENCY_PROVIDERS = []
# SaltWise's own pavement source.
SALTWISE_SOURCES = [
    ("Xweather Road Weather Conditions", "SaltWise source",
     "Modeled pavement forecast, not a sensor. In the full app it is read from saved snapshots taken by the trusted data "
     "service (no live request from the page) and shown only at verified, road-matched points and only within the returned "
     "horizon. This public demo includes no provider data."),
]

RAIN_NOTE = ("Rain at precipitation onset can discourage pretreatment or brining. This flag supports a person's existing "
             "review; it is not an automated treatment rule.")
READINESS_CONTEXT = ("This check is meant to work alongside an operator’s own deployment package, not replace it. It infers "
                     "no trucks, crews or material from a storm type such as “clipper” or “coastal”, or from “partial” or "
                     "“full” deployment: every quantity comes from the values you enter or verify.")
ROAD_CONTEXT = ("Road context: functional classification, traffic volumes and road geometry can inform deployment plans. "
                "SaltWise has no route-level designations, so this point is not labeled critical and no priority score is "
                "applied.")
SCENARIO_WHY = ("Why this scenario: near-freezing events can alternate among rain, freezing rain, sleet and snow, which is "
                "harder to plan for than a consistent storm. This synthetic sequence lets you compare treatment timing across "
                "the whole storm; its times, temperatures, surfaces and treatment choices are invented.")
SCENARIO_RULES = [
    "The baseline is an illustrative comparison, not a measured description of DC operations.",
    "Delaying an application is not automatically a permanent saving: count any later, repeat or catch-up application.",
    "Equal assumed service requirements do not prove equal real-world safety or performance.",
    "Missing inputs make the comparison incomplete; they never mean zero resource needs.",
]

PRECIP_TYPES = ("freezing rain", "sleet", "snow", "rain")


def precip_types(description):
    """Precipitation types named in a forecast text, e.g. 'Rain And Snow' -> {'rain', 'snow'}."""
    d = (description or "").lower()
    found = set()
    if "freezing rain" in d:
        found.add("freezing rain")
        d = d.replace("freezing rain", "")
    for t in ("sleet", "snow", "rain"):
        if t in d:
            found.add(t)
    return found


def _t(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _names(types):
    """'rain and snow' for a set of types, in order (rain, freezing rain, sleet, snow)."""
    return " and ".join(sorted(types, key=("rain", "freezing rain", "sleet", "snow").index))


def changing_conditions(view):
    """Explanation when modeled pavement is on both sides of the physical freezing reference and the displayed precipitation
    text, read only in periods that overlap a returned modeled pavement period with a value, either changes type from one
    period to the next or names several types together. Periods without valid pavement (missing values inside the horizon,
    or beyond it) are never paired with pavement; withheld, expired or mismatched pavement has no values and yields None.
    A change is described only when successive periods name different types; one mixed description repeated throughout is
    described as such, not as a change. Uses only displayed values; adds no threshold, probability or confidence."""
    ref, unit = view["freezing_reference"]["value"], view["freezing_reference"]["unit"]
    pav_pts = [p for s in view["series"] if s["quantity"] == "pavement_temperature" and s["kind"] == "modeled"
               for p in s["points"] if p.get("value") is not None and p.get("kind", "modeled") == "modeled"]
    pav = [p["value"] for p in pav_pts]
    if not pav or not (min(pav) <= ref < max(pav)):
        return None
    valid = [(_t(p["valid_start"]), _t(p["valid_end"])) for p in pav_pts]
    pr = [s for s in view["series"] if s["quantity"] == "precipitation"]
    periods = sorted([(_t(p["valid_start"]), frozenset(precip_types(p.get("description"))))
                      for s in pr for p in s["points"]
                      if any(_t(p["valid_start"]) < b and _t(p["valid_end"]) > a for a, b in valid)], key=lambda x: x[0])
    steps = []                                       # successive distinct type sets, periods naming no type skipped
    for _, types in periods:
        if types and (not steps or steps[-1] != types):
            steps.append(types)
    if not steps or (len(steps) == 1 and len(steps[0]) < 2):
        return None
    kind = "synthetic scenario text" if pr[0]["kind"] == "simulation" or "synthetic" in pr[0]["source"].lower() else \
        f"provider forecast text, {pr[0]['source']}"
    if len(steps) > 1:
        what = (f"Changing conditions: in the periods with modeled pavement values, the precipitation shown ({kind}) changes "
                f"type from one period to the next: {', then '.join(_names(s) for s in steps)}.")
    else:
        what = (f"Mixed precipitation: in the periods with modeled pavement values, the precipitation shown ({kind}) names "
                f"{_names(steps[0])} together in every period that names a type. This is one mixed description, not a "
                "change over time.")
    return (f"{what} Modeled pavement in those returned periods moves across the {ref:g}°{unit} physical freezing reference. "
            "The surface can change from one period to the next, so these flags ask for closer human review of each period "
            "rather than one decision for the whole event."
            " No threshold, probability or forecast confidence is added.")
