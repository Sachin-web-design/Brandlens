import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DATA_FILE"] = os.path.join(tempfile.mkdtemp(), "subs.json")
from app import checks, logic  # noqa: E402

S = checks.BRAND["samples"]


def rules(text, **kw):
    return {f["rule_id"] for f in checks.review(text, **kw)["findings"] if f["status"] == "issue"}


class CheckTests(unittest.TestCase):
    def test_sample1_catches_planted_errors(self):
        r = rules(S[0]["text"])
        for want in ("T-1", "T-2", "C-1", "C-2", "C-3", "F-1", "F-2", "TN-2", "TN-3", "AC-1"):
            self.assertIn(want, r)

    def test_contradicted_fact_has_corrected_suggestion(self):
        fs = checks.review("Each bar has 12 g of protein.")["findings"]
        f = [x for x in fs if x["rule_id"] == "F-1"][0]
        self.assertEqual(f["suggestion"]["with"], "8 g of protein")
        self.assertEqual(f["severity"], "high")

    def test_sample2_year_cannot_verify_and_disclosure(self):
        r = rules(S[1]["text"])
        self.assertTrue({"F-3", "V-1", "D-1", "C-1"} <= r)

    def test_clean_sample_has_no_high_or_medium_issues(self):
        res = checks.review(S[2]["text"])
        self.assertEqual(res["counts"]["high"] + res["counts"]["medium"], 0)
        self.assertGreaterEqual(res["counts"]["info"], 4)

    def test_expired_offer_is_flagged_outdated(self):
        fs = checks.review("Diwali special: flat 20% off!", today=date(2026, 11, 4))["findings"]
        self.assertTrue(any(f["rule_id"] == "F-4" and f["severity"] == "high" for f in fs))

    def test_unknown_number_is_cannot_verify_not_guessed(self):
        self.assertIn("V-1", rules("Now with 35% more crunch."))

    def test_missing_alt_text(self):
        self.assertIn("AC-3", rules("Hello.", has_image=True, alt_text=""))
        self.assertNotIn("AC-3", rules("Hello.", has_image=True, alt_text="A bowl of oats on a table"))

    def test_disclosure_ok_with_hashtag(self):
        self.assertNotIn("D-1", rules("Partnered with @riya #ad"))

    def test_brand_hashtag_not_flagged(self):
        self.assertNotIn("T-2", rules("Love it #NourishDaily"))

    def test_claim_findings_offer_sentence_removal(self):
        text = "Great taste. Guaranteed to help you lose weight. Try it."
        fs = checks.review(text)["findings"]
        f = [x for x in fs if x["rule_id"] == "C-2"][0]
        self.assertEqual(f["suggestion"]["type"], "remove_sentence")
        self.assertEqual(text[f["suggestion"]["start"]:f["suggestion"]["end"]].strip(), "Guaranteed to help you lose weight.")

    def test_finding_ids_are_stable(self):
        a = [f["id"] for f in checks.review(S[0]["text"])["findings"]]
        b = [f["id"] for f in checks.review(S[0]["text"])["findings"]]
        self.assertEqual(a, b)


class WorkflowTests(unittest.TestCase):
    def payload(self, text, decisions=None):
        return {"title": "t", "author": "a", "text": text, "channel": "social", "has_image": False, "alt_text": "",
                "decisions": decisions or {}, "applied_fixes": []}

    def test_cannot_submit_with_unresolved_findings(self):
        with self.assertRaises(ValueError):
            logic.create(self.payload(S[0]["text"]))

    def test_submit_after_dismissals_then_human_decision(self):
        res = checks.review(S[0]["text"])
        dec = {f["id"]: {"action": "dismissed", "reason": "Approved exception"}
               for f in res["findings"] if f["severity"] in ("high", "medium")}
        sub = logic.create(self.payload(S[0]["text"], dec))
        self.assertEqual(sub["status"], "In review")
        with self.assertRaises(PermissionError):
            logic.decide(sub["id"], "creator", "approve", "")
        with self.assertRaises(ValueError):
            logic.decide(sub["id"], "reviewer", "request_changes", "")
        out = logic.decide(sub["id"], "reviewer", "approve", "ok")
        self.assertEqual(out["status"], "Approved")
        self.assertIn("dismissed high-severity", out["history"][-1]["comment"])

    def test_insights_counts(self):
        d = logic.insights()
        self.assertGreaterEqual(d["total"], 2)
        self.assertIn("claims", d["by_category"])


if __name__ == "__main__":
    unittest.main()
