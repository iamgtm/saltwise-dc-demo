"""Curated local media library (static/media): decorative stock footage and photographs with posters, served by
Streamlit static serving at /app/static/media/. Sources, creators and licenses: static/media/SOURCES.json (editable record)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "static" / "media" / "SOURCES.json"


def records():
    return json.loads(SOURCES.read_text())


def urls(slots):
    rec = {r["slot"]: r for r in records()}
    out = {}
    for s in slots:
        r = rec[s]
        out[s] = {"src": "/app/" + r["file"], "poster": "/app/" + r["poster"]}
        if r.get("file_small"):
            out[s]["small"] = "/app/" + r["file_small"]
    return out
