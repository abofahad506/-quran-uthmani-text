# Third-party materials (NOT covered by the MIT license)

The Quranic text, KFGQPC font, and surah banner below are third-party materials
and are not covered by this repository's MIT license. The Amiri font has its own
license, included alongside it.
Official KFGQPC source: https://fonts.qurancomplex.gov.sa/

| Item | Files | Terms |
|---|---|---|
| Quranic text (Hafs, Uthmani script and emlaey spelling) | `src/Mushaf-Hafs-Uthmanic.docx`, `src/kfgqpc_hafs_v30.json`, generated `site/index.html`, `site/quran.html`, `site/quran.json`, `site/quran-search.json`, `site/quran.txt` | KFGQPC's terms. The Unicode ayah text and emlaey search text are taken from the KFGQPC Hafs v3.0 data. The printed-page layout is generated from the source DOCX. |
| Font "KFGQPC HAFS Uthmanic Script" | `fonts/KFGQPC-Hafs-V30.ttf` | KFGQPC End-User License Agreement (see below) |
| Font "Amiri" | `fonts/Amiri-Regular.ttf` | SIL Open Font License 1.1 (`fonts/OFL-Amiri.txt`). Amiri is a Naskh-style Arabic typeface, not a Uthmanic-script font. |
| Surah banner image | `site/assets/surah-banner.png` | Extracted unchanged from the KFGQPC docx |

## KFGQPC font terms
Full text: `fonts/LICENSE-KFGQPC.txt` (copied verbatim from the license embedded in the
font, Version 3.0). In short: free to use, copy and distribute; may not be sold,
modified, altered, translated, reverse-engineered or reproduced; no warranty.
The font is served byte-for-byte as received (no conversion, no subsetting).

## Amiri font terms
The Amiri font is redistributed unmodified under the SIL Open Font License 1.1.
See `fonts/OFL-Amiri.txt` for the full license text. The font metadata identifies
the copyright holder as The Amiri Project Authors. Source: [Amiri on Google
Fonts](https://fonts.google.com/specimen/Amiri).

## Rules for this repository
1. Never edit the text of the Quran, only its layout.
2. Do not sell this repository's Quran text or the KFGQPC font.
3. Do not modify, convert or subset the KFGQPC font; keep it exactly as received.
4. For printing or critical publication, verify against the official printed mushaf.
