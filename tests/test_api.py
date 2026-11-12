import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None
from app import logic, tuning  # noqa: E402

S = Path(__file__).resolve().parent.parent / "data" / "samples"


@unittest.skipIf(TestClient is None, "httpx not installed")
class ApiFlowTests(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        logic.DATA_FILE = d / "subs.json"
        tuning.FILE = d / "tuning.json"
        from app.main import app
        self.c = TestClient(app)

    def up(self, name):
        return self.c.post("/api/upload", files={"file": (name, (S / name).read_bytes(), "application/octet-stream")})

    def test_upload_review_lock_dismiss_submit(self):
        r = self.up("bad_post.png")
        self.assertEqual(r.status_code, 200)
        uid = r.json()["upload_id"]
        body = {"text": "Our new oat bar.", "channel": "Instagram post", "has_image": True, "alt_text": "", "use_ai": False, "upload_id": uid}
        rv = self.c.post("/api/review", json=body).json()
        ids = {f["rule_id"] for f in rv["findings"]}
        self.assertTrue({"V-IMG-1", "AC-4", "AC-3"} <= ids)
        sub = dict(body, title="Image post", author="a", decisions={}, applied_fixes=[])
        locked = self.c.post("/api/submissions", json=sub)
        self.assertEqual(locked.status_code, 400)
        self.assertIn("still need", locked.json()["detail"])
        sub["decisions"] = {f["id"]: {"action": "dismissed", "reason": "Approved exception"} for f in rv["findings"] if f["severity"] in ("high", "medium")}
        ok = self.c.post("/api/submissions", json=sub)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "In review")
        self.assertTrue(any(f["origin"] == "file" for f in ok.json()["findings"]))

    def test_docx_upload_then_text_review(self):
        r = self.up("launch_brief.docx").json()
        rv = self.c.post("/api/review", json={"text": r["text"], "channel": "Website", "use_ai": False, "upload_id": r["upload_id"]}).json()
        rules = {f["rule_id"] for f in rv["findings"]}
        self.assertTrue({"T-3", "C-1", "C-2", "F-2", "D-1", "AC-3"} <= rules)

    def test_bad_uploads_return_400(self):
        r = self.c.post("/api/upload", files={"file": ("x.exe", b"abc", "application/octet-stream")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unsupported", r.json()["detail"])

    def test_benchmark_samples_and_assets_are_served(self):
        b = self.c.get("/api/benchmark").json()
        self.assertEqual(b["rules"]["items"], 50)
        self.assertIn("ai", b)
        self.assertEqual(self.c.get("/samples/ok_post.png").status_code, 200)
        self.assertEqual(self.c.get("/assets/logo.png").status_code, 200)
        self.assertIn("palette", self.c.get("/api/brand").json()["visual"])

    def test_review_without_ai_key_and_with_empty_text_does_not_crash(self):
        self.assertEqual(self.c.post("/api/review", json={"text": "", "use_ai": True}).status_code, 200)

    def test_submit_requires_a_title(self):
        r = self.c.post("/api/submissions", json={"text": "Hello everyone.", "title": " ", "channel": "Website"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
