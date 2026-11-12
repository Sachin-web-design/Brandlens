"""Retrieval of approved passages (Round 3, Improvement 1).

Lightweight BM25 keyword retrieval over the Brand Knowledge Base: approved facts, approved claims,
claim rules, terminology rules, tone guide and disclosure policy. It is NOT an embedding search (no
vector database), so it matches shared words, not meaning. The model only ever sees the passages
retrieved here, and every AI answer must cite one of their IDs (see ai.validate).
"""
import math
import re
from collections import Counter
from datetime import date

from . import checks

_STOP = set("a an the and or of to in on for with is are was were be been it its this that our your you we at by as "
            "from have has had not no do does can will just so if then than too very".split())


# Small synonym map so common wordings reach the right approved fact (keyword search cannot do this by itself).
_SYN = {"started": "founded", "launched": "founded", "established": "founded", "began": "founded", "since": "founded",
        "cost": "price", "costs": "price", "priced": "price", "₹": "rs", "inr": "rs", "rupees": "rs", "calories": "kcal",
        "calorie": "kcal", "preservative": "preservatives", "oat": "oats", "gram": "g", "grams": "g"}


def tokens(s):
    out = []
    for w in re.findall(r"[a-z0-9₹%]+", s.lower()):
        if w in _STOP:
            continue
        w = _SYN.get(w, w)
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def sentences(text):
    """(start, end, sentence) for each sentence of the content."""
    return [(m.start(), m.end(), m.group().strip()) for m in re.finditer(r"[^.!?\n]+[.!?]*", text) if m.group().strip()]


def build_passages(today=None):
    """One citable passage per approved source. Expired facts stay in the index but are marked."""
    today = today or date.today()
    b = checks.BRAND
    ps = []
    for f in b["facts"]:
        exp = bool(f.get("valid_until")) and date.fromisoformat(f["valid_until"]) < today
        ps.append({"id": f["id"], "kind": "fact", "text": f["label"] + ". " + f["text"], "owner": f["owner"],
                   "expired": exp, "valid_until": f.get("valid_until")})
    for c in b["approved_claims"]:
        ps.append({"id": c["id"], "kind": "approved_claim", "text": "Approved claim: " + c["text"] + ". Evidence: " + c["evidence"],
                   "owner": "", "expired": False, "valid_until": None})
    for c in b["claim_rules"]:
        ps.append({"id": c["rule"], "kind": "claim_rule", "text": c["source"] + " " + c["why"], "owner": "", "expired": False,
                   "valid_until": None})
    for t in b["terms"]:
        ps.append({"id": t["rule"], "kind": "term_rule", "text": t["source"], "owner": "", "expired": False, "valid_until": None})
    ps.append({"id": "TN", "kind": "tone", "text": b["tone"]["summary"] + " " + b["tone"]["source_hype"], "owner": "",
               "expired": False, "valid_until": None})
    d = b["disclosure"]
    ps.append({"id": d["rule"], "kind": "disclosure", "text": d["source"], "owner": "", "expired": False, "valid_until": None})
    return ps


class Index:
    def __init__(self, passages, k1=1.5, b=0.75):
        self.passages, self.k1, self.b = passages, k1, b
        self.docs = [Counter(tokens(p["text"])) for p in passages]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1.0
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query, k=3):
        q = tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    f = d[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        return [dict(self.passages[i], score=round(s, 3)) for s, i in scored[:k]]


_INDEX = {}


def index():
    key = date.today().isoformat()
    if key not in _INDEX:
        _INDEX.clear()
        _INDEX[key] = Index(build_passages())
    return _INDEX[key]


def retrieve(query, k=3):
    return index().search(query, k)


def retrieve_for_text(text, per_sentence=3, cap=8):
    """Union of the best passages for every sentence, best first, always including the tone guide."""
    seen = {}
    for _s, _e, sent in sentences(text):
        for p in retrieve(sent, per_sentence):
            if p["id"] not in seen or p["score"] > seen[p["id"]]["score"]:
                seen[p["id"]] = p
    out = sorted(seen.values(), key=lambda p: -p["score"])[:cap]
    if "TN" not in {p["id"] for p in out}:
        out.append(next(p for p in index().passages if p["id"] == "TN"))
    return out
