#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v30 — офлайн-тесты восстановления после отказов и предохранителя цикла.

Сценарии:
  R1: повторная регистрация Q1/H1 → отказ с явным сообщением агенту;
      probe без PREDICT → `predict_invalid` с подсказкой;
      следующий ход ВОССТАНАВЛИВАЕТСЯ и проба исполняется; Q/H сохранены.
  R2: идентичные пары (запрос, ответ) в F2 → стоп `response_loop` (K=3) раньше `call_limit`.
  R3: повторы с РАЗНЫМИ запросами (растущий контекст, стиль v28) — НЕ цикл.
Модель не вызывается; сеть не используется.
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

from channel import LoopbackChannel, make_respond  # noqa: E402
from journal import read_journal, run_dir_for  # noqa: E402
from session import Session  # noqa: E402
from world import load_battery  # noqa: E402

ARTIFACTS = K0_DIR / "artifacts"
SEED = 101
BATTERY = tuple(sorted(i.cell.as_text()
                       for i in load_battery(ARTIFACTS / "heldout_battery.json")))
F1 = "\n".join(f"PREDICT: {c} = present" for c in BATTERY)

QH = ("QUESTION Q1: что происходит с O1 при T=0 H=2? REF: t01\n"
      "HYPOTHESIS H1 OF Q1: O1 при T=0 H=2 остаётся present. "
      "PREDICT: O1 T=0 H=2 = present")
PROBE_NOPRED = "ACTION: probe O3 T=1 H=0"
PROBE_OK_1 = "PREDICT: O1 T=0 H=2 = present\nACTION: probe O1 T=0 H=2"
PROBE_OK_2 = "PREDICT: O2 T=1 H=0 = present\nACTION: probe O2 T=1 H=0"
PROBE_OK_3 = "PREDICT: O4 T=1 H=0 = present\nACTION: probe O4 T=1 H=0"


class RecoveryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, seed=SEED, **opts):
        run = run_dir_for(self.base, "K0-M1", seed)
        ch = LoopbackChannel(queue)
        sess = Session(run, make_respond(ch), seed=seed, **opts)
        res = sess.run()
        return sess, res, run


class TestRecovery(RecoveryCase):
    def test_recovery_after_refusals(self):
        queue = [F1, QH, QH, PROBE_NOPRED,
                 PROBE_OK_1, PROBE_OK_2, PROBE_OK_3, PROBE_OK_3]
        sess, res, run = self.run_session(queue, max_calls=8)
        rows = read_journal(run / "raw" / "journal.jsonl")
        types = [r["type"] for r in rows]
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "call_limit")
        self.assertEqual(types.count("question"), 1)
        self.assertEqual(types.count("hypothesis"), 1)
        rej = [r for r in rows if r["type"] == "action_rejected"]
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0]["reason"], "predict_invalid")
        self.assertGreaterEqual(types.count("probe_outcome"), 1)
        hints = [r.get("hint") or "" for r in sess.rejections]
        self.assertTrue(any("повторно регистрировать не нужно" in h for h in hints))
        self.assertTrue(any("отдельная строка PREDICT" in h for h in hints))

    def test_loop_fuse_stops_identical_pairs(self):
        queue = [F1, QH] + [QH] * 12
        sess, res, run = self.run_session(queue)
        rows = read_journal(run / "raw" / "journal.jsonl")
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "response_loop")
        self.assertEqual(rows[-1]["type"], "stop")
        self.assertEqual(rows[-1]["reason"], "response_loop")
        self.assertLess(res.respond_calls, 30)

    def test_growing_context_repeats_not_fused(self):
        queue = [F1] + [PROBE_OK_1] * 6
        sess, res, run = self.run_session(queue, max_calls=7)
        rows = read_journal(run / "raw" / "journal.jsonl")
        types = [r["type"] for r in rows]
        self.assertNotEqual(res.stop_reason, "response_loop")
        self.assertGreaterEqual(types.count("probe_outcome"), 5)

    def test_same_invalid_action_is_fused(self):
        """Крайний случай (ревью v30, ред.2): одинаковое некорректное действие;
        каждый отказ пишет action_rejected — журнал растёт, прогресса нет."""
        queue = [F1, QH, PROBE_NOPRED, PROBE_NOPRED, PROBE_NOPRED,
                 PROBE_NOPRED, PROBE_NOPRED]
        sess, res, run = self.run_session(queue)
        rows = read_journal(run / "raw" / "journal.jsonl")
        types = [r["type"] for r in rows]
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "response_loop")
        self.assertGreaterEqual(types.count("action_rejected"), 3)
        self.assertLess(res.respond_calls, 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
