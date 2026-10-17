#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v33-A — офлайн-тесты F1-feedback при повторной попытке (модель не вызывается).

T1: невалидный F1 (значения `?`) → попытка 2 содержит блок [ОТКАЗ F1]
    с перечнем невалидных строк; попытка 2 принимается.
T2: валидный F1 с первой попытки → блока нет; попытка 1.
T3: три невалидных подряд → стоп invalid_final F1 (без изменений).
T4: причина отказа видна в JSON-артефакте вызова (render_context: f1_rejection).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(CODE_DIR))

from calls import render_context  # noqa: E402
from channel import LoopbackChannel, make_respond  # noqa: E402
from journal import read_journal, run_dir_for  # noqa: E402
from session import Session  # noqa: E402
import prompts  # noqa: E402

SEED = 101

GOOD = (
    "PREDICT: O1 T=2 H=1 = disappeared\n"
    "PREDICT: O3 T=2 H=0 = present\n"
    "PREDICT: O3 T=2 H=1 = present\n"
    "PREDICT: O3 T=2 H=2 = present\n"
    "PREDICT: O2 T=2 H=1 = present\n"
    "PREDICT: O2 T=2 H=2 = present\n"
    "PREDICT: O4 T=2 H=1 = present\n"
    "PREDICT: O4 T=2 H=2 = present\n"
    "PREDICT: O1 T=1 H=0 = disappeared"
)
# точная копия аномального ответа v32 (три значения `?`)
BAD = (
    "PREDICT: O1 T=2 H=1 = disappeared\n"
    "PREDICT: O3 T=2 H=0 = present\n"
    "PREDICT: O3 T=2 H=1 = present\n"
    "PREDICT: O3 T=2 H=2 = ?\n"
    "PREDICT: O2 T=2 H=1 = present\n"
    "PREDICT: O2 T=2 H=2 = present\n"
    "PREDICT: O4 T=2 H=1 = ?\n"
    "PREDICT: O4 T=2 H=2 = ?\n"
    "PREDICT: O1 T=1 H=0 = disappeared"
)


class FeedbackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, max_calls=5):
        run = run_dir_for(self.base, "K0-M1", SEED)
        ch = LoopbackChannel(queue)
        # та же сборка промпта, что в живом прогоне (attempt доходит до билдера)
        sess = Session(run, make_respond(ch, prompts.build_prompt), seed=SEED,
                       max_calls=max_calls)
        res = sess.run()
        return sess, res, run, ch


