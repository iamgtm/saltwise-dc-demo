"""Road Weather map: the five registered demonstration points on the DCGIS District boundary, with their review flags.

Presentation only. Every marker, flag and value comes from the views the page already built (saltwise_contract /
evidence_snapshot) and from the read-only location registry; nothing here computes weather or applies a rule. The
boundary is the existing DCGIS asset (Web Mercator, north up); points use the same projection. No tiles, no streets,
no network: pan, zoom, hover and clicks use data already on the page. A point without registry coordinates is listed,
never placed. Hiding a layer changes the display only; every road stays in service assumptions, charts and Storm Lab.
"""
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
TZ_NOTE = "America/New_York (ET)"

# Marker categories. "flag" names the existing rule (saltwise_contract.FLAG_TITLES) a category shows; categories with
# flag None and status "not_defined" have no SaltWise rule yet, so no location is ever assigned to them.
CATEGORIES = [
    {"id": "treatment_review", "label": "Treatment review", "flag": "treatment_review", "color": "#FF9A57", "shape": "triangle",
     "meaning": "Pavement at or below the physical freezing reference with a wet, slush, snow or ice surface in a displayed period.",
     "evidence": "Modeled pavement temperature and surface state (provider or synthetic). Illustrative rule, not policy."},
    {"id": "refreeze_review", "label": "Refreeze risk", "flag": "refreeze_review", "color": "#8FD3FF", "shape": "diamond",
     "meaning": "After a wet surface, pavement reaches the physical freezing reference.",
     "evidence": "Modeled pavement temperature and surface state. Illustrative rule, not policy."},
    {"id": "rain_timing_review", "label": "Rain-timing review", "flag": "rain_timing_review", "color": "#C3B2FF", "shape": "drop",
     "meaning": "Rain is forecast before snow; rain may dilute or wash off pre-treatment. DPW already weighs this.",
     "evidence": "Forecast precipitation text and probability. Illustrative rule, not policy."},
    {"id": "evidence_review", "label": "Obtain surface evidence", "flag": "evidence_review", "color": "#F4D35E", "shape": "question",
     "meaning": "Pavement evidence is missing, withheld or ends inside the window. Missing evidence never means no treatment.",
     "evidence": "Coverage, freshness, road-match and data checks on the returned series."},
    {"id": "no_flag", "label": "No current salt indication", "flag": None, "color": "#C4C9D0", "shape": "ring",
     "meaning": "No review flag in the selected window. This is not a statement that treatment is unnecessary or that the road "
                "is safe; conditions beyond the shown evidence are unknown.",
     "evidence": "Absence of review flags for the displayed evidence only."},
    {"id": "cold_material", "label": "Cold-material review", "flag": None, "color": "#8A939E", "shape": "none", "status": "not_defined",
     "meaning": "Not defined in SaltWise yet: there is no rule for material performance in cold, so no location is shown in "
                "this category.", "evidence": "None. A rule would need agreed inputs first."},
    {"id": "monitor", "label": "Monitor", "flag": None, "color": "#8A939E", "shape": "none", "status": "not_defined",
     "meaning": "Not defined in SaltWise yet: there is no monitoring rule, so no location is shown in this category.",
     "evidence": "None. A rule would need agreed inputs first."},
]
PRIORITY = ["treatment_review", "refreeze_review", "rain_timing_review", "evidence_review"]
LAYERS = [("flags", "Review markers", "Shape and color by review flag. Off: plain location dots; no road is removed."),
          ("temps", "Pavement-temperature labels", "Selected-period pavement value beside each point, where one exists."),
          ("names", "Location names", "Short names beside each point.")]


def boundary():
    b = json.loads((HERE / "assets" / "dc_boundary.json").read_text())
    return b


def _merc(lon, lat):
    return math.radians(lon) * 6378137.0, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137.0


def project(lat, lon, b=None):
    """Registry lat/lon to the boundary's view box (same Web Mercator frame as dc_boundary.json; north up)."""
    b = b or boundary()
    x0, y0, x1, y1 = b["processing"]["bbox_wgs84"]
    (mx0, my0), (mx1, my1) = _merc(x0, y0), _merc(x1, y1)
    s = b["view_box"][2] / (mx1 - mx0)
    mx, my = _merc(lon, lat)
    return round((mx - mx0) * s, 2), round((my1 - my) * s, 2)


def registry_points():
    """{location_id: registry entry with x, y} from the read-only registry; {} if it cannot be read (points are then listed)."""
    import evidence_snapshot as es
    try:
        reg = json.loads(es.registry_path().read_text())
    except (OSError, ValueError):
        return {}
    b, out = boundary(), {}
    for loc in reg.get("locations", []):
        lat, lon = loc.get("lat"), loc.get("lon")
        x, y = project(lat, lon, b) if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else (None, None)
        out[loc["id"]] = {"x": x, "y": y, "geographic_status": loc.get("geographic_status") or "unknown", "name": loc.get("name")}
    return out


