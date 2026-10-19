"""Evidence page: data kinds, sources, methods, request counts, and what is built versus planned. No requests."""
import json

import streamlit as st

import media
import nws_outlook as nws
from storm_lab_view import html_table

KINDS = [
    {"Kind": "Observation", "Meaning": "Measured by a sensor at a time", "In SaltWise now": "Not shown (no validated current observations)"},
    {"Kind": "Provider forecast", "Meaning": "Issued by a weather provider", "In SaltWise now": "Storm Outlook: NWS air forecast for one DC reference point; Road Weather (provider data): NWS hourly air forecast at verified points"},
    {"Kind": "Modeled", "Meaning": "Provider model of road conditions", "In SaltWise now": "Road Weather (provider data): Xweather modeled pavement at road-matched points, from saved snapshots; not sensor observations"},
    {"Kind": "Simulation", "Meaning": "Synthetic or hypothetical values", "In SaltWise now": "Road Weather scenarios, review-flag examples, Storm Lab"},
    {"Kind": "Planned", "Meaning": "Designed but not built", "In SaltWise now": "Listed below; never shown as working"},
    {"Kind": "Unavailable", "Meaning": "No usable value for that time", "In SaltWise now": "Shown as gaps or 'Unavailable', never as zero or as 'no treatment'"},
]
SOURCES = [
    {"Source": "NWS api.weather.gov", "Status": "Approved · Storm Outlook on Load; saved snapshots at verified points",
     "Notes": "Storm Outlook: hourly forecast and DC alerts for 38.8945, -77.0426, requested only when you press Load. Road Weather: "
              "hourly forecasts fetched by the trusted data service through the grid URLs NWS returns, with precipitation type from "
              "the structured gridpoint weather layer, within the shared request caps."},
    {"Source": "Xweather Road Weather Conditions", "Status": "Approved · saved snapshots (included allowance)",
     "Notes": "Provider-modeled pavement forecast, not a sensor. The 2026-10-15 responses cover 20.25 h and supply no issue time. "
              "Shown only where the location is verified and the provider road name matched."},
    {"Source": "DDOT RWIS / DCGIS", "Status": "Approved after checks · not connected",
     "Notes": "Latest public readings inspected were from 2023 to January 2024; historical records never appear as current."},
    {"Source": "Synthetic scenarios", "Status": "Built-in",
     "Notes": "All Road Weather and Storm Lab values. Illustrative, not observations or forecasts."},
]
METHODS = [
    ("Air and pavement", "Kept as separate, labeled series. Air temperature never stands in for pavement."),
    ("Pavement horizon", "Only the returned horizon is shown; later periods are labeled unavailable, never extended."),
    ("Freezing line", "32 °F / 0 °C is a physical reference, not a treatment rule."),
    ("Review flags", "Illustrative rules, not approved DC thresholds. They prompt human review and never approve or cancel treatment."),
    ("Storm Lab", "Material per application = lane-miles × rate. Totals include every initial, later and catch-up "
                  "application inside one shared window. Material avoided = baseline total − scenario total; it can be negative."),
    ("Assumptions", "Rates (default 200 lb per lane-mile), lane-miles (default 1 per point) and the baseline plan are "
                    "editable assumptions, not verified DC values or practice."),
    ("Freshness", "Freshness limits are not yet decided. Source times and ages are shown, not judged. Periods whose valid time has "
                  "ended are withheld. Retrieval age is not forecast age; Xweather supplies no issue time."),
    ("Location statuses", "Geographic verification (DCGIS), provider road-name matching and bridge-specific modeling are separate. "
                          "Pavement is shown only where the location is verified and the provider road matched."),
    ("Missing evidence", "Never means treatment is unnecessary and never takes a road out of assumed service."),
]
BUILT = [("Road Weather", "Air and pavement views with review flags · synthetic scenarios or saved provider snapshots"),
         ("Storm Lab", "Full-storm material comparison · simulation"),
         ("Storm Outlook", "72-hour NWS air forecast and DC alerts · one reference point")]
PLANNED = [("Remaining location reviews", "Rhode Island Ave NW road match, MLK Jr Ave SE point, bridge-specific modeling"),
           ("Scheduled snapshot refresh", "Templates prepared only; nothing installed or enabled"),
           ("Current RWIS observations", "After location, timestamp, unit and quality checks"),
           ("Accessibility verification", "Keyboard and screen-reader testing")]

SEASONAL = [
    {"Source": '<a href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml">NOAA CPC ENSO Diagnostic Discussion</a>',
     "Date": "Issued 8 October 2026",
     "What it says": "El Ni\u00f1o Advisory; a strong-to-very strong El Ni\u00f1o is likely through January\u2013March 2027 (greater than 83% chance)."},
    {"Source": '<a href="https://www.weather.gov/lwx/research_dcbalt_elnino">NWS Baltimore/Washington: El Ni\u00f1o and DC/Baltimore winters</a>',
     "Date": "Historical composites",
     "What it says": "In past El Ni\u00f1o winters DC averaged near-normal temperature and precipitation and above-normal seasonal snowfall, from a small sample; individual winters vary."},
]


