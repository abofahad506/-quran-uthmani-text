# -quran-uthmani-text

The visual mushaf edition is the reference edition. The linked text edition is a companion for browsing and search, using King Fahd Complex (KFGQPC) Hafs v3.0 text data.

## Quick links

- Live mushaf: [open the GitHub Pages site](https://abofahad506.github.io/-quran-uthmani-text/)
- Text edition: [browse linked surahs and ayahs](https://abofahad506.github.io/-quran-uthmani-text/quran.html)
- Per-surah JSON index: [data/index.json](https://abofahad506.github.io/-quran-uthmani-text/data/index.json)
- Plain-text download: [quran.txt](https://abofahad506.github.io/-quran-uthmani-text/quran.txt)
- Source and provenance: [`NOTICE.md`](NOTICE.md)
- License and rights: [repository code and third-party material](#license-and-rights)
- Checksums: [`CHECKSUMS.sha256`](CHECKSUMS.sha256)

## Companion text edition

The visual edition at the [Mushaf viewer](https://abofahad506.github.io/-quran-uthmani-text/)
is authoritative for reference. The linked text edition and its UTF-8 `quran.json`,
`quran-search.json`, and `quran.txt` files are companion resources for browsing,
search, and programmatic use; they do not replace the visual mushaf. The text is
from the KFGQPC Hafs v3.0 dataset (`src/kfgqpc_hafs_v30.json`), while printed-page
layout comes from `src/Mushaf-Hafs-Uthmanic.docx`.

The Pages build validates all 6,236 generated JSON, HTML, and plain-text ayahs against the matching KFGQPC Unicode source records; it also validates the search index against the source emlaey records and checks printed-page references against the visual DOCX layout. Any mismatch fails the build before it can be published. The structured JSON organizes
ayahs by surah and includes the Uthmani text, the original emlaey search text,
juz, printed page and line references, and stable URLs. The Unicode ayah text is
preserved as supplied by KFGQPC without normalization. Search uses the separate,
compact `quran-search.json` index and loads it only when a search is submitted.

The linked text edition provides stable fragments for each surah and ayah. For
example, [Al-Baqarah](https://abofahad506.github.io/-quran-uthmani-text/quran.html#s2)
and [ayah 255](https://abofahad506.github.io/-quran-uthmani-text/quran.html#s2-a255)
can be linked directly. Each ayah is displayed with its `surah:ayah` reference
before the source text, so copying a passage retains its citation. The page also
supports Arabic text search (matching ignores diacritics) and copying one ayah
or a continuous ayah range with citations. Search uses the KFGQPC
`aya_text_emlaey` field alongside the displayed Uthmani text, so common modern
spellings can find their Uthmani-rendered ayahs. Search normalization is applied
only to matching, never to the source text shown or copied. The same relative
URLs are included in the JSON `url` fields.

## Repository layout

- `src/kfgqpc_hafs_v30.json`: source Uthmani and emlaey ayah records from KFGQPC.
- `src/Mushaf-Hafs-Uthmanic.docx`: source visual mushaf layout.
- `tools/build.py`: builds the visual mushaf, linked text edition, and legacy downloads.
- `tools/build_surahs.py`: builds the agent-friendly per-surah JSON and HTML pages.
- `tools/verify.py` and `tools/verify_build.py`: verify source fidelity, generated data, and reproducibility.
- `site/`: GitHub Pages assets; full page and data outputs are generated during the build.
- `fonts/`: original KFGQPC font and its license.
- `NOTICE.md` and `LICENSE`: third-party rights notice and repository code license.

## Data format

The per-surah index is a JSON array with one record per surah. Its `file` path is
relative to `data/index.json`. Each file contains a `surah` number, Arabic name,
and ordered `ayahs`; each ayah has its number, `surah:ayah` key, and verbatim
source text.

The first index record is:

```json
{
  "surah": 1,
  "name_ar": "الفَاتِحَةِ",
  "ayah_count": 7,
  "file": "surahs/001.json"
}
```

The following ayah records are copied from `data/surahs/001.json`:

```json
[
  {
    "ayah": 1,
    "key": "1:1",
    "text": "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ ۝١"
  },
  {
    "ayah": 7,
    "key": "1:7",
    "text": "صِرَٰطَ ٱلَّذِينَ أَنۡعَمۡتَ عَلَيۡهِمۡ غَيۡرِ ٱلۡمَغۡضُوبِ عَلَيۡهِمۡ وَلَا ٱلضَّآلِّينَ ۝٧"
  }
]
```

For compatibility, the existing [`quran.json`](https://abofahad506.github.io/-quran-uthmani-text/quran.json)
and `data/surah/NNN.json` endpoints remain available. The new
`data/surahs/NNN.json` files use the smaller schema above and include no
search-normalized text.

## Usage examples

Fetch one surah and select ayah 7 in JavaScript:

```js
const base = "https://abofahad506.github.io/-quran-uthmani-text/";
const index = await fetch(new URL("data/index.json", base))
  .then(response => response.json());
const surah = index.find(item => item.surah === 1);
const data = await fetch(new URL(
  surah.file,
  new URL("data/", base)
)).then(response => response.json());
const ayah = data.ayahs.find(item => item.key === "1:7");
console.log(ayah.text);
```

The same lookup in Python:

```python
import json
from urllib.request import urlopen

base = "https://abofahad506.github.io/-quran-uthmani-text/"
with urlopen(base + "data/index.json") as response:
    index = json.load(response)
surah = next(item for item in index if item["surah"] == 1)
with urlopen(base + "data/" + surah["file"]) as response:
    data = json.load(response)
ayah = next(item for item in data["ayahs"] if item["key"] == "1:7")
print(ayah["text"])
```

## Rebuilding the data

With Python 3.12 and the repository dependencies available, run the same
generation and checks used by GitHub Actions:

```sh
mkdir -p site/fonts
cp fonts/KFGQPC-Hafs-V30.ttf fonts/LICENSE-KFGQPC.txt site/fonts/
python tools/build.py
python tools/verify_build.py
python -m pip install fonttools
python tools/verify.py
python tools/test_verify.py
```

`tools/build.py` regenerates the visual and linked editions, per-surah JSON,
plain-text and HTML files, discovery files, and `CHECKSUMS.sha256`. The generated
site is published by the Pages workflow; do not edit its output by hand.
`python tools/build_surahs.py` regenerates only the agent-friendly per-surah JSON
and HTML; run the full build afterward to refresh the site indexes and checksums.

## Versioning

Current source text version: **KFGQPC Hafs v3.0**. Generated surah files are
derived from `src/kfgqpc_hafs_v30.json`; the visual mushaf remains the reference.

### Existing complete JSON shape

The legacy [`quran.json`](https://abofahad506.github.io/-quran-uthmani-text/quran.json)
keeps its existing extended schema:

```json
{
  "attribution": "King Fahd Glorious Quran Printing Complex (KFGQPC), Madinah, Saudi Arabia",
  "edition": "Hafs narration, Uthmani script, KFGQPC version 3.0",
  "source": "src/Mushaf-Hafs-Uthmanic.docx",
  "text_source": "src/kfgqpc_hafs_v30.json",
  "text_status": "Companion text edition; the visual mushaf edition is the reference.",
  "search_source": "KFGQPC Hafs v3.0 data, aya_text_emlaey field",
  "surahs": [
    {
      "number": 1,
      "name": "<source surah title>",
      "ayahs": [
        {
          "number": 1,
          "pages": [1],
          "lines": [2, 2],
          "juz": 1,
          "text": "<KFGQPC Uthmani ayah text>",
          "search_text": "<KFGQPC emlaey spelling>",
          "url": "quran.html#s1-a1"
        }
      ]
    }
  ]
}
```

## Copying the text

- Copy `quran.json`'s `text` field exactly as published. Never normalize it (NFC, NFD, NFKC, NFKD), or strip, add, or reorder combining marks; preserve U+06DD and its following ayah digits. In the example word, source order is U+0651 (shadda) then U+064E (fatha); NFC reverses it.
- `search_text` is for matching only, never for copying as Quranic text. The JSON `text` field includes U+06DD and the Arabic-Indic ayah number.
- Each `quran.txt` ayah line is `surah:ayah [page(s)] <text>`; strip exactly the `surah:ayah [page(s)] ` prefix (for example, `1:1 [1] `) before copying.
- Correct rendering requires the [KFGQPC Hafs font](fonts/KFGQPC-Hafs-V30.ttf); see its [license](fonts/LICENSE-KFGQPC.txt) and [`NOTICE.md`](NOTICE.md).

The plain-text file uses one ayah per line in the format
`surah:ayah [printed page(s)] <source text>`. The Quranic text is from the
**King Fahd Glorious Quran Printing Complex**; its rights and terms are not
covered by this repository's MIT license. See [`NOTICE.md`](NOTICE.md).
Verify against the official printed mushaf for critical use.
[Open the Quran Pages website](https://abofahad506.github.io/-quran-uthmani-text/)

## Rendering with the font

The embedded font family name is `KFGQPC Hafs V3`. Link to or download the original,
unmodified font file; do not convert or subset it. Its license forbids modification.
See [`fonts/LICENSE-KFGQPC.txt`](fonts/LICENSE-KFGQPC.txt) and [`NOTICE.md`](NOTICE.md).
The [one-ayah demo](https://abofahad506.github.io/-quran-uthmani-text/example.html)
uses the KFGQPC font from its absolute URL.

```css
@font-face {
  font-family: "KFGQPC Hafs V3";
  src: url("https://abofahad506.github.io/-quran-uthmani-text/fonts/KFGQPC-Hafs-V30.ttf") format("truetype");
}
.quran { font-family: "KFGQPC Hafs V3", serif; }
```

```html
<div class="quran" lang="ar" dir="rtl">[Insert source ayah text unchanged]</div>
```

---

## 📜 Disclaimer & Attribution

### 📌 Attribution

The Quranic text provided in this repository is in Uthmani script and sourced from the official editions of the **King Fahd Complex for the Printing of the Holy Quran** in Madinah. All rights to the text, its verification, and original typography belong to the Complex.

### ⚠️ Disclaimer

* This repository is created solely for technical and educational purposes (helping developers, researchers, and creators build digital tools and applications).
* I do not claim ownership of the Holy Quran text, nor is this repository intended for any commercial profit.
* Users are advised to verify and double-check with official sources when using the text for physical printing or critical publications.

---

### 📄 Licensing

* The Quranic text, the KFGQPC Hafs font, and the surah banner image belong to the Complex and are **not** covered by the MIT license. See [`NOTICE.md`](NOTICE.md) and [`fonts/LICENSE-KFGQPC.txt`](fonts/LICENSE-KFGQPC.txt).
* The MIT license applies only to the code I wrote (`tools/`, `site/style.css`, and the GitHub Actions workflow).
* The font is included unmodified, exactly as published by the Complex.

---

## License and rights

**Proposed clarification — needs-owner-review:** the MIT license in `LICENSE`
covers repository code and tooling only. The Quran text and KFGQPC font are
subject to KFGQPC rights and terms, are not covered by MIT, and are described in
[`NOTICE.md`](NOTICE.md) and [`fonts/LICENSE-KFGQPC.txt`](fonts/LICENSE-KFGQPC.txt).

The official [King Fahd Glorious Quran Printing Complex website](https://qurancomplex.gov.sa/)
provides further source information.
