import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import retrieval  # noqa: E402


class RetrievalTests(unittest.TestCase):
    def test_best_passage_for_a_protein_claim(self):
        self.assertEqual(retrieval.retrieve("Each bar has 12 g of protein")[0]["id"], "F-1")

    def test_synonyms_reach_the_founding_year_and_price(self):
        self.assertEqual(retrieval.retrieve("We were started back in 2017")[0]["id"], "F-3")
        self.assertEqual(retrieval.retrieve("It costs only Rs 59")[0]["id"], "F-2")

    def test_expired_offer_is_retrieved_and_marked_expired(self):
        top = retrieval.retrieve("Our Diwali offer is back this week")[0]
        self.assertEqual(top["id"], "F-4")
        self.assertTrue(top["expired"])

    def test_no_overlap_returns_nothing(self):
        self.assertEqual(retrieval.retrieve("zzz qqq"), [])

    def test_retrieve_for_text_is_capped_and_always_has_the_tone_guide(self):
        ps = retrieval.retrieve_for_text("Each bar has 8 g of protein. It costs Rs 49. No added preservatives. Made with whole oats.")
        ids = [p["id"] for p in ps]
        self.assertIn("TN", ids)
        self.assertLessEqual(len(ps), 9)
        self.assertTrue({"F-1", "F-2", "A-1"} <= set(ids))

    def test_sentences_have_offsets(self):
        text = "One. Two! Three?"
        for s, e, t in retrieval.sentences(text):
            self.assertIn(t, text[s:e])


if __name__ == "__main__":
    unittest.main()
