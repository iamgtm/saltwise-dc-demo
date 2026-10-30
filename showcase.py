"""Home hero: full-width cinematic five-slide showcase (st.components.v2; shadow-DOM styles, local media).

Each slide has its own decorative background clip and poster (static/media, see media.py and SOURCES.json),
a dark overlay, a large light heading and a sharp foreground graphic in a translucent panel. Slide changes,
autoplay, video playback and animation run in the browser only: no Python rerun, tool load or weather request.
Python hears from the component only when an Open button is pressed (trigger "open" -> page key).
Background footage is generic stock video, never a live DC camera or a demonstration location; every number in a
foreground graphic comes from the synthetic scenarios and saltwise_contract via slide_data().
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import media
import saltwise_contract as sc
import scenarios
from data import get_view

HERE = Path(__file__).resolve().parent
SELECTORS = ["Home", "Storm Outlook", "Road Weather", "Storm Lab", "Evidence"]
OPEN_TARGETS = {"home": "storm", "outlook": "outlook", "weather": "weather", "storm": "storm", "evidence": "evidence"}
INTERVAL_MS = 8000

# Full-width photographic introduction (same component, so hero and photo meet without a gap).
INTRO = {
    "media": "intro_photo",
    "heading": "Weather intelligence, for what\u2019s coming next",
    "text": ("NOAA\u2019s October 2026 update forecasts a strong to very strong El Ni\u00f1o into early 2027. DC\u2019s snowfall remains "
             "uncertain, so planning must adapt to each storm. SaltWise brings weather and pavement evidence together to explore "
             "ways to reduce avoidable salt use while maintaining winter access."),
    "source_label": "Seasonal context: NOAA CPC ENSO discussion, issued Oct 8, 2026",
    "source_url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
}

SLIDES = [
    {"id": "home", "tab": "Home", "headline": "Less avoidable salt. More informed winter planning.",
     "text": "A sustainability planning layer beside DC’s existing forecasts and deployment plans. People make every treatment decision.",
     "features": ["Sustainability first", "People decide", "Simulated scenarios"],
     "button": "Explore Storm Lab", "target": "storm", "media": "home_dc_city",
     "tag": "District outline · DCGIS boundary · no road locations shown"},
    {"id": "weather", "tab": "Road Weather", "headline": "Air and pavement. Clearly separated.",
     "text": "Compare air and pavement temperatures as separate lines, with illustrative flags marking hours worth a review.",
     "features": ["Separate air and pavement", "Physical freezing reference", "Illustrative review flags"],
     "button": "Open Road Weather", "target": "weather", "media": "weather_road",
     "tag": "Synthetic values · registered points on the DCGIS boundary"},
    {"id": "outlook", "tab": "Storm Outlook", "headline": "See what’s approaching.",
     "text": "A 72-hour NWS air-temperature and precipitation outlook with official DC alerts, loaded only when you ask.",
     "features": ["72-hour NWS outlook", "Official DC alerts", "One DC reference point"],
     "button": "Open Storm Outlook", "target": "outlook", "media": "outlook_storm_clouds",
     "tag": "Illustrative forecast window · not a forecast"},
    {"id": "storm", "tab": "Storm Lab", "headline": "Count the whole storm.",
     "text": "Add initial and later applications across the full storm window before comparing material use.",
     "features": ["Initial applications", "Later and catch-up rounds", "Full-window totals"],
     "button": "Open Storm Lab", "target": "storm", "media": "stormlab_snowplow",
     "tag": "Simulation fixture · illustrative assumptions"},
    {"id": "evidence", "tab": "Evidence", "headline": "Know where every value comes from.",
     "text": "Every value carries its source, valid time and kind; assumptions are stated and results download as JSON.",
     "features": ["Sources and valid times", "Evidence kinds", "JSON downloads"],
     "button": "Open Evidence", "target": "evidence", "media": "evidence_bridge",
     "tag": "How SaltWise labels evidence"},
]


def _clock(ts):
    return pd.Timestamp(ts).strftime("%-I %p").lower().replace("am", "a.m.").replace("pm", "p.m.")


@st.cache_data
def slide_data():
    """Numbers for the Road Weather and Storm Lab previews, from the same fixtures and calculations as the tools."""
    import home
    _, v = get_view("michigan_ave_ne_bridge", "F", "overnight", 0)
    series = {s["quantity"]: s["points"] for s in v["series"]}
    times = [p["valid_start"] for p in series["air_temperature"]]
    pav = {p["valid_start"]: p["value"] for p in series.get("pavement_temperature", [])}
    review = {r["valid_start"] for r in v["review_periods"] if r["pavement"] is not None}
    weather = {
        "location": next(name for lid, name, *_ in scenarios.LOCATIONS if lid == "michigan_ave_ne_bridge"),
        "units": "°F", "freezing": v["freezing_reference"]["value"],
        "hours": [_clock(t) for t in times], "end": _clock(series["air_temperature"][-1]["valid_end"]),
        "air": [p["value"] for p in series["air_temperature"]],
        "pavement": [pav.get(t) for t in times],
        "review": [t in review for t in times],
    }
    res, _ = home.default_comparison(use_submitted=False)
    views = {lid: get_view(lid, "F", "overnight", 0)[1] for lid, *_ in scenarios.LOCATIONS}
    unresolved = sc.unresolved_requirements(home.default_plans()["scenario"], views)
    full = sc.sensitivity(res["baseline"]["total_lb"], res["scenario"]["initial_lb"],
                          res["baseline"]["total_lb"] - res["scenario"]["initial_lb"])[2]
    storm = {
        "baseline": {k: res["baseline"][f"{k}_lb"] for k in ("initial", "later", "total")},
        "scenario": {k: res["scenario"][f"{k}_lb"] for k in ("initial", "later", "total")},
        "incomplete": bool(unresolved), "unresolved": len(unresolved),
        "full_catchup_total": full["scenario_total_lb"], "full_catchup_avoided": full["material_avoided_lb"],
        "rate": 200, "points": len(scenarios.LOCATIONS),
    }
    boundary = json.loads((HERE / "assets" / "dc_boundary.json").read_text())
    return {"weather": weather, "storm": storm, "boundary": {"view_box": boundary["view_box"], "path": boundary["path"]},
            "road_map": compact_map(views)}


def compact_map(views):
    """Homepage preview of the Road Weather map: registry points and their existing synthetic overnight flags (°F)."""
    import road_map
    reg = road_map.registry_points()
    pts = []
    for lid, name, short, *_ in scenarios.LOCATIONS:
        ids = [f["id"] for f in views[lid]["flags"] or []]
        r = reg.get(lid) or {}
        pts.append({"short": short, "x": r.get("x"), "y": r.get("y"), "partial": r.get("geographic_status") == "partial",
                    "category": next((c for c in road_map.PRIORITY if c in ids), "no_flag"), "n": len(ids),
                    "flags": [f["title"] for f in views[lid]["flags"] or []]})
    used = {p["category"] for p in pts}
    cats = [{k: c[k] for k in ("id", "label", "color", "shape")} for c in road_map.CATEGORIES if c["id"] in used]
    return {"points": pts, "categories": cats}


HTML = '<div class="sw-root" data-sw-root></div>'

CSS = r"""
:host { display:block; }
.sw-root { color:#FFFFFF; font-family:inherit; --accent:#D2560A; --accent-hi:#FF9A57; --muted:rgba(255,255,255,.80); }
.hero { position:relative; overflow:hidden; min-height:max(720px, 100vh); background:#0B0F14; display:flex; width:100vw; margin-left:calc(50% - 50vw); }
.bgs, .bg, .shade { position:absolute; inset:0; }
.bg { opacity:0; transition:opacity 1s cubic-bezier(.4,0,.2,1); z-index:0; }
.bg.on { opacity:1; z-index:2; }
.bg.prev { opacity:1; z-index:1; transition:none; }
.bg video { width:100%; height:100%; object-fit:cover; display:block; }
.shade { z-index:3; background:linear-gradient(180deg, rgba(6,10,14,.62) 0%, rgba(6,10,14,.38) 34%, rgba(6,10,14,.46) 62%, rgba(6,10,14,.82) 100%); }
.inner { position:relative; z-index:4; width:100%; max-width:1240px; margin:0 auto; padding:96px 32px 26px; box-sizing:border-box; display:flex; flex-direction:column; }
.notice { align-self:center; font-family:ui-monospace, Menlo, monospace; letter-spacing:.12em; font-size:11px; text-transform:uppercase; color:#FFE4D1;
  border:1px solid rgba(255,154,87,.55); background:rgba(210,86,10,.16); border-radius:999px; padding:4px 12px; margin-bottom:18px; }
.stage { display:grid; flex:1; }
.slide { grid-area:1/1; display:flex; flex-direction:column; align-items:center; text-align:center; opacity:0; visibility:hidden;
  transition:opacity .8s cubic-bezier(.4,0,.2,1), visibility 0s linear .8s; }
.slide.on { opacity:1; visibility:visible; transition:opacity .8s cubic-bezier(.4,0,.2,1), visibility 0s; }
.copy { transform:translateY(8px); transition:transform .8s cubic-bezier(.2,.7,.2,1); display:flex; flex-direction:column; align-items:center; }
.slide.on .copy { transform:none; }
h2 { font-size:56px; line-height:1.2; letter-spacing:-.04em; font-weight:300; margin:0 0 12px; max-width:760px; color:#FFFFFF; text-wrap:balance; }
.lead { font-size:18px; line-height:1.5; color:var(--muted); max-width:640px; margin:0 0 14px; }
ul.feat { list-style:none; padding:0; margin:0 0 18px; display:flex; flex-wrap:wrap; justify-content:center; gap:6px 22px; font-size:16px; }
ul.feat li { display:flex; align-items:center; gap:7px; color:#FFFFFF; }
ul.feat li::before { content:"\2713"; color:var(--accent-hi); font-weight:700; }
.open { font:inherit; font-size:16px; font-weight:650; color:#1A0B02; background:var(--accent); border:0; border-radius:999px; padding:11px 22px; cursor:pointer;
  box-shadow:0 8px 24px rgba(0,0,0,.25); margin-bottom:22px; }
.open:hover { filter:brightness(1.08); }
.glass { width:min(560px, 100%); height:250px; box-sizing:border-box; background:rgba(255,255,255,.08); backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,.20); border-radius:8px; padding:12px 16px 10px; display:flex; flex-direction:column; text-align:left; }
.vtag { align-self:flex-start; font-family:ui-monospace, Menlo, monospace; letter-spacing:.08em; font-size:10.5px; text-transform:uppercase; color:rgba(255,255,255,.85);
  border:1px dashed rgba(255,255,255,.4); border-radius:999px; padding:2px 9px; margin-bottom:6px; }
.legend { display:flex; flex-wrap:wrap; gap:4px 14px; font-size:12.5px; color:#FFFFFF; margin:0 0 4px; padding:0; list-style:none; }
.legend li { display:flex; align-items:center; gap:6px; }
.legend svg { width:24px; height:10px; }
svg.g { display:block; width:100%; flex:1; min-height:0; overflow:visible; }
.cap { font-size:12px; color:rgba(255,255,255,.78); margin-top:4px; }
.bars { display:flex; flex-direction:column; gap:12px; margin-top:4px; }
.lbl { display:flex; justify-content:space-between; flex-wrap:wrap; gap:2px 10px; font-size:13.5px; margin-bottom:5px; }
.lbl em { font-style:normal; color:rgba(255,255,255,.8); }
.track { position:relative; height:24px; border-radius:6px; background:rgba(255,255,255,.10); overflow:hidden; }
.seg { position:absolute; top:0; bottom:0; width:0; transition:width 1.2s cubic-bezier(.3,.7,.2,1); }
.seg.init { left:0; background:var(--accent); }
.seg.later { background:repeating-linear-gradient(135deg, #BFD4EA 0 6px, #8FB0D2 6px 12px); }
.seg.unknown { border:2px dashed rgba(255,255,255,.7); border-left:0; border-radius:0 6px 6px 0; }
.warn { font-size:12.5px; color:#FFE4D1; border-left:3px solid var(--accent-hi); padding:4px 9px; background:rgba(210,86,10,.18); border-radius:4px; margin-top:8px; }
.ev { display:grid; grid-template-columns:auto 1fr auto; gap:6px 12px; align-items:center; font-size:13px; margin-top:4px; }
.ev .k { font-family:ui-monospace, Menlo, monospace; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; border-radius:999px; padding:2px 8px; border:1px solid rgba(255,255,255,.45); white-space:nowrap; }
.ev .k.pf { border-style:solid; } .ev .k.sim { border-style:dashed; } .ev .k.na { border-style:dotted; color:rgba(255,255,255,.75); }
.ev .t { color:rgba(255,255,255,.8); font-size:12px; white-space:nowrap; }
.controls { display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:12px 20px; margin-top:18px; }
[role=tablist] { display:flex; flex-wrap:wrap; justify-content:center; gap:6px 8px; }
[role=tab] { font:inherit; font-size:15px; display:flex; align-items:center; gap:8px; background:rgba(255,255,255,.04); color:rgba(255,255,255,.72);
  border:1px solid rgba(255,255,255,.22); border-radius:6px; padding:7px 13px 7px 10px; cursor:pointer; }
[role=tab]:hover { color:#FFFFFF; }
[role=tab][aria-selected=true] { color:#FFFFFF; border-color:rgba(255,255,255,.85); background:rgba(255,255,255,.10); }
.ring { width:15px; height:15px; flex:none; }
.ring circle { fill:none; stroke-width:2.2; }
.ring .bgc { stroke:rgba(255,255,255,.35); }
.ring .fg { stroke:#FFFFFF; stroke-dasharray:44; stroke-dashoffset:44; transform:rotate(-90deg); transform-origin:50% 50%; opacity:0; }
[aria-selected=true] .ring .fg { opacity:1; }
.playing [aria-selected=true] .ring .fg { animation:ring var(--dur) linear forwards; }
.paused [aria-selected=true] .ring .fg, .hold [aria-selected=true] .ring .fg { animation-play-state:paused; }
.manual [aria-selected=true] .ring .fg { animation:none; stroke-dashoffset:0; }
@keyframes ring { to { stroke-dashoffset:0; } }
.nav { display:flex; align-items:center; gap:8px; }
.nav button { font:inherit; font-size:14px; color:#FFFFFF; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.28); border-radius:6px; height:38px; min-width:38px; padding:0 12px; cursor:pointer; }
.nav button:hover { border-color:#FFFFFF; }
.count { font-family:ui-monospace, Menlo, monospace; font-size:12px; letter-spacing:.12em; color:rgba(255,255,255,.75); }
button:focus-visible { outline:2px solid var(--accent-hi); outline-offset:3px; }
.intro { position:relative; overflow:hidden; width:100vw; margin-left:calc(50% - 50vw); height:max(560px, 92vh); background:#09151C; display:flex; }
.intro img { position:absolute; left:0; top:-6%; width:100%; height:112%; object-fit:cover; display:block; will-change:transform; }
.intro .shade { z-index:1; background:linear-gradient(180deg, rgba(9,21,28,.55) 0%, rgba(9,21,28,.30) 38%, rgba(9,21,28,.62) 70%, rgba(9,21,28,.86) 100%); }
.intro .txt { position:relative; z-index:2; margin:auto auto 12vh; max-width:860px; padding:0 24px; text-align:center; opacity:0; transform:translateY(18px);
  transition:opacity 1s ease, transform 1s cubic-bezier(.2,.7,.2,1); }
.intro.seen .txt { opacity:1; transform:none; }
.intro h2 { font-size:44px; line-height:1.2; letter-spacing:-.035em; font-weight:300; margin:0 0 16px; max-width:none; }
.intro p { font-size:19px; line-height:1.6; color:rgba(255,255,255,.86); margin:0 0 16px; }
.src { font-size:12.5px; color:rgba(255,255,255,.72); }
.src a, .src button { color:rgba(255,255,255,.88); font:inherit; background:none; border:0; padding:0; cursor:pointer; text-decoration:underline; text-underline-offset:2px; }
.src a:focus-visible, .src button:focus-visible { outline:2px solid #FF9A57; outline-offset:2px; }
.draw { stroke-dasharray:1; stroke-dashoffset:0; }
.slide.on .draw { animation:draw 1.6s ease-out both; }
@keyframes draw { from { stroke-dashoffset:1; } to { stroke-dashoffset:0; } }
@keyframes sweep { from { transform:translateX(0); } to { transform:translateX(var(--sweep)); } }
.playhead { animation:sweep 7s ease-in-out infinite alternate; }
.frozen .playhead { animation-play-state:paused; }
@media (max-width: 860px) {
  .hero { min-height:100svh; }
  .inner { padding:84px 16px 18px; }
  .notice { align-self:flex-start; }
  .slide, .copy { align-items:flex-start; text-align:left; }
  h2 { font-size:36px; letter-spacing:-.03em; }
  .lead { font-size:16px; }
  ul.feat { justify-content:flex-start; font-size:15px; gap:4px 16px; }
  .glass { height:auto; min-height:200px; }
  .ev { grid-template-columns:auto 1fr; } .ev .t { display:none; }
  svg.g { flex:none; height:150px; }
  .controls { justify-content:flex-start; }
  [role=tablist] { justify-content:flex-start; }
  [role=tab] { font-size:14px; padding:6px 10px 6px 8px; }
  .intro { height:auto; min-height:88svh; }
  .intro .txt { margin:auto 0 64px; text-align:left; padding:0 16px; }
  .intro h2 { font-size:30px; }
  .intro p { font-size:16.5px; }
}
.reduced .slide, .reduced .copy, .reduced .bg, .reduced .seg, .reduced .txt { transition:none !important; }
.reduced .intro .txt { opacity:1; transform:none; }
.reduced .intro img { transform:none !important; }
.reduced .draw, .reduced .playhead { animation:none !important; }
.glass.wide { width:min(860px, 100%); }
.wx { display:grid; grid-template-columns:250px 1fr; gap:14px; flex:1; min-height:0; }
.wxc { display:flex; flex-direction:column; min-width:0; min-height:0; }
.rmc { position:relative; border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,.16);
  background:radial-gradient(ellipse 70% 60% at 50% 40%, rgba(26,39,51,.92) 0%, rgba(14,22,32,.92) 70%); display:flex; align-items:center; justify-content:center; padding:6px; }
.rmc-map { position:relative; height:100%; max-height:200px; }
.rmc-map svg { position:absolute; inset:0; width:100%; height:100%; }
.rmk { position:absolute; width:16px; height:16px; margin:-8px 0 0 -8px; }
.rmk svg { position:absolute; inset:0; width:16px; height:16px; filter:drop-shadow(0 1px 2px rgba(0,0,0,.6)); }
.rmk i { position:absolute; inset:-10px; border-radius:50%; background:radial-gradient(circle, var(--c) 0%, rgba(0,0,0,0) 68%); opacity:.35; }
.rmc.go .rmk { animation:rmkIn .55s cubic-bezier(.2,.8,.2,1.2) both; animation-delay:var(--d); }
@keyframes rmkIn { from { opacity:0; transform:scale(.4); } to { opacity:1; transform:none; } }
.rmc-lg { position:absolute; left:6px; top:6px; margin:0; padding:5px 7px; list-style:none; font-size:11px; line-height:1.35; color:#F2F4F6;
  background:rgba(22,32,42,.6); -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px); border:1px solid rgba(255,255,255,.18); border-radius:8px; }
.rmc-lg li { display:flex; align-items:center; gap:4px; } .rmc-lg svg { width:11px; height:11px; }
.rmc.go .rmc-lg { animation:rmkLg .5s ease-out both; }
@keyframes rmkLg { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:none; } }
@media (max-width: 640px) { .wx { grid-template-columns:1fr; } .rmc { height:220px; } }
.reduced .rmc.go .rmk, .reduced .rmc.go .rmc-lg { animation:none !important; }
"""

JS = r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector('[data-sw-root]');
  if (!root) return;
  if (root.__swCleanup) root.__swCleanup();
  const S = data.slides, D = data.data, M = data.media, N = S.length, DUR = data.interval_ms;
  const I = { ...data.intro, media: data.media[data.intro.media] };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const fmt = n => Math.round(n).toLocaleString('en-US');
  const html = document.documentElement;

  function homeArt() {
    const b = D.boundary;
    return `<svg class="g" viewBox="${b.view_box.join(' ')}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Outline of the District of Columbia (DCGIS boundary). No road locations are drawn.">
      <path class="draw" pathLength="1" d="${b.path}" fill="rgba(255,255,255,.06)" stroke="#FFFFFF" stroke-width="2.2" stroke-linejoin="round"/></svg>
      <div class="cap">Five demonstration settings · precise placement not yet verified, so none are drawn.</div>`;
  }
  function outlookArt() {
    const marks = [0, 24, 48, 72].map((h, i) => `<line x1="${30 + i * 160}" y1="150" x2="${30 + i * 160}" y2="158" stroke="rgba(255,255,255,.7)"/>
      <text x="${30 + i * 160}" y="176" fill="#FFFFFF" font-size="13" text-anchor="${i === 0 ? 'start' : i === 3 ? 'end' : 'middle'}">${h === 0 ? 'Now' : '+' + h + ' h'}</text>`).join('');
    const cloud = (x, y) => `<path d="M${x - 24} ${y} a15 15 0 0 1 11 -26 a19 19 0 0 1 36 4 a13 13 0 0 1 2 22z" fill="rgba(255,255,255,.28)"/>`;
    return `<svg class="g" viewBox="0 0 540 186" role="img" aria-label="Illustrative 72-hour window with clouds, snow and an alert marker. Not a forecast.">
      <rect x="30" y="120" width="480" height="10" rx="5" fill="rgba(255,255,255,.14)"/>
      <rect x="190" y="120" width="230" height="10" rx="5" fill="#BFD4EA" opacity=".75"/>
      ${cloud(120, 92)}${cloud(280, 86)}<g fill="#FFFFFF"><circle cx="268" cy="100" r="2.6"/><circle cx="280" cy="108" r="2.6"/><circle cx="292" cy="100" r="2.6"/></g>
      <rect x="392" y="62" width="66" height="26" rx="13" fill="rgba(210,86,10,.30)" stroke="#FF9A57"/><text x="425" y="80" fill="#FFFFFF" font-size="13" text-anchor="middle">Alert</text>
      <line x1="30" y1="150" x2="510" y2="150" stroke="rgba(255,255,255,.35)"/>${marks}
      <g class="playhead" style="--sweep:480px"><line x1="30" y1="40" x2="30" y2="156" stroke="#FF9A57" stroke-width="2"/><circle cx="30" cy="125" r="6" fill="#FF9A57"/></g></svg>
      <div class="cap">Storm Outlook loads NWS atmospheric forecasts on request for one DC reference point; it has no pavement forecast.</div>`;
  }
  function sym(shape, color) {
    const P = { triangle: `<path d="M12 2 L22 21 L2 21 Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      diamond: `<path d="M12 1.5 L22 12 L12 22.5 L2 12 Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      drop: `<path d="M12 2 C18 10 20 14 20 16 A8 8 0 0 1 4 16 C4 14 6 10 12 2 Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      question: `<circle cx="12" cy="12" r="10" fill="${color}" stroke="#0E1620" stroke-width="1.5"/><text x="12" y="17" text-anchor="middle" font-size="14" font-weight="700" fill="#0E1620" font-family="system-ui,sans-serif">?</text>`,
      ring: `<circle cx="12" cy="12" r="8" fill="rgba(14,22,32,.6)" stroke="${color}" stroke-width="3"/>` };
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${P[shape] || P.ring}</svg>`;
  }
  function mapArt() {
    const m = D.road_map, b = D.boundary, W = b.view_box[2], H = b.view_box[3], C = Object.fromEntries(m.categories.map(c => [c.id, c]));
    const placed = m.points.filter(p => p.x !== null);
    const desc = m.points.map(p => `${p.short}: ${p.flags.length ? p.flags.join(', ') : 'no review flag'}`).join('; ');
    return `<div class="rmc" role="img" aria-label="Map preview: five registered points on the DC boundary with synthetic overnight review flags. ${esc(desc)}.">
      <div class="rmc-map" style="aspect-ratio:${W} / ${H}"><svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${b.path}" fill="rgba(255,255,255,.05)" stroke="rgba(255,255,255,.7)" stroke-width="2.4" stroke-linejoin="round"/></svg>
        ${placed.map((p, i) => `<span class="rmk${p.partial ? ' part' : ''}" style="left:${(p.x / W * 100).toFixed(2)}%;top:${(p.y / H * 100).toFixed(2)}%;--c:${C[p.category].color};--d:${i * 160 + 250}ms"><i></i>${sym(C[p.category].shape, C[p.category].color)}</span>`).join('')}</div>
      <ul class="rmc-lg" aria-hidden="true">${m.categories.map(c => `<li>${sym(c.shape, c.color)}${esc(c.label)}</li>`).join('')}</ul></div>`;
  }
  function weatherArt() {
    return `<div class="wx">${mapArt()}<div class="wxc">${chartArt()}</div></div>`;
  }
  function chartArt() {
    const w = D.weather, n = w.hours.length, W = 540, H = 170, L = 34, R = 6, T = 8, B = 22;
    const vals = w.air.concat(w.pavement.filter(v => v !== null), [w.freezing]);
    const lo = Math.floor(Math.min(...vals) - 1), hi = Math.ceil(Math.max(...vals) + 1);
    const x = i => L + i * (W - L - R) / n, y = v => T + (hi - v) * (H - T - B) / (hi - lo);
    const step = arr => arr.map((v, i) => v === null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)} ${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean).join(' ');
    const yt = [lo, w.freezing, hi].map(v => `<text x="${L - 6}" y="${y(v) + 4}" fill="#FFFFFF" font-size="12" text-anchor="end">${v}°</text>`).join('');
    const xt = w.hours.map((h, i) => i % 3 === 0 ? `<text x="${x(i) + (i ? 0 : 1)}" y="${H - 4}" fill="#FFFFFF" font-size="12" text-anchor="${i ? 'middle' : 'start'}">${esc(h)}</text>` : '').join('') + `<text x="${x(n)}" y="${H - 4}" fill="#FFFFFF" font-size="12" text-anchor="end">${esc(w.end)}</text>`;
    return `<ul class="legend" aria-label="Chart key">
        <li><svg viewBox="0 0 24 10"><line x1="0" y1="5" x2="24" y2="5" stroke="#BFD4EA" stroke-width="3" stroke-dasharray="6 3"/></svg>Air · synthetic</li>
        <li><svg viewBox="0 0 24 10"><line x1="0" y1="5" x2="24" y2="5" stroke="#FF9A57" stroke-width="3"/></svg>Pavement · synthetic</li>
        <li><svg viewBox="0 0 24 10"><line x1="0" y1="5" x2="24" y2="5" stroke="#FFFFFF" stroke-width="1.5" stroke-dasharray="2 4"/></svg>${w.freezing} ${w.units} freezing · physical</li></ul>
      <svg class="g" viewBox="0 0 ${W} ${H}" role="img" aria-label="Synthetic overnight scenario at ${esc(w.location)}: air ${w.air[0]} to ${w.air[n - 1]}${w.units}; pavement ${w.pavement[0]} to ${w.pavement[n - 1]}${w.units}.">
        <line x1="${L}" y1="${y(w.freezing)}" x2="${W - R}" y2="${y(w.freezing)}" stroke="#FFFFFF" stroke-opacity=".7" stroke-width="1.5" stroke-dasharray="2 4"/>
        <polyline class="draw" pathLength="1" points="${step(w.air)}" fill="none" stroke="#BFD4EA" stroke-width="3" stroke-dasharray="6 3"/>
        <polyline class="draw" pathLength="1" points="${step(w.pavement)}" fill="none" stroke="#FF9A57" stroke-width="3"/>${yt}${xt}</svg>
      <div class="cap">${esc(w.location)} · overnight · synthetic scenario, not a reading.</div>`;
  }
  function stormArt() {
    const s = D.storm, max = Math.max(s.baseline.total, s.full_catchup_total, s.scenario.total) || 1, pct = v => (100 * v / max).toFixed(2) + '%';
    return `<div class="bars" role="img" aria-label="Simulated whole-storm material. Baseline ${fmt(s.baseline.initial)} lb initial plus ${fmt(s.baseline.later)} lb later, ${fmt(s.baseline.total)} lb. Scenario ${fmt(s.scenario.initial)} lb initial${s.incomplete ? '; later need not yet counted, comparison incomplete' : ''}.">
      <div><div class="lbl"><b>Baseline (illustrative)</b><em>${fmt(s.baseline.initial)} + ${fmt(s.baseline.later)} = ${fmt(s.baseline.total)} lb</em></div>
        <div class="track"><div class="seg init" data-w="${pct(s.baseline.initial)}"></div><div class="seg later" data-l="${pct(s.baseline.initial)}" data-w="${pct(s.baseline.later)}"></div></div></div>
      <div><div class="lbl"><b>Scenario</b><em>${fmt(s.scenario.initial)} lb counted${s.incomplete ? ' · later need not yet counted' : ''}</em></div>
        <div class="track"><div class="seg init" data-w="${pct(s.scenario.initial)}"></div>
        ${s.incomplete ? `<div class="seg unknown" data-l="${pct(s.scenario.total)}" data-w="${pct(Math.max(s.full_catchup_total - s.scenario.total, 0))}"></div>` : ''}</div></div></div>
      ${s.incomplete ? `<div class="warn">Comparison incomplete: no saving is shown until every later round is counted.</div>` : ''}
      <div class="cap">${s.points} demonstration points · overnight · ${s.rate} lb per lane-mile assumed · simulated.</div>`;
  }
  function evidenceArt() {
    return `<div class="ev" role="list" aria-label="How values are labeled">
        <span class="k pf" role="listitem">Provider forecast</span><span>NWS air temperature and precipitation · Storm Outlook</span><span class="t">valid hour · issued time</span>
        <span class="k sim" role="listitem">Simulation</span><span>Synthetic scenarios · Road Weather and Storm Lab</span><span class="t">scenario time</span>
        <span class="k pf" role="listitem">Physical reference</span><span>32 °F / 0 °C freezing line</span><span class="t">not a rule</span>
        <span class="k na" role="listitem">Unavailable</span><span>Live pavement evidence · not connected</span><span class="t">shown as a gap</span></div>
      <div class="cap">Every value carries its source, valid time and kind. Inputs and results export as JSON.</div>`;
  }
  const ART = { home: homeArt, outlook: outlookArt, weather: weatherArt, storm: stormArt, evidence: evidenceArt };
  const uid = 'sw' + Math.random().toString(36).slice(2, 8);
  root.innerHTML = `<section class="hero" aria-roledescription="carousel" aria-label="SaltWise DC overview">
    <div class="bgs" aria-hidden="true">${S.map((s, i) => `<div class="bg" data-i="${i}"><video muted loop playsinline preload="none" disablepictureinpicture
        poster="${esc(M[s.media].poster)}" data-src="${esc(M[s.media].src)}"></video></div>`).join('')}<div class="shade"></div></div>
    <div class="inner">
      <div class="notice">Prototype · not for operational use · previews are labeled simulations</div>
      <div class="stage" aria-live="off">${S.map((s, i) => `
        <div class="slide" role="tabpanel" id="${uid}-p${i}" aria-labelledby="${uid}-t${i}" aria-roledescription="slide" data-i="${i}">
          <div class="copy"><h2>${esc(s.headline)}</h2><p class="lead">${esc(s.text)}</p>
            <ul class="feat">${s.features.map(f => `<li>${esc(f)}</li>`).join('')}</ul>
            <button class="open" type="button" data-target="${s.target}">${esc(s.button)} <span aria-hidden="true">→</span></button></div>
          <div class="glass${s.id === 'weather' ? ' wide' : ''}"><span class="vtag">${esc(s.tag)}</span>${ART[s.id]()}</div>
        </div>`).join('')}</div>
      <div class="controls">
        <div role="tablist" aria-label="Choose a slide">${S.map((s, i) => `<button type="button" role="tab" id="${uid}-t${i}" aria-controls="${uid}-p${i}" data-i="${i}">
          <svg class="ring" viewBox="0 0 16 16" aria-hidden="true"><circle class="bgc" cx="8" cy="8" r="7"/><circle class="fg" cx="8" cy="8" r="7"/></svg>${esc(s.tab)}</button>`).join('')}</div>
        <div class="nav"><span class="count" aria-hidden="true"></span>
          <button type="button" data-act="prev" aria-label="Previous slide">←</button>
          <button type="button" data-act="next" aria-label="Next slide">→</button></div>
      </div>
    </div></section>
    <section class="intro" aria-labelledby="${uid}-intro">
      <img alt="" aria-hidden="true" decoding="async" loading="lazy" src="${esc(I.media.src)}" srcset="${esc(I.media.small || I.media.src)} 1200w, ${esc(I.media.src)} 2400w" sizes="100vw">
      <div class="shade"></div>
      <div class="txt"><h2 id="${uid}-intro">${esc(I.heading)}</h2><p>${esc(I.text)}</p>
        <div class="src"><a href="${esc(I.source_url)}" target="_blank" rel="noopener noreferrer">${esc(I.source_label)}</a> · <button type="button" class="ev-link">Sources and details on Evidence</button></div></div>
    </section>`;

  const hero = root.querySelector('.hero'), intro = root.querySelector('.intro'), introImg = intro.querySelector('img');
  const slides = [...root.querySelectorAll('.slide')], tabs = [...root.querySelectorAll('[role=tab]')], bgs = [...root.querySelectorAll('.bg')];
  const vids = bgs.map(b => b.querySelector('video'));
  const count = root.querySelector('.count'), stage = root.querySelector('.stage');
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  hero.style.setProperty('--dur', DUR + 'ms');
  vids.forEach(v => { v.controls = false; v.removeAttribute('controls'); });
  // Rotation and video are independent. Rotation: always on (one timer), reset by every slide change, held only while
  // keyboard focus is inside the hero (so focus never lands in a hidden slide), while the tab is hidden or the hero is off
  // screen, and never under reduced motion. Video: plays whenever its slide is active and the hero is visible.
  let cur = Math.min(Math.max(root.__swIndex || 0, 0), N - 1);
  let focused = false, hidden = document.hidden, onScreen = true;
  let timer = null, startedAt = 0, remaining = DUR;
  const offs = [], on = (el, ev, fn, o) => { el.addEventListener(ev, fn, o); offs.push(() => el.removeEventListener(ev, fn, o)); };
  const canRotate = () => !mq.matches && !focused && !hidden && onScreen;
  function syncVideo() {
    vids.forEach((v, k) => {
      const want = k === cur && !hidden && onScreen && !mq.matches;
      if (want) { if (!v.getAttribute('src')) { v.src = v.dataset.src; v.preload = 'auto'; } const p = v.play(); if (p) p.catch(() => {}); }
      else if (!v.paused) v.pause();
    });
  }
  function animateBars(slide) {
    slide.querySelectorAll('.seg').forEach(seg => { seg.style.width = '0'; if (seg.dataset.l) seg.style.left = seg.dataset.l; });
    const run = () => slide.querySelectorAll('.seg').forEach(seg => {
      const later = seg.classList.contains('later') || seg.classList.contains('unknown');
      setTimeout(() => { seg.style.width = seg.dataset.w; }, mq.matches ? 0 : (later ? 1150 : 150));
    });
    mq.matches ? run() : requestAnimationFrame(() => requestAnimationFrame(run));
  }
  function restartRing() { const fg = tabs[cur].querySelector('.fg'); fg.style.animation = 'none'; void fg.getBoundingClientRect(); fg.style.animation = ''; }
  function schedule() {                       // the only place the rotation timer is created
    clearTimeout(timer); timer = null;
    const run = canRotate();
    hero.classList.toggle('playing', !mq.matches);
    hero.classList.toggle('hold', !run && !mq.matches);
    hero.classList.toggle('frozen', hidden || mq.matches || !onScreen);
    hero.classList.toggle('reduced', mq.matches);
    stage.setAttribute('aria-live', run ? 'off' : 'polite');
    if (run) { startedAt = performance.now(); timer = setTimeout(() => { timer = null; show(cur + 1); }, remaining); }
    root.__swTimerActive = !!timer;
  }
  function hold() { if (timer) remaining = Math.max(remaining - (performance.now() - startedAt), 300); clearTimeout(timer); timer = null; schedule(); }
  function show(i, opts = {}) {
    const old = cur; cur = (i + N) % N; root.__swIndex = cur;
    slides.forEach((s, k) => { const a = k === cur; s.classList.toggle('on', a); s.inert = !a; s.setAttribute('aria-hidden', a ? 'false' : 'true'); });
    tabs.forEach((t, k) => { const a = k === cur; t.setAttribute('aria-selected', a); t.tabIndex = a ? 0 : -1; });
    const nb = bgs[cur], ob = bgs[old];
    bgs.forEach(b => { if (b !== nb && b !== ob) b.classList.remove('on', 'prev'); });
    if (ob && ob !== nb && ob.classList.contains('on')) {
      ob.classList.remove('on'); ob.classList.add('prev');
      const done = () => { ob.classList.remove('prev'); nb.removeEventListener('transitionend', done); };
      mq.matches ? done() : nb.addEventListener('transitionend', done);
    }
    nb.classList.add('on'); nb.classList.remove('prev');
    count.textContent = `${String(cur + 1).padStart(2, '0')} / ${String(N).padStart(2, '0')}`;
    animateBars(slides[cur]); restartRing();
    const rmc = slides[cur].querySelector('.rmc');          // map preview: markers reveal in sequence each time the slide opens
    if (rmc) { rmc.classList.remove('go'); void rmc.offsetWidth; rmc.classList.add('go'); }
    if (opts.focusTab) tabs[cur].focus({ preventScroll: true });
    remaining = DUR; schedule(); syncVideo();
  }
  tabs.forEach((t, k) => on(t, 'click', () => show(k)));
  on(root.querySelector('[data-act=prev]'), 'click', () => show(cur - 1));
  on(root.querySelector('[data-act=next]'), 'click', () => show(cur + 1));
  on(root.querySelector('[role=tablist]'), 'keydown', e => {
    const map = { ArrowRight: cur + 1, ArrowLeft: cur - 1, Home: 0, End: N - 1 };
    if (e.key in map) { e.preventDefault(); show(map[e.key], { focusTab: true }); }
  });
  root.querySelectorAll('.open').forEach(b => on(b, 'click', () => setTriggerValue('open', b.dataset.target)));
  on(root.querySelector('.ev-link'), 'click', () => setTriggerValue('open', 'evidence'));
  // keyboard focus inside the hero holds rotation temporarily; mouse clicks do not
  on(hero, 'focusin', e => { if (e.target.matches && e.target.matches(':focus-visible')) { focused = true; hold(); } });
  on(hero, 'focusout', e => { if (!hero.contains(e.relatedTarget)) { focused = false; schedule(); } });
  on(document, 'visibilitychange', () => { hidden = document.hidden; hidden ? hold() : schedule(); syncVideo(); });
  on(mq, 'change', () => { schedule(); syncVideo(); });
  // header: light-on-dark while the hero or the photo is under it; hero video and rotation pause off screen
  html.classList.add('sw-home');
  const headerLine = 68;
  const underHeader = el => { const r = el.getBoundingClientRect(); return r.top < headerLine && r.bottom > headerLine; };
  const updateHeader = () => html.classList.toggle('sw-over-hero', underHeader(hero) || underHeader(intro));
  const io = new IntersectionObserver(() => {
    updateHeader();
    const r = hero.getBoundingClientRect(), vis = r.bottom > 0 && r.top < window.innerHeight;
    if (vis !== onScreen) { onScreen = vis; vis ? schedule() : hold(); syncVideo(); }
  }, { threshold: Array.from({ length: 41 }, (_, k) => k / 40) });
  io.observe(hero);
  const ioIntro = new IntersectionObserver(es => { updateHeader(); es.forEach(e => { if (e.isIntersecting && e.intersectionRatio > 0.25) intro.classList.add('seen'); }); },
                                           { threshold: Array.from({ length: 21 }, (_, k) => k / 20) });
  ioIntro.observe(intro);
  html.classList.add('sw-over-hero');
  const host = root.getRootNode().host;
  function scroller() { let e = host && host.parentElement; while (e && e !== document.body) { const st = getComputedStyle(e); if (/(auto|scroll)/.test(st.overflowY) && e.scrollHeight > e.clientHeight) return e; e = e.parentElement; } return document.scrollingElement; }
  function pullUp() { if (!host) return; hero.style.marginTop = '0px'; const sc = scroller(); const base = sc === document.scrollingElement ? 0 : sc.getBoundingClientRect().top;
    const top = host.getBoundingClientRect().top - base + (sc.scrollTop || 0); hero.style.marginTop = (-Math.max(0, Math.round(top))) + 'px'; }
  // restrained parallax on the photo (transform only, rAF-throttled, passive listener; none for reduced motion)
  let ticking = false;
  const parallax = () => { ticking = false; if (mq.matches) { introImg.style.transform = ''; return; }
    const r = intro.getBoundingClientRect(), vh = window.innerHeight; if (r.bottom < 0 || r.top > vh) return;
    const prog = (vh - r.top) / (vh + r.height); introImg.style.transform = `translate3d(0, ${((prog - 0.5) * 8).toFixed(2)}%, 0)`; };
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(parallax); } };
  const sc0 = scroller(); const scTarget = sc0 === document.scrollingElement ? window : sc0;
  on(scTarget, 'scroll', onScroll, { passive: true });
  requestAnimationFrame(() => { pullUp(); parallax(); updateHeader(); }); on(window, 'resize', () => { pullUp(); parallax(); });
  show(cur);
  const cleanup = () => { clearTimeout(timer); timer = null; root.__swTimerActive = false; io.disconnect(); ioIntro.disconnect(); offs.forEach(f => f()); offs.length = 0;
    vids.forEach(v => { try { v.pause(); } catch (e) {} });
    html.classList.remove('sw-home', 'sw-over-hero'); root.__swCleanup = null; };
  root.__swCleanup = cleanup;
  return cleanup;
}
"""


def _register():
    return st.components.v2.component("saltwise_showcase", html=HTML, css=CSS, js=JS, isolate_styles=True)


_component = _register()


def _mount(**kwargs):
    """Mount the component; re-register first if this Streamlit runtime has not seen it (e.g. a fresh test runtime)."""
    global _component
    from streamlit.errors import StreamlitAPIException
    try:
        return _component(**kwargs)
    except StreamlitAPIException as e:
        if "not registered" not in str(e):
            raise
        _component = _register()
        return _component(**kwargs)


def render(key="home_showcase"):
    """Mount the showcase. Returns the page key to open when an Open button was pressed this run, else None."""
    result = _mount(key=key, data={"slides": SLIDES, "data": slide_data(), "interval_ms": INTERVAL_MS,
                                   "media": media.urls([s["media"] for s in SLIDES] + [INTRO["media"]]), "intro": INTRO},
                    on_open_change=lambda: None)
    target = getattr(result, "open", None) if result is not None else None
    return target if target in OPEN_TARGETS.values() else None
