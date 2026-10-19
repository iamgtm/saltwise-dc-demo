"""Home: "Make every treatment count", a scroll-driven sustainability story below the hero slideshow (st.components.v2).

Four ideas the slideshow does not cover: timing, whole-storm accounting, sensitivity, and missing evidence.
Desktop: short chapters on the left (dashed dividers); a sticky panel on the right shows the matching visual
(IntersectionObserver, no timer, no autoplay). Each visual is layered: a local stock-footage clip (static/media; decorative,
not data) plays behind a sharp foreground graphic. Mobile: each visual sits inside its chapter.
Scrolling and decorative motion run in the browser only: no Python rerun, polling, model call or weather request.
Python hears from the component only when a chapter's button is pressed (trigger "open" -> page key).

Every number comes from the synthetic scenarios and saltwise_contract (compare_plans, sensitivity) via
chapter_data(). Chapter 02 uses a fully specified presentation-layer hypothetical (not a fixture, not a plan).
"""
import copy
from datetime import timedelta

import pandas as pd
import streamlit as st

import media
import saltwise_contract as sc
import scenarios
from data import get_view

OPEN_TARGETS = ("weather", "storm", "evidence")

CHAPTERS = [
    {"id": "timing", "product": "Road Weather", "media": "outlook_storm_clouds", "nav": "Timing",
     "headline": "Timing changes the planning question.",
     "text": "Rain, cooling and a changing road surface rarely line up at one moment. Reading the sequence shows "
             "when concerns overlap and a person should look closer; a single temperature cannot.",
     "button": "Explore Road Weather", "target": "weather"},
    {"id": "whole", "product": "Storm Lab", "media": "stormlab_snowplow", "nav": "Whole storm",
     "headline": "Count the whole storm.",
     "text": "Postponing an application does not save salt by itself. If the road still needs a catch-up round, "
             "the apparent saving from the first round disappears once every round is counted.",
     "button": "Open Storm Lab", "target": "storm"},
    {"id": "sensitivity", "product": "Storm Lab", "media": "weather_road", "nav": "Sensitivity",
     "headline": "Test whether the result holds up.",
     "text": "Hold the plans fixed and vary only the later treatment the scenario might need. The result can "
             "shrink to zero or turn negative, so a reduction is only as strong as that assumption.",
     "button": "Test the assumptions in Storm Lab", "target": "storm"},
    {"id": "evidence", "product": "Evidence", "media": "evidence_bridge", "nav": "Missing evidence",
     "headline": "Missing evidence must not erase a road.",
     "text": "When pavement evidence is unavailable, the road stays visible and stays in assumed service. "
             "The gap calls for more evidence and human review, never a quiet “no treatment”.",
     "button": "Inspect Evidence", "target": "evidence"},
]


def _clock(ts):
    t = pd.Timestamp(ts)
    return t.strftime("%-I %p").lower().replace("am", "a.m.").replace("pm", "p.m.")


def _span(start, end):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    return f"{s.strftime('%a %b %-d')} {_clock(s)} – {e.strftime('%a %b %-d')} {_clock(e)}"


def _window(E, hours):
    return {"start": E.isoformat(), "end": (E + timedelta(hours=hours)).isoformat()}


