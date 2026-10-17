#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты сканирования секретов (этап подготовки; офлайн, без сети).

Запуск: python3 lab/autonomy/k0/code/tests/test_secret_scan.py -v
"""
from __future__ import annotations

import base64
import binascii
import sys
import tempfile
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
sys.path.insert(0, str(CODE_DIR))

from secret_scan import (  # noqa: E402
    MIN_SECRET_LEN, scan_bytes, scan_exceptions, scan_file, scan_text,
    scan_tree, secret_forms,
)

SECRET = "K0SeKret/+=42ü"


class TestForms(unittest.TestCase):

    def test_forms_values(self):
        f = secret_forms(SECRET)
        self.assertEqual(f["exact"], SECRET)
        self.assertEqual(f["hex"], binascii.hexlify(SECRET.encode("utf-8")).decode())
        self.assertEqual(f["b64"], base64.b64encode(SECRET.encode("utf-8")).decode())
        expected_b64url = base64.urlsafe_b64encode(
            SECRET.encode("utf-8")).decode().rstrip("=")
        self.assertIn(expected_b64url, {v.rstrip("=") for v in f.values()})
        self.assertIn("url", f)
        self.assertIn("lower", f)

    def test_short_secret_rejected(self):
        for bad in ("", "a", "ab", "abc"):
            with self.assertRaises(ValueError):
                secret_forms(bad)
        self.assertEqual(MIN_SECRET_LEN, 4)


class TestScanText(unittest.TestCase):

    def test_hits(self):
        f = secret_forms(SECRET)
        self.assertIn("exact", scan_text(f"префикс {SECRET} суффикс", SECRET))
        self.assertIn("hex", scan_text(f"x{f['hex']}y", SECRET))
        self.assertIn("b64", scan_text(f["b64"], SECRET))

    def test_case_insensitive_hex(self):
        f = secret_forms(SECRET)
        self.assertIn("hex", scan_text(f["hex"].upper(), SECRET))

    def test_clean(self):
        self.assertEqual(scan_text("никаких секретов тут нет", SECRET), [])

    def test_bytes_non_utf8(self):
        data = b"\xff\xfe" + SECRET.encode("utf-8")
        self.assertIn("exact", scan_bytes(data, SECRET))


class TestScanTree(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tree(self):
        (self.base / "a.txt").write_text(f"leak: {SECRET}", encoding="utf-8")
        (self.base / "sub").mkdir()
        (self.base / "sub" / "b.bin").write_bytes(
            secret_forms(SECRET)["hex"].encode("ascii"))
        (self.base / "c.txt").write_text("чисто", encoding="utf-8")
        found = scan_tree(self.base, SECRET)
        names = {Path(f["path"]).name for f in found}
        self.assertEqual(names, {"a.txt", "b.bin"})

    def test_single_file_clean(self):
        p = self.base / "clean.txt"
        p.write_text("нет секрета", encoding="utf-8")
        self.assertEqual(scan_file(p, SECRET), [])


class TestScanExceptions(unittest.TestCase):

    def test_exceptions(self):
        excs = [ValueError(f"boom {SECRET}"), RuntimeError("чисто")]
        found = scan_exceptions(excs, SECRET)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["exception"], "ValueError")
        self.assertIn("exact", found[0]["forms"])

    def test_clean(self):
        self.assertEqual(scan_exceptions([ValueError("ok"), KeyError("x")], SECRET), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
