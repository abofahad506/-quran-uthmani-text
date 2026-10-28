#!/usr/bin/env python3
"""Mutation tests for the generated-text integrity verifier."""
import importlib.util
import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "tools" / "verify.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("quran_integrity_verifier", VERIFY_PATH)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    return verifier


class VerifyMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        shutil.copytree(ROOT / "site", self.root / "site")
        for directory in ("src", "fonts", "tools"):
            (self.root / directory).mkdir()
        shutil.copy2(
            ROOT / "src" / "kfgqpc_hafs_v30.json",
            self.root / "src" / "kfgqpc_hafs_v30.json",
        )
        shutil.copy2(
            ROOT / "fonts" / "KFGQPC-Hafs-V30.ttf",
            self.root / "fonts" / "KFGQPC-Hafs-V30.ttf",
        )
        shutil.copy2(
            ROOT / "fonts" / "LICENSE-KFGQPC.txt",
            self.root / "fonts" / "LICENSE-KFGQPC.txt",
        )
        shutil.copy2(
            ROOT / "tools" / "allowed_codepoints.json",
            self.root / "tools" / "allowed_codepoints.json",
        )
        for filename in ("README.md", "NOTICE.md"):
            shutil.copy2(ROOT / filename, self.root / filename)

        self.verifier = load_verifier()
        self.verifier.ROOT = self.root
        self.verifier.SOURCE_PATH = self.root / "src" / "kfgqpc_hafs_v30.json"
        self.verifier.ALLOWLIST_PATH = self.root / "tools" / "allowed_codepoints.json"
        self.verifier.FONT_PATH = self.root / "fonts" / "KFGQPC-Hafs-V30.ttf"
        self.verifier.SITE = self.root / "site"
        self.verifier.SITE_FONT_PATH = (
            self.root / "site" / "fonts" / "KFGQPC-Hafs-V30.ttf"
        )
        self.verifier.URL_DOCUMENTS = tuple(
            self.root / path
            for path in (
                "site/llms.txt",
                "README.md",
                "NOTICE.md",
                "site/llms-full.txt",
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.verifier.main()

    def tearDown(self):
        self.temp_dir.cleanup()

    def assert_verifier_fails(self, expected_message):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                self.verifier.main()
        self.assertIn(expected_message, str(result.exception))

    def mutate_html_ayah(self, transform):
        html_path = self.root / "site" / "quran.html"
        original = html_path.read_text(encoding="utf-8")
        match = re.search(
            r'(<p id="s1-a1">.*?<span class="ayah">)(.*?)(</span>)',
            original,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "Could not locate ayah 1:1 in generated HTML")
        changed_ayah = transform(match.group(2))
        html_path.write_text(
            original[:match.start(2)] + changed_ayah + original[match.end(2):],
            encoding="utf-8",
        )
        return html_path, original

    def test_reordered_combining_marks_fail(self):
        def swap_marks(text):
            points = list(text)
            for index in range(len(points) - 1):
                if ord(points[index]) == 0x0651 and ord(points[index + 1]) == 0x064E:
                    points[index], points[index + 1] = points[index + 1], points[index]
                    return "".join(points)
            self.fail("Ayah 1:1 has no adjacent U+0651/U+064E sequence")

        path, original = self.mutate_html_ayah(swap_marks)
        try:
            self.assert_verifier_fails("differs at code point index")
        finally:
            path.write_text(original, encoding="utf-8")

    def test_inserted_bidi_control_fails(self):
        path, original = self.mutate_html_ayah(
            lambda text: text[:1] + "\u200f" + text[1:]
        )
        try:
            self.assert_verifier_fails("differs at code point index")
        finally:
            path.write_text(original, encoding="utf-8")

    def test_changed_overall_checksum_fails(self):
        checksum_path = self.root / "site" / "checksums.json"
        original = checksum_path.read_text(encoding="utf-8")
        checksums = json.loads(original)
        checksums["overall"] = "0" * 64
        checksum_path.write_text(
            json.dumps(checksums, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            self.assert_verifier_fails("checksums.json differs")
        finally:
            checksum_path.write_text(original, encoding="utf-8")

    def test_changed_font_byte_fails(self):
        font_path = self.root / "site" / "fonts" / "KFGQPC-Hafs-V30.ttf"
        original = font_path.read_bytes()
        altered = bytes([original[0] ^ 1]) + original[1:]
        font_path.write_bytes(altered)
        try:
            self.assert_verifier_fails("SHA-256 mismatch")
        finally:
            font_path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
