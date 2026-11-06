from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, checks, logic

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="BrandLens")


class ReviewIn(BaseModel):
    text: str
    channel: str = "social"
    has_image: bool = False
    alt_text: str = ""
    use_ai: bool = True


class SubmitIn(ReviewIn):
    title: str
    author: str = "Demo creator"
    decisions: Dict[str, Dict[str, str]] = {}
    applied_fixes: List[Dict[str, str]] = []


class DecisionIn(BaseModel):
    role: str
    action: str
    comment: str = ""


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
            "approved_claims": b["approved_claims"]}


@app.post("/api/review")
def review(p: ReviewIn):
    res = checks.review(p.text, p.channel, p.has_image, p.alt_text)
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


@app.get("/api/submissions")
def submissions():
    return logic.list_submissions()


@app.post("/api/submissions")
def submit(p: SubmitIn):
    d = p.dict() if hasattr(p, "dict") else p.model_dump()
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


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.get("/")
def home():
    return FileResponse(str(ROOT / "static" / "index.html"))
