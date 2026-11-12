"""Benchmark of 50 sample posts with planted issues (Round 3, Improvement 1).
Run `python -m app.benchmark` for the rule layer, or `python -m app.benchmark --ai` (needs GEMINI_API_KEY)
to also measure the optional AI layer. Results are saved to data/benchmark_results.json."""
import json
import sys
from datetime import datetime, timezone

from . import ai, checks

BENCH = checks.ROOT / "data" / "benchmark.json"
RESULTS = checks.ROOT / "data" / "benchmark_results.json"


def load():
    return json.loads(BENCH.read_text(encoding="utf-8"))["items"]


def _span(item, planted):
    q = planted.get("quote") or ""
    i = item["text"].find(q) if q else -1
    return (i, i + len(q)) if i >= 0 else None


def _hits(item, planted, findings):
    sp = _span(item, planted)
    for f in findings:
        if planted["rule_ids"] and f["rule_id"] in planted["rule_ids"]:
            return True
        if sp and f["start"] is not None and f["start"] < sp[1] and sp[0] < f["end"]:
            return True
    return False


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def run_rules(items=None):
    items = items or load()
    planted_total = caught = 0
    by_cat, by_layer = {}, {"rules": [0, 0], "ai": [0, 0]}
    clean = fa_hm = fa_any = 0
    issues = cites = cannot = 0
    missed, false_alarms = [], []
    for it in items:
        fs = [f for f in checks.review(it["text"], it["channel"], it["has_image"], it["alt_text"])["findings"] if f["status"] == "issue"]
        issues += len(fs)
        cites += sum(1 for f in fs if f["rule_id"] and f["source"])
        cannot += sum(1 for f in fs if f["rule_id"] == "V-1")
        if it["clean"]:
            clean += 1
            if any(f["severity"] in ("high", "medium") for f in fs):
                fa_hm += 1
            if fs:
                fa_any += 1
                false_alarms.append({"id": it["id"], "text": it["text"], "rules": [f["rule_id"] for f in fs]})
            continue
        for p in it["planted"]:
            ok = _hits(it, p, fs)
            planted_total += 1
            caught += ok
            c = by_cat.setdefault(p["category"], [0, 0])
            c[0] += ok
            c[1] += 1
            by_layer[p["layer"]][0] += ok
            by_layer[p["layer"]][1] += 1
            if not ok:
                missed.append({"id": it["id"], "category": p["category"], "layer": p["layer"], "text": it["text"]})
    return {"items": len(items), "clean_items": clean, "planted_issues": planted_total, "caught": caught,
            "recall_pct": _pct(caught, planted_total),
            "recall_rule_targeted_pct": _pct(*by_layer["rules"]), "recall_ai_targeted_pct": _pct(*by_layer["ai"]),
            "by_category": {k: {"caught": v[0], "total": v[1], "pct": _pct(*v)} for k, v in sorted(by_cat.items())},
            "false_alarm_items_high_medium": fa_hm, "false_alarm_rate_pct": _pct(fa_hm, clean),
            "false_alarm_items_any": fa_any, "false_alarm_any_pct": _pct(fa_any, clean),
            "findings": issues, "with_valid_citation_pct": _pct(cites, issues), "cannot_verify_pct": _pct(cannot, issues),
            "missed": missed, "false_alarms": false_alarms}


def run_ai(items=None, llm=None):
    """Measures the optional AI layer on top of the rules. Needs GEMINI_API_KEY (or an injected llm for tests)."""
    items = items or load()
    ai_targeted = ai_caught = both_caught = planted_total = 0
    clean = clean_with_ai = accepted = cited = cannot = rejected = errors = 0
    model = ""
    for it in items:
        rules = [f for f in checks.review(it["text"], it["channel"], it["has_image"], it["alt_text"])["findings"] if f["status"] == "issue"]
        extra, status, stats = ai.analyse_full(it["text"], rules, llm=llm)
        if "error" in stats:
            errors += 1
            continue
        model = model or status
        accepted += stats["accepted"]
        cited += stats["cited"]
        cannot += stats["cannot_verify"]
        rejected += stats["rejected_not_in_text"] + stats["rejected_bad_category"]
        if it["clean"]:
            clean += 1
            clean_with_ai += 1 if extra else 0
            continue
        for p in it["planted"]:
            planted_total += 1
            by_ai = _hits(it, dict(p, rule_ids=[]), extra)
            by_rules = _hits(it, p, rules)
            both_caught += 1 if (by_ai or by_rules) else 0
            if p["layer"] == "ai":
                ai_targeted += 1
                ai_caught += 1 if by_ai else 0
    return {"items_run": len(items) - errors, "errors": errors, "ai_targeted_issues": ai_targeted,
            "ai_caught_of_ai_targeted": ai_caught, "ai_recall_pct": _pct(ai_caught, ai_targeted),
            "combined_recall_pct": _pct(both_caught, planted_total),
            "clean_items_with_ai_finding": clean_with_ai, "ai_false_alarm_pct": _pct(clean_with_ai, clean),
            "ai_findings_accepted": accepted, "with_valid_source_pct": _pct(cited, accepted),
            "cannot_verify_pct": _pct(cannot, accepted), "rejected_by_validator": rejected,
            "status": model, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def stored():
    return json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}


def results():
    st = stored()
    return {"rules": run_rules(), "ai": st.get("ai") or {"run": False,
            "note": "The AI layer has not been measured yet. Run `python -m app.benchmark --ai` with GEMINI_API_KEY set."}}


def main(argv):
    st = stored()
    st["rules"] = run_rules()
    st["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if "--ai" in argv:
        if not ai.enabled():
            print("GEMINI_API_KEY is not set: AI layer not measured.")
            return 1
        st["ai"] = run_ai()
    RESULTS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    r = st["rules"]
    print("Rule layer on %d items (%d clean, %d planted issues)" % (r["items"], r["clean_items"], r["planted_issues"]))
    print("  recall overall %s%% | rule-targeted %s%% | AI-targeted %s%%" % (r["recall_pct"], r["recall_rule_targeted_pct"], r["recall_ai_targeted_pct"]))
    print("  false alarms on clean: %s%% (high/medium), %s%% (any)" % (r["false_alarm_rate_pct"], r["false_alarm_any_pct"]))
    print("  valid citation %s%% | cannot verify %s%%" % (r["with_valid_citation_pct"], r["cannot_verify_pct"]))
    if "ai" in st:
        print("  AI layer:", json.dumps(st["ai"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
