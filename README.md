# -quran-uthmani-text

The Complete Holy Quran text in Uthmani script, sourced from the King Fahd Complex for the Printing of the Holy Quran.

[Open the Mushaf viewer](https://abofahad506.github.io/-quran-uthmani-text/) ·
[Browse linked surahs and ayahs](https://abofahad506.github.io/-quran-uthmani-text/quran.html) ·
[Download JSON](https://abofahad506.github.io/-quran-uthmani-text/quran.json) ·
[Download search index](https://abofahad506.github.io/-quran-uthmani-text/quran-search.json) ·
[Download plain text](https://abofahad506.github.io/-quran-uthmani-text/quran.txt)

## Machine-readable text

The Pages build generates UTF-8 `quran.json`, `quran-search.json`, and `quran.txt`
from the KFGQPC Hafs v3.0 data and the source DOCX. The structured JSON organizes
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

Example JSON shape:

```json
{
  "attribution": "King Fahd Glorious Quran Printing Complex (KFGQPC), Madinah, Saudi Arabia",
  "edition": "Hafs narration, Uthmani script, KFGQPC version 3.0",
  "source": "src/Mushaf-Hafs-Uthmanic.docx",
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

The plain-text file uses one ayah per line in the format
`surah:ayah [printed page(s)] <source text>`. The Quranic text is from the
**King Fahd Glorious Quran Printing Complex**; its rights and terms are not
covered by this repository's MIT license. See [`NOTICE.md`](NOTICE.md).
Verify against the official printed mushaf for critical use.
[Open the Quran Pages website](https://abofahad506.github.io/-quran-uthmani-text/)

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

* [King Fahd Complex for the Printing of the Holy Quran]
* https://fonts.qurancomplex.gov.sa/ten-readings
