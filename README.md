# SaltWise DC: review demo (simulation mode)

A shared review build of the SaltWise DC dashboard, a student research prototype that flags locations for human review to
reduce avoidable salt use while keeping required road service. **People make every treatment decision; SaltWise never
approves or cancels treatment. Treatment thresholds are illustrative.**

## What this build does and does not do
- **Simulation mode only.** Road Weather and Storm Lab show a synthetic scenario, labelled "SYNTHETIC SCENARIO". A banner on every page says so.
- **Data kinds stay distinct:**
  - simulated values are never presented as observations or forecasts;
  - air and pavement temperatures are separate series;
  - missing values show as gaps or "Unavailable", never as zero or "no treatment".
- **Live weather requests are disabled** (`demo_config.LIVE_WEATHER_REQUESTS = False`):
  - Storm Outlook's "Load NWS forecast" button is disabled;
  - the NWS loader refuses before any cache, log or network access;
  - no request can reach the National Weather Service or Xweather.
- **No provider data, credentials or secrets are included.**
  - The provider-data switch on Road Weather is locked to the simulated scenario.
  - The Evidence page reports that no snapshot store exists.
  - No Streamlit secrets are needed.
- **Pages:** Home, Storm Outlook, Road Weather, Storm Lab, Evidence. Storm Lab's inputs, comparison and JSON exports work as in the full app.

## Run locally (Python 3.12)
```
cd saltwise-dc-demo
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```
Then open the URL Streamlit prints (normally http://localhost:8501).

## Deploy on Streamlit Community Cloud (public link)
1. **Sign in:** go to https://share.streamlit.io and sign in with the GitHub account that owns this public repository.
2. **Create the app:** click **Create app**, then **Yup, I have an app**, and enter:
   - Repository: `iamgtm/saltwise-dc-demo`;
   - Branch: `main`;
   - Main file path: `main.py`;
   - App URL: a subdomain of your choice, for example `saltwise-dc-demo`.
3. **Advanced settings:** set **Python version** to **3.12**. Leave **Secrets** empty, then click **Save** or **Deploy**.
4. **Share the link:** apps deployed from public repositories are public. Anyone with the app link (`https://<subdomain>.streamlit.app`) can open it in a browser without signing in.

**Community Cloud notes** (from its documentation):
- apps are hosted in the United States;
- the working directory is the repository root;
- some settings are fixed by the platform (for example, error details are hidden).

## Files
- `main.py` is the entry point, with top navigation; `app.py` is the Road Weather page.
- The remaining `*.py` files hold the other pages and the logic.
- `demo_config.py` holds the demo build settings and banner.
- `.streamlit/config.toml` holds the theme and static file serving; `static/media/` holds local media, with `SOURCES.json` as the licence record.
- `assets/` holds the logo and DC boundary; `data/locations/registry.json` lists the five review locations (public location metadata only).

## Changes from the source dashboard (demo build only)
- **Added** `demo_config.py` and a banner shown on every page.
- **Contained paths:** `nws_outlook.py`, `evidence_snapshot.py` and `freshness.py` resolve every path inside this package.
- **Live loading disabled:** `nws_outlook.py` refuses live requests, and `outlook_view.py` disables the Load button and explains why.
- **Simulation only:** `app.py` locks the data-mode switch to the simulated scenario.
- **Cloud config:** `.streamlit/config.toml` drops the local-only server address and headless settings.
- **Unchanged:** calculations, assumptions, evidence labels, exports and visual design.

## Media credits (decorative footage and photographs; not data)
| File | Creator | Licence | Source |
| --- | --- | --- | --- |
| `home_dc_city.mp4` | Jonmallard | CC BY 4.0 | https://commons.wikimedia.org/wiki/File%3AWashington_monument_timelapse.webm |
| `outlook_storm_clouds.mp4` | Grand Canyon NPS | Public domain | https://commons.wikimedia.org/wiki/File%3ATime-lapse_Video-_Winter_Storm_at_Yaki_Point_Grand_Canyon_2014-01-31_%2812242435983%29.webm |
| `weather_road.mp4` | Vladislav Sanikovich | CC BY 3.0 | https://commons.wikimedia.org/wiki/File%3AAerial_views_of_a_car_driving_in_snow_through_a_forest.webm |
| `stormlab_snowplow.mp4` | Роман Рябенко | CC0 | https://commons.wikimedia.org/wiki/File%3A%D0%9F%D0%BB%D1%83%D0%B6%D0%BD%D0%B8%D0%B9_%D1%81%D0%BD%D1%96%D0%B3%D0%BE%D0%BE%D1%87%D0%B8%D1%81%D0%BD%D0%B8%D0%BA_%D0%BD%D0%B0_%D0%B2%D1%83%D0%BB%D0%B8%D1%86%D1%96.webm |
| `evidence_bridge.mp4` | G. Edward Johnson | CC BY 4.0 | https://commons.wikimedia.org/wiki/File%3AEast_Potomac_Park_under_I-395_Washington_DC_2024-01-13_08-06-41_1.webm |
| `intro_photo.jpg` | Victoria Stauffenberg | Public domain | https://commons.wikimedia.org/wiki/File%3ALincoln_Memorial_at_National_Mall_%26_Memorial_Parks_%28e0a73461-c2c5-43aa-b667-6f2df69cdfdb%29.jpg |
