"""Road Weather page: road maintenance presentation (opening copy and DC street photo, selected-road readout, winter
operations workflow, plow clip, whole-storm note). Mounted by app.py when it runs as the Road Weather page.

Presentation only. The readout is road_map.location_card for the page's own view, selected road, units, window and
inspected time, so it always matches the map card and the chart; this module adds no weather pipeline, rule, threshold or
model call. Photographs and the plow clip are illustrative scenery (static/media/SOURCES.json), never current road
observations. Image entrances run in the browser (zoom_media below) and never trigger a rerun.
"""
import html

import streamlit as st

import media

CSS = """<style>
.sw-rm-anchor { scroll-margin-top: 84px; }
.sw-rm-eyebrow { font: 600 12px/1.3 ui-monospace, Menlo, monospace; letter-spacing: .14em; color: #6B7280; text-transform: uppercase; }
.sw-rm-h { font-size: clamp(34px, 3.4vw, 52px) !important; line-height: 1.08 !important; letter-spacing: -.03em; font-weight: 400 !important; margin: .35rem 0 .7rem; color: #15171C; }
.sw-rm-lede { font-size: 18px; line-height: 1.55; color: #4B5563; max-width: 34em; margin: 0 0 1rem; }
.sw-rm-sum { border-top: 1px solid #D9E0E6; padding-top: .8rem; margin-top: .2rem; }
.sw-rm-mode { display: inline-block; font: 600 11px/1.4 ui-monospace, Menlo, monospace; letter-spacing: .08em; text-transform: uppercase;
  color: #8A3A00; border: 1px dashed #D2560A; border-radius: 6px; padding: 1px 7px; margin-bottom: .5rem; }
.sw-rm-vals { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: .4rem 0 .6rem; }
.sw-rm-v .k { font-size: 13px; color: #6B7280; } .sw-rm-v .v { font-size: 30px; font-weight: 600; letter-spacing: -.02em; color: #15171C; }
.sw-rm-v .s { font-size: 13px; color: #6B7280; line-height: 1.4; }
.sw-rm-flags { display: flex; flex-wrap: wrap; gap: 6px; margin: .2rem 0 .5rem; }
.sw-rm-flag { font-size: 13px; border: 1px solid #F0B48A; background: #FFF4EC; color: #8A3A00; border-radius: 999px; padding: 2px 9px; }
.sw-rm-flag.none { border-color: #C4C9D0; background: #F2F4F6; color: #4B5563; }
.sw-rm-text { font-size: 15px; line-height: 1.55; color: #1F2937; margin: .2rem 0; }
.sw-rm-meta { font-size: 13px; color: #6B7280; margin: .2rem 0; }
.sw-rm-split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr); gap: 48px; border-top: 1px solid #D9E0E6;
  padding: 44px 0 36px; margin-top: 28px; }
.sw-rm-split h2 { font-size: clamp(26px, 2.4vw, 36px); line-height: 1.15; letter-spacing: -.02em; font-weight: 400; margin: 0; color: #15171C; }
.sw-rm-split p { font-size: 17px; line-height: 1.6; color: #4B5563; margin: 0 0 1rem; max-width: 40em; }
.st-key-rw_pair { background: #EEF1F4; border-radius: 10px; padding: clamp(18px, 2.6vw, 44px); margin: 36px 0 12px; }
.st-key-rw_pair h2 { font-size: clamp(28px, 2.6vw, 42px) !important; line-height: 1.12 !important; letter-spacing: -.02em; font-weight: 400 !important; margin: .3rem 0 .8rem; color: #15171C; }
.st-key-rw_pair p { font-size: 17px; line-height: 1.6; color: #3F4652; max-width: 34em; }
[data-testid="stColumn"]:has([class*="st-key-rwcard_"]) { position: relative; }
[class*="st-key-rwcard_"] { position: absolute !important; inset: 0; margin: 0 !important; z-index: 2; width: auto !important; }
[class*="st-key-rwcard_"] .stButton, [class*="st-key-rwcard_"] button { width: 100% !important; height: 100% !important; min-height: 0 !important; }
[class*="st-key-rwcard_"] button { opacity: 0; cursor: pointer; }
[data-testid="stColumn"]:has([class*="st-key-rwcard_"] button:hover) .sw-card { border-color: #D2560A; }
[data-testid="stColumn"]:has([class*="st-key-rwcard_"] button:focus-visible) .sw-card { outline: 3px solid #D2560A; outline-offset: 2px; }
@media (max-width: 640px) { [data-testid="stColumn"]:has(.sw-card:not(.sw-card-selected)) [class*="st-key-rwcard_"] { display: none !important; } }
.sw-rm-credits { font-size: 12.5px; color: #6B7280; line-height: 1.5; margin: 10px 0 0; max-width: 110ch; }
.sw-rm-steps { list-style: none; padding: 0; margin: .4rem 0 0; display: grid; gap: 0; }
.sw-rm-steps li { display: grid; grid-template-columns: 40px 1fr; gap: 12px; padding: 14px 0; border-top: 1px solid #E5E9EE; }
.sw-rm-steps b { display: block; font-weight: 600; color: #15171C; font-size: 17px; margin-bottom: 2px; }
.sw-rm-steps span.n { font: 600 13px/1.6 ui-monospace, Menlo, monospace; color: #D2560A; }
.sw-rm-steps span.t { font-size: 15.5px; color: #4B5563; line-height: 1.5; }
.sw-rm-note { font-size: 14px; color: #6B7280; border-left: 3px solid #C4C9D0; padding-left: 10px; margin-top: .6rem; }
@media (max-width: 760px) { .sw-rm-split { grid-template-columns: 1fr; gap: 14px; padding: 30px 0 22px; } .sw-rm-vals { gap: 8px; }
  .sw-rm-v .v { font-size: 24px; } }
</style>"""

