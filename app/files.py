"""Image, DOCX and PDF review (Round 3, Improvement 2).

What is measured (plain code, no AI): text extraction, brand-palette match and an estimated text contrast
on flat graphics, logo presence by template matching, missing alt text and heading structure in DOCX.
What is NOT done: no OCR (text inside images is not read), no checks of images inside PDFs, and palette or
contrast are not judged on photographs. Uploaded files are treated as data, never as instructions.
"""
import io
import uuid
from collections import OrderedDict

import numpy as np
from PIL import Image

from . import checks

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 20000
MAX_PDF_PAGES = 20
IMG_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
STORE = OrderedDict()  # upload_id -> {"findings": [...], "notes": [...]}
V = checks.BRAND["visual"]


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(x) for x in rgb)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def c(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def contrast_ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _flat(im):
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    return im.convert("RGB")


def dominant_colors(im):
    """(share, mean_rgb) for the most common coarse colour buckets, plus how flat (graphic-like) the image is."""
    small = im.copy()
    small.thumbnail((160, 160))
    a = np.asarray(small).reshape(-1, 3).astype(np.int32)
    key = (a[:, 0] >> 5) * 64 + (a[:, 1] >> 5) * 8 + (a[:, 2] >> 5)
    out = []
    for k in np.unique(key):
        m = key == k
        out.append((float(m.mean()), a[m].mean(axis=0)))
    out.sort(key=lambda x: -x[0])
    return out


def ncc_best(img, tpl):
    """Best normalised cross-correlation of tpl inside img (both float 2D arrays, 0..1), by FFT."""
    H, W = img.shape
    h, w = tpl.shape
    if h > H or w > W or h < 4 or w < 4:
        return 0.0
    t = tpl - tpl.mean()
    tn = float(np.sqrt((t * t).sum()))
    if tn < 1e-6:
        return 0.0
    corr = np.fft.irfft2(np.fft.rfft2(img, s=(H, W)) * np.fft.rfft2(t[::-1, ::-1], s=(H, W)), s=(H, W))
    num = corr[h - 1:H, w - 1:W]
    pad = lambda x: np.pad(x.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    box = lambda a: a[h:, w:] - a[:-h, w:] - a[h:, :-w] + a[:-h, :-w]
    n = h * w
    s1, s2 = box(pad(img)), box(pad(img * img))
    var = np.maximum(s2 - s1 * s1 / n, n * 1e-4)
    return float((num / (np.sqrt(var) * tn)).max())


def logo_score(im):
    path = checks.ROOT / "data" / V["logo"]
    if not path.exists():
        return None
    g = im.convert("L")
    g.thumbnail((256, 256))
    arr = np.asarray(g, dtype=np.float64) / 255.0
    lg = Image.open(path).convert("L")
    best = 0.0
    for frac in (0.05, 0.06, 0.072, 0.086, 0.10, 0.124, 0.149, 0.179, 0.215, 0.258, 0.31, 0.37):
        w = max(12, int(g.width * frac))
        t = np.asarray(lg.resize((w, w), Image.LANCZOS), dtype=np.float64) / 255.0
        best = max(best, ncc_best(arr, t))
    return round(best, 2)


def _f(cat, sev, text, why, rule, source, sugg=None, conf="medium"):
    f = checks._mk(cat, sev, None, None, text, why, rule, source, sugg, confidence=conf)
    f["origin"] = "file"
    return f


def analyse_image(im, label="image"):
    """Returns (findings, notes, meta) for one image."""
    im = _flat(im)
    findings, notes = [], []
    cols = dominant_colors(im)
    top6 = sum(c[0] for c in cols[:6])
    graphic = top6 >= 0.80
    meta = {"size": list(im.size), "graphic": graphic, "dominant": [_hex(c[1]) for c in cols[:4]]}
    pal = [_rgb(h) for h in V["palette"]]
    if graphic:
        off, examples = 0.0, []
        for share, rgb in cols[:6]:
            d = min(float(np.linalg.norm(rgb - np.array(p))) for p in pal)
            if d > V["palette_distance"] and share >= 0.03:
                off += share
                examples.append(_hex(rgb))
        meta["off_palette_share"] = round(off, 2)
        if off > V["off_palette_limit"]:
            findings.append(_f("visual", "medium", label, "About %d%% of this graphic uses colours outside the brand palette (for example %s)."
                               % (round(off * 100), ", ".join(examples[:3])), "V-IMG-1", V["source_palette"],
                               {"type": "note", "text": "Recolour the graphic with the brand palette: " + ", ".join(V["palette"][:4]) + "."}))
        if len(cols) >= 2:
            ratio = contrast_ratio(cols[0][1], cols[1][1])
            meta["contrast"] = float(ratio)
            if ratio < V["min_contrast"]:
                findings.append(_f("accessibility", "high" if ratio < 3 else "medium", label,
                                   "Estimated contrast between the two main colours is %.1f:1, below %.1f:1. Estimated from the two dominant colours; text itself is not read (no OCR)."
                                   % (ratio, V["min_contrast"]), "AC-4", V["source_contrast"],
                                   {"type": "note", "text": "Use darker text on a light background, or the reverse, until the ratio is at least 4.5:1."}))
    else:
        notes.append("%s looks like a photograph, so palette and contrast were not judged (they are only measured on flat graphics)." % label)
    sc = logo_score(im)
    meta["logo_score"] = sc
    if sc is None:
        notes.append("Logo file is missing on the server, so logo use was not checked.")
    elif sc < V["logo_threshold"]:
        findings.append(_f("visual", "low", label, "The Nourish Daily logo was not detected (match score %.2f, needs %.2f). Template matching is a heuristic, so please confirm by eye."
                           % (sc, V["logo_threshold"]), "BR-1", V["source_logo"], {"type": "note", "text": "Place the logo on the graphic, or dismiss this with a reason if the graphic should not carry it."}))
    notes.append("Text inside images is not read (no OCR). Add the text of the graphic to the content box so it can be reviewed.")
    return findings, notes, meta


def read_docx(data):
    from docx import Document
    doc = Document(io.BytesIO(data))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                if c.text.strip():
                    paras.append(c.text.strip())
    headings = sum(1 for p in doc.paragraphs if p.style is not None and p.style.name.lower().startswith(("heading", "title")))
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
    alts = [((d.get("descr") or d.get("title") or "").strip()) for d in doc.element.body.iter(ns)]
    blobs = [r.target_part.blob for r in doc.part.rels.values() if "image" in r.reltype][:3]
    return "\n".join(paras), headings, alts, blobs


def read_pdf(data):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(data))
    pages = [(p.extract_text() or "").strip() for p in r.pages[:MAX_PDF_PAGES]]
    return "\n".join(t for t in pages if t), len(r.pages)


def process(filename, data):
    if len(data) > MAX_BYTES:
        raise ValueError("The file is larger than 5 MB.")
    if not data:
        raise ValueError("The file is empty.")
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    findings, notes, text, meta, kind = [], [], "", {}, ext
    if ext in IMG_EXT:
        kind = "image"
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except Exception:
            raise ValueError("This image could not be read.")
        findings, notes, meta = analyse_image(im, "image: " + filename)
    elif ext == "docx":
        try:
            text, headings, alts, blobs = read_docx(data)
        except Exception:
            raise ValueError("This DOCX file could not be read.")
        meta = {"headings": headings, "images": len(alts)}
        for i, a in enumerate(alts, 1):
            if len(a) < 8:
                findings.append(_f("accessibility", "medium", "image %d in the document" % i, "This image in the document has no useful alt text.",
                                   "AC-3", "Accessibility 6.3: Every image needs alt text describing what it shows.",
                                   {"type": "note", "text": "Right-click the image in Word, choose Alt Text and describe what it shows."}, "high"))
        if len(text.split()) > 150 and headings == 0:
            findings.append(_f("accessibility", "low", "document structure", "A long document with no headings is hard to navigate with a screen reader.", "AC-5",
                               "WCAG 2.2 SC 1.3.1 and 2.4.6: Use real headings to structure content.", {"type": "note", "text": "Apply Heading styles to section titles."}))
        for n, blob in enumerate(blobs, 1):
            try:
                f2, n2, m2 = analyse_image(Image.open(io.BytesIO(blob)), "embedded image %d" % n)
                findings += f2
                notes += [x for x in n2 if "OCR" not in x]
            except Exception:
                notes.append("Embedded image %d could not be analysed." % n)
        notes.append("Text inside embedded images is not read (no OCR).")
    elif ext == "pdf":
        try:
            text, pages = read_pdf(data)
        except Exception:
            raise ValueError("This PDF could not be read.")
        meta = {"pages": pages}
        if not text:
            notes.append("No extractable text was found. It may be a scanned PDF; OCR is not included, so paste the text instead.")
        notes.append("Images inside PDFs are not checked (text only).")
        if pages > MAX_PDF_PAGES:
            notes.append("Only the first %d pages were read." % MAX_PDF_PAGES)
    else:
        raise ValueError("Unsupported file type. Upload a PNG, JPG, WEBP, GIF, DOCX or PDF file.")
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
        notes.append("Only the first %d characters were read." % MAX_TEXT)
    uid = "U" + uuid.uuid4().hex[:10]
    STORE[uid] = {"findings": findings, "notes": notes}
    while len(STORE) > 100:
        STORE.popitem(last=False)
    return {"upload_id": uid, "kind": kind, "filename": filename, "text": text, "has_image": kind == "image",
            "findings": findings, "notes": notes, "meta": meta}


def cached(upload_id):
    """Findings produced by an earlier upload (empty if unknown)."""
    e = STORE.get(upload_id or "")
    return [dict(f) for f in e["findings"]] if e else []
