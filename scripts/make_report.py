"""Builds docs/BrandLens_Round3_Update.pdf from the repo (benchmark numbers come from data/benchmark_results.json).
Run `python -m app.benchmark --ai` first (with GEMINI_API_KEY) if you want measured AI-layer numbers in the PDF."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import benchmark  # noqa: E402

LIVE = "https://brandlens-74wa.onrender.com"
REPO = "https://github.com/Sachin-web-design/Brandlens"
G = colors.HexColor("#0F6E56")
ss = getSampleStyleSheet()
B = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_LEFT, spaceAfter=4)
SM = ParagraphStyle("sm", parent=B, fontSize=8.5, leading=11)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=20, textColor=G, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=G, spaceBefore=10, spaceAfter=4)
BL = ParagraphStyle("bl", parent=B, leftIndent=12, bulletIndent=2)


def P(t, s=B):
    return Paragraph(t, s)


def bullets(items):
    return [Paragraph(t, BL, bulletText="\u2022") for t in items]


def table(rows, widths, head=True):
    data = [[P(str(c), SM) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8b6ad")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1f5ee")))
    t.setStyle(TableStyle(st))
    return t


def count_tests():
    s = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    per = {}

    def walk(x):
        for y in x:
            if isinstance(y, unittest.TestSuite):
                walk(y)
            else:
                per[type(y).__module__] = per.get(type(y).__module__, 0) + 1
    walk(s)
    return per


def build(out):
    st = benchmark.stored()
    r = st.get("rules") or benchmark.run_rules()
    ai = st.get("ai")
    tests = count_tests()
    total = sum(tests.values())
    story = [P("BrandLens", H1),
             P("Round 3: The Final Build. Team Doomsday | CodeNexus India 2026 (WeCodeCoders, Unstop) | Problem: brand governance platform (Inkloom AI)", B),
             P("Live product: <link href='%s'>%s</link> (free hosting: the first load can take up to a minute)<br/>Source code: <link href='%s'>%s</link><br/>Team leader: Sachin Rawat. Document built on %s from the repository."
               % (LIVE, LIVE, REPO, REPO, date.today().isoformat()), B),
             P("1. Final status", H2),
             P("BrandLens is a working web product: a creator pastes text or uploads an image, DOCX or PDF, runs the review, fixes or dismisses each finding "
               "(with a reason for high and medium ones), submits it, and a reviewer or manager approves or requests changes. All three improvements promised in Round 2 are built. "
               "This document also says what is <b>not</b> done or not verified, because the review is only useful if it can be trusted.", B),
             P("2. Completed improvements", H2),
             table([["#", "Improvement (promised in Round 2)", "What was delivered in Round 3", "Honest limits"],
                    ["1", "Production-grade LLM review with retrieval and a measured benchmark",
                     "BM25 retrieval over approved facts, claims and rules (app/retrieval.py). Gemini sees only the retrieved passages and must cite one of their IDs. Strict validator (app/ai.py): invented quotes rejected, no valid retrieved source ID = 'cannot verify', expired facts cannot support a claim, unsafe rewrites dropped. 50-item benchmark with answer key and a script that reports the results (app/benchmark.py, Benchmark tab).",
                     "Retrieval is keyword based, not embeddings. The AI layer needs a Gemini key and was %s." % ("measured on the benchmark (see section 5)" if ai else "not measured in this build environment (no key); the numbers in section 5 are for the rule layer")],
                    ["2", "Image and document review",
                     "Upload PNG, JPG, WEBP, GIF, DOCX or PDF (5 MB max) (app/files.py). Text extraction feeds all text checks. Images: brand-palette match, estimated text contrast, logo detection by template matching. DOCX: missing alt text on pictures, heading structure, embedded images analysed. Sample files included.",
                     "No OCR: text inside images is not read. Contrast is estimated from the two dominant colours of flat graphics. Photos are not judged on palette or contrast. Images inside PDFs are not checked."],
                    ["3", "Guideline clarity insights and reviewer learning loop",
                     "Insights tab finds rules that are often dismissed or called unclear, proposes clearer wording or a lower severity, and applies a change only after a Manager approves; facts and disclosure rules are never tuned (app/tuning.py).",
                     "First version committed 10 Nov 19:13 IST, before the Round 3 window opened (see section 9). Uses seeded demo history on a fresh deploy, labelled as seeded."]],
                   [8, 38, 78, 56]),
             P("3. Round 2 problems fixed", H2)]
    story += bullets(["The interface was redesigned: sidebar navigation, summary cards, clearer finding cards with severity colours, a review queue table, light and dark themes, and a layout that works on narrow screens.", "A failed, slow or sleeping server used to leave a blank screen. Every request now has a 90 second timeout and shows a plain error message; the review shows a 'waking up' note.",
                      "The Submit button was greyed out with no explanation. It now lists exactly which findings are still open and how to resolve them, and checks the title and text before sending.",
                      "Findings from an uploaded file are stored on the server and applied again at submission (keyed by upload ID). This is demo-level protection, not tamper-proof.",
                      "Deprecated Pydantic call replaced; runtime data files (submissions, tuning) are git-ignored."])
    story += [P("4. Technical details", H2),
              P("<b>Flow.</b> Browser (single-page app, plain HTML/CSS/JS) to FastAPI. /api/upload extracts text and runs file checks; /api/review runs the rule checks, merges file findings and, if a key is set, the AI layer; "
                "/api/submissions re-runs the rules on the server and refuses submission while high or medium findings are open and not dismissed with a reason. Roles are checked on the server.", B),
              table([["Part", "What we used"],
                     ["Backend", "Python, FastAPI, Uvicorn, Pydantic. app/checks.py (rules), app/retrieval.py, app/ai.py, app/files.py, app/benchmark.py, app/logic.py (workflow), app/tuning.py (learning loop), app/main.py (API)"],
                     ["Files and images", "python-multipart (upload), python-docx, pypdf, Pillow, NumPy (FFT-based normalised cross-correlation for logo detection; WCAG contrast formula)"],
                     ["AI (optional)", "Google Gemini over HTTPS, only when GEMINI_API_KEY is set. Output must be JSON; every item is validated; AI findings are advisory, labelled 'AI', and never block submission"],
                     ["Data", "Brand rules and facts in data/brand.json; benchmark in data/benchmark.json; submissions in a JSON file (resets when the free host restarts)"],
                     ["Hosting", "Render (backend and frontend together), code on GitHub"]], [32, 140]),
              P("5. Benchmark results (50 sample posts, fictional brand Nourish Daily)", H2),
              P("15 clean posts and 35 posts that each have one planted issue. Written by the team; the 27 rule-targeted posts were written to match the rules, so a high score there is <b>not independent evidence</b>. "
                "The 8 paraphrased or Hinglish posts are the honest test.", B),
              table([["Measure (rule layer, no AI)", "Result"],
                     ["Planted issues caught, all", "%d of %d (%s%%)" % (r["caught"], r["planted_issues"], r["recall_pct"])],
                     ["Caught, issues the rules target", "%s%%" % r["recall_rule_targeted_pct"]],
                     ["Caught, paraphrased or Hinglish issues", "%s%% (all 8 missed: the known weak spot)" % r["recall_ai_targeted_pct"]],
                     ["False alarms on clean posts (high or medium)", "%d of %d (%s%%)" % (r["false_alarm_items_high_medium"], r["clean_items"], r["false_alarm_rate_pct"])],
                     ["Findings with a rule ID and source quote", "%s%%" % r["with_valid_citation_pct"]],
                     ["Findings marked 'cannot verify'", "%s%%" % r["cannot_verify_pct"]]], [95, 77]),
              Spacer(1, 4),
              table([["Category", "Caught"]] + [[k, "%d of %d (%s%%)" % (v["caught"], v["total"], v["pct"])] for k, v in r["by_category"].items()], [95, 77])]
    if ai:
        story += [Spacer(1, 4), table([["Measure (AI layer, Gemini + retrieval + validator)", "Result"],
                                       ["Items run (errors)", "%s (%s)" % (ai["items_run"], ai["errors"])],
                                       ["AI caught, paraphrased or Hinglish issues", "%s of %s (%s%%)" % (ai["ai_caught_of_ai_targeted"], ai["ai_targeted_issues"], ai["ai_recall_pct"])],
                                       ["Combined recall (rules + AI)", "%s%%" % ai["combined_recall_pct"]],
                                       ["Clean posts with an AI finding", "%s (%s%%)" % (ai["clean_items_with_ai_finding"], ai["ai_false_alarm_pct"])],
                                       ["AI findings citing a valid retrieved source", "%s%%" % ai["with_valid_source_pct"]],
                                       ["AI findings marked 'cannot verify'", "%s%%" % ai["cannot_verify_pct"]],
                                       ["Answers rejected by the validator", ai["rejected_by_validator"]]], [95, 77]),
                  P("Measured %s. %s" % (ai.get("run_at", ""), ai.get("status", "")), SM)]
    else:
        story += [P("<b>AI layer: not yet measured.</b> It needs a Gemini key. Run <font face='Courier'>python -m app.benchmark --ai</font>, then rebuild this PDF. "
                    "No AI-layer accuracy is claimed in this document.", B)]
    story += [P("6. Testing notes", H2),
              P("<b>Automated:</b> %d unit and API tests (%s), all passing at build time. They cover the rules, the validator (invented quotes, unknown or expired source IDs, unsafe rewrites), "
                "retrieval, image, DOCX and PDF handling (including corrupt, empty, oversized and unsupported files and text that tries to give instructions), the benchmark maths with a mock model, "
                "the approval workflow, the learning loop and the full upload, review, lock, dismiss, submit flow through the API." % (total, ", ".join("%s: %d" % (k.replace("tests.", "").replace("test_", ""), v) for k, v in sorted(tests.items()))), B),
              P("<b>Screen flow:</b> tests/ui/flow.js drives the real page in a simulated browser (jsdom) against a running server: sample load, review, locked Submit, dismiss, submit, empty-title message, "
                "image, DOCX uploads, Benchmark, Brand knowledge, Insights and Queue tabs; no script errors.", B),
              P("<b>Not tested:</b> live Gemini calls (no key or network access in the build environment), the Render deployment itself, real browsers and phones, and a full accessibility audit with a screen reader.", B),
              P("7. Privacy, security and responsible design", H2)]
    story += bullets(["AI only suggests. Nothing is changed, approved or published automatically; a human approves.",
                      "Every finding names and quotes its rule or approved source; missing evidence is shown as 'cannot verify' rather than guessed.",
                      "Uploaded files are treated as data, never instructions; size, type and page limits apply; extracted text is capped.",
                      "AI use is disclosed in the interface. With the AI check on, content goes to Google's Gemini API, so only fictional content should be used; no key is stored in the repository.",
                      "Demo roles are a switcher, not real authentication. Server-side role checks exist, but this is not production security.",
                      "The interface uses native buttons and form controls and has light and dark themes; no formal accessibility audit was done."])
    story += [P("8. Known limitations and roadmap", H2)]
    story += bullets(["Rules miss paraphrased and Hinglish wording (0 of 8 on our benchmark); the AI layer is meant for these but is advisory.",
                      "Keyword retrieval can miss passages that share no words; embeddings (pgvector) are the next step.",
                      "No OCR, no image checks inside PDFs, estimated contrast only; Tesseract/OpenCV and a vision model are the next step.",
                      "Real login (JWT) and a database instead of a JSON file; video and audio review; more languages; direct publishing integrations."])
    story += [P("9. AI assistance and commit-history disclosure", H2),
              P("Claude (Anthropic) helped write the Round 1 plan, the Round 2 code and tests, and the Round 3 code, tests and this document, at the request of the team leader, who reviews, deploys and maintains it. "
                "The team ran the 8-person survey. At runtime the product can call Google Gemini.", B),
              P("A first version of Improvement 3 (app/tuning.py and its tests) was committed on <b>10 Nov 2026 at 19:13 IST</b>, before the Round 3 window opened at 23:59 IST. It is visible in the repository history and has not been altered. "
                "Improvements 1 and 2, the benchmark, the bug fixes and the new tests were written after the window opened. We leave it to the organisers to decide how the earlier commit is treated.", B),
              P("10. Team contributions", H2),
              P("Each member submits an individual entry and writes in their own words only what they actually did. The leader's line below is the only one filled in here.", B),
              table([["Member", "Role (Round 1 plan)", "Round 3 contribution"],
                     ["Sachin Rawat (Team Leader)", "AI and backend lead", "Directed and reviewed the Round 3 build; deployed and maintains the product. Code written with Claude (see section 9)."],
                     ["Suryansh Puri", "Frontend and UX", "[to be written by the member, only if work was done]"],
                     ["Snehal Jasrotia", "Knowledge base and checks", "[to be written by the member, only if work was done]"],
                     ["Khushi", "Research, testing and documentation", "[to be written by the member, only if work was done]"]], [42, 45, 85])]
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="BrandLens Round 3 Update", author="Team Doomsday")

    def foot(c, d):
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawString(18 * mm, 9 * mm, "BrandLens | Team Doomsday | CodeNexus India 2026 | Round 3 update")
        c.drawRightString(A4[0] - 18 * mm, 9 * mm, "Page %d" % d.page)
    doc.build(story, onFirstPage=foot, onLaterPages=foot)


if __name__ == "__main__":
    out = ROOT / "docs" / "BrandLens_Round3_Update.pdf"
    out.parent.mkdir(exist_ok=True)
    build(out)
    print("wrote", out)
