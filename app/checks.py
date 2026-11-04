"""Rule-based review checks. Every finding cites the rule or approved source it relies on."""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "data" / "brand.json").read_text(encoding="utf-8"))
SEV = {"high": 0, "medium": 1, "low": 2, "info": 3}
NUM = r"\d+(?:\.\d+)?\s?%|\d+\s*out\s*of\s*\d+|(?:₹|rs\.?\s?)\s?\d+|\d+(?:\.\d+)?\s*(?:g|kg|ml|kcal|calories)\b"


def _mk(cat, sev, start, end, text, why, rule, source, suggestion=None, confidence="high", status="issue"):
    return {"category": cat, "severity": sev, "start": start, "end": end, "text": text, "why": why,
            "rule_id": rule, "source": source, "suggestion": suggestion, "confidence": confidence, "status": status}


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def review(text, channel="social", has_image=False, alt_text="", today=None):
    today = today or date.today()
    out = []

    # 1. Terminology (exact rules)
    for t in BRAND["terms"]:
        pat = "|".join(re.escape(a) for a in t["avoid"])
        for m in re.finditer(r"(?<![#\w])(?:%s)(?!\w)" % pat, text, re.I):
            out.append(_mk("terminology", "medium", m.start(), m.end(), m.group(),
                           "'%s' is not preferred. Use '%s'." % (m.group(), t["use"]), t["rule"], t["source"],
                           {"type": "replace", "with": t["use"]}))

    # 2. Promotional claims
    for c in BRAND["claim_rules"]:
        for m in re.finditer(c["pattern"], text, re.I):
            out.append(_mk("claims", c["severity"], m.start(), m.end(), m.group(), c["why"], c["rule"], c["source"],
                           {"type": "note", "text": c["fix"]}))
    for c in BRAND["approved_claims"]:
        for m in re.finditer(re.escape(c["text"]), text, re.I):
            out.append(_mk("claims", "info", m.start(), m.end(), m.group(),
                           "Supported by approved claim %s." % c["id"], c["id"], "Evidence on file: " + c["evidence"],
                           status="supported"))

    # 3. Facts: supported, contradicted, outdated; unmatched numbers are 'cannot verify'
    covered = []
    for f in BRAND["facts"]:
        expired = f.get("valid_until") and date.fromisoformat(f["valid_until"]) < today
        for m in re.finditer(f["pattern"], text, re.I):
            covered.append((m.start(), m.end()))
            src = "%s (owner: %s)" % (f["text"], f["owner"])
            if expired:
                out.append(_mk("facts", "high", m.start(), m.end(), m.group(),
                               "Outdated: this offer or fact expired on %s." % f["valid_until"], f["id"], src,
                               {"type": "note", "text": "Remove it, or ask the owner (%s) for a current version." % f["owner"]}))
                continue
            if f.get("value") is None:
                continue
            nums = [g for g in m.groups() if g]
            if not nums:
                continue
            val = float(nums[0].replace(",", ""))
            if abs(val - f["value"]) < 1e-9:
                out.append(_mk("facts", "info", m.start(), m.end(), m.group(),
                               "Matches approved fact %s." % f["id"], f["id"], src, status="supported"))
            else:
                gi = [i for i, g in enumerate(m.groups()) if g][0] + 1
                gs, ge = m.start(gi) - m.start(), m.end(gi) - m.start()
                new = m.group()[:gs] + _fmt(f["value"]) + m.group()[ge:]
                out.append(_mk("facts", "high", m.start(), m.end(), m.group(),
                               "Contradicts approved fact %s (%s)." % (f["id"], f["label"]), f["id"], src,
                               {"type": "replace", "with": new}))
    for m in re.finditer(NUM, text, re.I):
        if not any(s <= m.start() and m.end() <= e for s, e in covered):
            out.append(_mk("facts", "medium", m.start(), m.end(), m.group(),
                           "No approved source found for this figure, so it cannot be verified.", "V-1",
                           "Facts policy 5.1: Every number must match an approved fact.",
                           {"type": "note", "text": "Add an approved fact for it, or remove the figure."}, confidence="medium"))

    # 4. Tone (rule-based approximation)
    tone = BRAND["tone"]
    for w in tone["avoid"]:
        for m in re.finditer(r"(?<!\w)%s(?!\w)" % re.escape(w), text, re.I):
            out.append(_mk("tone", "low", m.start(), m.end(), m.group(), "Hype word. Describe the benefit plainly.",
                           "TN-1", tone["source_hype"], confidence="medium"))
    for m in re.finditer(r"!{2,}", text):
        out.append(_mk("tone", "medium", m.start(), m.end(), m.group(), "Too many exclamation marks.", "TN-2",
                       tone["source_excl"], {"type": "replace", "with": "!"}))
    for m in re.finditer(r"\b[A-Z]{4,}\b", text):
        if m.group() not in tone["caps_ok"]:
            out.append(_mk("tone", "low", m.start(), m.end(), m.group(), "Whole word in capitals reads as shouting.",
                           "TN-3", tone["source_caps"], {"type": "replace", "with": m.group().capitalize()}))

    # 5. Accessibility
    for m in re.finditer(r"#[a-z0-9]{9,}\b", text):
        out.append(_mk("accessibility", "low", m.start(), m.end(), m.group(),
                       "Long all-lowercase hashtags are hard for screen readers.", "AC-1",
                       "Accessibility 6.1: Capitalise each word in a hashtag, like #HealthySnacks.",
                       {"type": "note", "text": "Capitalise each word, for example #HealthySnacks."}))
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        if len(m.group().split()) > 25:
            out.append(_mk("accessibility", "low", m.start(), m.end(), m.group().strip()[:40] + "...",
                           "Sentence is longer than 25 words and hard to read.", "AC-2",
                           "Accessibility 6.2: Keep sentences under 25 words.",
                           {"type": "note", "text": "Split it into two shorter sentences."}))
    if has_image and len(alt_text.strip()) < 8:
        out.append(_mk("accessibility", "medium", None, None, "", "Image has no useful alt text.", "AC-3",
                       "Accessibility 6.3: Every image needs alt text describing what it shows.",
                       {"type": "note", "text": "Add a short description of the image."}))

    # 6. Partnership disclosure
    d = BRAND["disclosure"]
    if not re.search(d["ok"], text, re.I):
        for m in re.finditer(d["pattern"], text, re.I):
            out.append(_mk("disclosure", "high", m.start(), m.end(), m.group(),
                           "Partnership mentioned without a clear disclosure.", d["rule"], d["source"],
                           {"type": "append", "text": " #ad"}))

    out.sort(key=lambda f: (f["start"] if f["start"] is not None else 10 ** 9, SEV[f["severity"]]))
    seen = {}
    for f in out:
        key = (f["rule_id"], f["text"].lower())
        seen[key] = seen.get(key, -1) + 1
        f["id"] = "%s|%s|%d" % (f["rule_id"], f["text"].lower(), seen[key])
    counts = {s: sum(1 for f in out if f["severity"] == s) for s in SEV}
    return {"findings": out, "counts": counts}