def _cards(items, tag, cls):
    return '<div class="sw-cards">' + "".join(
        f'<div class="sw-card2 {cls}"><div class="sw-card2-k">{tag}</div><b>{t}</b><br>{d}</div>' for t, d in items) + "</div>"


def render():
    st.markdown('<div class="sw-section">EVIDENCE · SOURCES · METHODS</div>'
                '<h2 class="sw-h2">How SaltWise builds and labels its evidence</h2>', unsafe_allow_html=True)
    st.markdown('<div class="sw-section">KINDS OF EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown(html_table(KINDS, ["Kind", "Meaning", "In SaltWise now"]), unsafe_allow_html=True)
    st.markdown('<div class="sw-section">DATA SOURCES</div>', unsafe_allow_html=True)
    st.markdown(html_table(SOURCES, ["Source", "Status", "Notes"]), unsafe_allow_html=True)
    _provider_snapshot()
    b = nws.RequestBudget()
    c = b.counts()
    st.caption(f"Weather requests logged by this app process: {c['run']} of {b.caps['per_run']}; today (America/New_York): "
               f"{c['day']} of {b.caps['per_day']}, failed attempts included. Reading this page sends no request.")
    st.markdown('<div class="sw-section">METHODS</div>', unsafe_allow_html=True)
    st.markdown(html_table([{"Topic": t, "Method": m} for t, m in METHODS], ["Topic", "Method"]), unsafe_allow_html=True)
    st.markdown('<div class="sw-section">BUILT (PROTOTYPE)</div>', unsafe_allow_html=True)
    st.markdown(_cards(BUILT, "PROTOTYPE", ""), unsafe_allow_html=True)
    st.markdown('<div class="sw-section">PLANNED · NOT AVAILABLE YET</div>', unsafe_allow_html=True)
    st.markdown(_cards(PLANNED, "PLANNED", "sw-card2-planned"), unsafe_allow_html=True)
    st.markdown('<div class="sw-section">SEASONAL CONTEXT (HOMEPAGE INTRODUCTION)</div>', unsafe_allow_html=True)
    st.caption("Seasonal outlook context only: it is not a road forecast, not a treatment rule and is not used in any SaltWise calculation.")
    st.markdown(html_table(SEASONAL, ["Source", "Date", "What it says"]), unsafe_allow_html=True)
    st.markdown('<div class="sw-section">HOMEPAGE MEDIA CREDITS · DECORATIVE FOOTAGE, NOT DATA</div>', unsafe_allow_html=True)
    st.caption("Homepage videos and the photograph are illustrative stock media. They are not live cameras, not DC monitoring views and not demonstration locations.")
    st.markdown(media_credits(), unsafe_allow_html=True)


def media_credits():
    """Homepage background footage: decorative stock video, not data. Rendered from static/media/SOURCES.json."""
    rows = [{"Scene": r["scene"], "Creator": r["creator"] or "unknown",
             "License": f'<a href="{r["license_url"]}">{r["license"]}</a>' if r.get("license_url") else r["license"],
             "Source": f'<a href="{r["page"]}">Wikimedia Commons</a>', "Local file": r["file"].split("/")[-1],
             "Changes": r["changes"]} for r in media.records()]
    return html_table(rows, ["Scene", "Creator", "License", "Source", "Local file", "Changes"])


def _provider_snapshot():
    """Read-only summary of the trusted service's saved snapshots: three separate location statuses, times, attribution."""
    import evidence_snapshot as es
    from data import load_snapshots
    now = es.now_utc().replace(second=0, microsecond=0)
    snap = load_snapshots(es.store_token(), st.session_state.get("reload_count", 0))
    st.markdown('<div class="sw-section">PROVIDER EVIDENCE SNAPSHOT · READ-ONLY</div>', unsafe_allow_html=True)
    st.caption(f"Saved by the trusted data service and read at {es.iso(now)} without contacting any provider "
               f"(store {snap['store_status']}). {es.FRESHNESS_NOTE} Missing or withheld evidence never removes a road "
               "from assumed service.")
    st.markdown(html_table(es.location_rows(snap, now), ["Location", "Geographic verification", "Provider road match",
                                                         "Bridge-specific modeling", "Pavement evidence", "Air evidence"]), unsafe_allow_html=True)
    st.markdown(html_table(es.time_rows(snap, now), ["Location", "Source", "Shown", "Retrieved (UTC)", "Issued",
                                                     "Returned coverage (UTC)", "Retrieval age"]), unsafe_allow_html=True)
    st.markdown('<div class="sw-rule-note">Pavement data: <a href="https://www.xweather.com/" target="_blank" rel="noopener">Powered by '
                'Vaisala Xweather</a> · Air data: <a href="https://www.weather.gov/" target="_blank" rel="noopener">National Weather '
                'Service</a></div>', unsafe_allow_html=True)
    st.download_button("Download evidence snapshot (JSON, sanitized)", json.dumps(es.export_all(snap, now), indent=2),
                       file_name="saltwise_evidence_snapshot.json", mime="application/json", key="evidence_snapshot_download")
