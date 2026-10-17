# -*- coding: utf-8 -*-
"""Тесты preflight запускного пути (code/run_first.py) — v37-A, доп. №6.

Проверяется, что ДО первого обращения к модели запускной путь блокируется:
T1 STOP-файл; T2 каталог запуска существует; T3 хэш не совпадает;
T3b обязательный файл отсутствует; T4 чужой digest модели; T4b ошибка
проверки модели; T4c модель без digest; T5 всё в порядке → пустой список;
T6 статическая целостность снимка (обязательные файлы, утверждённый MODEL_PIN,
хэши совпадают с файлами).
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

K0_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(K0_DIR / "code"))

import run_first  # noqa: E402

PIN = run_first.MODEL_PIN


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.run_dir = self.tmp / "runs" / "run_x"
        self.stop = self.tmp / "STOP"

    def tearDown(self):
        self._tmp.cleanup()

    def test_t1_stop_file_blocks(self):
        self.stop.write_text("stop", encoding="utf-8")
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop,
                                    {"a.py": "0" * 64},
                                    lambda: PIN + "x")
        self.assertTrue(any(p.startswith("STOP") for p in probs))

    def test_t2_run_dir_exists_blocks(self):
        self.run_dir.mkdir(parents=True)
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop, {},
                                    lambda: PIN + "x")
        self.assertTrue(any(p.startswith("run_dir_exists") for p in probs))

    def test_t3_sha_mismatch_blocks(self):
        (self.tmp / "a.py").write_bytes(b"x")
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop,
                                    {"a.py": sha_bytes(b"y")},
                                    lambda: PIN + "x")
        self.assertTrue(any(p.startswith("sha_mismatch: a.py") for p in probs))

    def test_t3b_missing_file_blocks(self):
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop,
                                    {"b.py": "0" * 64},
                                    lambda: PIN + "x")
        self.assertTrue(any(p.startswith("missing: b.py") for p in probs))

    def test_t4_model_identity_blocks(self):
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop, {},
                                    lambda: "deadbeef" * 8)
        self.assertTrue(any(p.startswith("model_identity") for p in probs))

    def test_t4b_model_check_error_blocks(self):
        def boom():
            raise RuntimeError("connection refused")
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop, {}, boom)
        self.assertTrue(any(p.startswith("model_check_error") for p in probs))

    def test_t4c_model_without_digest_blocks(self):
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop, {},
                                    lambda: None)
        self.assertTrue(any(p.startswith("model_unavailable") for p in probs))

    def test_t5_all_ok_no_problems(self):
        (self.tmp / "a.py").write_bytes(b"x")
        probs = run_first.preflight(self.tmp, self.run_dir, self.stop,
                                    {"a.py": sha_bytes(b"x")},
                                    lambda: PIN + "0123456789")
        self.assertEqual(probs, [])

    def test_t6_snapshot_static_integrity(self):
        required = (
            "code/prompts.py", "code/session.py", "code/journal.py",
            "code/parser.py", "code/calls.py", "code/channel.py",
            "code/world.py", "code/auditor.py", "K0_PROTOCOL_v37.md",
        )
        self.assertEqual(run_first.MODEL_PIN, "e8bb5f9335d7")
        for rel in required:
            self.assertIn(rel, run_first.SNAPSHOT)
        self.assertEqual(len(run_first.SNAPSHOT), len(required))
        for rel, expected in run_first.SNAPSHOT.items():
            self.assertEqual(run_first._sha(K0_DIR / rel), expected, rel)


if __name__ == "__main__":
    unittest.main()