OPENING = ('<div id="sw-road-maintenance" class="sw-rm-anchor"></div><div class="sw-rm-eyebrow">Road Weather · road maintenance</div>'
           '<h2 class="sw-rm-h">Smarter winter maintenance. Less avoidable salt.</h2>'
           '<p class="sw-rm-lede">Review road conditions, understand changing weather, and compare treatment choices '
           'while keeping winter access at the center.</p>')


def opening_copy():
    st.markdown(CSS + OPENING, unsafe_allow_html=True)


def photo():
    zoom_media("home_dc_street", "Snow-covered Q Street NW in the Dupont Circle neighborhood of Washington, DC, after a blizzard",
               ratio="10 / 9", scale=1.18, key="rm_photo_street")


def summary(card, provider):
    """Readout for the selected road at the page's inspected time (same card as the map)."""
    p, a = card["pavement"], card["air"]
    mode = "Provider evidence · saved snapshots" if provider else "Synthetic scenario · illustrative, not live weather"
    flags = "".join(f'<span class="sw-rm-flag">▲ {html.escape(f["title"])}{" · " + html.escape(f["time"]) if f["time"] else ""}</span>'
                    for f in card["flags"]) or '<span class="sw-rm-flag none">No review flag in this window</span>'
    pav_sub = (f'{html.escape(card["evidence"]["pavement"])}' + (f' · surface {html.escape(p["surface"])}' if p.get("surface") else "")
               if p["value"] is not None else html.escape(p.get("why") or "Unavailable"))
    air_sub = html.escape(card["evidence"]["air"]) if a["value"] is not None else html.escape(a.get("why") or "Unavailable")
    status = " · ".join(f"{html.escape(k)}: {html.escape(v)}" for k, v in card["statuses"])
    st.markdown(
        f'<div class="sw-rm-sum" data-testid="rm-summary"><span class="sw-rm-mode">{mode}</span>'
        f'<div class="sw-rm-meta">{html.escape(card["name"])} · period {html.escape(card["period"])} · {html.escape(card["tz"])} · {card["units"]}</div>'
        f'<div class="sw-rm-vals"><div class="sw-rm-v"><div class="k">Pavement temperature</div><div class="v">{html.escape(p["text"])}</div>'
        f'<div class="s">{pav_sub}</div></div><div class="sw-rm-v"><div class="k">Air temperature</div><div class="v">{html.escape(a["text"])}</div>'
        f'<div class="s">{air_sub}</div></div></div><div class="sw-rm-flags">{flags}</div>'
        f'<p class="sw-rm-text">{html.escape(card["explain"])}</p><p class="sw-rm-meta"><b>Next step:</b> {html.escape(card["next"])}</p>'
        f'<p class="sw-rm-meta">{status}</p><p class="sw-rm-meta"><a href="#sw-rw-chart">Chart and time readout ↓</a> · '
        f'<a href="#sw-rw-review">Review flags, evidence details and JSON export ↓</a></p></div>', unsafe_allow_html=True)


def workflow():
    st.markdown(
        '<div class="sw-rm-split"><div><div class="sw-rm-eyebrow">How it works</div><h2>Winter maintenance operations</h2></div><div>'
        '<p>Planners already work from forecasts and established deployment packages. SaltWise adds one review loop beside them, '
        'using only the evidence it can show with its source, valid time and kind.</p><ol class="sw-rm-steps">'
        '<li><span class="n">01</span><span class="t"><b>Review conditions</b>Air and pavement temperatures stay separate, inside the '
        'returned forecast horizon, for each registered road.</span></li>'
        '<li><span class="n">02</span><span class="t"><b>Examine the reason for a flag</b>Every review flag states the displayed values '
        'behind it. Flags are illustrative rules, not policy; people make every treatment decision.</span></li>'
        '<li><span class="n">03</span><span class="t"><b>Compare a scenario</b>Storm Lab totals initial, later and catch-up applications '
        'across the whole storm before any comparison.</span></li></ol></div></div>', unsafe_allow_html=True)