class TestF1Feedback(FeedbackCase):
    def test_t1_feedback_on_second_attempt(self):
        sess, res, run, ch = self.run_session([BAD, GOOD], max_calls=2)
        rows = read_journal(run / "raw" / "journal.jsonl")
        st = [r for r in rows if r["type"] == "forecast_status"]
        self.assertEqual([r["status"] for r in st], ["invalid_retry", "ok"])
        p1 = ch.sent[0][2]
        p2 = ch.sent[1][2]
        self.assertNotIn("[ОТКАЗ F1]", p1)
        self.assertIn("[ОТКАЗ F1]", p2)
        self.assertIn("- строка 4: PREDICT: O3 T=2 H=2 = ?", p2)
        self.assertIn("пропуск клетки O3 T=2 H=2", p2)
        self.assertIn("повтори ровно 9 строк", p2)
        self.assertEqual(len(sess.f1_pred), 9)

    def test_t2_no_feedback_on_first_attempt(self):
        sess, res, run, ch = self.run_session([GOOD], max_calls=1)
        rows = read_journal(run / "raw" / "journal.jsonl")
        st = [r for r in rows if r["type"] == "forecast_status"]
        self.assertEqual([r["status"] for r in st], ["ok"])
        self.assertNotIn("[ОТКАЗ F1]", ch.sent[0][2])
        self.assertEqual(len(sess.f1_pred), 9)

    def test_t3_three_invalid_still_final(self):
        sess, res, run, ch = self.run_session([BAD, BAD, BAD], max_calls=3)
        rows = read_journal(run / "raw" / "journal.jsonl")
        st = [r for r in rows if r["type"] == "forecast_status"]
        self.assertEqual([r["status"] for r in st],
                         ["invalid_retry", "invalid_retry", "invalid_final"])
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "invalid_final F1")
        for p in ch.sent[1:]:
            self.assertIn("[ОТКАЗ F1]", p[2])
        self.assertEqual(sess.respond_calls, 3)

    def test_t4_rejection_visible_in_artifact(self):
        sess, res, run, ch = self.run_session([BAD, GOOD], max_calls=2)
        ctx2 = sess.sent_contexts[1]
        rc = render_context(ctx2)
        self.assertIn('"f1_rejection"', rc)
        self.assertIn("PREDICT: O3 T=2 H=2 = ?", rc)
        rc1 = render_context(sess.sent_contexts[0])
        self.assertNotIn('"f1_rejection"', rc1)


    # --- v33 review: несколько типов невалидного F1 -------------------------
    def test_t5_missing_cell(self):
        """Пропуск клетки: блок перечисляет пропуск; сырых строк нет."""
        text = "\n".join(GOOD.splitlines()[:-1])          # нет O1 T=1 H=0
        sess, res, run, ch = self.run_session([text, GOOD], max_calls=2)
        p2 = ch.sent[1][2]
        idx = p2.find("[ОТКАЗ F1]")
        self.assertGreaterEqual(idx, 0)
        block = p2[idx:]
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(bullets), 1)
        self.assertIn("- пропуск клетки O1 T=1 H=0", block)
        self.assertNotIn("невалидный PREDICT", block)
        self.assertNotIn("лишняя конструкция", block)

    def test_t6_invalid_line(self):
        """Невалидное значение: строка в блоке + пропуск её клетки — по одной раз."""
        bad = GOOD.replace("PREDICT: O3 T=2 H=2 = present",
                           "PREDICT: O3 T=2 H=2 = PRESENT")
        sess, res, run, ch = self.run_session([bad, GOOD], max_calls=2)
        block = ch.sent[1][2][ch.sent[1][2].find("[ОТКАЗ F1]"):]
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(bullets), 3)                  # невалидная строка + пропуск + сырая строка
        self.assertEqual(block.count("строка 4: невалидный PREDICT"), 1)
        self.assertEqual(block.count("- строка 4: PREDICT: O3 T=2 H=2 = PRESENT"), 1)
        self.assertEqual(block.count("пропуск клетки O3 T=2 H=2"), 1)

    def test_t7_combination_duplicate_invalid_missing(self):
        """Сочетание: дубликат клетки + лишняя конструкция + два пропуска.
        Каждая ошибка — ровно один раз; привязка — из фактического разбора."""
        lines = GOOD.splitlines()
        lines[6] = "PREDICT: O2 T=2 H=1 = present"        # дубликат клетки O2T2H1
        lines[8] = "ACTION: probe O1 T=0 H=0"             # лишняя конструкция (action)
        bad = "\n".join(lines)
        sess, res, run, ch = self.run_session([bad, GOOD], max_calls=2)
        block = ch.sent[1][2][ch.sent[1][2].find("[ОТКАЗ F1]"):]
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(bullets), 6)                  # 4 problems + 2 сырые строки
        self.assertEqual(block.count("строка 7: дубликат клетки O2 T=2 H=1"), 1)
        self.assertEqual(block.count("строка 9: лишняя конструкция (action)"), 1)
        self.assertEqual(block.count("пропуск клетки O1 T=1 H=0"), 1)
        self.assertEqual(block.count("пропуск клетки O4 T=2 H=1"), 1)
        self.assertEqual(block.count("- строка 7: PREDICT: O2 T=2 H=1 = present"), 1)
        self.assertEqual(block.count("- строка 9: ACTION: probe O1 T=0 H=0"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
