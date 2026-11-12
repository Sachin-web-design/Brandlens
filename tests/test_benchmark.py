import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import benchmark  # noqa: E402


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_has_50_items_with_clean_and_planted_posts(self):
        items = benchmark.load()
        self.assertEqual(len(items), 50)
        self.assertEqual(sum(i["clean"] for i in items), 15)
        self.assertEqual(len({i["id"] for i in items}), 50)
        self.assertTrue(all(i["planted"] for i in items if not i["clean"]))

    def test_rule_layer_metrics(self):
        r = benchmark.run_rules()
        self.assertEqual(r["planted_issues"], 35)
        self.assertEqual(r["recall_rule_targeted_pct"], 100.0)
        self.assertEqual(r["recall_ai_targeted_pct"], 0.0)  # the rules cannot catch paraphrases: a known weak spot
        self.assertEqual(r["false_alarm_items_high_medium"], 0)
        self.assertEqual(r["with_valid_citation_pct"], 100.0)
        self.assertEqual(len(r["missed"]), 8)

    def test_ai_metrics_with_an_injected_model(self):
        def llm(prompt):
            if "Nothing else on the shelf" in prompt:
                return json.dumps([{"quote": "Nothing else on the shelf even comes close", "category": "claims", "why": "w", "source_id": ""}]), "mock"
            return "[]", "mock"
        r = benchmark.run_ai(llm=llm)
        self.assertEqual(r["ai_targeted_issues"], 8)
        self.assertEqual(r["ai_caught_of_ai_targeted"], 1)
        self.assertEqual(r["ai_recall_pct"], 12.5)
        self.assertEqual(r["cannot_verify_pct"], 100.0)  # no source cited, so it is shown as cannot verify
        self.assertEqual(r["clean_items_with_ai_finding"], 0)
        self.assertEqual(r["errors"], 0)

    def test_ai_run_counts_model_errors(self):
        def boom(prompt):
            raise RuntimeError("HTTP 500")
        r = benchmark.run_ai(llm=boom)
        self.assertEqual(r["errors"], 50)


if __name__ == "__main__":
    unittest.main()
