#!/usr/bin/env python3
"""Verify generated Quran text against the KFGQPC source and font coverage."""
import glob
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
SITE_FONT_PATH = SITE / "fonts" / "KFGQPC-Hafs-V30.ttf"
EXPECTED_FONT_SHA256 = "c9dd7e71a454565b13d89e5e6f2663a918acb0a20a23eea31eccb32a3aeec47a"
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


def checksums_for_records(records):
    per_surah = {}
    all_text = []
    for surah_number in range(1, 115):
        texts = [
            record["aya_text_unicode"]
            for record in records
            if record["sura_no"] == surah_number
        ]
        if not texts:
            fail(f"KFGQPC source is missing surah {surah_number}")
        per_surah[f"{surah_number:03}"] = hashlib.sha256(
            "\n".join(texts).encode("utf-8")
        ).hexdigest()
        all_text.extend(texts)
    return {
        "algorithm": "SHA-256",
        "per_surah": per_surah,
        "overall": hashlib.sha256("\n".join(all_text).encode("utf-8")).hexdigest(),
    }


def verify_font_hashes():
    for font_path in (FONT_PATH, SITE_FONT_PATH):
        digest = hashlib.sha256(font_path.read_bytes()).hexdigest()
        if digest != EXPECTED_FONT_SHA256:
            fail(
                f"{font_path.relative_to(ROOT)} SHA-256 mismatch: "
                f"found {digest}, expected {EXPECTED_FONT_SHA256}"
            )


def expand_target(base, path_parts):
    pattern_parts = [
        part.replace("NNN", "[0-9][0-9][0-9]")
        for part in path_parts
    ]
    pattern = base.joinpath(*pattern_parts)
    if "NNN" not in "/".join(path_parts):
        return [pattern]
    return [Path(path) for path in sorted(glob.glob(str(pattern)))]


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
        return expand_target(ROOT, remaining)
    if hostname == "abofahad506.github.io":
        if not path_parts or path_parts[0] != "-quran-uthmani-text":
            return None
        remaining = path_parts[1:] or ["index.html"]
        return [
            *expand_target(SITE, remaining),
            *expand_target(ROOT, remaining),
        ]
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
            targets = target if isinstance(target, list) else [target]
            if not targets:
                fail(
                    f"{document.relative_to(ROOT)} URL pattern has no matching files: {url}"
                )
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

    verify_font_hashes()
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

    expected_checksums = checksums_for_records(ordered_records)
    actual_checksums = json.loads(
        (SITE / "checksums.json").read_text(encoding="utf-8")
    )
    if actual_checksums != expected_checksums:
        fail("site/checksums.json differs from SHA-256 checksums recomputed from KFGQPC source")
    verify_document_urls()
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
