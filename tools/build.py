#!/usr/bin/env python3
"""docx (KFGQPC Hafs mushaf) -> static HTML: one <section> per printed page,
one <div> per printed line. Text is copied verbatim; nothing is rewritten."""
import re, sys, zipfile, hashlib, json, pathlib
from xml.etree import ElementTree as ET
from html import escape, unescape

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/Mushaf-Hafs-Uthmanic.docx")
OUT = pathlib.Path("site")
KFGQPC_DATA = pathlib.Path(__file__).parent.parent.joinpath("src", "kfgqpc_hafs_v30.json")
SITE_URL = "https://abofahad506.github.io/-quran-uthmani-text"

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
    "Madinah, Saudi Arabia; Hafs narration, Uthmani script, KFGQPC v3.0. "
    "Text and emlaey search data from src/kfgqpc_hafs_v30.json; visual page layout "
    "from src/Mushaf-Hafs-Uthmanic.docx. The visual mushaf edition is the reference; "
    "the linked text edition is a companion for browsing and search. "
    "Rights and terms belong to KFGQPC; "
    "see NOTICE.md. Verify against the official printed mushaf for critical use."
)
quran = {
    "attribution": attribution,
    "edition": "Hafs narration, Uthmani script, KFGQPC version 3.0",
    "source": "src/Mushaf-Hafs-Uthmanic.docx",
    "text_source": "src/kfgqpc_hafs_v30.json",
    "text_status": "Companion text edition; the visual mushaf edition is the reference.",
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
    "# Companion Quranic text — Hafs narration, Uthmani script, KFGQPC v3.0",
    "# Reference edition: the visual mushaf at https://abofahad506.github.io/-quran-uthmani-text/",
    "# Text source: src/kfgqpc_hafs_v30.json; page layout source: src/Mushaf-Hafs-Uthmanic.docx",
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

surah_data_dir = OUT / "data" / "surah"
surah_data_dir.mkdir(parents=True, exist_ok=True)
surah_file_sizes = []
for surah in surahs:
    number = surah["number"]
    stem = f"{number:03}"
    surah_json_path = surah_data_dir / f"{stem}.json"
    surah_text_path = surah_data_dir / f"{stem}.txt"
    surah_json = {
        "attribution": attribution,
        "edition": quran["edition"],
        "surah_number": number,
        "name": surah["name"],
        "ayah_count": len(surah["ayahs"]),
        "ayahs": surah["ayahs"],
    }
    surah_json_path.write_text(
        json.dumps(surah_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    surah_text = "\n".join(
        f'{number}:{ayah["number"]} [{",".join(map(str, ayah["pages"]))}] {ayah["text"]}'
        for ayah in surah["ayahs"]
    )
    surah_text_path.write_text(surah_text + "\n", encoding="utf-8")

    generated_surah = json.loads(surah_json_path.read_text(encoding="utf-8"))
    if generated_surah != surah_json:
        raise ValueError(f"Generated surah JSON mismatch for surah {number}")
    expected_source_ayahs = [
        (record["aya_no"], record["aya_text_unicode"], record["aya_text_emlaey"])
        for record in records
        if record["sura_no"] == number
    ]
    if [
        (ayah["number"], ayah["text"], ayah["search_text"])
        for ayah in generated_surah["ayahs"]
    ] != expected_source_ayahs:
        raise ValueError(f"Generated surah JSON text mismatch against source for surah {number}")
    expected_text_lines = [
        f'{number}:{record["aya_no"]} [{record["page"]}] {record["aya_text_unicode"]}'
        for record in records
        if record["sura_no"] == number
    ]
    if surah_text_path.read_text(encoding="utf-8").splitlines() != expected_text_lines:
        raise ValueError(f"Generated surah text mismatch against source for surah {number}")
    surah_file_sizes.append(
        (surah, surah_json_path.stat().st_size, surah_text_path.stat().st_size)
    )

quran_html = [
    '<!doctype html>',
    '<html lang="ar" dir="rtl">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<meta name="description" content="النص المصاحب للقرآن الكريم برواية حفص والرسم العثماني وفق بيانات مجمع الملك فهد، مفهرس للسور والآيات؛ إصدار المصحف المرئي هو المرجع.">',
    '<meta name="robots" content="index,follow">',
    f'<link rel="canonical" href="{SITE_URL}/quran.html">',
    '<meta property="og:type" content="article">',
    '<meta property="og:title" content="النص المصاحب للقرآن الكريم — حفص، KFGQPC v3.0">',
    '<meta property="og:description" content="نص مفهرس للتصفح والبحث وفق بيانات مجمع الملك فهد؛ إصدار المصحف المرئي هو المرجع.">',
    f'<meta property="og:url" content="{SITE_URL}/quran.html">',
    '<title>النص المصاحب للقرآن الكريم — حفص، الرسم العثماني، KFGQPC v3.0</title>',
    '<style>',
    'body{max-width:52rem;margin:2rem auto;padding:0 1rem;color:#222;font-family:serif;line-height:1.9}',
    'h1,h2{line-height:1.4}h2{margin-top:2rem;padding-top:1rem;border-top:1px solid #ccc}',
    'a{color:#245b35}.ayah{font-size:1.25rem}.reference{font:1rem sans-serif;white-space:nowrap}',
    '.edition-note{padding:.75rem 1rem;background:#f2f4ef;border-inline-start:4px solid #52802B}',
    '.page-link{font:0.8rem sans-serif;white-space:nowrap}',
    '.tools{padding:1rem;background:#f2f4ef;border:1px solid #ccd4c8;border-radius:.5rem}',
    '.tools form{margin:.5rem 0}.tools input{max-width:100%;padding:.4rem}',
    'button{padding:.35rem .65rem;cursor:pointer}.copy-ayah{margin-inline:.5rem}',
    '#search-results{max-height:18rem;overflow:auto}#search-results li{margin:.25rem 0}',
    '</style>',
    '</head>',
    '<body>',
    '<header>',
    '<h1>النص المصاحب للقرآن الكريم — رواية حفص بالرسم العثماني</h1>',
    '<p class="edition-note" role="note">هذه نسخة نصية مصاحبة للتصفح والبحث، مصدرها بيانات مجمع الملك فهد (حفص، الإصدار 3.0). إصدار المصحف المرئي هو المرجع؛ <a href="index.html">افتح صفحات المصحف</a>.</p>',
    f'<p>{escape(attribution)}</p>',
    '<p><a href="index.html">عرض صفحات المصحف بالرسم العثماني</a> · '
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

generated_quran = json.loads((OUT / "quran.json").read_text(encoding="utf-8"))
generated_ayahs = [
    (surah["number"], ayah["number"], ayah["text"], ayah["search_text"])
    for surah in generated_quran["surahs"]
    for ayah in surah["ayahs"]
]
source_ayahs = [
    (
        record["sura_no"],
        record["aya_no"],
        record["aya_text_unicode"],
        record["aya_text_emlaey"],
    )
    for record in records
]
if generated_ayahs != source_ayahs:
    for generated, source in zip(generated_ayahs, source_ayahs):
        if generated != source:
            raise ValueError(
                f"Generated JSON text mismatch against KFGQPC source "
                f"for {source[0]}:{source[1]}"
            )
    raise ValueError("Generated JSON has a different ayah count from KFGQPC source")

generated_text_rows = re.findall(
    r"^(\d+):(\d+) \[\d+(?:,\d+)*\] (.+)$",
    (OUT / "quran.txt").read_text(encoding="utf-8"),
    re.MULTILINE,
)
if generated_text_rows != [
    (str(sura), str(aya), text) for sura, aya, text, _ in source_ayahs
]:
    raise ValueError("Generated plain text does not match the KFGQPC Unicode source")

generated_html_ayahs = [
    unescape(text)
    for text in re.findall(
        r'<span class="ayah">(.*?)</span>',
        (OUT / "quran.html").read_text(encoding="utf-8"),
    )
]
if generated_html_ayahs != [text for _, _, text, _ in source_ayahs]:
    raise ValueError("Generated HTML text does not match the KFGQPC Unicode source")

font_family = "KFGQPC Hafs V3"
font_url = f"{SITE_URL}/fonts/KFGQPC-Hafs-V30.ttf"
example_ayah = surahs[0]["ayahs"][0]
example_html = "\n".join([
    "<!doctype html>",
    '<html lang="ar" dir="rtl">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    "<title>KFGQPC Hafs font example — Al-Fatihah 1:1</title>",
    "<style>",
    "@font-face {",
    f'  font-family: "{font_family}";',
    f'  src: url("{font_url}") format("truetype");',
    "}",
    "body { margin: 2rem; }",
    f'.ayah {{ font-family: "{font_family}", serif; font-size: 2rem; line-height: 2; }}',
    "</style>",
    "</head>",
    "<body>",
    "<main>",
    "<h1>Al-Fatihah 1:1</h1>",
    f'<p class="ayah" lang="ar" dir="rtl">{escape(example_ayah["text"])}</p>',
    "</main>",
    "</body>",
    "</html>",
    "",
])
(OUT / "example.html").write_text(example_html, encoding="utf-8")
if [
    unescape(text)
    for text in re.findall(r'<p class="ayah" lang="ar" dir="rtl">(.*?)</p>', example_html)
] != [example_ayah["text"]]:
    raise ValueError("Font example ayah does not match the KFGQPC source")

generated_search = json.loads((OUT / "quran-search.json").read_text(encoding="utf-8"))
if [
    (int(ayah["reference"].split(":")[0]), int(ayah["reference"].split(":")[1]), ayah["text"])
    for ayah in generated_search["ayahs"]
] != [(sura, aya, text) for sura, aya, _, text in source_ayahs]:
    raise ValueError("Generated search index does not match the KFGQPC emlaey source")

llms_full_lines = [
    "# Full surah index — Quranic text companion",
    "",
    "> The visual mushaf edition is the reference. These per-surah files are companion resources.",
    "",
    "## English index",
    "",
    "| Surah | Ayahs | JSON size (bytes) | TXT size (bytes) | Files |",
    "|---|---:|---:|---:|---|",
]
for surah, json_size, text_size in surah_file_sizes:
    number = surah["number"]
    stem = f"{number:03}"
    base = f"{SITE_URL}/data/surah/{stem}"
    llms_full_lines.append(
        f'| Surah {number} ({surah["name"]}) | {len(surah["ayahs"])} | {json_size} | '
        f'{text_size} | [JSON]({base}.json) · [TXT]({base}.txt) |'
    )
llms_full_lines.extend([
    "",
    "Ayah URL pattern: `quran.html#s{surah}-a{ayah}`; for example, "
    f"[2:255]({SITE_URL}/quran.html#s2-a255). Surah URL pattern: `quran.html#s{{surah}}`.",
    "",
    "## الفهرس العربي",
    "",
    "| السورة | عدد الآيات | حجم JSON (بايت) | حجم TXT (بايت) | الملفات |",
    "|---|---:|---:|---:|---|",
])
for surah, json_size, text_size in surah_file_sizes:
    number = surah["number"]
    stem = f"{number:03}"
    base = f"{SITE_URL}/data/surah/{stem}"
    llms_full_lines.append(
        f'| سورة {number} ({surah["name"]}) | {len(surah["ayahs"])} | {json_size} | '
        f'{text_size} | [JSON]({base}.json) · [TXT]({base}.txt) |'
    )
llms_full_lines.extend([
    "",
    "نمط رابط الآية: `quran.html#s{surah}-a{ayah}`؛ مثال: "
    f"[البقرة ٢٥٥]({SITE_URL}/quran.html#s2-a255). ونمط رابط السورة: `quran.html#s{{surah}}`.",
    "",
])
(OUT / "llms-full.txt").write_text("\n".join(llms_full_lines), encoding="utf-8")

site_pages = [
    f"{SITE_URL}/",
    f"{SITE_URL}/quran.html",
    f"{SITE_URL}/example.html",
    f"{SITE_URL}/llms-full.txt",
    f"{SITE_URL}/data/surah/001.json",
    f"{SITE_URL}/data/surah/001.txt",
    f"{SITE_URL}/data/surah/002.json",
    f"{SITE_URL}/data/surah/114.json",
    f"{SITE_URL}/data/surah/114.txt",
]
sitemap_urls = "\n".join(
    f"  <url><loc>{url}</loc></url>" for url in site_pages
)
(OUT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"{sitemap_urls}\n"
    "</urlset>\n",
    encoding="utf-8",
)
(OUT / "robots.txt").write_text(
    "User-agent: *\n"
    "Allow: /\n"
    f"Sitemap: {SITE_URL}/sitemap.xml\n",
    encoding="utf-8",
)
allah_example = "".join(
    chr(codepoint)
    for codepoint in (0x0671, 0x0644, 0x0644, 0x0651, 0x064E, 0x0647, 0x0650)
)
(OUT / "llms.txt").write_text(
    "# القرآن الكريم — رواية حفص بالرسم العثماني\n\n"
    "> نص القرآن بالرسم العثماني وفق بيانات مجمع الملك فهد لطباعة المصحف الشريف، "
    "مع إصدار مرئي مطابق للمصحف. الإصدار المرئي هو المرجع، والنص أدناه إصدار مصاحب "
    "للتصفح والبحث وليس بديلًا عن المصحف المرئي.\n\n"
    "## إصدارات الموقع\n\n"
    f"- المصحف المرئي: {SITE_URL}/\n"
    f"- النص المفهرس حسب السور والآيات: {SITE_URL}/quran.html\n"
    f"- البيانات المنظمة بصيغة JSON: {SITE_URL}/quran.json\n"
    f"- النص الكامل بصيغة UTF-8: {SITE_URL}/quran.txt\n"
    f"- فهرس الآيات للبحث: {SITE_URL}/quran-search.json\n"
    f"- خريطة الموقع: {SITE_URL}/sitemap.xml\n\n"
    "## بيانات المصدر\n\n"
    "- إصدار النص: حفص، الرسم العثماني، مجمع الملك فهد، الإصدار 3.0؛ مصدر النص هو بيانات KFGQPC.\n"
    "- الإصدار المرئي هو المرجع، ويُستخدم النص المفهرس كإصدار مصاحب للتصفح والبحث.\n"
    "- JSON ينظم النص بحسب السور والآيات، ويضم مراجع الصفحات والأجزاء وروابط الآيات.\n"
    "- حقوق النص وشروط استخدامه تعود إلى مجمع الملك فهد؛ راجع NOTICE.md في المستودع. "
    "يرجى التحقق من المصحف الرسمي عند الاستخدامات الحرجة.\n\n"
    "## Rules for copying the Quranic text\n\n"
    "- Copy the `text` field from `quran.json` exactly as published. Never normalize it "
    "(NFC, NFD, NFKC, or NFKD); never strip, add, or reorder combining marks; and never "
    "replace or remove U+06DD or the digits after it.\n"
    f"- Example: in `{allah_example}`, the source order is U+0651 (shadda) then U+064E (fatha). "
    "NFC reverses that order. Preserve the source order exactly.\n"
    "- `search_text` (emlaey spelling) is for matching only. Never copy it as Quranic text.\n"
    "- The JSON `text` field includes the end-of-ayah mark U+06DD and the ayah number "
    "after it (Arabic-Indic digits in the published text).\n"
    "- In `quran.txt`, each ayah line is `surah:ayah [page(s)] <text>`, for example "
    "`1:1 [1] <text>`. Strip exactly the `surah:ayah [page(s)] ` prefix before copying; "
    "the remaining text includes U+06DD and its ayah number.\n"
    "- The text renders correctly only with the KFGQPC Hafs font. See the "
    "[font license](https://github.com/abofah506/-quran-uthmani-text/blob/main/fonts/LICENSE-KFGQPC.txt) "
    "and [NOTICE](https://github.com/abofah506/-quran-uthmani-text/blob/main/NOTICE.md).\n\n"
    "## Rendering with the font\n\n"
    f'The exact font family name from the font name table is `{font_family}`. '
    f'Link to or download the [unmodified font file]({font_url}); do not convert or subset it. '
    "The license forbids modification. See [the one-ayah demo]("
    f"{SITE_URL}/example.html).\n\n"
    "```css\n"
    "@font-face {\n"
    f'  font-family: "{font_family}";\n'
    f'  src: url("{font_url}") format("truetype");\n'
    "}\n"
    f'.quran {{ font-family: "{font_family}", serif; }}\n'
    "```\n\n"
    "```html\n"
    '<div lang="ar" dir="rtl" class="quran">[Insert source ayah text unchanged]</div>\n'
    "```\n\n"
    "## عرض النص بالخط\n\n"
    f'اسم عائلة الخط كما هو مسجل في جدول الأسماء هو `{font_family}`. '
    f'استخدم رابط الخط أو نزّل [الملف الأصلي دون تعديل]({font_url})؛ لا تحوّله ولا تستخرج جزءًا منه. '
    "ترخيص الخط يمنع تعديله. راجع [مثال عرض آية واحدة]("
    f"{SITE_URL}/example.html).\n\n"
    "```css\n"
    "@font-face {\n"
    f'  font-family: "{font_family}";\n'
    f'  src: url("{font_url}") format("truetype");\n'
    "}\n"
    f'.quran {{ font-family: "{font_family}", serif; }}\n'
    "```\n\n"
    "```html\n"
    '<div lang="ar" dir="rtl" class="quran">[ضع نص الآية كما ورد في المصدر دون تغيير]</div>\n'
    "```\n\n"
    "للاطلاع على الشروط، راجع "
    "[ترخيص الخط](https://github.com/abofah506/-quran-uthmani-text/blob/main/fonts/LICENSE-KFGQPC.txt) "
    "و[إشعار الحقوق](https://github.com/abofah506/-quran-uthmani-text/blob/main/NOTICE.md).\n\n"
    "## قواعد نسخ النص القرآني\n\n"
    "- انسخ حقل `text` من `quran.json` كما نُشر تمامًا. لا تُطبّق أي تطبيع "
    "(NFC أو NFD أو NFKC أو NFKD)، ولا تحذف العلامات المركبة أو تضفها أو تغيّر ترتيبها، "
    "ولا تستبدل علامة نهاية الآية U+06DD أو تحذفها أو تحذف الأرقام التي تليها.\n"
    f"- مثال: في `{allah_example}` يأتي U+0651 (الشدة) قبل U+064E (الفتحة) في المصدر؛ "
    "ويعكس NFC هذا الترتيب. حافظ على ترتيب المصدر كما هو تمامًا.\n"
    "- حقل `search_text` (الرسم الإملائي) مخصّص للمطابقة فقط، ولا تنسخه بوصفه نصًا قرآنيًا.\n"
    "- يتضمن حقل `text` في JSON علامة نهاية الآية U+06DD ورقم الآية بعدها "
    "(بالأرقام العربية الهندية في النص المنشور).\n"
    "- كل سطر آية في `quran.txt` بصيغة `رقم السورة:رقم الآية [رقم الصفحة] <النص>`، "
    "مثل `1:1 [1] <النص>`. احذف السابقة `رقم السورة:رقم الآية [رقم الصفحة] ` فقط قبل النسخ؛ "
    "ويظل النص بعد حذفها متضمنًا U+06DD ورقم الآية.\n"
    "- لا يظهر النص على نحو صحيح إلا بخط حفص لمجمع الملك فهد. راجع "
    "[ترخيص الخط](https://github.com/abofah506/-quran-uthmani-text/blob/main/fonts/LICENSE-KFGQPC.txt) "
    "و[إشعار الحقوق](https://github.com/abofah506/-quran-uthmani-text/blob/main/NOTICE.md).\n",
    encoding="utf-8",
)

print(
    f"{len(pages)} pages, {sum(len(p) for p in pages)} paragraphs, "
    f"{len(surahs)} surahs, {sum(len(s['ayahs']) for s in surahs)} ayahs"
)
largest_files = sorted(
    (path for path in OUT.rglob("*") if path.is_file()),
    key=lambda path: path.stat().st_size,
    reverse=True,
)[:5]
print("5 largest generated files:")
for path in largest_files:
    print(f"  {path.relative_to(OUT)}: {path.stat().st_size:,} bytes")