def pair():
    """Pale-grey paired section: what SaltWise never does with a road, next to a DC clearing photograph."""
    with st.container(key="rw_pair"):
        a, b = st.columns([1, 1.1], gap="large", vertical_alignment="center")
        with a:
            st.markdown('<div class="sw-rm-eyebrow">Assumed service</div><h2>Every road stays in service.</h2>'
                        '<p>SaltWise flags locations for review; it never approves, cancels or removes treatment. Missing or '
                        'expired evidence is shown as unavailable, with its reason, and never means a road needs no treatment.</p>'
                        '<p>Two of the five demonstration points are bridges. With provider data, each point shows its geographic '
                        'verification, provider road match and bridge-specific modeling status separately; nothing is assumed '
                        'where a match is missing.</p>', unsafe_allow_html=True)
        with b:
            zoom_media("rw_dc_clearing", "Vehicles clearing a Washington, DC street at night after the January 2026 snowstorm",
                       ratio="4 / 3", scale=1.15, key="rm_photo_clearing")


def landscape():
    zoom_media("rw_winter_landscape", "A snowcoach on a snow-packed road along the Madison River in Yellowstone National Park (not DC)",
               ratio="21 / 9", scale=1.2, full=True, key="rm_media_landscape", pos="50% 62%")
    st.markdown('<p class="sw-rm-credits">Photographs and video on this page are illustrative scenery, not current road observations. '
                'Q Street NW, Dupont Circle, DC, December 2009: dbking, CC BY 2.0. Clearing vehicles, Washington DC, January 2026: '
                'Sdkb, CC BY-SA 4.0. Snowplow on Pozharskoho Street, Kyiv, Ukraine: Роман Рябенко, CC0. Madison River road, '
                'Yellowstone: Jacob W. Frank, NPS, public domain. All via Wikimedia Commons; details in static/media/SOURCES.json.</p>',
                unsafe_allow_html=True)


def plow():
    zoom_media("stormlab_snowplow", "A snowplow clearing a snow-covered city street (not in DC)", ratio="21 / 9", scale=1.25,
               full=True, key="rm_media_plow", pos="50% 22%")


def whole_storm():
    st.markdown(
        '<div class="sw-rm-split"><div><div class="sw-rm-eyebrow">Full-storm accounting</div><h2>Count the whole storm.</h2></div><div>'
        '<p>A treatment skipped early can still need a catch-up application later. SaltWise compares plans only after every initial, later, '
        'repeat and catch-up application inside one shared storm window is counted, and it keeps every road in assumed service.</p>'
        '<p class="sw-rm-note">Actual salt reductions, financial savings and environmental benefits have not yet been measured. '
        'Storm Lab results are simulations with stated assumptions.</p></div></div>', unsafe_allow_html=True)


