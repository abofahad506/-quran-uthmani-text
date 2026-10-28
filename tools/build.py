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


AYAH_MARKER = re.compile(r"\u06dd([\u0660-\u0669]+)")
BASMALA = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"


def join_layout_text(left, right):
    if left and right and not left[-1].isspace() and not right[0].isspace():
        return left + " " + right
    return left + right


def paragraph_text(par):
    text = ""
    for line in par["lines"]:
        text = join_layout_text(text, line)
    return text


def extract_quran():
    surahs = []
    current_surah = None
    ayah_text = ""
    ayah_pages = set()

    def append_fragment(fragment, page_number):
        nonlocal ayah_text
        if fragment:
            ayah_text = join_layout_text(ayah_text, fragment)
            if fragment.strip():
                ayah_pages.add(page_number)

    def finish_ayah(marker, page_number):
        nonlocal ayah_text, ayah_pages
        digits = marker[1:].translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        number = int(digits)
        ayah_text = join_layout_text(ayah_text, marker)
        if marker:
            ayah_pages.add(page_number)
        if current_surah is None:
            raise ValueError("Found an ayah marker before the first surah heading")
        current_surah["ayahs"].append({
            "number": number,
            "pages": sorted(ayah_pages),
            "text": ayah_text.strip(),
        })
        ayah_text = ""
        ayah_pages = set()

    for page_number, page in enumerate(pages, 1):
        for par in page:
            text = paragraph_text(par)
            if is_sura_heading(par):
                if ayah_text.strip():
                    raise ValueError(f"Incomplete ayah before surah heading on page {page_number}")
                current_surah = {
                    "number": len(surahs) + 1,
                    "name": text,
                    "ayahs": [],
                }
                surahs.append(current_surah)
                continue
            if not text or text.strip() == BASMALA:
                continue
            if current_surah is None:
                raise ValueError(f"Found text before the first surah heading on page {page_number}")

            offset = 0
            for match in AYAH_MARKER.finditer(text):
                append_fragment(text[offset:match.start()], page_number)
                finish_ayah(match.group(), page_number)
                offset = match.end()
            append_fragment(text[offset:], page_number)

    if ayah_text.strip():
        raise ValueError("The source document ends with an incomplete ayah")
    if len(surahs) != 114:
        raise ValueError(f"Expected 114 surahs, found {len(surahs)}")
    total_ayahs = sum(len(surah["ayahs"]) for surah in surahs)
    if total_ayahs != 6236:
        raise ValueError(f"Expected 6236 ayahs, found {total_ayahs}")
    for surah in surahs:
        for expected, ayah in enumerate(surah["ayahs"], 1):
            if ayah["number"] != expected:
                raise ValueError(
                    f"Unexpected ayah number in surah {surah['number']}: "
                    f"expected {expected}, found {ayah['number']}"
                )
            if not ayah["pages"]:
                raise ValueError(
                    f"Missing page number for surah {surah['number']}, ayah {ayah['number']}"
                )
    return surahs


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

surahs = extract_quran()
attribution = (
    "Quranic text: King Fahd Glorious Quran Printing Complex (KFGQPC), "
    "Madinah, Saudi Arabia; Hafs narration. Extracted from "
    "src/Mushaf-Hafs-Uthmanic.docx. Rights and terms belong to KFGQPC; "
    "see NOTICE.md. Verify against the official printed mushaf for critical use."
)
quran = {
    "attribution": attribution,
    "edition": "Hafs narration, Uthmani script, KFGQPC version 3.0",
    "source": "src/Mushaf-Hafs-Uthmanic.docx",
    "surahs": surahs,
}
for surah in surahs:
    surah["url"] = f"quran.html#s{surah['number']}"
    for ayah in surah["ayahs"]:
        ayah["url"] = f"quran.html#s{surah['number']}-a{ayah['number']}"
(OUT / "quran.json").write_text(
    json.dumps(quran, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

plain_text = [
    "# Quranic text — Hafs narration, Uthmani script",
    f"# {attribution}",
    "# Each ayah line: surah number:ayah number [printed page(s)] <source text>",
    "",
]
for surah in surahs:
    plain_text.append(f"## {surah['number']}. {surah['name']}")
    for ayah in surah["ayahs"]:
        page_list = ",".join(str(number) for number in ayah["pages"])
        plain_text.append(
            f"{surah['number']}:{ayah['number']} [{page_list}] {ayah['text']}"
        )
    plain_text.append("")
(OUT / "quran.txt").write_text("\n".join(plain_text), encoding="utf-8")

quran_html = [
    '<!doctype html>',
    '<html lang="ar" dir="rtl">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<meta name="description" content="القرآن الكريم برواية حفص بالرسم العثماني، مقسم حسب السور والآيات مع روابط ثابتة.">',
    '<title>القرآن الكريم — نص عثماني وروابط الآيات</title>',
    '<style>',
    'body{max-width:52rem;margin:2rem auto;padding:0 1rem;color:#222;font-family:serif;line-height:1.9}',
    'h1,h2{line-height:1.4}h2{margin-top:2rem;padding-top:1rem;border-top:1px solid #ccc}',
    'a{color:#245b35}.ayah{font-size:1.25rem}.reference{font:1rem sans-serif;white-space:nowrap}',
    '.page-link{font:0.8rem sans-serif;white-space:nowrap}',
    '</style>',
    '</head>',
    '<body>',
    '<header>',
    '<h1>القرآن الكريم — رواية حفص بالرسم العثماني</h1>',
    f'<p>{escape(attribution)}</p>',
    '<p><a href="index.html">عرض صفحات المصحف</a> · '
    '<a href="quran.json">تنزيل JSON</a> · <a href="quran.txt">تنزيل النص</a></p>',
    '<nav aria-label="فهرس السور"><h2>فهرس السور</h2><ol>',
]
for surah in surahs:
    quran_html.append(
        f'<li><a href="#s{surah["number"]}">{escape(surah["name"])}</a></li>'
    )
quran_html.extend(['</ol></nav>', '</header>', '<main>'])
for surah in surahs:
    quran_html.append(
        f'<section aria-labelledby="s{surah["number"]}">'
        f'<h2 id="s{surah["number"]}"><a href="#s{surah["number"]}">'
        f'{escape(surah["name"])}</a></h2>'
    )
    for ayah in surah["ayahs"]:
        page_links = ", ".join(
            f'<a class="page-link" href="index.html#p{page_number}">{page_number}</a>'
            for page_number in ayah["pages"]
        )
        reference = f'{surah["number"]}:{ayah["number"]}'
        quran_html.append(
            f'<p id="s{surah["number"]}-a{ayah["number"]}">'
            f'<a class="reference" href="#s{surah["number"]}-a{ayah["number"]}">'
            f'{reference}</a> '
            f'<span class="ayah">{escape(ayah["text"])}</span> '
            f'<span class="page-link">[صفحة {page_links}]</span></p>'
        )
    quran_html.append('</section>')
quran_html.extend(['</main>', '</body>', '</html>', ''])
(OUT / "quran.html").write_text("\n".join(quran_html), encoding="utf-8")

print(
    f"{len(pages)} pages, {sum(len(p) for p in pages)} paragraphs, "
    f"{len(surahs)} surahs, {sum(len(s['ayahs']) for s in surahs)} ayahs"
)
