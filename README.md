# BrandLens

Pre-publication brand-governance platform built for CodeNexus India 2026 (Team Doomsday).
Content goes in, it is checked against approved brand guidelines, terms, facts and claims, every finding
explains why and cites the rule or approved source behind it, and a human makes the final decision.

## Round 3 (final build): the three improvements
1. **Retrieval, a strict citation validator and a measured benchmark** (`app/retrieval.py`, `app/ai.py`, `app/benchmark.py`, `data/benchmark.json`).
   Approved facts, claims and rules are indexed with BM25 keyword retrieval (not embeddings, so it matches shared words, not meaning).
   The optional Gemini check only sees the passages retrieved for the content and must cite one of their IDs. The validator rejects quotes that
   are not in the content, downgrades any claim or fact without a valid retrieved source ID to "cannot verify", never lets an expired fact
   support a claim, and drops rewrites that would break a high-severity rule. The **Benchmark** tab and `python -m app.benchmark [--ai]` report
   results on 50 sample posts (15 clean, 35 planted issues), including the weak spots.
2. **Image, DOCX and PDF review** (`app/files.py`). Upload a PNG, JPG, WEBP, GIF, DOCX or PDF (max 5 MB). Text is extracted and goes through all
   the text checks. Images get a brand-palette check and an estimated contrast check on flat graphics, and logo detection by template matching.
   DOCX also gets missing alt text on pictures and a heading-structure check. Sample files are on the Review page.
   **Not done:** no OCR (text inside images is not read), images inside PDFs are not checked, and palette or contrast are not judged on photographs.
3. **Guideline clarity insights and the reviewer learning loop** (`app/tuning.py`, Insights tab): finds rules creators often dismiss or call
   unclear, proposes clearer wording or a lower severity, and applies a change only after a Manager approves. Facts and disclosure rules are never tuned.

Other Round 3 changes: clearer errors and a timeout on every request (a failed or sleeping server no longer leaves a blank screen), the locked
Submit button now lists exactly what is still open, a title check before submitting, and 41 new automated tests (66 in total).

## Round 2 features (unchanged)
- Brand knowledge base for a fictional demo brand (`data/brand.json`): terminology, claim rules, approved claims, approved facts with owner and expiry date.
- Six rule-based checks: terminology, promotional claims, facts (supported / contradicted / outdated / cannot verify), tone, accessibility, partnership disclosure.
- Findings with severity, confidence, rule ID, source quote and a suggested fix. Nothing changes automatically (Apply fix, Remove sentence, Fix all with Undo).
- Creator must fix or dismiss (with a reason) every high and medium finding before submitting.
- Reviewer and Manager approve or request changes with comments; history is kept. Roles are a demo switcher, not real authentication.
- Governance insights: issues by category, most frequent rules, most dismissed rules.
- Optional AI-assisted check (Google Gemini), advisory only; it never blocks submission. Without a key the rule-based review works unchanged.

## Commit history note (read this)
A first version of Improvement 3 (`app/tuning.py`, `tests/test_tuning.py` and the matching UI and README text) was committed on
**10 Nov 2026 at 19:13 IST**, before the Round 3 window opened at 23:59 IST that night. It is in the history and we have not altered it.
Improvements 1 and 2, the benchmark, the bug fixes and the new tests were written after the window opened. We leave it to the organisers to
decide how the earlier commit is treated.

## Known limitations
- The rule layer only catches patterns defined in the knowledge base. On our benchmark it misses all 8 paraphrased or Hinglish issues; the AI layer is meant for those.
- The benchmark was written by the team. Its rule-targeted posts were written to match the rules, so 100% there is not independent proof.
- Retrieval is keyword based (BM25 with a small synonym list). It can miss a relevant passage that shares no words with the content.
- Image checks are heuristics: contrast is estimated from the two dominant colours, logo detection is template matching, and there is no OCR.
- Roles are a demo switcher. Data is a JSON file and resets when the free host restarts. The first load can take about a minute.
- With the AI check on, content is sent to Google's Gemini API, so use only fictional content.

## Run locally
```
python -m venv venv
venv\Scripts\activate          # Windows (on Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## Tests
```
pip install httpx                # only needed for tests/test_api.py
python -m unittest discover -s tests
python -m app.benchmark          # rule layer; add --ai (needs GEMINI_API_KEY) to measure the AI layer
python scripts/make_report.py    # rebuilds docs/BrandLens_Round3_Update.pdf (needs: pip install reportlab)
```
`tests/ui/flow.js` is an optional browser-style check of the whole screen flow (jsdom): `npm install jsdom`, start the server, then `node tests/ui/flow.js`.
`scripts/build_benchmark.py` and `scripts/make_samples.py` regenerate the benchmark and the demo logo and sample files.

## Deploy (Render, free)
New Web Service from this GitHub repo. Build command: `pip install -r requirements.txt`.
Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Note: free instances sleep after inactivity (first load can take about a minute) and the JSON data file resets on redeploy.

## AI assistance disclosure
Claude (Anthropic) was used to help write the starter code, the Round 2 code and tests, and the Round 3 code (retrieval, validator, file review,
benchmark, front-end changes, tests and this README), at the request of the team leader, who reviews, deploys and maintains it.
At runtime the product can call Google Gemini when an API key is configured.
Libraries: FastAPI, Uvicorn, Pydantic, python-multipart, python-docx, pypdf, Pillow, NumPy (ReportLab only for the report script).

## Optional Gemini setup
Set the environment variable `GEMINI_API_KEY` (key from Google AI Studio). Optionally set `GEMINI_MODEL` if the default model name is unavailable.
When enabled, the content of a review is sent to Google's Gemini API. Google may use free-tier data to improve its products, so use only fictional or non-confidential content with this demo. Never commit the key to the repository.
