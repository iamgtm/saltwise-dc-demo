# SaltWise DC: public demo (simulation mode)

A public demonstration build of the SaltWise DC dashboard, a student research prototype that flags locations for human
review to reduce avoidable salt use while keeping required road service. **People make every treatment decision; SaltWise
never approves or cancels treatment. Treatment thresholds are illustrative.**

Live app: https://saltwise-dc-demo.streamlit.app/

## What this build does and does not do
- **Simulation mode only.** Road Weather and Storm Lab show a synthetic scenario, labelled as such. A banner on every page says so.
- **Data kinds stay distinct:**
  - simulated values are never presented as observations or forecasts;
  - air and pavement temperatures are separate series, and pavement is shown only within its returned horizon;
  - missing values show as gaps or "Unavailable", never as zero or "no treatment".
- **Live weather requests are disabled** (`demo_config.LIVE_WEATHER_REQUESTS = False`):
  - Storm Outlook's "Load NWS forecast" button is disabled;
  - the NWS loader refuses before any cache, log or network access;
  - no request can reach the National Weather Service or Xweather.
- **No provider data, credentials, secrets or stakeholder correspondence are included.** The Road Weather data-mode switch is locked to the simulated scenario. No Streamlit secrets are needed.
- **Pages:**
  - **Home:** media and scroll animations.
  - **Storm Outlook:** the interface, with live loading off.
  - **Road Weather:** map with clickable roads, legend and detail panel; road cards and selector; air and pavement chart; review flags, evidence and JSON export.
  - **Storm Lab:** comparisons, later, repeat and catch-up accounting, sensitivity and exports.
  - **Evidence:** sources and methods.

## Run locally (Python 3.12)
```
cd saltwise-dc-demo
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```
Then open the URL Streamlit prints (normally http://localhost:8501).

## Streamlit Community Cloud
- **App settings:** repository `iamgtm/saltwise-dc-demo`, branch `main`, main file `main.py`, Python 3.12, no secrets.
- **Redeploy:** Community Cloud redeploys automatically when `main` changes.
- **Media paths:** media URLs are app-relative (`app/static/media/...`) so they work under Cloud's path prefix.

## Files
- **Entry point:** `main.py`, with top navigation. `app.py` is the Road Weather page; the other `*.py` files hold the remaining pages and logic.
- **Demo settings:** `demo_config.py` holds the demo build settings and banner. `run_config.json` holds only the approved freshness policy and the weather-request caps.
- **Configuration:** `.streamlit/config.toml` holds the theme and static file serving.
- **Media:** `static/media/` holds local media; `SOURCES.json` is the licence record.
- **Location data:** `assets/` holds the logo and DC boundary. `data/locations/registry.json` lists the five review locations (public location metadata only).

## Changes from the source dashboard (demo build only)
- **Banner:** added `demo_config.py` and a banner shown on every page.
- **Live loading disabled:** `nws_outlook.py` refuses live requests. `outlook_view.py` disables the Load button and explains why.
- **Simulation only:** `app.py` locks the data-mode switch to the simulated scenario.
- **Media:** `media.py` and `road_maintenance.py` use app-relative media URLs.
- **Correspondence removed:**
  - `dpw_feedback.py` carries no stakeholder correspondence; its notes are neutral and its functions are unchanged;
  - `evidence_view.py` shows only SaltWise's own pavement source in that section.
- **Cloud configuration:** `.streamlit/config.toml` drops the local-only server address and headless settings.
