import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import checks, logic, tuning  # noqa: E402


class TuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.old = (logic.DATA_FILE, tuning.FILE)
        logic.DATA_FILE = cls.tmp / "subs.json"
        tuning.FILE = cls.tmp / "tuning.json"

    @classmethod
    def tearDownClass(cls):
        logic.DATA_FILE, tuning.FILE = cls.old

    def setUp(self):
        for f in (logic.DATA_FILE, tuning.FILE):
            if f.exists():
                f.unlink()

    def rules(self):
        return {r["rule_id"]: r for r in tuning.clarity(logic.list_submissions())["rules"]}

    def test_seeded_history_flags_unclear_and_broken_rules(self):
        r = self.rules()
        self.assertEqual(r["T-3"]["diagnosis"], "unclear_or_strict")
        self.assertEqual(r["TN-1"]["diagnosis"], "unclear_or_strict")
        self.assertEqual(r["C-1"]["diagnosis"], "frequently_broken")
        self.assertEqual(r["T-3"]["proposal"]["to"], "low")
        self.assertIsNone(r["C-1"]["proposal"])

    def test_only_manager_can_approve(self):
        items = logic.list_submissions()
        for role in ("creator", "reviewer"):
            with self.assertRaises(PermissionError):
                tuning.apply(items, role, "T-3", "lower_severity")

    def test_manager_lowers_severity_and_it_reaches_the_review_then_reverts(self):
        items = logic.list_submissions()
        self.assertEqual([f for f in checks.review("Hi guys")["findings"] if f["rule_id"] == "T-3"][0]["severity"], "medium")
        tuning.apply(items, "manager", "T-3", "lower_severity")
        f = [f for f in checks.review("Hi guys")["findings"] if f["rule_id"] == "T-3"][0]
        self.assertEqual(f["severity"], "low")
        self.assertTrue(f["tuned"])
        tuning.apply(items, "manager", "T-3", "revert")
        self.assertEqual([f for f in checks.review("Hi guys")["findings"] if f["rule_id"] == "T-3"][0]["severity"], "medium")

    def test_cannot_tune_rules_without_a_proposal(self):
        items = logic.list_submissions()
        with self.assertRaises(ValueError):
            tuning.apply(items, "manager", "C-1", "lower_severity")  # clear rule, often broken: no tuning
        with self.assertRaises(ValueError):
            tuning.apply(items, "manager", "F-1", "lower_severity")  # compliance-critical: never tuned

    def test_accept_wording_is_stored(self):
        items = logic.list_submissions()
        out = tuning.apply(items, "manager", "T-3", "accept_wording")
        t3 = [r for r in out["rules"] if r["rule_id"] == "T-3"][0]
        self.assertIn("Allowed: 'everyone'", t3["wording"])


if __name__ == "__main__":
    unittest.main()
