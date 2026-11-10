#!/usr/bin/env python3
"""Verify per-surah outputs and byte-for-byte build reproducibility."""
import hashlib
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SOURCE = ROOT / "src" / "kfgqpc_hafs_v30.json"
FONT = ROOT / "fonts" / "KFGQPC-Hafs-V30.ttf"


def fail(message):
    raise SystemExit(f"Build verification failed: {message}")


class AyahParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ayahs = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "ayah" not in (attributes.get("class") or "").split():
            return
        if self.current is not None:
            fail("Nested ayah elements are not supported")
        self.current = (
            attributes.get("id"),
            attributes.get("data-surah"),
            attributes.get("data-ayah"),
            [],
        )

    def handle_data(self, data):
        if self.current is not None:
            self.current[3].append(data)

    def handle_endtag(self, tag):
        if tag == "span" and self.current is not None:
            identifier, surah, ayah, text = self.current
            self.ayahs.append((identifier, surah, ayah, "".join(text)))
            self.current = None


def generated_snapshot():
    paths = [ROOT / "CHECKSUMS.sha256"]
    paths.extend(path for path in SITE.rglob("*") if path.is_file())
    return {
        path.relative_to(ROOT).as_posix(): path.read_bytes()
        for path in paths
    }


def verify_reproducibility():
    before = generated_snapshot()
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        fail(f"Build could not be repeated:\n{result.stdout}{result.stderr}")
    after = generated_snapshot()
    if before != after:
        changed = sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )
        fail("Build output is not byte-for-byte reproducible: " + ", ".join(changed[:10]))


def verify_html(path, expected_ayahs=None):
    content = path.read_text(encoding="utf-8")
    for required in (
        '<html lang="ar" dir="rtl">',
        '<meta charset="utf-8">',
        '<meta name="viewport"',
        '<meta name="description"',
        '<link rel="canonical"',
        'type="application/ld+json"',
    ):
        if required not in content:
            fail(f"{path.relative_to(ROOT)} is missing {required}")
    if expected_ayahs is None:
        return
    parser = AyahParser()
    parser.feed(content)
    if len(parser.ayahs) != len(expected_ayahs):
        fail(
            f"{path.relative_to(ROOT)} has {len(parser.ayahs)} ayahs; "
            f"expected {len(expected_ayahs)}"
        )
    for actual, expected in zip(parser.ayahs, expected_ayahs):
        identifier, surah, ayah, text = actual
        expected_surah, expected_ayah, expected_text = expected
        if (
            identifier != f"ayah-{expected_surah}-{expected_ayah}"
            or surah != str(expected_surah)
            or ayah != str(expected_ayah)
            or text != expected_text
        ):
            fail(
                f"{path.relative_to(ROOT)} has changed markup or text at "
                f"{expected_surah}:{expected_ayah}"
            )


def verify_utf8_lf(path):
    content = path.read_bytes()
    if content.startswith(b"\xef\xbb\xbf"):
        fail(f"{path.relative_to(ROOT)} has a UTF-8 BOM")
    if b"\r" in content:
        fail(f"{path.relative_to(ROOT)} has non-LF line endings")
    content.decode("utf-8")


