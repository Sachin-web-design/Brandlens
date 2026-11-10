"""Guideline clarity insights and the reviewer learning loop.
Looks at review history, finds rules that are unclear or too strict (or often broken), proposes changes,
and applies them ONLY after a Manager approves. Compliance-critical rules (facts, disclosure) are never tuned."""
import json
import os
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import checks

FILE = Path(os.environ.get("TUNING_FILE", checks.ROOT / "data" / "tuning.json"))
LOCK = threading.Lock()
ORDER = ["low", "medium", "high"]
PROTECTED = {"facts", "disclosure"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"overrides": {}, "wording": {}}


def _save(d):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def overrides():
    return _load()["overrides"]


def wording():
    return _load()["wording"]


def meta():
    """rule_id -> (category, base severity, source text)"""
    b, m = checks.BRAND, {}
    for t in b["terms"]:
        m[t["rule"]] = ("terminology", "medium", t["source"])
    for c in b["claim_rules"]:
        m[c["rule"]] = ("claims", c["severity"], c["source"])
    t = b["tone"]
    m["TN-1"] = ("tone", "low", t["source_hype"])
    m["TN-2"] = ("tone", "medium", t["source_excl"])
    m["TN-3"] = ("tone", "low", t["source_caps"])
    m["AC-1"] = ("accessibility", "low", "Accessibility 6.1: Capitalise each word in a hashtag, like #HealthySnacks.")
    m["AC-2"] = ("accessibility", "low", "Accessibility 6.2: Keep sentences under 25 words.")
    m["AC-3"] = ("accessibility", "medium", "Accessibility 6.3: Every image needs alt text describing what it shows.")
    m["D-1"] = ("disclosure", "high", b["disclosure"]["source"])
    m["V-1"] = ("facts", "medium", "Facts policy 5.1: Every number must match an approved fact.")
    for f in b["facts"]:
        m[f["id"]] = ("facts", "high", f["text"])
    return m


def default_wording(rule_id):
    for t in checks.BRAND["terms"]:
        if t["rule"] == rule_id:
            return ("%s Allowed: '%s'. Not allowed: '%s'. Applies to all public content unless a Manager approves an exception."
                    % (t["source"], t["use"], t["avoid"][0]))
    src = meta().get(rule_id, ("", "", ""))[2]
    return src + " Add one allowed and one not-allowed example, and say when the rule does not apply."


def stats(items):
    m, S = meta(), {}

    def row(rid):
        cat, sev, src = m.get(rid, ("other", "low", rid))
        return S.setdefault(rid, {"rule_id": rid, "category": cat, "base_severity": sev, "source": src,
                                  "flagged": 0, "dismissed": 0, "fixes_applied": 0, "reasons": Counter()})
    for s in items:
        for f in s["findings"]:
            if f["status"] != "issue":
                continue
            r = row(f["rule_id"])
            r["flagged"] += 1
            d = f.get("decision")
            if d and d.get("action") == "dismissed":
                r["dismissed"] += 1
                r["reasons"][d.get("reason", "")] += 1
        for fx in s.get("applied_fixes", []):
            r = row(fx.get("rule_id", "?"))
            r["flagged"] += 1
            r["fixes_applied"] += 1
    return S


def _diagnose(r):
    rate = r["dismissed"] / r["flagged"] if r["flagged"] else 0
    unclear = r["reasons"].get("Guideline is unclear", 0)
    if r["flagged"] >= 3 and (rate >= 0.5 or unclear >= 2):
        return "unclear_or_strict"
    if r["flagged"] >= 4 and rate < 0.3 and r["fixes_applied"] >= 3:
        return "frequently_broken"
    return "ok"


def clarity(items):
    ov, wd, rules = overrides(), wording(), []
    for rid, r in stats(items).items():
        diag = _diagnose(r)
        tuned = rid in ov
        if diag == "ok" and not tuned:
            continue
        rate = r["dismissed"] / r["flagged"] if r["flagged"] else 0
        sev = ov[rid]["severity"] if tuned else r["base_severity"]
        proposal = None
        if diag == "unclear_or_strict":
            label = "Possibly unclear or too strict"
            text = ("Creators dismissed this rule in %d%% of cases (%d of %d), %d times as 'Guideline is unclear'. "
                    "Clarify it with one allowed and one not-allowed example, and say when it does not apply."
                    % (round(rate * 100), r["dismissed"], r["flagged"], r["reasons"].get("Guideline is unclear", 0)))
            if r["category"] in PROTECTED:
                text += " This is a compliance-critical rule, so its severity is never tuned automatically."
            elif r["base_severity"] != "low" and not tuned:
                to = ORDER[ORDER.index(r["base_severity"]) - 1]
                proposal = {"type": "lower_severity", "from": r["base_severity"], "to": to,
                            "text": "Lower severity from %s to %s until the wording is clarified." % (r["base_severity"], to)}
        elif diag == "frequently_broken":
            label = "Clear but often broken"
            text = ("This rule was triggered %d times and %d fixes were applied, but it is rarely disputed. "
                    "The rule is clear; creators may need a reminder, template or training." % (r["flagged"], r["fixes_applied"]))
        else:
            label = "Tuned by a Manager"
            text = "Severity was changed by a Manager. Revert if the wording is now clear."
        rules.append({"rule_id": rid, "category": r["category"], "severity": sev, "source": r["source"],
                      "flagged": r["flagged"], "dismissed": r["dismissed"], "dismissal_rate": round(rate, 2),
                      "fixes_applied": r["fixes_applied"], "reasons": dict(r["reasons"]), "diagnosis": diag,
                      "diagnosis_label": label, "suggestion": text, "proposal": proposal, "tuned": tuned,
                      "wording": (wd.get(rid) or {}).get("text", ""), "default_wording": default_wording(rid)})
    rules.sort(key=lambda x: (x["diagnosis"] == "ok", -x["flagged"]))
    return {"rules": rules}


def apply(items, role, rule_id, action, text=""):
    if role != "manager":
        raise PermissionError("Only a Manager can approve guideline changes.")
    with LOCK:
        d = _load()
        if action == "lower_severity":
            rule = next((r for r in clarity(items)["rules"] if r["rule_id"] == rule_id), None)
            if not rule or not rule["proposal"]:
                raise ValueError("No approved-eligible proposal exists for this rule.")
            d["overrides"][rule_id] = {"severity": rule["proposal"]["to"], "from": rule["proposal"]["from"],
                                       "approved_by": "manager", "at": _now()}
        elif action == "revert":
            d["overrides"].pop(rule_id, None)
        elif action == "accept_wording":
            w = (text or "").strip() or default_wording(rule_id)
            d["wording"][rule_id] = {"text": w[:600], "approved_by": "manager", "at": _now()}
        else:
            raise ValueError("Unknown action")
        _save(d)
    return clarity(items)