def _period(points, t):
    for p in points:
        if pd.Timestamp(p["valid_start"]) <= t < pd.Timestamp(p["valid_end"]):
            return p
    return None


def _fmt(v, unit):
    return None if v is None else f"{v:.1f}°{unit}"


def location_card(lid, short, view, status, reg, t, units, provider, tfmt):
    """Card content for one location from its existing view. No value is created; missing ones carry their reason."""
    U = "F" if units == "F" else "C"
    by = {s["quantity"]: s for s in view["series"]}
    flags = [{"id": f["id"], "title": f["title"], "time": tfmt(f["valid_time"]) if f.get("valid_time") else "",
              "reason": f.get("reason") or "", "next": f.get("next_step") or ""} for f in (view["flags"] or [])]
    ids = [f["id"] for f in flags]
    cat = next((c for c in PRIORITY if c in ids), "no_flag")
    withheld = "; ".join(w["reason"] for w in view.get("withheld") or []) or None

    def read(q):
        s = by.get(q)
        p = _period(s["points"], t) if s else None
        if not s or not p or p.get("value") is None:
            why = (withheld if q == "pavement_temperature" and withheld else
                   "No value for the selected period (outside the returned horizon or missing)." if s else "Not supplied by this source.")
            return {"value": None, "text": "Unavailable", "why": why, "kind": "unavailable", "source": s["source"] if s else None}
        return {"value": p["value"], "text": _fmt(p["value"], U) if q != "precipitation" else None, "kind": p.get("kind", s["kind"]),
                "source": s["source"], "valid": f"{tfmt(p['valid_start'])} – {tfmt(p['valid_end'])}", "freshness": p.get("freshness"),
                "surface": p.get("surface_condition"), "description": p.get("description")}

    pav, air, pr = read("pavement_temperature"), read("air_temperature"), read("precipitation")
    if pr.get("kind") != "unavailable":
        pr["text"] = ", ".join(x for x in (pr.get("description") or "No precipitation named",
                                            f"{pr['value']:.0f}% chance" if pr.get("value") is not None else None) if x)
    if provider:
        evidence = {"pavement": "Modeled pavement (Xweather; provider model, not a sensor)" if pav["value"] is not None else "Unavailable",
                    "air": "Provider forecast (NWS)" if air["value"] is not None else "Unavailable"}
        statuses = [("Geographic verification", status["geo_label"]), ("Provider road match", status["road_label"]
                     + (f" (Xweather: {status['provider_road']})" if status.get("provider_road") else ""))]
        if status.get("is_bridge"):
            statuses.append(("Bridge-specific modeling", status["bridge_label"]))
    else:
        evidence = {"pavement": "Synthetic scenario (illustrative modeled-pavement shape)" if pav["value"] is not None else "Unavailable",
                    "air": "Synthetic scenario (illustrative NWS-shaped forecast)" if air["value"] is not None else "Unavailable"}
        rm = view["location"]["road_match"]
        statuses = [("Registry point", {"verified": "DCGIS-verified coordinate", "partial": "Partially verified coordinate"}.get(
                         (reg or {}).get("geographic_status"), "No registry coordinate") if reg else "No registry coordinate"),
                    ("Road identity", f"{rm['returned_name']}: values are a synthetic scenario, not tied to this road")]
    first = flags[0] if flags else None
    return {
        "id": lid, "name": view["location"]["name"], "short": short, "category": cat, "flags": flags,
        "x": (reg or {}).get("x"), "y": (reg or {}).get("y"),
        "partial": (reg or {}).get("geographic_status") == "partial",
        "unmatched": bool(provider and status and status.get("pavement_reason")),
        "period": tfmt(t.isoformat()), "tz": TZ_NOTE, "units": f"°{U}",
        "pavement": pav, "air": air, "precip": pr,
        "wind": {"text": "Unavailable", "why": "Not supplied by the sources SaltWise uses for this view."},
        "dew": {"text": "Unavailable", "why": "Not supplied by the sources SaltWise uses for this view."},
        "evidence": evidence, "statuses": statuses, "synthetic": not provider,
        "explain": first["reason"] if first else ("No review flags in the selected window. This is not a statement that treatment "
                                                  "is unnecessary; conditions beyond the shown evidence are unknown."),
        "next": first["next"] if first else "Keep watching the forecast; confirm conditions in the field before deciding.",
        "label": f"{pav['text']}" if pav["value"] is not None else "n/a",
    }


