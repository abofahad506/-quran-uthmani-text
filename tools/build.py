#!/usr/bin/env python3
"""docx (KFGQPC Hafs mushaf) -> static HTML: one <section> per printed page,
one <div> per printed line. Text is copied verbatim; nothing is rewritten."""
import re, sys, zipfile, hashlib, json, pathlib
from xml.etree import ElementTree as ET
from html import escape

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/Mushaf-Hafs-Uthmanic.docx")
OUT = pathlib.Path("site")
KFGQPC_DATA = pathlib.Path(__file__).parent.parent.joinpath("src", "kfgqpc_hafs_v30.json")

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
records = json.loads(KFGQPC_DATA.read_text(encoding="utf-8"))
if not isinstance(records, list) or len(records) != 6236:
    raise ValueError("KFGQPC data must contain exactly 6,236 ayah records")

records_by_reference = {}
for record in records:
    reference = (record["sura_no"], record["aya_no"])
    if reference in records_by_reference:
        raise ValueError(f"Duplicate KFGQPC record for {reference[0]}:{reference[1]}")
    if not record["aya_text_unicode"] or not record["aya_text_emlaey"]:
        raise ValueError(f"Missing KFGQPC text for {reference[0]}:{reference[1]}")
    if not 1 <= record["page"] <= len(pages):
        raise ValueError(f"Invalid KFGQPC page for {reference[0]}:{reference[1]}")
    if not 1 <= record["line_start"] <= record["line_end"] <= 15:
        raise ValueError(f"Invalid KFGQPC line range for {reference[0]}:{reference[1]}")
    markers = AYAH_MARKER.findall(record["aya_text_unicode"])
    marker_number = (
        int(markers[-1].translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        if markers else None
    )
    if marker_number != record["aya_no"]:
        raise ValueError(f"Invalid KFGQPC ayah marker for {reference[0]}:{reference[1]}")
    if not 1 <= record["jozz"] <= 30:
        raise ValueError(f"Invalid KFGQPC juz for {reference[0]}:{reference[1]}")
    records_by_reference[reference] = record

if len(records_by_reference) != sum(len(surah["ayahs"]) for surah in surahs):
    raise ValueError("KFGQPC data does not match the extracted surah and ayah count")

for surah in surahs:
    for ayah in surah["ayahs"]:
        reference = (surah["number"], ayah["number"])
        record = records_by_reference.get(reference)
        if record is None:
            raise ValueError(f"Missing KFGQPC record for {reference[0]}:{reference[1]}")
        if ayah["pages"] != [record["page"]]:
            raise ValueError(f"Page mismatch for KFGQPC record {reference[0]}:{reference[1]}")
        ayah["text"] = record["aya_text_unicode"]
        ayah["search_text"] = record["aya_text_emlaey"]
        ayah["pages"] = [record["page"]]
        ayah["lines"] = [record["line_start"], record["line_end"]]
        ayah["juz"] = record["jozz"]

attribution = (
    "Quranic text: King Fahd Glorious Quran Printing Complex (KFGQPC), "
    "Madinah, Saudi Arabia; Hafs narration. Uthmani text and emlaey search text "
    "from src/kfgqpc_hafs_v30.json; page layout from src/Mushaf-Hafs-Uthmanic.docx. "
    "Rights and terms belong to KFGQPC; "
    "see NOTICE.md. Verify against the official printed mushaf for critical use."
)
quran = {
    "attribution": attribution,
    "edition": "Hafs narration, Uthmani script, KFGQPC version 3.0",
    "source": "src/Mushaf-Hafs-Uthmanic.docx",
    "search_source": "KFGQPC Hafs v3.0 data, aya_text_emlaey field",
    "surahs": surahs,
}
for surah in surahs:
    surah["url"] = f"quran.html#s{surah['number']}"
    for ayah in surah["ayahs"]:
        ayah["url"] = f"quran.html#s{surah['number']}-a{ayah['number']}"
(OUT / "quran.json").write_text(
    json.dumps(quran, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

search_index = {
    "attribution": "King Fahd Glorious Quran Printing Complex (KFGQPC), Hafs v3.0",
    "field": "aya_text_emlaey",
    "ayahs": [
        {
            "reference": f'{surah["number"]}:{ayah["number"]}',
            "text": ayah["search_text"],
            "url": ayah["url"],
        }
        for surah in surahs
        for ayah in surah["ayahs"]
    ],
}
(OUT / "quran-search.json").write_text(
    json.dumps(search_index, ensure_ascii=False, separators=(",", ":")) + "\n",
    encoding="utf-8",
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
    '.tools{padding:1rem;background:#f2f4ef;border:1px solid #ccd4c8;border-radius:.5rem}',
    '.tools form{margin:.5rem 0}.tools input{max-width:100%;padding:.4rem}',
    'button{padding:.35rem .65rem;cursor:pointer}.copy-ayah{margin-inline:.5rem}',
    '#search-results{max-height:18rem;overflow:auto}#search-results li{margin:.25rem 0}',
    '</style>',
    '</head>',
    '<body>',
    '<header>',
    '<h1>القرآن الكريم — رواية حفص بالرسم العثماني</h1>',
    f'<p>{escape(attribution)}</p>',
    '<p><a href="index.html">عرض صفحات المصحف</a> · '
    '<a href="quran.json">تنزيل JSON</a> · <a href="quran.txt">تنزيل النص</a></p>',
    '<section class="tools" aria-label="البحث والنسخ">',
    '<form id="search-form" role="search">',
    '<label for="search-query">ابحث في نص الآيات:</label> ',
    '<input id="search-query" type="search" dir="rtl" autocomplete="off" required> ',
    '<button type="submit">بحث</button>',
    '</form>',
    '<ol id="search-results" aria-label="نتائج البحث"></ol>',
    '<form id="copy-range-form">',
    '<label for="copy-start">نسخ مدى آيات — من مرجع (سورة:آية):</label> ',
    '<input id="copy-start" inputmode="numeric" dir="ltr" placeholder="2:255" required> ',
    '<label for="copy-end">إلى:</label> ',
    '<input id="copy-end" inputmode="numeric" dir="ltr" placeholder="2:257" required> ',
    '<button type="submit">نسخ المدى</button>',
    '</form>',
    '<p id="action-status" role="status" aria-live="polite"></p>',
    '</section>',
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
            f'<span class="page-link">[صفحة {page_links}]</span> '
            f'<button class="copy-ayah" type="button" '
            f'data-copy-ayah="{surah["number"]}:{ayah["number"]}" '
            f'aria-label="نسخ الآية {surah["number"]}:{ayah["number"]}">نسخ الآية</button></p>'
        )
    quran_html.append('</section>')
quran_html.extend([
    '</main>',
    '<script>',
    '"use strict";',
    'const statusMessage = document.getElementById("action-status");',
    'const ayahRows = Array.from(document.querySelectorAll("main p[id^=s][id*=-a]"));',
    'const ayahPositions = new Map(ayahRows.map((row, index) => [row.id, index]));',
    'function citationText(row) {',
    '  const reference = row.querySelector(".reference").textContent.trim();',
    '  const text = row.querySelector(".ayah").textContent.trim();',
    '  return `${reference} ${text}`;',
    '}',
    'async function copyText(text) {',
    '  try {',
    '    if (navigator.clipboard && window.isSecureContext) {',
    '      await navigator.clipboard.writeText(text);',
    '    } else {',
    '      const field = document.createElement("textarea");',
    '      field.value = text;',
    '      field.setAttribute("readonly", "");',
    '      field.style.position = "fixed";',
    '      field.style.opacity = "0";',
    '      document.body.appendChild(field);',
    '      field.select();',
    '      const copied = document.execCommand("copy");',
    '      field.remove();',
    '      if (!copied) throw new Error("Clipboard copy command was rejected");',
    '    }',
    '    statusMessage.textContent = "تم نسخ النص مع المرجع.";',
    '  } catch (error) {',
    '    console.error("Could not copy Quran text:", error);',
    '    statusMessage.textContent = "تعذر النسخ. تحقق من إذن الحافظة في المتصفح.";',
    '  }',
    '}',
    'document.addEventListener("click", event => {',
    '  const button = event.target.closest("[data-copy-ayah]");',
    '  if (!button) return;',
    '  const row = button.closest("p");',
    '  if (row) copyText(citationText(row));',
    '});',
    'function parseReference(value) {',
    '  const digits = value.trim().replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 0x660));',
    '  const match = digits.match(/^(\\d+)\\s*:\\s*(\\d+)$/);',
    '  if (!match) return null;',
    '  const row = document.getElementById(`s${Number(match[1])}-a${Number(match[2])}`);',
    '  return row && ayahPositions.has(row.id) ? row : null;',
    '}',
    'document.getElementById("copy-range-form").addEventListener("submit", event => {',
    '  event.preventDefault();',
    '  const start = parseReference(document.getElementById("copy-start").value);',
    '  const end = parseReference(document.getElementById("copy-end").value);',
    '  if (!start || !end) {',
    '    statusMessage.textContent = "أدخل مرجعين صحيحين بصيغة سورة:آية.";',
    '    return;',
    '  }',
    '  const first = ayahPositions.get(start.id);',
    '  const last = ayahPositions.get(end.id);',
    '  if (first > last) {',
    '    statusMessage.textContent = "يجب أن يسبق مرجع البداية مرجع النهاية.";',
    '    return;',
    '  }',
    '  copyText(ayahRows.slice(first, last + 1).map(citationText).join("\\n"));',
    '});',
    'function searchKey(value) {',
    '  return value.normalize("NFD").replace(/[\\u064B-\\u065F\\u0670\\u06D6-\\u06ED\\u08F0-\\u08F2ـ]/g, "").replace(/[أإآٱ]/g, "ا").replace(/ءا/g, "ا").replace(/ى/g, "ي");',
    '}',
    'let searchIndexPromise;',
    'function loadSearchIndex() {',
    '  if (!searchIndexPromise) {',
    '    searchIndexPromise = fetch("quran-search.json").then(response => {',
    '      if (!response.ok) throw new Error(`Search index request failed: ${response.status}`);',
    '      return response.json();',
    '    }).then(data => {',
    '      if (data.field !== "aya_text_emlaey" || !Array.isArray(data.ayahs) || data.ayahs.length !== 6236) {',
    '        throw new Error("Invalid KFGQPC search index");',
    '      }',
    '      return data.ayahs.map(ayah => ({...ayah, key: searchKey(ayah.text)}));',
    '    }).catch(error => {',
    '      searchIndexPromise = null;',
    '      throw error;',
    '    });',
    '  }',
    '  return searchIndexPromise;',
    '}',
    'document.getElementById("search-form").addEventListener("submit", async event => {',
    '  event.preventDefault();',
    '  const query = searchKey(document.getElementById("search-query").value.trim());',
    '  const results = document.getElementById("search-results");',
    '  results.replaceChildren();',
    '  if (!query) {',
    '    statusMessage.textContent = "اكتب نصًا للبحث.";',
    '    return;',
    '  }',
    '  statusMessage.textContent = "جارٍ البحث في النص الإملائي والعثماني...";',
    '  try {',
    '    const index = await loadSearchIndex();',
    '    const standardMatches = new Set(index.filter(ayah => ayah.key.includes(query)).map(ayah => ayah.url.split("#").pop()));',
    '    const matches = ayahRows.filter(row => standardMatches.has(row.id) || searchKey(row.querySelector(".ayah").textContent).includes(query));',
    '    const shown = matches.slice(0, 100);',
    '    for (const row of shown) {',
    '      const item = document.createElement("li");',
    '      const link = document.createElement("a");',
    '      link.href = `#${row.id}`;',
    '      link.textContent = `${row.querySelector(".reference").textContent.trim()} — ${row.querySelector(".ayah").textContent.trim()}`;',
    '      item.appendChild(link);',
    '      results.appendChild(item);',
    '    }',
    '    statusMessage.textContent = matches.length',
    '      ? `عدد النتائج: ${matches.length}${matches.length > shown.length ? ` (عُرضت أول ${shown.length})` : ""}.`',
    '      : "لا توجد نتائج مطابقة."; ',
    '  } catch (error) {',
    '    console.error("Could not search KFGQPC text:", error);',
    '    statusMessage.textContent = "تعذر تحميل فهرس البحث. حاول مجددًا لاحقًا.";',
    '  }',
    '});',
    '</script>',
    '</body>',
    '</html>',
    '',
])
(OUT / "quran.html").write_text("\n".join(quran_html), encoding="utf-8")

print(
    f"{len(pages)} pages, {sum(len(p) for p in pages)} paragraphs, "
    f"{len(surahs)} surahs, {sum(len(s['ayahs']) for s in surahs)} ayahs"
)
