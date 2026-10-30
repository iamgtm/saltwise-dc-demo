"""SYNTHETIC scenarios for fixture mode. Illustrative weather only - not observations or forecasts.

Each real demonstration-point NAME is paired with a SYNTHETIC road identity ("SYN-ROAD-x").
Coordinates are unknown (None): real locations are not validated and are never mapped.
Shapes follow the NWS forecastHourly and road-weather payloads so the same evidence functions apply.
"""
import math
from datetime import datetime, timedelta, timezone

ET = timezone(timedelta(hours=-5))
SCENARIO_TIME = datetime(2026, 12, 15, 21, 0, tzinfo=ET)       # synthetic "now": 9 p.m. ET
SCENARIO_ISSUED = SCENARIO_TIME - timedelta(hours=1)            # synthetic issue time
AIR_HOURS, PAVEMENT_HOURS = 72, 24                              # pavement shape mirrors a 24 h provider horizon

# Scenario-only settings for synthetic mode. NOT approved operational freshness limits (still unresolved).
SCENARIO_ONLY_FRESHNESS_LIMITS = {
    "_status": "SCENARIO-ONLY - not approved for live operations",
    "nws_air_forecast_max_age_hours": 24,
    "xweather_pavement_max_age_hours": 12,
    "rwis_observation_max_age_minutes": 60,
}

LOCATIONS = [
    # id, real demonstration-point name, short label, synthetic road id, scenario profile
    ("rhode_island_ave_nw_scott_circle", "Rhode Island Avenue NW near Scott Circle", "Rhode Island Ave NW", "SYN-ROAD-A", "warm_dry"),
    ("garfield_st_nw_34th_st_nw", "Garfield Street NW at 34th Street NW", "Garfield St NW", "SYN-ROAD-B", "severe_cold"),
    ("michigan_ave_ne_bridge", "Michigan Avenue NE bridge", "Michigan Ave NE bridge", "SYN-ROAD-C", "refreeze"),
    ("benning_rd_bridge", "Benning Road bridge", "Benning Rd bridge", "SYN-ROAD-D", "near_freezing_mixed"),
    ("mlk_jr_ave_se_alabama_ave_se", "Martin Luther King Jr. Avenue SE at Alabama Avenue SE", "MLK Jr Ave SE", "SYN-ROAD-E", "missing_pavement"),
]

PROFILE_LABEL = {
    "warm_dry": "Mild and dry",
    "severe_cold": "Severe cold",
    "refreeze": "Wet pavement cooling overnight",
    "near_freezing_mixed": "Near-freezing, changing precipitation",
    "missing_pavement": "Pavement values missing for part of the night",
}


def _profile(kind, i):
    """(air F, pavement F, surface condition, precip %, short forecast) for hour i."""
    diurnal = math.sin((i - 6) / 24 * 2 * math.pi)
    if kind == "warm_dry":
        return 46 + 5 * diurnal, 49 + 6 * diurnal, "DRY", 0, "Clear"
    if kind == "severe_cold":
        return 10 + 4 * diurnal, 14 + 5 * diurnal, "DRY" if i < 6 else "SNOW", 10 if i < 6 else 60, "Cold" if i < 6 else "Light Snow"
    if kind == "refreeze":
        pav = 36.0 - 0.9 * min(i, 7) + (0.8 * (i - 12) if i > 12 else 0)
        cond = "WET" if i < 4 else ("ICE" if i < 13 else "WET")
        return 36 - 0.3 * min(i, 6) + 2 * max(0, diurnal), pav, cond, 15, "Mostly Cloudy"
    if kind == "near_freezing_mixed":
        # Extends the former "rain turning to snow" profile. Rain at onset, then freezing rain, sleet, mixed rain and snow,
        # and snow while pavement hovers near the freezing reference, then a colder clear-out. Every time, temperature and
        # surface is invented and illustrative: not DC data and not supplied or approved by DPW.
        seq = ["Rain", "Rain", "Rain", "Freezing Rain", "Freezing Rain", "Sleet", "Rain And Snow", "Snow", "Snow", "Snow"]
        pav_seq = [35.0, 34.4, 33.8, 33.0, 32.4, 32.0, 32.6, 31.8, 31.4, 31.0, 30.5, 30.0, 29.6]
        air_seq = [36.0, 35.5, 35.0, 33.0, 32.6, 32.0, 33.0, 31.5, 31.0, 30.5, 30.0, 29.5, 29.0]
        pav = pav_seq[i] if i < len(pav_seq) else 29.6 + 0.4 * (i - 12)
        air = air_seq[i] if i < len(air_seq) else 29.0 + 3 * max(0, diurnal)
        cond = "WET" if i < 5 else ("SLUSH" if i < 7 else ("SNOW" if i < 10 else ("ICE" if pav <= 32 else "WET")))
        return air, pav, cond, 80 if i < len(seq) else 20, seq[i] if i < len(seq) else "Mostly Cloudy"
    # missing_pavement
    return 35 + 2 * diurnal, 34 + 2 * diurnal, "WET", 30, "Cloudy"


def scenario(location_id):
    loc_id, name, short, road, kind = next(x for x in LOCATIONS if x[0] == location_id)
    air_periods, pav_periods = [], []
    for i in range(AIR_HOURS):
        s = SCENARIO_TIME + timedelta(hours=i)
        air, _pav, _c, pop, short_fc = _profile(kind, i)
        air_periods.append({"number": i + 1, "startTime": s.isoformat(), "endTime": (s + timedelta(hours=1)).isoformat(),
                            "temperature": round(air), "temperatureUnit": "F",
                            "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": pop},
                            "shortForecast": short_fc})
    for i in range(PAVEMENT_HOURS):
        s = SCENARIO_TIME + timedelta(hours=i)
        _air, pav, cond, _p, _s = _profile(kind, i)
        missing = kind == "missing_pavement" and 3 <= i <= 5
        pav_periods.append({"timestamp": int(s.timestamp()), "dateTimeISO": s.isoformat(),
                            "roadSurface": None if missing else {"condition": cond, "tempF": round(pav, 1),
                                                                 "tempC": round((round(pav, 1) - 32) * 5 / 9, 1)}})
    return {
        "_synthetic": True,
        "_label": "SYNTHETIC SCENARIO - illustrative values, not real weather, not a verified location",
        "profile": kind, "profile_label": PROFILE_LABEL[kind],
        "evaluation_time": SCENARIO_TIME.isoformat(), "mode": "live",
        "location": {"location_id": loc_id, "name": name, "short": short,
                     "requested_lat": None, "requested_lon": None, "coordinates_verified": False,
                     "validation_status": "Not yet validated - coordinates and road match pending"},
        "nws_hourly": {"properties": {"updateTime": SCENARIO_ISSUED.isoformat(), "generatedAt": SCENARIO_ISSUED.isoformat(),
                                      "periods": air_periods}},
        "xweather_roadweather": {"success": True, "error": None, "response": [{
            "id": "synthetic", "dataSource": "synthetic-scenario", "loc": {"lat": None, "long": None},
            "road": {"type": "synthetic", "name": f"{road} (synthetic fixture road)"},
            "periods": pav_periods}]},
    }