def map_data(entries, selected, units, t, provider, tfmt, compact=False):
    """entries: [(location_id, short, view, provider_status_or_None)] in registry order."""
    reg = registry_points()
    b = boundary()
    locs = [location_card(lid, short, view, status, reg.get(lid), t, units, provider, tfmt) for lid, short, view, status in entries]
    return {"boundary": {"view_box": b["view_box"], "path": b["path"]}, "categories": CATEGORIES, "layers": LAYERS,
            "locations": locs, "selected": selected, "provider": provider, "compact": compact,
            "mode_note": ("Provider evidence from saved snapshots · modeled pavement only at road-matched points" if provider else
                          "Synthetic scenario values at registered points · illustrative, not live weather"),
            "credit": "District boundary: DCGIS / Open Data DC (OCTO). Points: SaltWise location registry. No streets drawn."}


HTML = '<div class="rm" data-rm-root></div>'

CSS = r"""
:host { display:block; }
.rm { --bg:#0E1620; --line:rgba(255,255,255,.14); --txt:#F2F4F6; --mut:#B8C1CC; font:15px/1.45 "Source Sans 3","Source Sans Pro",system-ui,sans-serif; color:var(--txt); }
.card { position:relative; border-radius:16px; overflow:hidden; border:1px solid var(--line);
  background:radial-gradient(ellipse 70% 60% at 50% 40%, #1A2733 0%, #0E1620 70%); box-shadow:0 18px 50px rgba(14,22,32,.28); }
.card.pre { opacity:0; transform:translateY(10px); }
.card.in { animation:cardIn .6s cubic-bezier(.2,.7,.2,1) both; }
@keyframes cardIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
.top { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:1px solid var(--line); }
.mode { font:600 12px/1.3 ui-monospace,Menlo,monospace; letter-spacing:.08em; text-transform:uppercase; color:#FFD3B0; }
.zoom { display:flex; gap:6px; }
.btn { font:inherit; font-size:14px; color:var(--txt); background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.28); border-radius:8px; padding:5px 10px; cursor:pointer; }
.btn:hover { background:rgba(255,255,255,.16); }
button:focus-visible, summary:focus-visible, input:focus-visible { outline:3px solid #FFFFFF; outline-offset:2px; box-shadow:0 0 0 6px rgba(255,154,87,.55); }
.stage { position:relative; height:540px; overflow:hidden; touch-action:none; cursor:grab; }
.stage.drag { cursor:grabbing; }
.layer { position:absolute; left:50%; top:50%; width:var(--w); height:var(--h); margin-left:calc(var(--w) / -2); margin-top:calc(var(--h) / -2);
  transform:translate(var(--tx,0px), var(--ty,0px)) scale(var(--z,1)); transform-origin:50% 50%; transition:transform .25s ease; }
.stage.drag .layer { transition:none; }
.layer svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
.mk { position:absolute; width:34px; height:34px; margin:-17px 0 0 -17px; padding:0; border:0; background:none; cursor:pointer; color:inherit;
  transform:scale(calc(1 / var(--z,1))); border-radius:50%; }
.mk .halo { position:absolute; inset:-14px; border-radius:50%; background:radial-gradient(circle, var(--c) 0%, rgba(0,0,0,0) 68%); opacity:.30; transition:opacity .3s, inset .3s; }
.mk svg.sym { position:absolute; inset:5px; width:24px; height:24px; overflow:visible; filter:drop-shadow(0 1px 2px rgba(0,0,0,.6)); }
.mk.sel .halo { inset:-24px; opacity:.6; }
.mk.sel::after { content:""; position:absolute; inset:-5px; border-radius:50%; border:2px solid #FFFFFF; }
.mk.pre { opacity:0; transform:scale(calc(.4 / var(--z,1))); }
.mk.in { animation:mkIn .5s cubic-bezier(.2,.8,.2,1.2) both; animation-delay:var(--d); }
@keyframes mkIn { from { opacity:0; transform:scale(calc(.4 / var(--z,1))); } to { opacity:1; transform:scale(calc(1 / var(--z,1))); } }
.mk .more { position:absolute; right:-8px; top:-8px; min-width:18px; height:18px; padding:0 4px; border-radius:9px; background:#FFFFFF; color:#0E1620;
  font:700 11px/18px system-ui,sans-serif; }
.mk .tag { position:absolute; left:30px; top:50%; transform:translateY(-50%); white-space:nowrap; font-size:13px; line-height:1.25; text-align:left;
  background:rgba(14,22,32,.78); border:1px solid rgba(255,255,255,.18); border-radius:6px; padding:2px 6px; pointer-events:none; }
.mk .tag b { font-weight:600; } .mk .tag span { color:#FFD3B0; }
.mk.plain .halo { display:none; }
.legend { position:absolute; left:14px; top:14px; z-index:3; width:min(300px, calc(100% - 28px)); max-height:calc(100% - 28px); overflow:auto;
  background:rgba(22,32,42,.62); -webkit-backdrop-filter:blur(10px) saturate(1.2); backdrop-filter:blur(10px) saturate(1.2);
  border:1px solid rgba(255,255,255,.18); border-radius:14px; box-shadow:0 8px 24px rgba(0,0,0,.25); }
.legend.pre { opacity:0; transform:translateX(-12px); }
.legend.in { animation:lgIn .55s ease-out both; animation-delay:.25s; }
@keyframes lgIn { from { opacity:0; transform:translateX(-12px); } to { opacity:1; transform:none; } }
.lg-h { display:flex; align-items:center; justify-content:space-between; gap:8px; width:100%; font:600 14px/1.3 inherit; font-family:inherit;
  color:var(--txt); background:none; border:0; padding:10px 12px; cursor:pointer; text-align:left; }
.lg-h .chev { transition:transform .2s; } .legend.closed .chev { transform:rotate(-90deg); }
.legend.closed .lg-b { display:none; }
.lg-b { padding:0 12px 12px; }
.lg-b details { border-top:1px solid rgba(255,255,255,.10); }
.lg-b summary { display:flex; align-items:center; gap:8px; padding:6px 0; cursor:pointer; list-style:none; font-size:14px; }
.lg-b summary::-webkit-details-marker { display:none; }
.lg-b summary .n { margin-left:auto; color:var(--mut); font-size:12px; }
.lg-b details p { margin:0 0 8px 26px; color:#DCE2E8; font-size:13px; }
.lg-b .nd { color:var(--mut); }
.lg-sub { margin:10px 0 4px; font:600 11px/1.2 ui-monospace,Menlo,monospace; letter-spacing:.1em; text-transform:uppercase; color:var(--mut); }
.lg-b label { display:flex; gap:8px; align-items:flex-start; font-size:14px; padding:3px 0; cursor:pointer; }
.lg-b label small { display:block; color:var(--mut); font-size:12px; }
.lg-b input { margin-top:3px; accent-color:#FF9A57; }
.ico { width:18px; height:18px; flex:none; }
.detail { position:absolute; right:14px; top:14px; z-index:3; width:min(360px, calc(100% - 28px)); max-height:calc(100% - 28px); overflow:auto;
  background:rgba(14,22,32,.86); -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,.2); border-radius:14px; padding:14px 16px; }
.detail.enter { animation:dIn .28s ease-out both; }
@keyframes dIn { from { opacity:0; transform:translateX(14px); } to { opacity:1; transform:none; } }
.detail h3 { margin:0 28px 4px 0; font-size:18px; line-height:1.3; }
.detail .x { position:absolute; right:10px; top:10px; width:30px; height:30px; padding:0; font-size:18px; line-height:1; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 10px; }
.chip { display:inline-flex; align-items:center; gap:5px; font-size:13px; border:1px solid rgba(255,255,255,.25); border-radius:999px; padding:2px 8px; }
.chip.syn { border-style:dashed; color:#FFD3B0; }
.vals { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:8px 0; }
.val { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); border-radius:10px; padding:8px 10px; }
.val .k { font-size:12px; color:var(--mut); } .val .v { font-size:18px; font-weight:600; } .val .s { font-size:12px; color:var(--mut); }
.meta { font-size:13px; color:#DCE2E8; margin:6px 0; }
.detail details { margin-top:8px; border-top:1px solid rgba(255,255,255,.12); padding-top:6px; }
.detail summary { cursor:pointer; font-weight:600; font-size:14px; }
.detail dl { display:grid; grid-template-columns:auto 1fr; gap:4px 10px; margin:8px 0 0; font-size:13px; }
.detail dt { color:var(--mut); } .detail dd { margin:0; }
.detail .fl { margin:8px 0 0; padding-left:0; list-style:none; font-size:13px; }
.detail .fl li { margin:0 0 8px; } .detail .fl b { font-size:14px; }
.acts { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.acts .btn { font-size:13px; }
.foot { display:flex; flex-wrap:wrap; justify-content:space-between; gap:6px 14px; padding:8px 16px 12px; font-size:12px; color:var(--mut); border-top:1px solid var(--line); }
.unplaced { padding:8px 16px; font-size:13px; color:#DCE2E8; border-top:1px solid var(--line); }
.unplaced button { margin:4px 6px 0 0; }
.sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
@media (max-width: 820px) {
  .stage { height:auto; aspect-ratio: 4 / 4.6; }
  .legend, .detail { position:static; width:auto; max-height:none; margin:10px; }
  .wrap-narrow { display:flex; flex-direction:column; }
  .mk .tag { font-size:12px; }
}
@media (prefers-reduced-motion: reduce) {
  .card.pre, .mk.pre, .legend.pre { opacity:1; transform:none; }
  .card.in, .mk.in, .legend.in, .detail.enter { animation:none; }
  .layer, .mk .halo, .lg-h .chev { transition:none; }
}
"""