# ---------------- zoom-out media (browser only) ----------------
ZHTML = '<figure class="zm" data-zm></figure>'
ZCSS = r"""
:host { display:block; }
.zm { position:relative; overflow:hidden; margin:0; aspect-ratio:var(--ar); background:#DDE3E8; border-radius:var(--rad, 10px); }
.zm.full { --rad:0px; width:100vw; margin-left:calc(50% - 50vw); max-height:min(78vh, 760px); }
.zm img, .zm video { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block;
  object-position:var(--pos, 50% 50%); transform:scale(var(--s, 1)); transform-origin:50% 55%; will-change:transform; }
@media (max-width: 760px) { .zm:not(.full) { aspect-ratio: 4 / 3.2; } .zm.full { aspect-ratio: 4 / 3; } }
"""
ZJS = r"""
export default function (component) {
  const { data, parentElement } = component;
  const fig = parentElement.querySelector('[data-zm]');
  if (!fig || !data) return;
  if (fig.__zmCleanup) fig.__zmCleanup();
  const done = window.__swZoomDone = window.__swZoomDone || {};          // survives Streamlit reruns on this page session
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (fig.dataset.src !== data.src) {                                      // build once; reruns reuse the same element
    fig.dataset.src = data.src; fig.className = 'zm' + (data.full ? ' full' : ''); fig.style.setProperty('--ar', data.ratio); fig.style.setProperty('--pos', data.pos || '50% 50%');
    const alt = data.alt.replace(/"/g, '&quot;');
    fig.innerHTML = data.kind === 'video'
      ? `<video muted loop playsinline preload="none" disablepictureinpicture poster="${data.poster}" aria-label="${alt}"><source src="${data.large && innerWidth * (devicePixelRatio || 1) >= 1400 ? data.large : data.src}" type="video/mp4"></video>`
      : `<img loading="lazy" decoding="async" src="${data.src}" ${data.srcset ? `srcset="${data.srcset}" sizes="${data.sizes}"` : ''} alt="${alt}" decoding="async">`;
  }
  const el = fig.firstElementChild, S0 = data.scale, id = data.id;
  const scroller = document.querySelector('[data-testid=stMain]') || window;
  let cur = done[id] || mq.matches ? 1 : (fig.__zmCur || S0), raf = 0;     // reruns continue where the image is
  el.style.setProperty('--s', cur);
  // Scroll-linked zoom-out (as in the reference): the image starts enlarged when it enters and settles to its final framing
  // as its top travels from the bottom of the viewport to ~35% from the top. Smoothed per frame; once settled it stays put.
  // Nothing moves or completes before the image is really on screen: the mode is chosen when it first intersects the
  // viewport (high in the viewport then, e.g. the opening photo on load: a ~1 s entrance; otherwise scroll-linked), and if
  // the layout pushes it off screen again before it settles (maps and charts above it still sizing), it resets.
  const vis = () => { const r = fig.getBoundingClientRect(); return r.height > 0 && r.bottom > 0 && r.top < innerHeight; };
  const target = () => { if (fig.__zmMode === 'entrance') return 1; const r = fig.getBoundingClientRect(), vh = innerHeight;
    const p = Math.min(1, Math.max(0, (vh - r.top) / (vh * 0.65))); return S0 - (S0 - 1) * p; };
  const tick = () => { raf = 0; if (done[id] || !fig.__zmMode) return;
    const tg = target(); cur += (tg - cur) * (fig.__zmMode === 'entrance' ? 0.07 : 0.16); if (Math.abs(tg - cur) < 0.0008) cur = tg;
    fig.__zmCur = cur; el.style.setProperty('--s', cur.toFixed(4));
    if (cur <= 1.0005 && tg <= 1.0005 && vis()) { done[id] = true; el.style.setProperty('--s', 1); stop(); return; }
    if (Math.abs(tg - cur) > 0.0008) raf = requestAnimationFrame(tick); };
  const onScroll = () => { if (!raf) raf = requestAnimationFrame(tick); };
  let seen = null;
  const stop = () => { scroller.removeEventListener('scroll', onScroll); removeEventListener('resize', onScroll); if (seen) seen.disconnect(); if (raf) cancelAnimationFrame(raf); };
  if (!done[id] && !mq.matches) {
    seen = new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) { if (!done[id]) { fig.__zmMode = null; cur = fig.__zmCur = S0; el.style.setProperty('--s', S0); } return; }
      if (!fig.__zmMode) fig.__zmMode = e.boundingClientRect.top < innerHeight * 0.5 ? 'entrance' : 'scroll';
      onScroll(); }), { threshold: 0 });
    seen.observe(fig);
    scroller.addEventListener('scroll', onScroll, { passive: true }); addEventListener('resize', onScroll);
  }
  // Video plays only while visible and never under reduced motion (the poster is the still fallback).
  let io = null;
  if (el.tagName === 'VIDEO') {
    io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting && !mq.matches) { const pr = el.play(); if (pr) pr.catch(() => {}); } else el.pause(); }), { threshold: 0.2 });
    io.observe(fig);
  }
  const cleanup = () => { stop(); if (io) io.disconnect(); fig.__zmCleanup = null; };
  fig.__zmCleanup = cleanup;
  return cleanup;
}
"""


def _zregister():
    return st.components.v2.component("saltwise_zoom_media", html=ZHTML, css=ZCSS, js=ZJS, isolate_styles=True)


_zcomp = _zregister()


def zoom_media(slot, alt, ratio, scale, key, full=False, pos=None):
    global _zcomp
    from streamlit.errors import StreamlitAPIException
    rec = next(r for r in media.records() if r["slot"] == slot)
    u = media.urls([slot])[slot]
    srcset = ", ".join(f"app/{v['file']} {v['w']}w" for v in rec.get("variants") or [])    # never wider than the source
    data = {"id": key, "kind": "video" if rec.get("kind") == "video" else "image", "src": u["src"], "srcset": srcset,
            "sizes": "100vw" if full else "(max-width: 760px) 100vw, 50vw", "large": "app/" + rec["file_large"] if rec.get("file_large") else None,
            "poster": u["poster"], "alt": alt, "ratio": ratio, "scale": scale, "full": full, "pos": pos}
    try:
        return _zcomp(key=key, data=data)
    except StreamlitAPIException as e:
        if "not registered" not in str(e):
            raise
        _zcomp = _zregister()
        return _zcomp(key=key, data=data)
