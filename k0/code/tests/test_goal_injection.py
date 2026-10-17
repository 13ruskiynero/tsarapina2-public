#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v37-A — офлайн-тесты внедрения пригодной открытой цели (модель не вызывается).

T1: после первого исполненного решения цель внедряется (journal goal eligible=True,
    call=5); реестр получает Q2/H2.
T2: в следующем промпте видна секция [ГИПОТЕЗЫ] с H2 (клетка O4 T=2 H=1, «открыта»);
    в секции нет слов действия (probe/PREDICT/ACTION/выполни/следующий шаг).
T3: до первого решения внедрения нет (journal goal отсутствует).
T4: если клетка цели уже раскрыта — внедрения нет; journal goal eligible=False,
    reason=already_probed.
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
import prompts  # noqa: E402

SEED = 101

F1 = ("PREDICT: O1 T=2 H=1 = disappeared\n"
      "PREDICT: O3 T=2 H=0 = present\n"
      "PREDICT: O3 T=2 H=1 = present\n"
      "PREDICT: O3 T=2 H=2 = present\n"
      "PREDICT: O2 T=2 H=1 = present\n"
      "PREDICT: O2 T=2 H=2 = present\n"
      "PREDICT: O4 T=2 H=1 = present\n"
      "PREDICT: O4 T=2 H=2 = present\n"
      "PREDICT: O1 T=1 H=0 = disappeared")

QH = ("QUESTION Q1: каково состояние O3 при T=2 H=0? REF: t07\n"
      "HYPOTHESIS H1 OF Q1: O3 при T=2 H=0 будет present. "
      "PREDICT: O3 T=2 H=0 = present")
PROBE_H1 = "PREDICT: O3 T=2 H=0 = present\nACTION: probe O3 T=2 H=0"
VERDICT = "VERDICT: H1 refuted AFTER P1"
DECISION = ("DECISION: probe O4 T=2 H=0 USING V1\n"
            "PREDICT: O4 T=2 H=0 = present\n"
            "ACTION: probe O4 T=2 H=0")
NOTE = "NOTE: жду"

QH_GOALCELL = ("QUESTION Q1: каково состояние O4 при T=2 H=1? REF: t07\n"
               "HYPOTHESIS H1 OF Q1: O4 при T=2 H=1 будет present. "
               "PREDICT: O4 T=2 H=1 = present")
PROBE_GOALCELL = "PREDICT: O4 T=2 H=1 = present\nACTION: probe O4 T=2 H=1"
VERDICT_OK = "VERDICT: H1 supported AFTER P1"


class GoalCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, max_calls=7):
        run = run_dir_for(self.base, "K0-M1", SEED)
        ch = LoopbackChannel(queue)
        sess = Session(run, make_respond(ch, prompts.build_prompt), seed=SEED,
                       max_calls=max_calls)
        sess.run()
        return sess, run, ch


class TestGoalInjection(GoalCase):
    def test_t1_goal_injected_after_first_decision(self):
        sess, run, ch = self.run_session(
            [F1, QH, PROBE_H1, VERDICT, DECISION, NOTE, NOTE], max_calls=7)
        rows = read_journal(run / "raw" / "journal.jsonl")
        g = [r for r in rows if r["type"] == "goal"]
        self.assertEqual(len(g), 1)
        self.assertTrue(g[0]["eligible"])
        self.assertEqual(g[0]["cell"], "O4 T=2 H=1")
        self.assertEqual(g[0]["call"], 5)          # цель поставлена после решения
        dec = [r for r in rows if r["type"] == "decision"]
        self.assertEqual(len(dec), 1)
        self.assertGreater(g[0]["seq"], dec[0]["seq"])

    def test_t2_goal_visible_in_next_prompt(self):
        sess, run, ch = self.run_session(
            [F1, QH, PROBE_H1, VERDICT, DECISION, NOTE, NOTE], max_calls=7)
        # первый F2-контекст, в котором виден H2 (sent_contexts включает F1/F3)
        ctx6 = next(c for c in sess.sent_contexts
                    if c.phase == "F2" and any(h.get("n") == 2 for h in c.hypotheses))
        self.assertTrue(any(h.get("n") == 2 and h.get("cell") == "O4 T=2 H=1"
                            for h in ctx6.hypotheses))
        prompt6 = ch.sent[5][2]
        self.assertIn("[ГИПОТЕЗЫ]", prompt6)
        self.assertIn("H2: клетка O4 T=2 H=1", prompt6)
        self.assertIn("открыта", prompt6)
        # секция — состояние, а не инструкция: слов действия в ней нет
        start = prompt6.find("[ГИПОТЕЗЫ]")
        end = prompt6.find("[МЕТКИ]", start)
        sec = prompt6[start:end if end > start else start + 200]
        for bad in ("probe", "PREDICT:", "ACTION:", "выполни", "следующий шаг"):
            self.assertNotIn(bad, sec)

    def test_t3_no_injection_before_decision(self):
        sess, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE, NOTE], max_calls=5)
        rows = read_journal(run / "raw" / "journal.jsonl")
        self.assertEqual([r for r in rows if r["type"] == "goal"], [])

    def test_t4_ineligible_when_cell_already_probed(self):
        # H1 — на клетке цели; она раскрыта P1 → цель непригодна
        sess, run, ch = self.run_session(
            [F1, QH_GOALCELL, PROBE_GOALCELL, VERDICT_OK, DECISION, NOTE, NOTE],
            max_calls=7)
        rows = read_journal(run / "raw" / "journal.jsonl")
        g = [r for r in rows if r["type"] == "goal"]
        self.assertEqual(len(g), 1)
        self.assertFalse(g[0]["eligible"])
        self.assertEqual(g[0]["reason"], "already_probed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
