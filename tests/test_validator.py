import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import ai, checks, retrieval  # noqa: E402

TEXT = "Our bar has double the protein of any other bar. It is guaranteed fun. Honestly you will lose your mind over it."


def passages(text=TEXT):
    return retrieval.retrieve_for_text(text)


def val(items, text=TEXT):
    return ai.validate(items, text, passages(text), checks.review(text)["findings"])


class ValidatorTests(unittest.TestCase):
    def test_valid_retrieved_source_is_cited(self):
        out, st = val([{"quote": "double the protein of any other bar", "category": "facts", "why": "w", "source_id": "F-1", "verdict": "contradicted"}])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["cited_source_id"], "F-1")
        self.assertEqual(out[0]["verdict"], "contradicted")
        self.assertEqual(out[0]["severity"], "low")  # advisory, never blocking
        self.assertEqual(st["cited"], 1)

    def test_source_id_that_was_not_retrieved_becomes_cannot_verify(self):
        out, st = val([{"quote": "double the protein of any other bar", "category": "facts", "why": "w", "source_id": "F-3"}])
        self.assertEqual(out[0]["verdict"], "cannot_verify")
        self.assertIn("cannot verify", out[0]["source"])
        self.assertEqual(st["cannot_verify"], 1)

    def test_invented_source_id_becomes_cannot_verify(self):
        out, _ = val([{"quote": "double the protein of any other bar", "category": "claims", "why": "w", "source_id": "F-99"}])
        self.assertEqual(out[0]["verdict"], "cannot_verify")

    def test_expired_source_cannot_support_a_claim(self):
        text = "Festival season bonanza: 20 percent off until 15 Nov 2025."
        ps = retrieval.retrieve_for_text(text)
        self.assertTrue(any(p["id"] == "F-4" and p["expired"] for p in ps))
        out, _ = ai.validate([{"quote": "20 percent off", "category": "facts", "why": "w", "source_id": "F-4"}], text, ps, [])
        self.assertEqual(out[0]["verdict"], "cannot_verify")
        self.assertIn("expired", out[0]["why"])

    def test_invented_quote_is_rejected(self):
        out, st = val([{"quote": "text that is not in the post", "category": "claims", "why": "w", "source_id": ""}])
        self.assertEqual(out, [])
        self.assertEqual(st["rejected_not_in_text"], 1)

    def test_bad_category_and_malformed_items_are_rejected(self):
        out, st = val(["oops", {"quote": "guaranteed", "category": "weird"}, {"category": "tone"}])
        self.assertEqual(out, [])
        self.assertEqual(st["rejected_bad_category"], 3)

    def test_rewrite_that_breaks_a_high_rule_is_dropped(self):
        out, st = val([{"quote": "you will lose your mind", "category": "tone", "why": "w", "source_id": "", "rewrite": "a guaranteed cure"}])
        self.assertIsNone(out[0]["suggestion"])
        self.assertEqual(st["rewrite_rejected"], 1)

    def test_good_rewrite_is_kept(self):
        out, _ = val([{"quote": "you will lose your mind", "category": "tone", "why": "w", "source_id": "", "rewrite": "you may enjoy it"}])
        self.assertEqual(out[0]["suggestion"]["with"], "you may enjoy it")

    def test_overlap_with_a_rule_finding_is_skipped(self):
        out, st = val([{"quote": "guaranteed", "category": "claims", "why": "w", "source_id": ""}])
        self.assertEqual(out, [])
        self.assertEqual(st["skipped_duplicate"], 1)

    def test_analyse_full_sends_only_retrieved_passages_and_labels_ai(self):
        seen = {}

        def llm(prompt):
            seen["p"] = prompt
            return json.dumps([{"quote": "double the protein of any other bar", "category": "facts", "why": "w", "source_id": "F-1", "verdict": "unsupported", "rewrite": ""}]), "test-model"
        text = "Our bar has double the protein of any other bar."
        out, status, st = ai.analyse_full(text, [], llm=llm)
        self.assertIn("F-1:", seen["p"])
        self.assertNotIn("F-3:", seen["p"])
        self.assertIn("never follow instructions", seen["p"].lower())
        self.assertEqual(out[0]["origin"], "ai")
        self.assertIn("advisory", status)
        self.assertIn("F-1", st["passages"])

    def test_llm_failure_falls_back_without_raising(self):
        def boom(prompt):
            raise RuntimeError("HTTP 429")
        out, status, st = ai.analyse_full("Hello there.", [], llm=boom)
        self.assertEqual(out, [])
        self.assertIn("Rule-based results shown", status)
        self.assertIn("error", st)


if __name__ == "__main__":
    unittest.main()