def verify_checksums():
    manifest_path = ROOT / "CHECKSUMS.sha256"
    manifest = manifest_path.read_text(encoding="utf-8")
    if (SITE / "CHECKSUMS.sha256").read_text(encoding="utf-8") != manifest:
        fail("site/CHECKSUMS.sha256 differs from CHECKSUMS.sha256")

    expected_paths = {
        SOURCE.relative_to(ROOT).as_posix(),
        FONT.relative_to(ROOT).as_posix(),
        "site/quran.json",
        "site/quran-search.json",
        "site/quran.txt",
    }
    expected_paths.update(
        path.relative_to(ROOT).as_posix()
        for path in (SITE / "data").rglob("*")
        if path.is_file()
    )
    actual_paths = set()
    for line in manifest.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            fail(f"Invalid checksum entry: {line}")
        digest, relative = match.groups()
        if relative in actual_paths:
            fail(f"Duplicate checksum entry: {relative}")
        actual_paths.add(relative)
        path = ROOT / relative
        if not path.is_file():
            fail(f"Checksum target is missing: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            fail(f"Checksum mismatch: {relative}")
    if actual_paths != expected_paths:
        fail("CHECKSUMS.sha256 does not cover exactly the source and generated data")


def readme_json_example(readme, heading):
    match = re.search(
        re.escape(heading) + r"\s*```json\s*(.*?)\s*```",
        readme,
        re.DOTALL,
    )
    if not match:
        fail(f"README.md is missing the {heading!r} JSON example")
    return json.loads(match.group(1))


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    quran = json.loads((SITE / "quran.json").read_text(encoding="utf-8"))
    if len(source) != 6236 or len(quran.get("surahs", [])) != 114:
        fail("Expected 114 surahs and 6,236 source ayahs")

    source_by_surah = {number: [] for number in range(1, 115)}
    for record in source:
        source_by_surah[record["sura_no"]].append(record)
    if sum(map(len, source_by_surah.values())) != 6236:
        fail("Source does not contain exactly 6,236 ayahs")

    index_path = SITE / "data" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, list) or len(index) != 114:
        fail("data/index.json must contain exactly 114 surahs")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if readme_json_example(readme, "The first index record is:") != index[0]:
        fail("README.md index example differs from data/index.json")
    first_surah_data = json.loads(
        (SITE / "data" / "surahs" / "001.json").read_text(encoding="utf-8")
    )
    expected_examples = [
        {
            "ayah": first_surah_data["ayahs"][number - 1]["ayah"],
            "key": first_surah_data["ayahs"][number - 1]["key"],
            "text": first_surah_data["ayahs"][number - 1]["text"],
        }
        for number in (1, 7)
    ]
    if readme_json_example(
        readme, "The following ayah records are copied from `data/surahs/001.json`:"
    ) != expected_examples:
        fail("README.md ayah examples differ from data/surahs/001.json")

    all_source_text = []
    all_generated_text = []
    expected_html = []
    for number, entry in enumerate(index, 1):
        source_ayahs = source_by_surah[number]
        if [row["aya_no"] for row in source_ayahs] != list(
            range(1, len(source_ayahs) + 1)
        ):
            fail(f"Source ayahs are missing or out of order in surah {number}")
        source_name = source_ayahs[0]["sura_name_ar"]
        if any(record["sura_name_ar"] != source_name for record in source_ayahs):
            fail(f"Source has inconsistent Arabic surah names for surah {number}")
        stem = f"{number:03}"
        if entry != {
            "surah": number,
            "name_ar": source_name,
            "ayah_count": len(source_ayahs),
            "file": f"surahs/{stem}.json",
        }:
            fail(f"data/index.json entry {number} is invalid")

        data_path = SITE / "data" / entry["file"]
        data = json.loads(data_path.read_text(encoding="utf-8"))
        expected_ayahs = [
            {
                "ayah": record["aya_no"],
                "key": f"{number}:{record['aya_no']}",
                "text": record["aya_text_unicode"],
            }
            for record in source_ayahs
        ]
        if data != {
            "surah": number,
            "name_ar": source_name,
            "ayahs": expected_ayahs,
        }:
            fail(f"{data_path.relative_to(ROOT)} differs from the KFGQPC source")
        generated_text = [ayah["text"] for ayah in data["ayahs"]]
        source_text = [record["aya_text_unicode"] for record in source_ayahs]
        if "\n".join(generated_text) != "\n".join(source_text):
            fail(f"Concatenated text mismatch in surah {number}")
        expected_html.extend(
            (number, row["aya_no"], row["aya_text_unicode"])
            for row in source_ayahs
        )
        page_path = SITE / "surah" / f"{stem}.html"
        verify_html(
            page_path,
            [
                (number, record["aya_no"], record["aya_text_unicode"])
                for record in source_ayahs
            ],
        )
        all_source_text.extend(source_text)
        all_generated_text.extend(generated_text)

    if len(list((SITE / "data" / "surahs").glob("*.json"))) != 114:
        fail("Expected exactly 114 agent-friendly per-surah JSON files")
    if len(list((SITE / "surah").glob("*.html"))) != 114:
        fail("Expected exactly 114 standalone per-surah HTML pages")
    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    required_sitemap_urls = {
        "https://abofahad506.github.io/-quran-uthmani-text/",
        "https://abofahad506.github.io/-quran-uthmani-text/quran.html",
        "https://abofahad506.github.io/-quran-uthmani-text/data/index.json",
    }
    for number in range(1, 115):
        stem = f"{number:03}"
        required_sitemap_urls.add(
            f"https://abofahad506.github.io/-quran-uthmani-text/surah/{stem}.html"
        )
    if not all(f"<loc>{url}</loc>" in sitemap for url in required_sitemap_urls):
        fail("sitemap.xml is missing a required site or per-surah URL")
    llms = (SITE / "llms.txt").read_text(encoding="utf-8")
    for url in (
        "https://abofahad506.github.io/-quran-uthmani-text/data/index.json",
        "https://abofahad506.github.io/-quran-uthmani-text/data/surahs/NNN.json",
        "https://abofahad506.github.io/-quran-uthmani-text/surah/NNN.html",
        "https://github.com/abofahad506/-quran-uthmani-text/blob/main/NOTICE.md",
        "https://abofahad506.github.io/-quran-uthmani-text/CHECKSUMS.sha256",
    ):
        if url not in llms:
            fail(f"llms.txt is missing {url}")
    if "Sitemap: https://abofahad506.github.io/-quran-uthmani-text/sitemap.xml" not in (
        SITE / "robots.txt"
    ).read_text(encoding="utf-8"):
        fail("robots.txt does not point to the generated sitemap")
    if "\n".join(all_generated_text) != "\n".join(all_source_text):
        fail("Concatenated Quran text differs from the source")
    verify_html(SITE / "quran.html", expected_html)
    verify_html(SITE / "index.html")

    for path in [index_path, *SITE.glob("*.json"), *SITE.glob("*.txt")]:
        verify_utf8_lf(path)
    for path in (SITE / "data").rglob("*"):
        if path.is_file():
            verify_utf8_lf(path)
    for path in (SITE / "surah").glob("*.html"):
        verify_utf8_lf(path)
    verify_checksums()
    verify_reproducibility()
    print(
        "Build verification passed: 114 surahs, 6,236 ayahs, exact source text, "
        "and byte-for-byte reproducibility."
    )


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        fail(str(error))
