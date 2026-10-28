#!/usr/bin/env python3
"""docx (KFGQPC Hafs mushaf) -> static HTML: one <section> per printed page,
one <div> per printed line. Text is copied verbatim; nothing is rewritten."""
import re, sys, zipfile, hashlib, json, pathlib
from xml.etree import ElementTree as ET
from html import escape

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/Mushaf-Hafs-Uthmanic.docx")
OUT = pathlib.Path("site")

root = ET.fromstring(zipfile.ZipFile(SRC).read("word/document.xml"))
body = root.find(W + "body")

pages, page = [], []


def new_par(jc):
    return {"jc": jc, "sura": False, "lines": [""]}


def has_text(par):
    return any(l.strip() for l in par["lines"])


def is_sura_heading(par):
    return "".join(par["lines"]).lstrip().startswith("سُورَةُ")


def flush_page():
    global page
    if page:
        pages.append(page)
    page = []


for p in body.iter(W + "p"):
    ppr = p.find(W + "pPr")
    jc = None
    if ppr is not None and ppr.find(W + "jc") is not None:
        jc = ppr.find(W + "jc").get(W + "val")
    par = new_par("center" if jc == "center" else "both")
    for r in p.iter(W + "r"):
        for ch in r:
            if ch.tag == W + "t":
                par["lines"][-1] += ch.text or ""
            elif ch.tag == W + "br":
                if ch.get(W + "type") == "page":
                    if has_text(par):
                        par["sura"] = is_sura_heading(par)
                        page.append(par)
                    par = new_par(par["jc"])
                    flush_page()
                else:
                    par["lines"].append("")
    if has_text(par):
        par["sura"] = is_sura_heading(par)
        page.append(par)
flush_page()


def norm(t):
    return re.sub(r"[ \t\r\n]+", " ", t).strip()


html_pages, hashes = [], []
for n, pg in enumerate(pages, 1):
    rows = []
    for par in pg:
        cls = "sura" if par["sura"] else ("c" if par["jc"] == "center" else "j")
        for ln in par["lines"]:
            ln = norm(ln)
            if ln:
                rows.append(f'<div class="l {cls}">{escape(ln)}</div>')
    txt = "\n".join(norm(l) for par in pg for l in par["lines"] if norm(l))
    hashes.append(hashlib.sha256(txt.encode()).hexdigest()[:16])
    html_pages.append(
        f'<div class="pw" id="p{n}"><section class="page">'
        f'<div class="frame"></div><div class="txt">{"".join(rows)}</div>'
        f'<footer><b>- {n} -</b><span>خط النسخ الحاسوبي ـ رواية حفص ـ مجمع الملك فهد لطباعة المصحف الشريف ـ النسخة رقم ٣،٠</span></footer>'
        f'</section></div>')

tpl = (pathlib.Path(__file__).parent / "template.html").read_text(encoding="utf-8")
OUT.mkdir(exist_ok=True)
(OUT / "index.html").write_text(tpl.replace("{{PAGES}}", "\n".join(html_pages)), encoding="utf-8")
(OUT / "page-hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
print(f"{len(pages)} pages, {sum(len(p) for p in pages)} paragraphs")
