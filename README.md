# BrandLens

Pre-publication brand-governance platform built for CodeNexus India 2026 (Team Doomsday).
Content goes in, it is checked against approved brand guidelines, terms, facts and claims, every finding
explains why and cites the rule or approved source behind it, and a human makes the final decision.

## What works now (Round 2 build)
- Brand knowledge base for a fictional demo brand (`data/brand.json`): terminology, claim rules, approved claims, approved facts with owner and expiry date.
- Review of text with six rule-based checks: terminology, promotional claims, facts (supported / contradicted / outdated / cannot verify), tone, accessibility, partnership disclosure.
- Findings with severity, confidence, rule ID, source quote and a suggested fix. Nothing changes automatically.
- Creator must fix or dismiss (with a reason) every high and medium finding before submitting.
- Reviewer / Manager approve or request changes with comments. History and comments are kept.
- Governance insights: issues by category, most frequent rules, most dismissed rules.
- No login for judges: use the "Viewing as" role switcher (demo only, not real authentication).

## Not built yet (planned)
LLM-based tone and claim understanding, image review, document upload, claims expiry reminders,
guideline clarity suggestions, reviewer learning loop, real authentication.

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
python -m unittest discover -s tests
```

## Deploy (Render, free)
New Web Service from this GitHub repo. Build command: `pip install -r requirements.txt`.
Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Note: free instances sleep after inactivity (first load can take about a minute) and the JSON data file resets on redeploy.

## AI assistance disclosure
Claude (Anthropic) was used to help write the starter code, tests and this README. The team reviewed, runs and maintains it.
Libraries: FastAPI, Uvicorn, Pydantic.

## Optional Gemini setup
Set the environment variable `GEMINI_API_KEY` (key from Google AI Studio). Optionally set `GEMINI_MODEL` if the default model name is unavailable.
When enabled, the content of a review is sent to Google's Gemini API. Google may use free-tier data to improve its products, so use only fictional or non-confidential content with this demo. Never commit the key to the repository.
