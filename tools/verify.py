#!/usr/bin/env python3
"""Verify generated Quran text against the KFGQPC source and font coverage."""
import hashlib
import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "src" / "kfgqpc_hafs_v30.json"
ALLOWLIST_PATH = ROOT / "tools" / "allowed_codepoints.json"
FONT_PATH = ROOT / "fonts" / "KFGQPC-Hafs-V30.ttf"
SITE = ROOT / "site"
URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
URL_DOCUMENTS = (
    ROOT / "site" / "llms.txt",
    ROOT / "README.md",
    ROOT / "NOTICE.md",
    ROOT / "site" / "llms-full.txt",
)


def fail(message):
    raise SystemExit(f"Integrity verification failed: {message}")


def codepoints(text):
    return [ord(character) for character in text]


def format_codepoints(points):
    return ", ".join(f"U+{point:04X}" for point in points) or "(empty)"


def compare_text(label, actual, expected):
    actual_points = codepoints(actual)
    expected_points = codepoints(expected)
    if actual_points == expected_points:
        return
    mismatch = next(
        (
            index
            for index, (left, right) in enumerate(zip(actual_points, expected_points))
            if left != right
        ),
        min(len(actual_points), len(expected_points)),
    )
    actual_point = actual_points[mismatch:mismatch + 1]
    expected_point = expected_points[mismatch:mismatch + 1]
    fail(
        f"{label} differs at code point index {mismatch}: "
        f"found {format_codepoints(actual_point)}, expected "
        f"{format_codepoints(expected_point)} "
        f"(found length {len(actual_points)}, expected {len(expected_points)})"
    )


def verify_rows(label, actual_rows, source_by_reference, allowlist, cmap):
    if len(actual_rows) != len(source_by_reference):
        fail(
            f"{label} has {len(actual_rows)} ayahs; "
            f"expected {len(source_by_reference)}"
        )
    expected_references = sorted(source_by_reference)
    actual_references = [(surah, ayah) for surah, ayah, _ in actual_rows]
    if actual_references != expected_references:
        fail(f"{label} ayah references are missing, duplicated, or out of order")
    seen = set()
    for surah_number, ayah_number, text in actual_rows:
        reference = (surah_number, ayah_number)
        if reference in seen:
            fail(f"{label} has duplicate ayah {surah_number}:{ayah_number}")
        seen.add(reference)
        source_record = source_by_reference.get(reference)
        if source_record is None:
            fail(f"{label} contains unknown ayah {surah_number}:{ayah_number}")
        expected = source_record["aya_text_unicode"]
        compare_text(f"{label} ayah {surah_number}:{ayah_number}", text, expected)
        for point in codepoints(text):
            if point not in allowlist:
                fail(
                    f"{label} ayah {surah_number}:{ayah_number} contains "
                    f"unapproved code point U+{point:04X}"
                )
            if point not in cmap:
                fail(
                    f"Font cmap is missing U+{point:04X} used by "
                    f"{label} ayah {surah_number}:{ayah_number}"
                )


def source_ordered_records(records):
    return sorted(records, key=lambda record: (record["sura_no"], record["aya_no"]))


def url_target(url):
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    if hostname == "github.com":
        if len(path_parts) < 2 or path_parts[:2] != [
            "abofahad506",
            "-quran-uthmani-text",
        ]:
            return None
        remaining = path_parts[2:]
        if not remaining:
            return ROOT
        if len(remaining) >= 3 and remaining[0] in ("blob", "tree", "raw"):
            remaining = remaining[2:]
        else:
            return None
        return ROOT.joinpath(*remaining)
    if hostname == "abofahad506.github.io":
        if not path_parts or path_parts[0] != "-quran-uthmani-text":
            return None
        remaining = path_parts[1:] or ["index.html"]
        return SITE.joinpath(*remaining), ROOT.joinpath(*remaining)
    return False


