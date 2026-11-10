#!/usr/bin/env python3
"""Build per-surah JSON and HTML from the KFGQPC source records."""
import json
from html import escape
from pathlib import Path

SITE_URL = "https://abofahad506.github.io/-quran-uthmani-text"
RIGHTS_NOTE = (
    "Quranic text rights belong to the King Fahd Glorious Quran Printing "
    "Complex (KFGQPC); see the repository NOTICE.md. The text is not covered "
    "by the repository's MIT license."
)
NOTICE_URL = (
    "https://github.com/abofahad506/-quran-uthmani-text/blob/main/NOTICE.md"
)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(text)


def json_ld(name):
    value = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": name,
            "inLanguage": "ar",
            "publisher": {
                "@type": "Organization",
                "name": "King Fahd Glorious Quran Printing Complex (KFGQPC)",
            },
            "license": RIGHTS_NOTE,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return value.replace("<", "\\u003c")


def render_surah_page(surah, source_ayahs):
    number = surah["number"]
    stem = f"{number:03}"
    name = surah["name"]
    title = f"{name} — القرآن الكريم برواية حفص"
    description = f"النص القرآني — {name}، برواية حفص والرسم العثماني."
    lines = [
        '<!doctype html>',
        '<html lang="ar" dir="rtl">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="description" content="{escape(description, quote=True)}">',
        '<meta name="robots" content="index,follow">',
        f'<link rel="canonical" href="{SITE_URL}/surah/{stem}.html">',
        f'<title>{escape(title)}</title>',
        '<style>',
        'body{max-width:52rem;margin:2rem auto;padding:0 1rem;color:#222;font-family:serif;line-height:1.9}',
        '@font-face{font-family:"KFGQPC Hafs V3";src:url("../fonts/KFGQPC-Hafs-V30.ttf") format("truetype")}',
        'nav,footer{font:1rem sans-serif}nav{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}',
        '.ayah{font-family:"KFGQPC Hafs V3",serif;font-size:1.35rem}.reference{font:1rem sans-serif;white-space:nowrap}',
        '</style>',
        '<script type="application/ld+json">',
        json_ld(title),
        '</script>',
        '</head>',
        '<body>',
        '<header>',
        f'<h1>{escape(name)}</h1>',
        '<nav aria-label="التنقل بين السور">',
    ]
    previous_number = number - 1
    next_number = number + 1
    if previous_number:
        lines.append(
            f'<a rel="prev" href="{previous_number:03}.html">'
            f'السورة السابقة ({previous_number})</a>'
        )
    else:
        lines.append('<span></span>')
    lines.append('<a href="../quran.html">فهرس السور والآيات</a>')
    if next_number <= 114:
        lines.append(
            f'<a rel="next" href="{next_number:03}.html">'
            f'السورة التالية ({next_number})</a>'
        )
    else:
        lines.append('<a href="../data/index.json">فهرس JSON للسور</a>')
    lines.extend([
        '</nav>',
        f'<p><a href="../data/surahs/{stem}.json">تنزيل بيانات السورة بصيغة JSON</a>'
        ' · <a href="../data/index.json">فهرس السور بصيغة JSON</a></p>',
        '</header>',
        '<main>',
    ])
    for ayah in source_ayahs:
        ayah_number = ayah["aya_no"]
        verse_id = f"ayah-{number}-{ayah_number}"
        lines.append(
            f'<p><span class="reference">{number}:{ayah_number}</span> '
            f'<span class="ayah" id="{verse_id}" data-surah="{number}" '
            f'data-ayah="{ayah_number}">{escape(ayah["aya_text_unicode"])}</span></p>'
        )
    lines.extend([
        '</main>',
        '<footer>',
        f'<p>{escape(RIGHTS_NOTE)} '
        f'<a href="{NOTICE_URL}">NOTICE.md</a></p>',
        '<p><a href="../index.html">العودة إلى المصحف المرئي</a></p>',
        '</footer>',
        '</body>',
        '</html>',
        '',
    ])
    return "\n".join(lines)


def build_surah_outputs(records, output_dir):
    if len(records) != 6236:
        raise ValueError(f"Expected 6,236 source ayahs, found {len(records)}")

    records_by_surah = {number: [] for number in range(1, 115)}
    for record in records:
        number = record["sura_no"]
        if number not in records_by_surah:
            raise ValueError(f"Invalid source surah number: {number}")
        records_by_surah[number].append(record)

    index = []
    data_dir = Path(output_dir) / "data"
    for number in range(1, 115):
        source_ayahs = records_by_surah[number]
        if not source_ayahs:
            raise ValueError(f"Source is missing surah {number}")
        name = source_ayahs[0]["sura_name_ar"]
        if not name or any(ayah["sura_name_ar"] != name for ayah in source_ayahs):
            raise ValueError(f"Inconsistent Arabic surah name in surah {number}")
        if [ayah["aya_no"] for ayah in source_ayahs] != list(
            range(1, len(source_ayahs) + 1)
        ):
            raise ValueError(f"Source ayahs are missing or out of order in surah {number}")

        stem = f"{number:03}"
        surah = {"number": number, "name": name}
        json_path = f"surahs/{stem}.json"
        index.append({
            "surah": number,
            "name_ar": name,
            "ayah_count": len(source_ayahs),
            "file": json_path,
        })
        surah_data = {
            "surah": number,
            "name_ar": name,
            "ayahs": [
                {
                    "ayah": ayah["aya_no"],
                    "key": f"{number}:{ayah['aya_no']}",
                    "text": ayah["aya_text_unicode"],
                }
                for ayah in source_ayahs
            ],
        }
        write_text(
            data_dir / json_path,
            json.dumps(surah_data, ensure_ascii=False, indent=2) + "\n",
        )
        write_text(
            Path(output_dir) / "surah" / f"{stem}.html",
            render_surah_page(surah, source_ayahs),
        )

    write_text(
        data_dir / "index.json",
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
    )


def main():
    root = Path(__file__).resolve().parents[1]
    source = json.loads(
        (root / "src" / "kfgqpc_hafs_v30.json").read_text(encoding="utf-8")
    )
    build_surah_outputs(source, root / "site")


if __name__ == "__main__":
    main()
