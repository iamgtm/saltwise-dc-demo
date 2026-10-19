"""Deterministic planner briefing: Python-generated text from computed review items, coverage and evidence only.

No language model, no network, no new thresholds or material rates, and no treatment approval. Every review item is
listed with its rule, window and evidence IDs; uncertainty and missing evidence are always stated, and evidence is
never described as fresh unless an approved freshness policy confirms it.
"""
import saltwise_contract as sc

LABEL = "PYTHON-GENERATED BRIEFING"
METHOD = ("Deterministic Python text built only from computed review items, coverage and evidence. No language model and no new "
          "thresholds or material rates; it never approves or cancels treatment.")
PENDING = ("DPW and DOEE operational input: pending. DPW acknowledged the inquiry and offered coordination; substantive answers "
           "and the DOEE referral are pending, so nothing here reflects their review or validation of these rules.")
DECISION = "People make every treatment decision. SaltWise flags locations for review and never approves or cancels treatment."


def _when(iso):
    return sc._when(iso) if iso else "unknown"


def _fresh(fr, label):
    if not fr:
        return None
    age = (f"retrieved {fr['retrieval_age_h']:g} h before the evaluation time (a lower bound on forecast age, not proof of it)"
           if fr.get("retrieval_age_h") is not None else "retrieval time unknown")
    issue = f"provider issue time {fr['issue_time']}" if fr.get("issue_time") else "provider issue time not supplied"
    if fr["status"] == "not_assessed":
        return f"{label}: freshness not assessed because no freshness policy is approved, so it is not confirmed fresh; {issue}; {age}."
    if fr.get("confirmed_fresh"):
        return f"{label}: within the approved freshness policy {fr['policy']}; {issue}; {age}."
    return f"{label}: freshness {fr['status'].replace('_', ' ')} under {fr['policy']}, so it is not confirmed fresh; {issue}; {age}."


def _coverage(c):
    parts = []
    for key, label in (("air", "Air forecast"), ("pavement", "Pavement modeled forecast (returned horizon only, never extended)")):
        x = c[key]
        if not x["supported_to"]:
            parts.append(f"{label}: no supported values in the selected window.")
        else:
            tail = f"; the last {x['unsupported_h']:g} h of the window are unsupported" if x["unsupported_h"] > 0 else ""
            parts.append(f"{label}: supported from {_when(x['supported_from'])} to {_when(x['supported_to'])}{tail}.")
    return " ".join(parts)


def build(packs, generated_at, data_mode):
    """packs: review_items.build() results. Returns the briefing as structured sections plus Markdown text."""
    provider = data_mode == "provider_snapshot"
    head = [f"**{LABEL}** — {METHOD}",
            f"Evaluated at {generated_at}. Data: "
            + ("saved provider snapshots (NWS air forecast; Xweather modeled pavement, not sensor observations)." if provider
               else "synthetic scenario (illustrative, not a forecast).")]
    sections, body = [], []
    for p in packs:
        L, items = p["location"], p["items"]
        s = L["statuses"]
        lines = [(f"{L['name']}: {len(items)} review item(s) from illustrative rules." if items else
                  f"{L['name']}: no illustrative review rule fired in the supported evidence. This is not a statement that "
                  "treatment is unnecessary; conditions outside the supported coverage are unknown."),
                 f"Location statuses (kept separate): geographic verification — {s['geographic_verification']['label']}; provider "
                 f"road match — {s['provider_road_matching']['label']}; bridge-specific modeling — {s['bridge_specific_modeling']['label']}.",
                 _coverage(p["coverage"])]
        lines += [x for x in (_fresh(p["freshness"].get("pavement"), "Pavement evidence"), _fresh(p["freshness"].get("air"), "Air evidence")) if x]
        refs = []
        for it in items:
            ids = it["evidence_ids"]
            cited = ids[:3]
            ev = ((", ".join(f"`{i}`" for i in cited) + (f" and {len(ids) - 3} more in the export" if len(ids) > 3 else ""))
                  if ids else "none available (see missing evidence)")
            lines.append(f"- [{it['item_id']}] **{it['title']}** — rule `{it['rule']['rule_id']}` v{it['rule']['rule_version']}; "
                         f"{_when(it['window']['start'])} to {_when(it['window']['end'])}. {it['explanation']} Evidence: {ev}. "
                         f"Next human review step: {it['next_step']}")
            refs.append({"item_id": it["item_id"], "evidence_ids_cited": cited, "evidence_ids_total": len(ids)})
        unc = list(dict.fromkeys(p["location_uncertainty"] + p["conflicting"] + [m for it in items for m in it["missing"]]))
        if unc:
            lines.append("Uncertainty and missing evidence: " + " ".join(unc[:8])
                         + (f" ({len(unc) - 8} more in the export.)" if len(unc) > 8 else ""))
        lines.append("This location stays in assumed service; missing or withheld evidence never means treatment is unnecessary.")
        sections.append({"location_id": L["location_id"], "lines": lines, "items": refs})
        body.append("\n\n".join(lines))
    return {"label": LABEL, "method": METHOD, "generated_at": generated_at, "data_mode": data_mode, "llm_used": False,
            "sections": sections, "pending_operational_input": PENDING, "decision_note": DECISION,
            "text": "\n\n".join(head + body + [f"**Operational input:** {PENDING}", DECISION])}