def verify_document_urls():
    legacy = "github.com/abofah506"
    for document in URL_DOCUMENTS:
        if not document.is_file():
            fail(f"URL check document is missing: {document.relative_to(ROOT)}")
        for match in URL_RE.finditer(document.read_text(encoding="utf-8")):
            url = match.group().rstrip(".,;:!?)]}،؛")
            if legacy in url.lower():
                fail(
                    f"{document.relative_to(ROOT)} contains a legacy GitHub URL: {url}"
                )
            target = url_target(url)
            if target is False:
                continue
            if target is None:
                fail(
                    f"{document.relative_to(ROOT)} contains a GitHub URL outside "
                    f"this repository: {url}"
                )
            targets = target if isinstance(target, tuple) else (target,)
            for candidate in targets:
                try:
                    candidate.resolve().relative_to(ROOT.resolve())
                except ValueError:
                    fail(f"URL escapes the repository path: {url}")
            if not any(candidate.exists() for candidate in targets):
                fail(
                    f"{document.relative_to(ROOT)} URL points to a missing path: "
                    f"{url} -> "
                    + " or ".join(str(candidate.relative_to(ROOT)) for candidate in targets)
                )


def main():
    verify_document_urls()
    records = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        fail("KFGQPC source must be a non-empty JSON array")
    ordered_records = source_ordered_records(records)
    source_by_reference = {}
    for record in ordered_records:
        reference = (record["sura_no"], record["aya_no"])
        if reference in source_by_reference:
            fail(f"KFGQPC source contains duplicate ayah {reference[0]}:{reference[1]}")
        source_by_reference[reference] = record

    allowlist_data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    if allowlist_data.get("source") != "src/kfgqpc_hafs_v30.json":
        fail(f"{ALLOWLIST_PATH.relative_to(ROOT)} has an unexpected source label")
    try:
        allowlist = {
            int(value.removeprefix("U+"), 16)
            for value in allowlist_data["codepoints"]
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        fail(f"{ALLOWLIST_PATH.relative_to(ROOT)} has invalid code point entries")
    if len(allowlist) != len(allowlist_data["codepoints"]):
        fail(f"{ALLOWLIST_PATH.relative_to(ROOT)} contains duplicate code points")
    source_codepoints = {
        point
        for record in ordered_records
        for point in codepoints(record["aya_text_unicode"])
    }
    new_source_points = sorted(source_codepoints - allowlist)
    if new_source_points:
        fail(
            "KFGQPC source has code points missing from "
            f"{ALLOWLIST_PATH.relative_to(ROOT)}: {format_codepoints(new_source_points)}"
        )

    font = TTFont(FONT_PATH, lazy=True)
    try:
        cmap = set(font.getBestCmap() or {})
    finally:
        font.close()

    quran = json.loads((SITE / "quran.json").read_text(encoding="utf-8"))
    quran_rows = [
        (surah["number"], ayah["number"], ayah["text"])
        for surah in quran["surahs"]
        for ayah in surah["ayahs"]
    ]
    verify_rows("site/quran.json", quran_rows, source_by_reference, allowlist, cmap)

    surah_json_paths = sorted((SITE / "data" / "surah").glob("*.json"))
    surah_text_paths = sorted((SITE / "data" / "surah").glob("*.txt"))
    if len(surah_json_paths) != 114 or len(surah_text_paths) != 114:
        fail(
            "Expected 114 per-surah JSON and TXT files; found "
            f"{len(surah_json_paths)} JSON and {len(surah_text_paths)} TXT"
        )

    verified_surah_texts = {}
    for surah_number in range(1, 115):
        stem = f"{surah_number:03}"
        json_path = SITE / "data" / "surah" / f"{stem}.json"
        text_path = SITE / "data" / "surah" / f"{stem}.txt"
        surah_json = json.loads(json_path.read_text(encoding="utf-8"))
        if surah_json.get("surah_number") != surah_number:
            fail(f"{json_path.relative_to(ROOT)} has the wrong surah_number")
        surah_rows = [
            (surah_number, ayah["number"], ayah["text"])
            for ayah in surah_json.get("ayahs", [])
        ]
        expected_records = [
            record for record in ordered_records if record["sura_no"] == surah_number
        ]
        surah_source_by_reference = {
            (record["sura_no"], record["aya_no"]): record
            for record in expected_records
        }
        verify_rows(
            str(json_path.relative_to(ROOT)),
            surah_rows,
            surah_source_by_reference,
            allowlist,
            cmap,
        )
        expected_lines = [
            f'{surah_number}:{record["aya_no"]} '
            f'[{record["page"]}] {record["aya_text_unicode"]}'
            for record in expected_records
        ]
        actual_lines = text_path.read_text(encoding="utf-8").splitlines()
        if len(actual_lines) != len(expected_lines):
            fail(
                f"{text_path.relative_to(ROOT)} has {len(actual_lines)} lines; "
                f"expected {len(expected_lines)} ayah lines"
            )
        text_rows = []
        for line_number, (line, expected_line) in enumerate(
            zip(actual_lines, expected_lines), 1
        ):
            match = re.fullmatch(r"(\d+):(\d+) \[([0-9,]+)\] (.+)", line)
            expected_match = re.fullmatch(
                r"(\d+):(\d+) \[([0-9,]+)\] (.+)", expected_line
            )
            if not match or not expected_match:
                fail(f"{text_path.relative_to(ROOT)} line {line_number} has invalid format")
            if match.group(1, 2, 3) != expected_match.group(1, 2, 3):
                fail(
                    f"{text_path.relative_to(ROOT)} line {line_number} has "
                    "a reference or page prefix mismatch"
                )
            text_rows.append(
                (int(match.group(1)), int(match.group(2)), match.group(4))
            )
        verify_rows(
            str(text_path.relative_to(ROOT)),
            text_rows,
            surah_source_by_reference,
            allowlist,
            cmap,
        )
        verified_surah_texts[surah_number] = [
            record["aya_text_unicode"] for record in expected_records
        ]

    quran_text = (SITE / "quran.txt").read_text(encoding="utf-8")
    plain_text_rows = []
    for line in quran_text.splitlines():
        match = re.fullmatch(r"(\d+):(\d+) \[([0-9,]+)\] (.+)", line)
        if match:
            plain_text_rows.append(
                (int(match.group(1)), int(match.group(2)), match.group(4))
            )
    verify_rows(
        "site/quran.txt",
        plain_text_rows,
        source_by_reference,
        allowlist,
        cmap,
    )

    html_content = (SITE / "quran.html").read_text(encoding="utf-8")
    html_rows = [
        (int(surah), int(ayah), unescape(text))
        for surah, ayah, text in re.findall(
            r'<p id="s(\d+)-a(\d+)">.*?<span class="ayah">(.*?)</span>',
            html_content,
            re.DOTALL,
        )
    ]
    verify_rows(
        "site/quran.html",
        html_rows,
        source_by_reference,
        allowlist,
        cmap,
    )

    surah_hashes = {
        f"{surah_number:03}": hashlib.sha256(
            "\n".join(texts).encode("utf-8")
        ).hexdigest()
        for surah_number, texts in verified_surah_texts.items()
    }
    overall_text = "\n".join(
        text
        for surah_number in range(1, 115)
        for text in verified_surah_texts[surah_number]
    )
    checksums = {
        "algorithm": "SHA-256",
        "per_surah": surah_hashes,
        "overall": hashlib.sha256(overall_text.encode("utf-8")).hexdigest(),
    }
    (SITE / "checksums.json").write_text(
        json.dumps(checksums, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Integrity verification passed: "
        f"{len(source_by_reference):,} ayahs, "
        f"{len(source_codepoints)} allowed code points, font cmap coverage verified."
    )


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        fail(str(error))
