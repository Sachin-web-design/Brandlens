from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, benchmark, checks, files, logic, tuning

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="BrandLens")


class ReviewIn(BaseModel):
    text: str
    channel: str = "social"
    has_image: bool = False
    alt_text: str = ""
    use_ai: bool = True
    upload_id: str = ""


class SubmitIn(ReviewIn):
    title: str
    author: str = "Demo creator"
    decisions: Dict[str, Dict[str, str]] = {}
    applied_fixes: List[Dict[str, str]] = []


class DecisionIn(BaseModel):
    role: str
    action: str
    comment: str = ""


class TuneIn(BaseModel):
    role: str
    rule_id: str
    action: str
    text: str = ""


class CommentIn(BaseModel):
    role: str
    text: str


def _call(fn, *a):
    try:
        return fn(*a)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except KeyError:
        raise HTTPException(404, "Not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/brand")
def brand():
    b = checks.BRAND
    return {"name": b["name"], "tone": b["tone"]["summary"], "samples": b["samples"],
            "facts": [{k: f[k] for k in ("id", "label", "text", "owner", "valid_until")} for f in b["facts"]],
            "terms": [{"rule": t["rule"], "avoid": t["avoid"], "use": t["use"]} for t in b["terms"]],
            "claims": [{"rule": c["rule"], "source": c["source"]} for c in b["claim_rules"]],
            "approved_claims": b["approved_claims"], "visual": b["visual"],
            "clarified": [{"rule_id": k, "text": v["text"]} for k, v in tuning.wording().items()]}


@app.post("/api/review")
def review(p: ReviewIn):
    res = checks.review(p.text, p.channel, p.has_image, p.alt_text)
    extra = files.cached(p.upload_id)
    if extra:
        res = checks.finalize(res["findings"] + extra)
    res["ai"] = {"enabled": ai.enabled(), "status": "AI-assisted check: not configured (rule-based checks only)."}
    if ai.enabled() and not p.use_ai:
        res["ai"]["status"] = "AI-assisted check: switched off for this review."
    elif ai.enabled():
        extra, status = ai.analyse(p.text, res["findings"])
        res["ai"]["status"] = status
        if extra:
            merged = checks.finalize(res["findings"] + extra)
            merged["ai"] = res["ai"]
            return merged
    return res


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read(files.MAX_BYTES + 1)
    return _call(files.process, file.filename or "upload", data)


@app.get("/api/benchmark")
def bench():
    return benchmark.results()


@app.get("/api/submissions")
def submissions():
    return logic.list_submissions()


@app.post("/api/submissions")
def submit(p: SubmitIn):
    d = p.model_dump() if hasattr(p, "model_dump") else p.dict()
    return _call(logic.create, d)


@app.post("/api/submissions/{sub_id}/decision")
def decision(sub_id: str, p: DecisionIn):
    return _call(logic.decide, sub_id, p.role, p.action, p.comment)


@app.post("/api/submissions/{sub_id}/comments")
def comments(sub_id: str, p: CommentIn):
    return _call(logic.add_comment, sub_id, p.role, p.text)


@app.get("/api/insights")
def insights():
    return logic.insights()


@app.get("/api/clarity")
def clarity():
    return tuning.clarity(logic.list_submissions())


@app.post("/api/clarity/apply")
def clarity_apply(p: TuneIn):
    return _call(tuning.apply, logic.list_submissions(), p.role, p.rule_id, p.action, p.text)


@app.post("/api/clarity/suggest")
def clarity_suggest(p: TuneIn):
    rule = next((r for r in tuning.clarity(logic.list_submissions())["rules"] if r["rule_id"] == p.rule_id), None)
    if not rule:
        raise HTTPException(404, "Rule not in the clarity list")
    examples = [f["text"] for s in logic.list_submissions() for f in s["findings"] if f["rule_id"] == p.rule_id][:3]
    text = ai.suggest_wording(rule["source"], rule["reasons"], examples)
    return {"text": text or rule["default_wording"], "from_ai": bool(text)}


app.mount("/samples", StaticFiles(directory=str(ROOT / "data" / "samples")), name="samples")
app.mount("/assets", StaticFiles(directory=str(ROOT / "data" / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.get("/")
def home():
    return FileResponse(str(ROOT / "static" / "index.html"))