JS = r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector('[data-rm-root]');
  if (!root || !data) return;
  // The root persists across Streamlit reruns: drop the previous run's listeners and observers before adding new ones.
  if (root.__rmCleanup) root.__rmCleanup();
  const ac = new AbortController(), sig = { signal: ac.signal };
  const D = data, L = D.locations, C = Object.fromEntries(D.categories.map(c => [c.id, c]));
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  const narrow = window.matchMedia('(max-width: 820px)');
  // UI state survives Streamlit reruns (same page session); weather data never lives here.
  const ui = window.__swRoadMap = window.__swRoadMap || { intro: false, legend: !narrow.matches, layers: { flags: true, temps: true, names: true },
                                                          card: true, cardFor: null, z: 1, tx: 0, ty: 0, focus: null, after: null };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const sym = (shape, color, size = 24) => {
    const s = size, h = s / 2;
    const P = {
      triangle: `<path d="M${h} 2 L${s - 2} ${s - 3} L2 ${s - 3} Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      diamond: `<path d="M${h} 1.5 L${s - 2} ${h} L${h} ${s - 1.5} L2 ${h} Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      drop: `<path d="M${h} 2 C${h + 6} ${h - 2} ${s - 4} ${h + 2} ${s - 4} ${h + 4} A${h - 4} ${h - 4} 0 0 1 4 ${h + 4} C4 ${h + 2} ${h - 6} ${h - 2} ${h} 2 Z" fill="${color}" stroke="#0E1620" stroke-width="1.5"/>`,
      question: `<circle cx="${h}" cy="${h}" r="${h - 2}" fill="${color}" stroke="#0E1620" stroke-width="1.5"/><text x="${h}" y="${h + 5}" text-anchor="middle" font-size="${s * .6}" font-weight="700" fill="#0E1620" font-family="system-ui,sans-serif">?</text>`,
      ring: `<circle cx="${h}" cy="${h}" r="${h - 4}" fill="rgba(14,22,32,.6)" stroke="${color}" stroke-width="3"/>`,
      dot: `<circle cx="${h}" cy="${h}" r="${h - 6}" fill="#E8EDF2" stroke="#0E1620" stroke-width="1.5"/>`,
      none: `<circle cx="${h}" cy="${h}" r="${h - 5}" fill="none" stroke="${color}" stroke-width="1.5" stroke-dasharray="3 3"/>`,
    };
    return `<svg class="sym" viewBox="0 0 ${s} ${s}" aria-hidden="true">${P[shape] || P.dot}</svg>`;
  };
  const icon = c => sym(c.shape, c.color).replace('class="sym"', 'class="ico"');
  const counts = Object.fromEntries(D.categories.map(c => [c.id, L.filter(l => l.category === c.id).length]));
  const sel = L.find(l => l.id === D.selected) || L[0];
  if (ui.cardFor !== sel.id) { ui.card = true; }
  const enter = ui.cardFor !== sel.id && !mq.matches;
  ui.cardFor = sel.id;
  const vb = D.boundary.view_box, W = vb[2], H = vb[3];
  const placed = L.filter(l => l.x !== null && l.y !== null), unplaced = L.filter(l => l.x === null || l.y === null);
  const playIntro = !ui.intro && !mq.matches;

  const flagLabel = l => l.flags.length ? l.flags.map(f => f.title).join(', ') : C.no_flag.label;
  const markerHTML = (l, i) => {
    const c = C[l.category], show = ui.layers.flags, shape = show ? c.shape : 'dot';
    const tag = [ui.layers.names ? `<b>${esc(l.short)}</b>` : '', ui.layers.temps && l.pavement.value !== null ? `<span>${esc(l.pavement.text)}</span>` : ''].filter(Boolean).join(' · ');
    const more = show && l.flags.length > 1 ? `<span class="more" aria-hidden="true">+${l.flags.length - 1}</span>` : '';
    const aria = `${l.name}. ${show ? flagLabel(l) : 'Review markers hidden'}. Pavement ${l.pavement.text}${l.synthetic ? ' (synthetic scenario)' : ''}.${l.partial ? ' Coordinate partially verified.' : ''}${l.unmatched ? ' Pavement withheld.' : ''}`;
    return `<button type="button" class="mk${l.id === sel.id ? ' sel' : ''}${show ? '' : ' plain'}${playIntro ? ' pre' : ''}" data-id="${l.id}"
      style="left:${(l.x / W * 100).toFixed(3)}%; top:${(l.y / H * 100).toFixed(3)}%; --c:${c.color}; --d:${(i * 140 + 350)}ms"
      aria-pressed="${l.id === sel.id}" aria-label="${esc(aria)}" title="${esc(l.name)}"><span class="halo"></span>${sym(shape, c.color)}${more}${tag ? `<span class="tag">${tag}</span>` : ''}</button>`;
  };
  const legendHTML = () => `<div class="legend${ui.legend ? '' : ' closed'}${playIntro ? ' pre' : ''}" role="region" aria-label="Map legend and layers">
      <button type="button" class="lg-h" data-act="legend" aria-expanded="${ui.legend}">Map legend &amp; layers <span class="chev" aria-hidden="true">▾</span></button>
      <div class="lg-b">${D.categories.map(c => `<details><summary>${icon(c)}<span class="${c.status === 'not_defined' ? 'nd' : ''}">${esc(c.label)}</span>
          <span class="n">${c.status === 'not_defined' ? 'not defined' : counts[c.id] + ' shown'}</span></summary>
          <p>${esc(c.meaning)}<br><b>Evidence:</b> ${esc(c.evidence)}</p></details>`).join('')}
        <div class="lg-sub">Layers (display only)</div>
        ${D.layers.map(([k, lab, note]) => `<label><input type="checkbox" data-layer="${k}" ${ui.layers[k] ? 'checked' : ''}><span>${esc(lab)}<small>${esc(note)}</small></span></label>`).join('')}
        <div class="lg-sub">Point outline</div>
        <p style="margin:0;font-size:13px;color:#DCE2E8">White ring: selected road. Hidden layers never remove a road from service assumptions, charts or Storm Lab.</p>
      </div></div>`;
  const row = (k, v) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`;
  const detailHTML = l => {
    if (!ui.card) return '';
    const p = l.pavement, a = l.air;
    const chips = (l.flags.length ? l.flags.map(f => { const c = C[f.id] || C.no_flag; return `<span class="chip">${icon(c)}${esc(f.title)}${f.time ? ' · ' + esc(f.time) : ''}</span>`; }).join('')
                   : `<span class="chip">${icon(C.no_flag)}${esc(C.no_flag.label)}</span>`) + (l.synthetic ? '<span class="chip syn">Synthetic scenario</span>' : '');
    return `<section class="detail${enter ? ' enter' : ''}" role="region" aria-label="Details for ${esc(l.name)}" data-detail="${l.id}" tabindex="-1">
      <button type="button" class="btn x" data-act="close" aria-label="Close details for ${esc(l.name)}">×</button>
      <h3>${esc(l.name)}</h3><div class="chips">${chips}</div>
      <div class="vals"><div class="val"><div class="k">Pavement temperature</div><div class="v">${esc(p.text)}</div><div class="s">${esc(p.value !== null ? (p.surface ? 'Surface: ' + p.surface : 'Surface: not supplied') : p.why)}</div></div>
        <div class="val"><div class="k">Air temperature</div><div class="v">${esc(a.text)}</div><div class="s">${esc(a.value !== null ? 'Separate series; never stands in for pavement' : a.why)}</div></div></div>
      <div class="meta">Selected period: ${esc(l.period)} · ${esc(l.tz)} · ${esc(l.units)}</div>
      <div class="meta">${esc(l.explain)}</div><div class="meta"><b>Next step:</b> ${esc(l.next)}</div>
      <details><summary>Evidence details</summary><dl>
        ${row('Pavement evidence', l.evidence.pavement)}${p.source ? row('Pavement source', p.source) : ''}${p.valid ? row('Pavement valid', p.valid) : ''}${p.freshness ? row('Freshness', p.freshness) : ''}
        ${row('Air evidence', l.evidence.air)}${a.source ? row('Air source', a.source) : ''}${a.valid ? row('Air valid', a.valid) : ''}
        ${row('Precipitation', l.precip.text + (l.precip.value === null && l.precip.why ? ' (' + l.precip.why + ')' : ''))}
        ${row('Wind', l.wind.text + ' (' + l.wind.why + ')')}${row('Dew point', l.dew.text + ' (' + l.dew.why + ')')}
        ${l.statuses.map(([k, v]) => row(k, v)).join('')}</dl>
        ${l.flags.length ? `<ul class="fl">${l.flags.map(f => `<li><b>${esc(f.title)}</b>${f.time ? ' · ' + esc(f.time) : ''}<br>${esc(f.reason)}</li>`).join('')}</ul>` : ''}
      </details>
      <div class="acts"><button type="button" class="btn" data-act="chart">View this road’s chart</button>
        <button type="button" class="btn" data-act="evidence">Open evidence details</button>
        <button type="button" class="btn" data-act="stormlab">Storm Lab · evidence snapshot</button></div>
    </section>`;
  };
  const unplacedHTML = () => unplaced.length ? `<div class="unplaced">Not drawn (no registry coordinate): ${unplaced.map(l =>
    `<button type="button" class="btn" data-id="${l.id}" aria-pressed="${l.id === sel.id}">${esc(l.name)}</button>`).join('')}</div>` : '';

  root.innerHTML = `<div class="card${playIntro ? ' pre' : ''}">
    <div class="top"><span class="mode">${esc(D.mode_note)}</span><div class="zoom" role="group" aria-label="Map zoom">
      <button type="button" class="btn" data-act="zin" aria-label="Zoom in">+</button><button type="button" class="btn" data-act="zout" aria-label="Zoom out">−</button>
      <button type="button" class="btn" data-act="zreset">Reset view</button></div></div>
    <div class="wrap-narrow">${narrow.matches ? legendHTML() : ''}<div class="stage" role="group" aria-label="Map of the District of Columbia with ${placed.length} registered demonstration points">
      <div class="layer" style="--w:${W}px; --h:${H}px">
        <svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${D.boundary.path}" fill="rgba(255,255,255,.05)" stroke="rgba(255,255,255,.75)" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>
        ${placed.map(markerHTML).join('')}</div>
      ${narrow.matches ? '' : legendHTML() + detailHTML(sel)}</div>
      ${narrow.matches ? detailHTML(sel) : ''}</div>
    ${unplacedHTML()}
    <div class="foot"><span>${esc(D.credit)}</span><span>Drag to pan when zoomed · Enter selects a point · Esc closes details</span></div>
    <div class="sr" aria-live="polite" data-live></div></div>`;

  const card = root.querySelector('.card'), stage = root.querySelector('.stage'), layer = root.querySelector('.layer');
  // Fit the boundary to the stage; zoom/pan are pure display transforms over already-loaded data.
  const fit = () => { const r = stage.getBoundingClientRect(); const s = Math.min((r.width - 24) / W, (r.height - 24) / H);
    layer.style.width = (W * s) + 'px'; layer.style.height = (H * s) + 'px'; layer.style.marginLeft = (-W * s / 2) + 'px'; layer.style.marginTop = (-H * s / 2) + 'px'; };
  const applyZoom = () => { layer.style.setProperty('--z', ui.z); layer.style.setProperty('--tx', ui.tx + 'px'); layer.style.setProperty('--ty', ui.ty + 'px'); };
  fit(); applyZoom();
  const ro = new ResizeObserver(fit); ro.observe(stage);
  // Narrow layouts stack legend, map and details so nothing overlays the points; move them when the breakpoint changes.
  const place = () => { const wrap = root.querySelector('.wrap-narrow'), lg = root.querySelector('.legend'), dt = root.querySelector('.detail');
    if (narrow.matches) { if (lg) wrap.insertBefore(lg, stage); if (dt) wrap.appendChild(dt); } else { if (lg) stage.appendChild(lg); if (dt) stage.appendChild(dt); } };
  narrow.addEventListener('change', place, sig);

  let io = null;
  if (playIntro) {
    const play = () => { ui.intro = true; card.classList.remove('pre'); card.classList.add('in');
      root.querySelectorAll('.mk.pre, .legend.pre').forEach(e => { e.classList.remove('pre'); e.classList.add('in'); }); };
    io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); play(); } }, { threshold: 0.25 });
    io.observe(card);
  } else ui.intro = true;

  const live = root.querySelector('[data-live]');
  const scrollTo = el => el && el.scrollIntoView({ behavior: mq.matches ? 'auto' : 'smooth', block: 'start' });
  const doAfter = () => {          // actions that need the page after the selection has been applied
    const a = ui.after; ui.after = null; if (!a) return;
    const doc = document;
    if (a === 'chart') scrollTo(doc.querySelector('.sw-panel-start'));
    if (a === 'evidence') { const s = [...doc.querySelectorAll('summary')].find(e => /(^|\s)Evidence details\s*$/.test(e.innerText.trim()) && !e.closest('[data-rm-root]'));
      if (s) { const d = s.closest('details'); if (d && !d.open) s.click(); setTimeout(() => { scrollTo(s); s.focus({ preventScroll: true }); }, 250); } }
    if (a === 'stormlab') { const t = doc.querySelector('a[href$="/storm-lab"]') || [...doc.querySelectorAll('a')].find(e => /^\s*storm lab\s*$/i.test(e.innerText || '')); if (t) t.click(); }
  };

  root.addEventListener('click', e => {
    const b = e.target.closest('button, input'); if (!b) return;
    if (b.dataset.id) {
      if (b.dataset.id === sel.id) { ui.card = true; rebuildDetail(true); return; }
      ui.card = true; ui.focus = `[data-id="${b.dataset.id}"]`; setTriggerValue('select', b.dataset.id); return; }
    const act = b.dataset.act;
    if (act === 'legend') { ui.legend = !ui.legend; b.closest('.legend').classList.toggle('closed', !ui.legend); b.setAttribute('aria-expanded', ui.legend); }
    else if (act === 'close') { ui.card = false; const d = root.querySelector('.detail'); if (d) d.remove(); live.textContent = 'Details closed. ' + sel.name + ' stays selected.';
      const m = root.querySelector(`.mk[data-id="${sel.id}"], .unplaced [data-id="${sel.id}"]`); if (m) m.focus(); }
    else if (act === 'zin' || act === 'zout') { ui.z = Math.min(4, Math.max(1, ui.z * (act === 'zin' ? 1.4 : 1 / 1.4))); if (ui.z === 1) { ui.tx = 0; ui.ty = 0; } applyZoom(); }
    else if (act === 'zreset') { ui.z = 1; ui.tx = 0; ui.ty = 0; applyZoom(); }
    else if (act === 'chart' || act === 'evidence' || act === 'stormlab') { ui.after = act; doAfter(); }
  }, sig);
  root.addEventListener('change', e => { const k = e.target.dataset.layer; if (!k) return; ui.layers[k] = e.target.checked;
    ui.focus = `[data-layer="${k}"]`; rebuildMarkers(); }, sig);
  root.addEventListener('keydown', e => { if (e.key === 'Escape' && root.querySelector('.detail')) { e.preventDefault(); root.querySelector('[data-act=close]').click(); } }, sig);
  function rebuildMarkers() { layer.querySelectorAll('.mk').forEach(m => m.remove());
    layer.insertAdjacentHTML('beforeend', placed.map(markerHTML).join(''));
    layer.querySelectorAll('.mk').forEach(m => m.classList.remove('pre')); }
  function rebuildDetail(focus) { const old = root.querySelector('.detail'); if (old) old.remove();
    const host = narrow.matches ? root.querySelector('.wrap-narrow') : stage; host.insertAdjacentHTML('beforeend', detailHTML(sel));
    const d = root.querySelector('.detail'); if (d && focus) d.focus(); }
  // Drag to pan (only when zoomed in).
  let drag = null;
  stage.addEventListener('pointerdown', e => { if (ui.z <= 1 || e.target.closest('button, input, summary, .legend, .detail')) return;
    drag = { x: e.clientX, y: e.clientY, tx: ui.tx, ty: ui.ty }; stage.classList.add('drag'); stage.setPointerCapture(e.pointerId); }, sig);
  stage.addEventListener('pointermove', e => { if (!drag) return; ui.tx = drag.tx + e.clientX - drag.x; ui.ty = drag.ty + e.clientY - drag.y; applyZoom(); }, sig);
  stage.addEventListener('pointerup', () => { drag = null; stage.classList.remove('drag'); }, sig);

  if (ui.focus) { const f = root.querySelector(ui.focus); ui.focus = null; if (f) f.focus({ preventScroll: true }); }
  if (ui.pendingAnnounce !== sel.id) { live.textContent = 'Selected ' + sel.name + '. ' + flagLabel(sel) + '.'; ui.pendingAnnounce = sel.id; }
  const cleanup = () => { ac.abort(); ro.disconnect(); if (io) io.disconnect(); if (root.__rmCleanup === cleanup) root.__rmCleanup = null; };
  root.__rmCleanup = cleanup;
  return cleanup;
}
"""


def _register():
    return st.components.v2.component("saltwise_road_map", html=HTML, css=CSS, js=JS, isolate_styles=True)


_component = _register()


LOCATION_IDS = ("rhode_island_ave_nw_scott_circle", "garfield_st_nw_34th_st_nw", "michigan_ave_ne_bridge", "benning_rd_bridge",
                "mlk_jr_ave_se_alabama_ave_se")


def select_location(lid):
    """The one selection handler on Road Weather (map markers and point cards): sets the page's existing selected-road
    state; the selector, chart, readouts, flags, evidence and export all follow it on the same rerun."""
    if lid in LOCATION_IDS:
        st.session_state["location"] = lid


def _on_select(key):
    v = st.session_state.get(key)
    lid = getattr(v, "select", None) if v is not None else None
    if lid is None and hasattr(v, "get"):
        lid = v.get("select")
    select_location(lid)


def render(data, key="road_map"):
    """Mount the map. A marker click sets st.session_state['location'] through the callback before the next run."""
    global _component
    from streamlit.errors import StreamlitAPIException
    kw = dict(key=key, data=data, on_select_change=lambda: _on_select(key))
    try:
        return _component(**kw)
    except StreamlitAPIException as e:
        if "not registered" not in str(e):
            raise
        _component = _register()
        return _component(**kw)
