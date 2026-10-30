"""Home: sustainability closing section that blends into the footer (st.components.v2, shadow-DOM styles).

Muted evening slate gradient with a pale glow near the top and sparse, small, slowly drifting snow particles drawn on a
local canvas (decorative, not a snowfall report). The animation runs only while the section is visible and the tab is
shown, and not at all under reduced motion. Buttons send trigger "open" -> page key; Python calls st.switch_page.
"""
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
TARGETS = ("home", "outlook", "weather", "storm", "evidence")
HEADING = "Weather intelligence. Sustainability first."
TEXT = ("Bring weather, pavement evidence, and treatment comparisons into one view. Explore ways to reduce avoidable salt use "
        "while maintaining safe, accessible roads—with people making every treatment decision.")
CTA = "Explore Storm Lab"
LINKS = [("Home", "home"), ("Road Weather", "weather"), ("Storm Outlook", "outlook"), ("Storm Lab", "storm"), ("Evidence", "evidence")]


def _logo_light():
    svg = (HERE / "assets" / "saltwise_logo.svg").read_text()
    return svg.replace('<tspan fill="#15171C"', '<tspan fill="#F2F4F6"')


HTML = '<div data-cl-root></div>'
CSS = r"""
:host { display:block; }
.wrap { width:100vw; margin-left:calc(50% - 50vw); color:#FFFFFF; font-family:inherit; }
.closing { position:relative; overflow:hidden; min-height:max(520px, 64vh); display:flex; align-items:center; justify-content:center;
  background:radial-gradient(ellipse 70% 58% at 50% -4%, rgba(222,231,239,.52), rgba(222,231,239,0) 64%),
             linear-gradient(180deg, #66737F 0%, #46525E 36%, #26313B 74%, #121A21 100%); }
canvas.snow { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
.cta { position:relative; z-index:2; text-align:center; max-width:860px; padding:96px 24px; }
h2 { font-size:44px; line-height:1.2; letter-spacing:-.035em; font-weight:300; margin:0 0 18px; }
.cta p { font-size:19px; line-height:1.6; color:rgba(255,255,255,.86); margin:0 auto 28px; max-width:760px; }
.go { font:inherit; font-size:16px; font-weight:650; color:#1A0B02; background:#D2560A; border:0; border-radius:999px; padding:12px 24px; cursor:pointer; }
.go:hover { filter:brightness(1.08); }
footer { background:#121A21; padding:40px 48px 36px; }
.frow { display:flex; flex-wrap:wrap; align-items:flex-start; justify-content:space-between; gap:24px 48px; max-width:1864px; margin:0 auto; }
.brand { display:flex; flex-direction:column; gap:12px; max-width:440px; }
.logo { display:inline-flex; background:none; border:0; padding:0; cursor:pointer; width:max-content; }
.logo svg { width:200px; height:auto; display:block; }
.mission { font-size:14px; line-height:1.55; color:rgba(255,255,255,.72); margin:0; }
nav ul { list-style:none; margin:0; padding:0; display:flex; flex-wrap:wrap; gap:8px 22px; }
nav button, .meta button { font:inherit; font-size:15px; color:rgba(255,255,255,.86); background:none; border:0; padding:4px 0; cursor:pointer; }
nav button:hover, .meta button:hover { color:#FFFFFF; text-decoration:underline; text-underline-offset:3px; }
.meta { max-width:1864px; margin:28px auto 0; padding-top:18px; border-top:1px solid rgba(255,255,255,.12); display:flex; flex-wrap:wrap; gap:8px 24px;
  justify-content:space-between; font-size:13px; color:rgba(255,255,255,.62); }
.meta button { font-size:13px; color:rgba(255,255,255,.78); text-decoration:underline; text-underline-offset:2px; }
button:focus-visible { outline:2px solid #FF9A57; outline-offset:3px; border-radius:4px; }
@media (max-width: 760px) {
  .cta { padding:72px 16px; text-align:left; }
  h2 { font-size:30px; }
  .cta p { font-size:16.5px; }
  footer { padding:32px 16px 28px; }
  .logo svg { width:170px; }
}
"""
JS = r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector('[data-cl-root]');
  if (!root) return;
  if (root.__clCleanup) root.__clCleanup();
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  root.innerHTML = `<div class="wrap">
    <section class="closing" aria-labelledby="cl-h"><canvas class="snow" aria-hidden="true" data-frames="0"></canvas>
      <div class="cta"><h2 id="cl-h">${esc(data.heading)}</h2><p>${esc(data.text)}</p>
        <button type="button" class="go" data-target="storm">${esc(data.cta)} <span aria-hidden="true">→</span></button></div></section>
    <footer aria-label="SaltWise DC footer"><div class="frow">
      <div class="brand"><button type="button" class="logo" data-target="home" aria-label="SaltWise DC: go to Home">${data.logo}</button>
        <p class="mission">Reduce avoidable salt use while keeping safe, accessible roads and required service. Student prototype; people make every treatment decision.</p></div>
      <nav aria-label="Footer"><ul>${data.links.map(([t, k]) => `<li><button type="button" data-target="${k}">${esc(t)}</button></li>`).join('')}</ul></nav></div>
      <div class="meta"><span>Prototype · not for operational use · previews use labeled simulations</span>
        <button type="button" data-target="evidence">Media credits, licenses and seasonal sources</button></div></footer></div>`;
  const offs = [], on = (el, ev, fn, o) => { el.addEventListener(ev, fn, o); offs.push(() => el.removeEventListener(ev, fn, o)); };
  root.querySelectorAll('[data-target]').forEach(b => on(b, 'click', () => setTriggerValue('open', b.dataset.target)));
  // sparse, small, slow snow (decorative)
  const sec = root.querySelector('.closing'), cv = root.querySelector('canvas.snow'), ctx = cv.getContext('2d');
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  let W = 0, H = 0, flakes = [], raf = 0, last = 0, visible = false;
  function size() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2), r = sec.getBoundingClientRect();
    W = r.width; H = r.height; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(90, Math.max(24, W * H / 16000)));
    flakes = Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H, r: 0.5 + Math.random() * 1.1, a: 0.22 + Math.random() * 0.45,
      vy: 7 + Math.random() * 14, ph: Math.random() * 6.28, sw: 4 + Math.random() * 8 }));
    draw(0);
  }
  function draw(dt) {
    ctx.clearRect(0, 0, W, H);
    for (const f of flakes) {
      if (dt) { f.y += f.vy * dt; f.ph += dt * 0.5; if (f.y > H + 4) { f.y = -4; f.x = Math.random() * W; } }
      const x = f.x + Math.sin(f.ph) * f.sw;
      ctx.globalAlpha = f.a * (0.55 + 0.45 * (1 - f.y / Math.max(H, 1))); ctx.fillStyle = '#FFFFFF';
      ctx.beginPath(); ctx.arc(x, f.y, f.r, 0, 6.2832); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  function loop(t) { const dt = last ? Math.min((t - last) / 1000, 0.05) : 0; last = t; draw(dt); cv.dataset.frames = String(+cv.dataset.frames + 1); raf = requestAnimationFrame(loop); }
  function sync() { const run = visible && !document.hidden && !mq.matches;
    if (run && !raf) { last = 0; raf = requestAnimationFrame(loop); } else if (!run && raf) { cancelAnimationFrame(raf); raf = 0; } }
  const io = new IntersectionObserver(es => { visible = es[0].isIntersecting; sync(); }, { threshold: 0 });
  io.observe(sec);
  on(document, 'visibilitychange', sync); on(mq, 'change', sync); on(window, 'resize', size);
  size();
  const cleanup = () => { if (raf) cancelAnimationFrame(raf); raf = 0; io.disconnect(); offs.forEach(f => f()); offs.length = 0; root.__clCleanup = null; };
  root.__clCleanup = cleanup;
  return cleanup;
}
"""


def _register():
    return st.components.v2.component("saltwise_closing", html=HTML, css=CSS, js=JS, isolate_styles=True)


_component = _register()


def _mount(**kwargs):
    global _component
    from streamlit.errors import StreamlitAPIException
    try:
        return _component(**kwargs)
    except StreamlitAPIException as e:
        if "not registered" not in str(e):
            raise
        _component = _register()
        return _component(**kwargs)


def render(key="home_closing"):
    """Mount the closing section and footer. Returns the page key to open when a button was pressed, else None."""
    result = _mount(key=key, data={"heading": HEADING, "text": TEXT, "cta": CTA, "links": LINKS, "logo": _logo_light()},
                    on_open_change=lambda: None)
    target = getattr(result, "open", None) if result is not None else None
    return target if target in TARGETS else None
