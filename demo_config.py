"""Settings for the shared review build of SaltWise DC.

This build runs in simulation mode only: Road Weather and Storm Lab use the synthetic scenario, live weather requests
are disabled (no request to the National Weather Service or Xweather can be sent), and no provider snapshots or
credentials are included. Treatment thresholds stay illustrative; people make every treatment decision.
"""
DEMO_BUILD = True
LIVE_WEATHER_REQUESTS = False
BANNER_HTML = (
    '<style>.sw-demo-banner{margin:0 0 .75rem;padding:.55rem .9rem;border-left:4px solid #A3420A;background:#FFF4EC;'
    'color:#15171C;font-size:14px;line-height:1.45;border-radius:6px}.sw-demo-banner strong{color:#A3420A}</style>'
    '<div class="sw-demo-banner" role="note"><strong>DEMO · SIMULATION MODE.</strong> Road Weather and Storm Lab show a '
    'synthetic scenario, not observations or forecasts. Live weather requests are disabled and no provider data or '
    'credentials are included. Thresholds are illustrative; people make every treatment decision.</div>')
