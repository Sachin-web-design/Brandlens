import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import ai, checks  # noqa: E402

TEXT = "Nourish Daily is totally unbeatable and everyone will obviously love it. Each bar has 8 g of protein."


def run_with(reply):
    ai._call = lambda prompt: (reply, "test-model")
    existing = checks.review(TEXT)["findings"]
    return ai.analyse(TEXT, existing)


class AiLayerTests(unittest.TestCase):
    def test_valid_finding_is_accepted_and_labelled(self):
        reply = json.dumps([{"quote": "totally unbeatable", "category": "claims", "why": "Absolute superiority claim.",
                             "source_id": "", "rewrite": "a tasty oat bar"}])
        out, status = run_with(reply)
        self.assertEqual(len(out), 1)
        f = out[0]
        self.assertEqual(f["origin"], "ai")
        self.assertEqual(f["severity"], "low")
        self.assertIn("cannot verify", f["source"])
        self.assertEqual(f["suggestion"]["with"], "a tasty oat bar")
        self.assertIn("advisory", status)

    def test_invented_quote_is_rejected(self):
        reply = json.dumps([{"quote": "this text is not in the post", "category": "tone", "why": "x", "source_id": "", "rewrite": ""}])
        out, _ = run_with(reply)
        self.assertEqual(out, [])

    def test_known_source_id_is_cited(self):
        reply = json.dumps([{"quote": "8 g of protein", "category": "facts", "why": "Check", "source_id": "F-1", "rewrite": ""}])
        out, _ = run_with(reply)
        # overlaps an existing rule finding (supported fact), so it is skipped rather than duplicated
        self.assertEqual(out, [])
        reply = json.dumps([{"quote": "everyone will obviously love it", "category": "tone", "why": "Presumptuous", "source_id": "", "rewrite": ""}])
        out, _ = run_with(reply)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["source"].startswith("Tone guide"))

    def test_unknown_category_and_bad_json_do_not_crash(self):
        out, _ = run_with(json.dumps([{"quote": "unbeatable", "category": "weird", "why": "x", "source_id": "", "rewrite": ""}]))
        self.assertEqual(out, [])
        out, status = run_with("this is not json")
        self.assertEqual(out, [])
        self.assertIn("unavailable", status)

    def test_network_failure_falls_back(self):
        def boom(prompt):
            raise RuntimeError("HTTP 429 from model")
        ai._call = boom
        out, status = ai.analyse(TEXT, [])
        self.assertEqual(out, [])
        self.assertIn("Rule-based results shown", status)

    def test_enabled_depends_on_key(self):
        os.environ.pop("GEMINI_API_KEY", None)
        self.assertFalse(ai.enabled())
        os.environ["GEMINI_API_KEY"] = "x"
        self.assertTrue(ai.enabled())
        os.environ.pop("GEMINI_API_KEY")


if __name__ == "__main__":
    unittest.main()
