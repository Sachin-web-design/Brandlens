"""Submissions, human review decisions and insights. Stored in a JSON file (simple, no database setup)."""
import json
import os
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import checks

DATA_FILE = Path(os.environ.get("DATA_FILE", checks.ROOT / "data" / "submissions.json"))
LOCK = threading.Lock()
REVIEW_ROLES = ("reviewer", "manager")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save(items):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def _build(title, author, text, channel, has_image, alt_text, decisions, fixes, status, history):
    res = checks.review(text, channel, has_image, alt_text)
    findings = []
    for f in res["findings"]:
        f = dict(f)
        f["decision"] = (decisions or {}).get(f["id"])
        findings.append(f)
    return {"id": "S" + uuid.uuid4().hex[:8], "title": title, "author": author,
            "channel": channel, "text": text, "has_image": has_image, "alt_text": alt_text, "findings": findings,
            "applied_fixes": fixes or [], "status": status, "created": _now(), "history": history, "comments": []}



def _dismiss(text, rules, reason):
    res = checks.review(text)
    return {f["id"]: {"action": "dismissed", "reason": reason} for f in res["findings"] if f["rule_id"] in rules}


def _demo_history():
    """Seeded history so the clarity insights are not empty on a fresh deploy (clearly labelled as seeded)."""
    hist = [{"at": _now(), "who": "creator", "action": "submitted", "comment": "Seeded demo history"},
            {"at": _now(), "who": "reviewer", "action": "approved", "comment": ""}]
    out = []
    plan = [("Hey guys, try our new oat bar. Each bar has 8 g of protein.", {"T-3"}, "Guideline is unclear"),
            ("Hey guys! Our bar is epic and costs Rs 49.", {"T-3", "TN-1"}, "Guideline is unclear"),
            ("Thanks guys for the love. This amazing bar is made with whole oats.", {"T-3", "TN-1"}, "Guideline is unclear"),
            ("Epic launch day at our store. #healthysnacksforyou", {"TN-1", "AC-1"}, "Not applicable here"),
            ("Our game-changer bar has 8 g of protein!", {"TN-1"}, "Approved exception")]
    for text, rules, reason in plan:
        out.append(_build("Seeded demo post", "Seeded demo", text, "social", False, "", _dismiss(text, rules, reason), [],
                          "Approved", list(hist)))
    for _ in range(4):
        out.append(_build("Seeded demo post", "Seeded demo", "Great oat bar. Each bar has 8 g of protein.", "social", False, "",
                          {}, [{"rule_id": "C-1", "before": "the BEST", "after": ""}], "Approved", list(hist)))
    return out

def _load():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = []
    samples = checks.BRAND["samples"]
    a = _build("Launch post (clean)", "Demo creator", samples[2]["text"], "social", False, "", {}, [], "Approved",
               [{"at": _now(), "who": "creator", "action": "submitted", "comment": ""},
                {"at": _now(), "who": "reviewer", "action": "approved", "comment": "All figures match approved facts."}])
    b = _build("Influencer collab post", "Demo creator", samples[1]["text"], "social", False, "", {}, [], "Changes requested",
               [{"at": _now(), "who": "creator", "action": "submitted", "comment": ""},
                {"at": _now(), "who": "reviewer", "action": "changes requested",
                 "comment": "Founding year is wrong and the partnership needs #ad."}])
    items = [a, b] + _demo_history()
    _save(items)
    return items


def list_submissions():
    with LOCK:
        return list(reversed(_load()))


def get(sub_id):
    for s in _load():
        if s["id"] == sub_id:
            return s
    raise KeyError(sub_id)


def create(p):
    if not p["text"].strip():
        raise ValueError("Content is empty")
    if not p["title"].strip():
        raise ValueError("Please give the content a title")
    decisions = p.get("decisions") or {}
    res = checks.review(p["text"], p["channel"], p["has_image"], p["alt_text"])
    pending = [f for f in res["findings"] if f["severity"] in ("high", "medium")
               and (decisions.get(f["id"]) or {}).get("action") != "dismissed"]
    if pending:
        raise ValueError("%d finding(s) still need a fix or a dismissal reason." % len(pending))
    for fid, d in decisions.items():
        if d.get("action") == "dismissed" and not d.get("reason"):
            raise ValueError("A dismissed finding needs a reason.")
    sub = _build(p["title"].strip(), p.get("author") or "Demo creator", p["text"], p["channel"], p["has_image"],
                 p["alt_text"], decisions, p.get("applied_fixes"), "In review",
                 [{"at": _now(), "who": "creator", "action": "submitted", "comment": ""}])
    with LOCK:
        items = _load()
        items.append(sub)
        _save(items)
    return sub


def decide(sub_id, role, action, comment):
    if role not in REVIEW_ROLES:
        raise PermissionError("Only a reviewer or manager can decide.")
    if action not in ("approve", "request_changes"):
        raise ValueError("Unknown action")
    if action == "request_changes" and not comment.strip():
        raise ValueError("Please add a comment explaining the changes you need.")
    with LOCK:
        items = _load()
        for s in items:
            if s["id"] == sub_id:
                dismissed_high = sum(1 for f in s["findings"] if f["severity"] == "high"
                                     and (f.get("decision") or {}).get("action") == "dismissed")
                note = comment.strip()
                if action == "approve" and dismissed_high:
                    note += (" " if note else "") + "(Approved with %d dismissed high-severity finding(s).)" % dismissed_high
                s["status"] = "Approved" if action == "approve" else "Changes requested"
                s["history"].append({"at": _now(), "who": role, "action": "approved" if action == "approve"
                                     else "changes requested", "comment": note})
                _save(items)
                return s
    raise KeyError(sub_id)


def add_comment(sub_id, role, text):
    if not text.strip():
        raise ValueError("Comment is empty")
    with LOCK:
        items = _load()
        for s in items:
            if s["id"] == sub_id:
                s["comments"].append({"at": _now(), "who": role, "text": text.strip()})
                _save(items)
                return s
    raise KeyError(sub_id)


def insights():
    items = _load()
    by_cat, by_rule, dismissed, fixes = Counter(), Counter(), Counter(), Counter()
    for s in items:
        for f in s["findings"]:
            if f["status"] == "issue":
                by_cat[f["category"]] += 1
                by_rule[f["rule_id"]] += 1
                if (f.get("decision") or {}).get("action") == "dismissed":
                    dismissed[f["rule_id"]] += 1
        for fx in s["applied_fixes"]:
            fixes[fx.get("rule_id", "?")] += 1
    statuses = Counter(s["status"] for s in items)
    return {"total": len(items), "statuses": dict(statuses), "by_category": dict(by_cat.most_common()),
            "top_rules": by_rule.most_common(6), "dismissed_rules": dismissed.most_common(6),
            "fixes_applied": sum(fixes.values())}