@st.cache_data
def chapter_data():
    import home
    E = pd.Timestamp(scenarios.SCENARIO_TIME)
    lids = [lid for lid, *_ in scenarios.LOCATIONS]
    names = {lid: name for lid, name, *_ in scenarios.LOCATIONS}

    # 01 Timing: Benning Road bridge synthetic scenario, next 24 h (sequence lanes, no line chart).
    _, v = get_view("benning_rd_bridge", "F", "24h", 0)
    ser = {s["quantity"]: s["points"] for s in v["series"]}
    pav = {p["valid_start"]: p for p in ser.get("pavement_temperature", [])}
    pr = {p["valid_start"]: p for p in ser.get("precipitation", [])}
    rev = {r["valid_start"]: r["concerns"] for r in v["review_periods"]}
    frz = v["freezing_reference"]["value"]
    titles = getattr(sc, "FLAG_TITLES", {})
    hours = []
    for p in ser["air_temperature"]:
        t = p["valid_start"]
        pv = pav.get(t)
        hours.append({"t": _clock(t), "precip": (pr.get(t) or {}).get("description"),
                      "air_above": p["value"] > frz,
                      "surface": pv.get("surface_condition") if pv and pv.get("value") is not None else None,
                      "review": [titles.get(c, c) for c in rev.get(t, [])]})
    timing = {"location": names["benning_rd_bridge"], "freezing": frz, "hours": hours,
              "span": _span(ser["air_temperature"][0]["valid_start"], ser["air_temperature"][-1]["valid_end"])}

    # 02 Whole storm: fully specified hypothetical. Same points, rate, lane-miles and 12 h window for both plans.
    rate, lm = 200.0, {lid: 1.0 for lid in lids}
    t0, catch = E.isoformat(), (E + timedelta(hours=4)).isoformat()
    postponed = lids[:2]
    treat_now = {lid: {"initial": t0, "later": []} for lid in lids}
    postpone = {lid: ({"initial": None, "later": [catch]} if lid in postponed else {"initial": t0, "later": []}) for lid in lids}
    r2 = sc.compare_plans(treat_now, postpone, lm, rate, _window(E, 12))
    whole = {
        "a": {k: r2["baseline"][f"{k}_lb"] for k in ("initial", "later", "total")},
        "b": {k: r2["scenario"][f"{k}_lb"] for k in ("initial", "later", "total")},
        "apparent_first_round": r2["baseline"]["initial_lb"] - r2["scenario"]["initial_lb"],
        "avoided_whole_storm": r2["material_avoided_lb"],
        "assumptions": [
            ["Points", f"{len(lids)} demonstration points, 1 lane-mile each (illustrative)"],
            ["Rate", "200 lb per lane-mile (illustrative, not a DC value)"],
            ["Window (both plans)", f"{_span(E, E + timedelta(hours=12))} (12 h, synthetic time)"],
            ["Treat now", f"All {len(lids)} points at {_clock(E)}"],
            ["Postpone", f"{len(lids) - len(postponed)} points at {_clock(E)}; {len(postponed)} postponed, "
                         f"then a catch-up round at {_clock(catch)}"],
        ],
    }

    # 03 Sensitivity: Storm Lab default plans held fixed; only the scenario's later treatment varies.
    plans = home.default_plans()
    W = _window(E, 12)
    base = sc.compare_plans(plans["baseline"], plans["scenario"], lm, rate, W)
    one_round = rate * sum(lm.values())
    cases = sc.sensitivity(base["baseline"]["total_lb"], base["scenario"]["initial_lb"], one_round)
    k_max = int(max(c["later_lb"] for c in cases) // rate) + 1
    curve = []
    for k in range(k_max + 1):
        sp = copy.deepcopy(plans["scenario"])
        for j in range(k):                                  # k later applications, spread over the points
            lid = lids[j % len(lids)]
            sp[lid] = {**sp[lid], "later": list(sp[lid].get("later", [])) + [(E + timedelta(hours=6 + j // len(lids))).isoformat()]}
        r = sc.compare_plans(plans["baseline"], sp, lm, rate, W)
        curve.append({"later_lb": r["scenario"]["later_lb"], "avoided_lb": r["material_avoided_lb"]})
    sensitivity = {
        "curve": curve,
        "cases": [{"name": c["case"].split(" (")[0], "later_lb": c["later_lb"], "avoided_lb": c["material_avoided_lb"]} for c in cases],
        "break_even_later_lb": base["baseline"]["total_lb"] - base["scenario"]["initial_lb"],
        "assumptions": [
            ["Baseline (fixed)", f"{base['baseline']['total_lb']:,.0f} lb: initial and later rounds at all {len(lids)} points"],
            ["Scenario first round (fixed)", f"{base['scenario']['initial_lb']:,.0f} lb at the flagged points"],
            ["Rate, lane-miles, window (fixed)", "200 lb per lane-mile, 1 per point, 12 h (illustrative)"],
            ["Varied", "Later treatment the scenario needs, in whole application rounds per point"],
        ],
    }

    # 04 Missing evidence: per-location evidence status kept apart from the service assumption.
    roads = []
    for lid in lids:
        _, vv = get_view(lid, "F", "overnight", 0)
        pts = next((s["points"] for s in vv["series"] if s["quantity"] == "pavement_temperature"), [])
        have = sum(1 for p in pts if p.get("value") is not None)
        roads.append({"name": names[lid], "periods": vv["window_hours"], "with_pavement": have,
                      "evidence_flag": any(f["id"] == "evidence_review" for f in (vv["flags"] or [])),
                      "in_service": vv["location_in_assumed_service"]})
    return {"timing": timing, "whole": whole, "sensitivity": sensitivity, "roads": roads}


HTML = '<div data-dcs-root></div>'

CSS = r"""
:host { display:block; }
.dcs { --line:#D9E0E6; --text:#15171C; --muted:#4F5561; --inactive:#6B717C; --accent:#D2560A; --accent-text:#A3420A; --air:#3D6A96;
  color:var(--text); font-family:inherit; }
.bar-top { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px 16px; margin:18px 0 18px; }
.chapnav { display:flex; flex-wrap:wrap; gap:6px 8px; margin:0; padding:0; list-style:none; }
.chapnav button { font:inherit; font-size:14px; color:var(--muted); background:#FFFFFF; border:1px solid var(--line); border-radius:6px; padding:6px 12px; cursor:pointer; }
.chapnav button[aria-current=step] { color:var(--text); border-color:var(--accent); background:#FFF4EC; }
.chapnav .n { font-family:ui-monospace, Menlo, monospace; color:var(--accent-text); margin-right:6px; font-size:12px; }
.grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,2fr); gap:56px; }
.chap { min-height:52vh; display:flex; flex-direction:column; justify-content:center; padding:36px 0; border-top:1px solid var(--line); box-sizing:border-box; }
.chap:last-child { border-bottom:1px solid var(--line); }
.eyebrow { font-family:ui-monospace, Menlo, monospace; letter-spacing:.14em; font-size:13px; color:var(--muted); text-transform:uppercase; }
.eyebrow b { color:var(--accent-text); font-weight:600; }
.chap h3 { font-size:clamp(30px, 2.5vw, 44px); line-height:1.18; letter-spacing:-.025em; font-weight:400; margin:12px 0 12px; scroll-margin-top:120px; color:var(--text); }
.chap p { font-size:clamp(17px, 1.3vw, 20px); line-height:1.6; color:var(--muted); margin:0 0 20px; max-width:34em; }
@media (min-width: 901px) {
  .chap > .eyebrow, .chap > h3, .chap > p, .chap > .tool { opacity:.2; transition:opacity .4s ease; }
  .chap.active > .eyebrow, .chap.active > h3, .chap.active > p, .chap.active > .tool { opacity:1; }
  .chap:focus-within > .eyebrow, .chap:focus-within > h3, .chap:focus-within > p, .chap:focus-within > .tool { opacity:1; }   /* keyboard focus stays readable */
}
.chap h3:focus { outline:none; }
.chap h3:focus-visible { outline:2px solid var(--accent); outline-offset:4px; border-radius:4px; }
.tool { align-self:flex-start; font:inherit; font-size:clamp(15px, 1.05vw, 17px); font-weight:600; color:var(--accent-text); background:none; border:0; padding:4px 0; cursor:pointer;
  display:inline-flex; align-items:center; gap:10px; }
.tool .arr { display:inline-flex; width:28px; height:28px; border-radius:50%; background:var(--accent); color:#1A0B02; align-items:center; justify-content:center; font-size:15px; transition:transform .2s ease; }
.tool:hover .arr { transform:translateX(3px); }
.tool:hover .t { text-decoration:underline; }
button:focus-visible { outline:2px solid var(--accent); outline-offset:3px; border-radius:6px; }
.panel-col { position:relative; }
.panel { position:sticky; top:96px; width:min(100%, calc((100vh - 128px) * 805 / 546)); margin-left:auto; aspect-ratio:805 / 546; display:grid; }
.vis { grid-area:1/1; margin:0; position:relative; container-type:inline-size; border-radius:8px; overflow:hidden; border:1px solid var(--line); background:#0B0F14;
  box-shadow:0 14px 34px rgba(21,23,28,.10); opacity:0; visibility:hidden; z-index:0; transition:opacity .38s ease, visibility 0s linear .4s; }
.vis.on { opacity:1; visibility:visible; z-index:2; transition:opacity .38s ease, visibility 0s; }
.vis.prev { opacity:1; visibility:visible; z-index:1; transition:none; }
.media, .media video, .tint { position:absolute; inset:0; }
.media video { width:100%; height:100%; object-fit:cover; display:block; }
.tint { background:linear-gradient(180deg, rgba(8,12,16,.10), rgba(8,12,16,.32)); }
.fg { --u:calc(100cqi * 0.88 / 735); position:absolute; inset:5% 6% 8%; z-index:2; box-sizing:border-box; background:rgba(255,255,255,.20); border:1px solid rgba(255,255,255,.45);
  -webkit-backdrop-filter:blur(14px) contrast(.45) brightness(1.35); backdrop-filter:blur(14px) contrast(.45) brightness(1.35);
  --muted:#20242B; --line:rgba(21,23,28,.16);
  border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,.12); padding:calc(13 * var(--u)) calc(18 * var(--u)) calc(11 * var(--u)); display:flex; flex-direction:column; overflow:hidden; }
.inline { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); clip-path:inset(50%); white-space:nowrap; margin:0; }
.tag { align-self:flex-start; font-family:ui-monospace, Menlo, monospace; letter-spacing:.08em; font-size:calc(10.5 * var(--u)); color:#7A3108;
  border:1px dashed rgba(122,49,8,.55); background:rgba(255,248,242,.55); border-radius:999px; padding:2px 9px; text-transform:uppercase; margin-bottom:6px; }
.vtitle { font-size:calc(15.5 * var(--u)); font-weight:650; margin:0 0 2px; }
.vsub { font-size:calc(12.5 * var(--u)); color:var(--muted); margin:0 0 6px; }
.cap { font-size:calc(12.5 * var(--u)); color:var(--muted); line-height:1.45; margin-top:auto; padding-top:6px; }
svg.fgsvg { display:block; width:100%; height:auto; overflow:visible; }
.legend { display:flex; flex-wrap:wrap; gap:3px 12px; font-size:calc(12 * var(--u)); margin:0 0 6px; padding:0; list-style:none; }
.legend li { display:flex; align-items:center; gap:5px; }
.sw { display:inline-block; width:13px; height:10px; border-radius:3px; flex:none; border:1px solid rgba(21,23,28,.12); }
.chips { display:flex; flex-wrap:wrap; gap:6px 8px; margin:8px 0 0; }
.chip { font-size:calc(12 * var(--u)); border-radius:999px; padding:3px 10px; border:1px solid var(--line); background:rgba(255,255,255,.34); }
.chip.ok { border-color:#7FA285; background:rgba(242,248,243,.5); color:#24502C; }
.chip.na { border-color:#C4C9D0; border-style:dashed; color:var(--muted); }
.steps { display:flex; flex-direction:column; gap:10px; }
.step h4 { margin:0 0 4px; font-size:calc(12.5 * var(--u)); font-weight:650; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
.brow { display:grid; grid-template-columns:calc(86 * var(--u)) minmax(0,1fr) auto; align-items:center; gap:10px; font-size:calc(13.5 * var(--u)); margin:3px 0; }
.brow .val { font-variant-numeric:tabular-nums; min-width:calc(96 * var(--u)); text-align:right; }
.track { position:relative; height:calc(20 * var(--u)); border-radius:5px; background:rgba(255,255,255,.38); }
.seg { position:absolute; top:0; bottom:0; transform-origin:left center; }
.seg.init { background:var(--accent); border-radius:5px 0 0 5px; }
.seg.later { background:repeating-linear-gradient(135deg, var(--air) 0 6px, #6E8FB3 6px 12px); }
.note { font-size:calc(12.5 * var(--u)); color:#7A3108; background:rgba(255,244,236,.55); border-left:3px solid var(--accent); padding:4px 9px; border-radius:5px; }
.note.zero { color:var(--text); background:rgba(245,246,248,.5); border-left-color:#8A9099; }
table.cases { width:100%; border-collapse:collapse; font-size:calc(12 * var(--u)); margin-top:4px; }
table.cases th { text-align:left; color:var(--muted); font-weight:600; border-bottom:1px solid var(--line); padding:2px 6px; }
table.cases td { border-bottom:1px solid rgba(21,23,28,.10); padding:1px 6px; font-variant-numeric:tabular-nums; }
table.cases td.neg { color:#9B2C12; font-weight:600; }
.cn { display:inline-flex; width:17px; height:17px; border-radius:50%; align-items:center; justify-content:center; font-size:calc(10.5 * var(--u)); font-weight:700;
  background:rgba(255,255,255,.6); border:2px solid var(--text); margin-right:6px; }
.roads { display:flex; flex-direction:column; gap:5px; }
.rhead, .road { display:grid; grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) minmax(0,.8fr); gap:10px; align-items:center; }
.rhead { font-size:calc(11 * var(--u)); font-family:ui-monospace, Menlo, monospace; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:0 10px; }
.road { border:1px solid var(--line); border-radius:8px; padding:5px 10px; background:rgba(255,255,255,.30); font-size:calc(12.5 * var(--u)); }
.road b { font-weight:600; font-size:calc(12.5 * var(--u)); }
.ev { border-radius:6px; padding:3px 8px; background:rgba(242,246,250,.62); border:1px solid rgba(21,23,28,.14); }
.ev.gap { background:repeating-linear-gradient(135deg, rgba(255,255,255,.58) 0 6px, rgba(241,242,244,.38) 6px 12px); border:1px dashed #8A9099; }
.svc { border-radius:6px; padding:3px 8px; background:rgba(242,248,243,.62); border:1px solid #7FA285; color:#24502C; }
.road.flag { border-color:rgba(210,86,10,.55); box-shadow:0 0 0 3px rgba(210,86,10,.08); }
.next { font-size:calc(12 * var(--u)); color:#7A3108; margin-top:2px; grid-column:1 / -1; }
.fg svg text[fill="#4F5561"] { fill:#20242B; }
.fg svg rect[fill="#FFFFFF"] { fill:rgba(255,255,255,.35); }
.fg svg rect[fill="#FBE7DD"] { opacity:.5; }
.fg svg [stroke="#ECEEF1"], .fg svg [stroke="#E3E6EA"], .fg svg [stroke="#D5D9DF"] { stroke:rgba(21,23,28,.16); }
.draw { stroke-dasharray:1; stroke-dashoffset:0; }
.armed .draw { stroke-dashoffset:1; }
.played .draw { transition:stroke-dashoffset 1.4s cubic-bezier(.3,.6,.2,1); stroke-dashoffset:0; }
.armed .grow { transform:scaleX(0); }
.played .grow { transition:transform 1s cubic-bezier(.3,.7,.2,1); transform:scaleX(1); }
.played .grow.later { transition-delay:.8s; }
.armed .fadein { opacity:0; }
.played .fadein { transition:opacity .6s ease .9s; opacity:1; }
@media (max-width: 900px) {
  .grid { display:block; }
  .panel-col { display:none; }
  .chap { min-height:0; padding:28px 0 30px; }
  .chap h3 { font-size:27px; color:var(--text); scroll-margin-top:84px; }
  .chap p { font-size:17px; }
  .chap p { color:var(--muted); }
  .inline { container-type:inline-size; position:relative; width:auto; height:auto; overflow:hidden; clip:auto; clip-path:none; white-space:normal; display:block;
    margin:0 0 16px; border-radius:8px; border:1px solid var(--line); background:#0B0F14; }
  .inline .fg { --u:1px; position:relative; inset:auto; margin:20px 12px 20px; padding:12px 12px 10px; }
  .inline svg.fgsvg text { font-size:17px; }
  .brow { grid-template-columns:70px minmax(0,1fr) auto; }
  .rhead { display:none; }
  .road { grid-template-columns:1fr; gap:4px; }
}
.reduced * { transition:none !important; }
"""

JS = r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector('[data-dcs-root]');
  if (!root) return;
  if (root.__dcsCleanup) root.__dcsCleanup();
  const C = data.chapters, D = data.data, M = data.media, N = C.length;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const fmt = n => (n < 0 ? '−' : '') + Math.round(Math.abs(n)).toLocaleString('en-US');
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');

  // ---------- background footage (decorative, never data): lazy src, only the visible active clip plays ----------
  const frame = c => `<div class="media" aria-hidden="true"><video muted loop playsinline preload="none" disablepictureinpicture poster="${esc(M[c.media].poster)}" data-src="${esc(M[c.media].src)}"></video><div class="tint"></div></div>
`;

  // ---------- 01 timing: sequence lanes ----------
  function timing() {
    const T = D.timing, H = T.hours, n = H.length, W = 560, L = 4, R = 4, cw = (W - L - R) / n;
    const x = i => L + i * cw;
    const pc = d => !d ? '#FFFFFF' : /snow/i.test(d) && /rain/i.test(d) ? '#9DB6D2' : /snow/i.test(d) ? '#DCE6F2' : '#3D6A96';
    const SURF = ['#C9DCEF', '#7FA3C7', '#2F4E70', '#E8EEF4'];
    const surfaces = [...new Set(H.map(h => h.surface).filter(Boolean))];
    const sc = s => s ? SURF[surfaces.indexOf(s) % SURF.length] : 'url(#HATCH)';
    const lane = (y, f, label) => `<text x="${L}" y="${y - 5}" font-size="12" fill="#4F5561">${label}</text>` +
      H.map((h, i) => `<rect x="${x(i) + .6}" y="${y}" width="${cw - 1.2}" height="18" rx="3" ${f(h)} />`).join('');
    const rv = H.map((h, i) => h.review.length ? `<path class="fadein" d="M${x(i) + cw / 2} 168 l6 11 h-12z" fill="#D2560A"/>` : '').join('');
    const ticks = H.map((h, i) => i % 6 === 0 ? `<text x="${i ? x(i) : x(0)}" y="214" font-size="12" fill="#4F5561" text-anchor="${i ? 'middle' : 'start'}">${esc(h.t)}</text>` : '').join('');
    const precips = [...new Set(H.map(h => h.precip).filter(Boolean))];
    const firstReview = H.findIndex(h => h.review.length);
    return `<span class="tag">Illustrative sequence · synthetic scenario</span>
      <p class="vtitle">${esc(T.location)} scenario: how one storm unfolds</p>
      <p class="vsub">Valid ${esc(T.span)} · synthetic scenario time · hourly periods</p>
      <ul class="legend" aria-label="Sequence key">${precips.map(p => `<li><span class="sw" style="background:${pc(p)}"></span>${esc(p)}</li>`).join('')}
        <li><span class="sw" style="background:#F4C7A1"></span>Air above ${T.freezing} °F</li><li><span class="sw" style="background:#7D8896"></span>Air at or below ${T.freezing} °F</li>
        ${surfaces.map(s => `<li><span class="sw" style="background:${sc(s)}"></span>Surface: ${esc(s.toLowerCase())}</li>`).join('')}
        <li><span class="sw" style="background:repeating-linear-gradient(135deg,#fff 0 3px,#C4C9D0 3px 6px)"></span>Surface evidence unavailable</li>
        <li><svg viewBox="0 0 12 11" width="12" height="11"><path d="M6 0 l6 11 h-12z" fill="#D2560A"/></svg>Period for human review</li></ul>
      <svg class="fgsvg" viewBox="0 0 ${W} 220" role="img" aria-label="Synthetic ${esc(T.location)} sequence: ${esc(precips.join(', then '))}; air falls to or below freezing; surface changes; ${H.filter(h => h.review.length).length} periods flagged for human review.">
        <defs><pattern id="HATCH" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#FFFFFF"/><line x1="0" y1="0" x2="0" y2="6" stroke="#C4C9D0" stroke-width="3"/></pattern></defs>
        ${lane(18, h => `fill="${pc(h.precip)}" stroke="#E3E6EA"`, 'Precipitation')}
        ${lane(62, h => `fill="${h.air_above ? '#F4C7A1' : '#7D8896'}"`, `Air vs ${T.freezing} °F`)}
        ${lane(106, h => `fill="${sc(h.surface)}" stroke="#E3E6EA"`, 'Surface (synthetic)')}
        <text x="${L}" y="145" font-size="12" fill="#4F5561">Human review</text>
        <line x1="${L}" x2="${W - R}" y1="158" y2="158" stroke="#E3E6EA"/>
        ${H.map((h, i) => h.review.length ? `<rect class="fadein" x="${x(i) + .6}" y="150" width="${cw - 1.2}" height="16" rx="3" fill="#FFE3CF"/>` : '').join('')}
        ${rv}<line x1="${L}" x2="${W - R}" y1="194" y2="194" stroke="#D5D9DF"/>${ticks}</svg>
      <div class="cap">${firstReview >= 0 ? `Review periods begin at ${esc(H[firstReview].t)}, after rain, cooling and a surface change have started to overlap. ` : ''}Illustrative only: not treatment timing, a threshold or an automatic decision.</div>`;
  }

  // ---------- 02 whole storm: first round vs every round ----------
  function whole() {
    const S = D.whole, a = S.a, b = S.b, max = Math.max(a.total, b.total) || 1, pct = v => (100 * v / max).toFixed(2) + '%';
    const row = (lbl, init, later, val) => `<div class="brow"><span>${lbl}</span><div class="track">
        <div class="seg init grow" style="left:0;width:${pct(init)}"></div>${later ? `<div class="seg later grow" style="left:${pct(init)};width:${pct(later)}"></div>` : ''}</div><span class="val">${val}</span></div>`;
    return `<span class="tag">Hypothetical example · synthetic · not a plan</span>
      <p class="vtitle">Postponing is not the same as saving</p>
      <ul class="legend"><li><span class="sw" style="background:#D2560A"></span>Initial round</li><li><span class="sw" style="background:repeating-linear-gradient(135deg,#3D6A96 0 3px,#6E8FB3 3px 6px)"></span>Later / catch-up round</li></ul>
      <div class="steps" role="img" aria-label="First round only: treat now ${fmt(a.initial)} lb, postpone ${fmt(b.initial)} lb. Whole storm: treat now ${fmt(a.total)} lb, postpone ${fmt(b.initial)} plus ${fmt(b.later)} catch-up equals ${fmt(b.total)} lb; ${fmt(S.avoided_whole_storm)} lb avoided.">
        <div class="step"><h4>1 · First round only (not a total)</h4>
          ${row('Treat now', a.initial, 0, fmt(a.initial) + ' lb')}${row('Postpone', b.initial, 0, fmt(b.initial) + ' lb')}
          <div class="note">Looks like ${fmt(S.apparent_first_round)} lb less, but the storm is not over.</div></div>
        <div class="step"><h4>2 · Whole storm (every round counted)</h4>
          ${row('Treat now', a.initial, a.later, fmt(a.total) + ' lb')}${row('Postpone', b.initial, b.later, `${fmt(b.initial)} + ${fmt(b.later)} = ${fmt(b.total)} lb`)}
          <div class="note zero">Whole-storm difference: ${fmt(S.avoided_whole_storm)} lb avoided. The apparent saving was a delay.</div></div></div>
      <div class="chips"><span class="chip ok">Arithmetic complete: every application in this example is counted</span>
        <span class="chip na">Weather evidence: not assessed (hypothetical)</span></div>
      <div class="cap">Hypothetical: ${esc(S.assumptions.map(([k, v]) => v).slice(0, 2).join('; '))}; postponed points get one catch-up round.</div>`;
  }

  // ---------- 03 sensitivity: net avoided vs assumed later treatment ----------
  function sensitivity() {
    const S = D.sensitivity, cv = S.curve, W = 560, H = 158, L = 76, R = 14, T = 6, B = 24;
    const xs = cv.map(p => p.later_lb).concat(S.cases.map(c => c.later_lb)), ys = cv.map(p => p.avoided_lb).concat(S.cases.map(c => c.avoided_lb), [0]);
    const x0 = 0, x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const pad = (y1 - y0) * .08, lo = y0 - pad, hi = y1 + pad;
    const PADX = 22;   // keep case markers clear of the y-axis labels
    const x = v => L + PADX + (v - x0) * (W - L - R - 2 * PADX) / (x1 - x0 || 1), y = v => T + (hi - v) * (H - T - B) / (hi - lo || 1);
    const step = Math.max(200, Math.round((x1 / 4) / 200) * 200), yt = Math.max(200, Math.round(((hi - lo) / 4) / 200) * 200);
    const xT = []; for (let v = 0; v <= x1 + 1; v += step) xT.push(v);
    const yT = []; for (let v = Math.ceil(lo / yt) * yt; v <= hi; v += yt) yT.push(v);
    const line = cv.map(p => `${x(p.later_lb).toFixed(1)},${y(p.avoided_lb).toFixed(1)}`).join(' ');
    const neg = `<rect x="${L}" y="${y(0)}" width="${W - L - R}" height="${y(lo) - y(0)}" fill="#FBE7DD" opacity=".75"/>`;
    const marks = S.cases.map((c, i) => `<g class="fadein"><circle cx="${x(c.later_lb)}" cy="${y(c.avoided_lb)}" r="9" fill="#FFFFFF" stroke="#15171C" stroke-width="2"/>
      <text x="${x(c.later_lb)}" y="${y(c.avoided_lb) + 4}" font-size="11" font-weight="700" text-anchor="middle" fill="#15171C">${i + 1}</text></g>`).join('');
    return `<span class="tag">Accounting sensitivity · synthetic · not a prediction</span>
      <p class="vtitle">Net material avoided as the assumed later treatment grows</p>
      <ul class="legend"><li><svg viewBox="0 0 26 12" width="26" height="12"><line x1="0" y1="6" x2="26" y2="6" stroke="#D2560A" stroke-width="3"/></svg>Net avoided vs baseline (lb, y) by assumed later treatment (lb, x)</li>
        <li><span class="sw" style="background:#FBE7DD"></span>Below zero: the scenario uses more</li><li><span class="cn" style="width:14px;height:14px;font-size:9px">1</span>Storm Lab sensitivity cases</li></ul>
      <svg class="fgsvg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Net avoided falls from ${fmt(cv[0].avoided_lb)} lb with no later treatment to ${fmt(cv[cv.length - 1].avoided_lb)} lb at ${fmt(cv[cv.length - 1].later_lb)} lb later treatment; zero at ${fmt(S.break_even_later_lb)} lb.">
        ${neg}${yT.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${v === 0 ? '#8A9099' : '#ECEEF1'}" ${v === 0 ? 'stroke-width="1.5"' : ''}/><text x="${L - 8}" y="${y(v) + 4}" font-size="12" fill="#4F5561" text-anchor="end">${fmt(v)}</text>`).join('')}
        ${xT.map((v, i) => `<text x="${x(v)}" y="${H - 6}" font-size="12" fill="#4F5561" text-anchor="${i ? 'middle' : 'start'}">${fmt(v)}</text>`).join('')}
        <polyline class="draw" pathLength="1" points="${line}" fill="none" stroke="#D2560A" stroke-width="3" stroke-linejoin="round"/>${marks}</svg>
      <table class="cases"><thead><tr><th>Case</th><th>Later (lb)</th><th>Net avoided (lb)</th></tr></thead><tbody>
        ${S.cases.map((c, i) => `<tr><td><span class="cn">${i + 1}</span>${esc(c.name)}</td><td>${fmt(c.later_lb)}</td><td class="${c.avoided_lb < 0 ? 'neg' : ''}">${fmt(c.avoided_lb)}</td></tr>`).join('')}</tbody></table>
      <div class="cap">Each extra 200 lb of later treatment cancels 200 lb of apparent avoidance; nothing is avoided at ${fmt(S.break_even_later_lb)} lb. Plans, rate and window held fixed.</div>`;
  }

  // ---------- 04 missing evidence: evidence kept apart from the service assumption ----------
  function evidence() {
    const rows = D.roads.map(r => {
      const gap = r.with_pavement < r.periods;
      return `<div class="road ${gap ? 'flag' : ''}"><b>${esc(r.name)}</b>
        <span class="ev ${gap ? 'gap' : ''}">${gap ? `${r.with_pavement} of ${r.periods} periods; ${r.periods - r.with_pavement} unavailable` : `All ${r.periods} periods`}</span>
        <span class="svc">${r.in_service ? 'In assumed service' : 'Not in assumed service'}</span>
        ${gap ? '<span class="next">Next step: more evidence and human review. Missing is not zero and never “no treatment”.</span>' : ''}</div>`;
    }).join('');
    return `<span class="tag">Schematic · synthetic scenarios · not a map or live status</span>
      <p class="vtitle">Evidence and service are tracked separately</p>
      <p class="vsub">Overnight window (12 periods) · demonstration points, locations not yet verified</p>
      <div class="roads"><div class="rhead"><span>Road</span><span>Pavement evidence</span><span>Service assumption</span></div>${rows}</div>
      <div class="cap">An evidence gap changes what a person checks next; it never removes a road from the plan or the totals.</div>`;
  }

  const ART = { timing, whole, sensitivity, evidence };
  const fig = c => `${frame(c)}<div class="fg">${ART[c.id]()}</div>`;
  const uid = 'dc' + Math.random().toString(36).slice(2, 7);
  root.innerHTML = `<section class="dcs" aria-label="Make every treatment count">
    <div class="bar-top"><ul class="chapnav" aria-label="Jump to a chapter">${C.map((c, i) => `<li><button type="button" data-go="${i}"><span class="n">0${i + 1}</span>${esc(c.nav)}</button></li>`).join('')}</ul></div>
    <div class="grid">
      <div class="chapters">${C.map((c, i) => `<article class="chap" data-i="${i}" aria-labelledby="${uid}-c${i}">
          <div class="eyebrow"><b>0${i + 1}</b> · SaltWise ${esc(c.product)}</div>
          <h3 id="${uid}-c${i}" tabindex="-1">${esc(c.headline)}</h3><p>${esc(c.text)}</p>
          <figure class="inline" data-v="${i}" aria-label="${esc(c.headline)} (visual)">${fig(c)}</figure>
          <button type="button" class="tool" data-target="${c.target}"><span class="t">${esc(c.button)}</span><span class="arr" aria-hidden="true">→</span></button></article>`).join('')}</div>
      <div class="panel-col" aria-hidden="true"><div class="panel">${C.map((c, i) => `<figure class="vis" data-v="${i}">${fig(c)}</figure>`).join('')}</div></div>
    </div></section>`;

  const sec = root.querySelector('.dcs'), chaps = [...root.querySelectorAll('.chap')];
  const panelVis = [...root.querySelectorAll('.panel .vis')], inlineVis = [...root.querySelectorAll('.inline')];
  const navBtns = [...root.querySelectorAll('.chapnav button')];
  const offs = [], on = (el, ev, fn, o) => { el.addEventListener(ev, fn, o); offs.push(() => el.removeEventListener(ev, fn, o)); };
  let cur = -1, panelShown = false;
  const mqMobile = window.matchMedia('(max-width: 900px)');
  function applyMotion() {
    sec.classList.toggle('reduced', mq.matches);
    [...panelVis, ...inlineVis].forEach(v => { if (mq.matches) { v.classList.remove('armed'); v.classList.add('played'); } else if (!v.classList.contains('played')) v.classList.add('armed'); });
  }
  function play(v) {
    if (!v || v.classList.contains('played')) return;
    void v.getBoundingClientRect();
    requestAnimationFrame(() => { v.classList.add('played'); v.classList.remove('armed'); });
  }
  function activate(i) {
    if (i === cur || i < 0) return;
    const old = panelVis[cur];
    cur = i;
    chaps.forEach((c, k) => c.classList.toggle('active', k === i));
    navBtns.forEach((b, k) => k === i ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current'));
    const nv = panelVis[i];
    panelVis.forEach(v => { if (v !== nv && v !== old) v.classList.remove('on', 'prev'); });
    if (old && old !== nv) {                       // incoming fades in on top of the outgoing one: no blank frame
      old.classList.remove('on'); old.classList.add('prev');
      const done = () => { old.classList.remove('prev'); nv.removeEventListener('transitionend', done); };
      if (mq.matches) done(); else nv.addEventListener('transitionend', done);
    }
    nv.classList.add('on'); nv.classList.remove('prev');
    if (panelShown) play(nv);
    syncVideos();
  }
  function ctl(fig, want) { const v = fig.querySelector('video'); if (!v) return;
    if (want) { if (!v.getAttribute('src')) { v.src = v.dataset.src; v.preload = 'auto'; } const p = v.play(); if (p) p.catch(() => {}); }
    else if (!v.paused) v.pause(); }
  function syncVideos() { const ok = !document.hidden && !mq.matches, mob = mqMobile.matches;
    panelVis.forEach((f, k) => ctl(f, ok && !mob && panelShown && k === cur));
    inlineVis.forEach(f => ctl(f, ok && mob && f.__half)); }
  const io = new IntersectionObserver(es => { es.forEach(e => { if (e.isIntersecting) activate(+e.target.dataset.i); }); },
                                      { rootMargin: '-45% 0px -54% 0px', threshold: 0 });
  chaps.forEach(c => io.observe(c));
  // backgrounds run only while their frame is on screen
  const ioRun = new IntersectionObserver(es => { es.forEach(e => { e.target.classList.toggle('run', e.isIntersecting); e.target.__half = e.intersectionRatio >= 0.5; }); syncVideos(); }, { threshold: [0, 0.5, 1] });
  const pc = root.querySelector('.panel');
  ioRun.observe(pc); inlineVis.forEach(v => ioRun.observe(v));
  const io2 = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) play(e.target); }), { threshold: 0.35 });
  inlineVis.forEach(v => io2.observe(v));
  navBtns.forEach((b, k) => on(b, 'click', () => {
    const h = chaps[k].querySelector('h3');
    h.scrollIntoView({ behavior: mq.matches ? 'auto' : 'smooth', block: 'center' });
    h.focus({ preventScroll: true }); activate(k);
  }));
  on(document, 'visibilitychange', () => { sec.classList.toggle('tabhidden', document.hidden); syncVideos(); });
  root.querySelectorAll('.tool').forEach(b => on(b, 'click', () => setTriggerValue('open', b.dataset.target)));
  on(mq, 'change', () => { applyMotion(); syncVideos(); });
  on(mqMobile, 'change', syncVideos);
  applyMotion();
  const line = window.innerHeight * 0.45;
  let best = 0, bd = Infinity;
  chaps.forEach((c, k) => { const r = c.getBoundingClientRect(); const d = r.top > line ? r.top - line : (r.bottom < line ? line - r.bottom : 0); if (d < bd) { bd = d; best = k; } });
  activate(best);
  const vis = new IntersectionObserver(es => es.forEach(e => { panelShown = e.isIntersecting; if (panelShown && cur >= 0) play(panelVis[cur]); syncVideos(); }), { threshold: 0.2 });
  vis.observe(pc);
  const cleanup = () => { [...panelVis, ...inlineVis].forEach(f => { const v = f.querySelector('video'); if (v) try { v.pause(); } catch (e) {} });
    io.disconnect(); io2.disconnect(); ioRun.disconnect(); vis.disconnect(); offs.forEach(f => f()); offs.length = 0; root.__dcsCleanup = null; };
  root.__dcsCleanup = cleanup;
  return cleanup;
}
"""


def _register():
    return st.components.v2.component("saltwise_dc_showcase", html=HTML, css=CSS, js=JS, isolate_styles=True)


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


def render(key="home_dc_showcase"):
    """Mount the chapter showcase. Returns the page key to open when a chapter button was pressed this run, else None."""
    result = _mount(key=key, data={"chapters": CHAPTERS, "data": chapter_data(), "media": media.urls([c["media"] for c in CHAPTERS])},
                    on_open_change=lambda: None)
    target = getattr(result, "open", None) if result is not None else None
    return target if target in OPEN_TARGETS else None
