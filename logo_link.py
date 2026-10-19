"""Makes the st.logo image in the persistent header a keyboard-accessible Home link that uses the existing
client-side navigation (it clicks the top-nav or menu "Home" link), so session state is kept. Browser-only;
no Python rerun except the navigation itself. Mounted once per run from main.py (hidden element)."""
import streamlit as st

JS = r"""
export default function () {
  if (window.__swLogoCleanup) window.__swLogoCleanup();
  const SEL = '[data-testid=stHeaderLogo], [data-testid=stSidebarLogo]';
  const home = () => [...document.querySelectorAll('[data-testid=stTopNavLink], [data-testid=stSidebarNavLink]')]
    .find(a => a.textContent.trim() === 'Home');
  const decorate = () => document.querySelectorAll(SEL).forEach(img => {
    if (img.dataset.swHome) return;
    img.dataset.swHome = '1'; img.setAttribute('role', 'link'); img.tabIndex = 0;
    img.setAttribute('aria-label', 'SaltWise DC: go to Home'); img.setAttribute('alt', 'SaltWise DC');
  });
  const go = e => {
    const img = e.target.closest && e.target.closest(SEL);
    if (!img) return;
    if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
    const link = home();
    if (!link) return;                  // no client link available: leave default behavior
    e.preventDefault(); e.stopPropagation(); link.click();
  };
  decorate();
  const mo = new MutationObserver(decorate);
  mo.observe(document.body, { childList: true, subtree: true });
  document.addEventListener('click', go, true);
  document.addEventListener('keydown', go, true);
  const cleanup = () => { mo.disconnect(); document.removeEventListener('click', go, true); document.removeEventListener('keydown', go, true); window.__swLogoCleanup = null; };
  window.__swLogoCleanup = cleanup;
  return cleanup;
}
"""


def _register():
    return st.components.v2.component("saltwise_logo_link", js=JS, isolate_styles=True)


_component = _register()


def mount():
    global _component
    from streamlit.errors import StreamlitAPIException
    try:
        _component(key="sw_logo_link")
    except StreamlitAPIException as e:
        if "not registered" not in str(e):
            raise
        _component = _register()
        _component(key="sw_logo_link")
