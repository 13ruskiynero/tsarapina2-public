#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v35-A — офлайн-тесты секции [РЕШЕНИЕ] (модель не вызывается).

Во всех сценариях сессия начинается с валидного F1 (9 строк), затем F2.
T1: после принятого вердикта секция [РЕШЕНИЕ] появляется в следующем промпте:
    V1, H1, P1, клетка, прогноз, исход, «USING V1»; [ВЕРДИКТ] при этом исчезает.
T2: до принятого вердикта секции [РЕШЕНИЕ] нет.
T3: после принятого DECISION (USING V1) секция исчезает; в журнале — запись
    decision с descriptor и using=V1.
T4: маскированная проба не создаёт секцию (вердикта нет; [ВЕРДИКТ] ждёт P1).
T5: содержимое секции строится из записи (другая клетка: O1 T=1 H=0).
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
QH2 = ("QUESTION Q1: как ведёт себя O1 при T=1 H=0? REF: t02\n"
       "HYPOTHESIS H1 OF Q1: O1 при T=1 H=0 будет present. "
       "PREDICT: O1 T=1 H=0 = present")
PROBE_H1 = "PREDICT: O3 T=2 H=0 = present\nACTION: probe O3 T=2 H=0"
PROBE2 = "PREDICT: O1 T=1 H=0 = present\nACTION: probe O1 T=1 H=0"
PROBE_MASKED = "PREDICT: O3 T=2 H=0 = disappeared\nACTION: probe O3 T=2 H=0"
NOTE = "NOTE: жду"
VERDICT = "VERDICT: H1 refuted AFTER P1"
DECISION = ("DECISION: probe O3 T=2 H=2 USING V1\n"
            "PREDICT: O3 T=2 H=2 = disappeared\n"
            "ACTION: probe O3 T=2 H=2")


class DecisionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, max_calls=6):
        run = run_dir_for(self.base, "K0-M3", SEED)
        ch = LoopbackChannel(queue)
        sess = Session(run, make_respond(ch, prompts.build_prompt), seed=SEED,
                       max_calls=max_calls)
        res = sess.run()
        return sess, res, run, ch


def section(prompt, head="[РЕШЕНИЕ]"):
    i = prompt.find(head)
    return "" if i < 0 else prompt[i:]


class TestDecisionFeedback(DecisionCase):
    def test_t1_section_after_accepted_verdict(self):
        # 1 F1, 2 QH, 3 probe, 4 NOTE, 5 NOTE (промпт 5 — после вердикта... нет:
        # вердикта ещё нет; вердикт даётся вызовом 4? Нет — очередь 5 ответов.)
        # Требуется: F1, QH, probe, VERDICT, NOTE → промпт 5 после вердикта
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, VERDICT, NOTE], max_calls=5)
        self.assertEqual(len(ch.sent), 5)
        s4 = ch.sent[3][2]                    # промпт вызова вердикта (после P1)
        self.assertIn("[ВЕРДИКТ]", s4)
        self.assertNotIn("[РЕШЕНИЕ]", s4)     # вердикта ещё нет
        s5 = section(ch.sent[4][2])           # промпт после принятого вердикта
        self.assertIn("[РЕШЕНИЕ]", s5)
        self.assertIn("V1", s5)
        self.assertIn("H1", s5)
        self.assertIn("P1", s5)
        self.assertIn("O3 T=2 H=0", s5)
        self.assertIn("present", s5)
        self.assertIn("disappeared", s5)
        self.assertIn("USING V1", s5)
        self.assertIn("DECISION", s5)
        self.assertNotIn("[ВЕРДИКТ]", ch.sent[4][2])   # секция v34 уже не нужна

    def test_t2_no_section_before_verdict(self):
        # 1 F1, 2 QH, 3 probe, 4 NOTE — вердикта нет
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE], max_calls=4)
        self.assertIn("[ВЕРДИКТ]", ch.sent[3][2])
        self.assertNotIn("[РЕШЕНИЕ]", ch.sent[3][2])

    def test_t3_section_gone_after_decision(self):
        # 1 F1, 2 QH, 3 probe, 4 VERDICT, 5 DECISION+PREDICT+ACTION, 6 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, VERDICT, DECISION, NOTE], max_calls=6)
        self.assertIn("[РЕШЕНИЕ]", ch.sent[4][2])      # до решения
        self.assertNotIn("[РЕШЕНИЕ]", ch.sent[5][2])   # после принятого решения
        rows = read_journal(run / "raw" / "journal.jsonl")
        dec = [r for r in rows if r["type"] == "decision"]
        self.assertEqual(len(dec), 1)
        self.assertEqual(dec[0]["using"], "V1")
        self.assertEqual(dec[0]["descriptor"], "probe O3 T=2 H=2")

    def test_t4_masked_probe_no_section(self):
        # 1 F1, 2 QH, 3 probe (P1 revealed), 4 NOTE, 5 probe (P2 masked), 6 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE, PROBE_MASKED, NOTE], max_calls=6)
        self.assertIn("[ВЕРДИКТ]", ch.sent[4][2])      # ждёт вердикт по P1
        self.assertNotIn("[РЕШЕНИЕ]", ch.sent[4][2])   # вердикта нет
        self.assertIn("[ВЕРДИКТ]", ch.sent[5][2])      # маскированная P2 не снимает шаг
        self.assertNotIn("[РЕШЕНИЕ]", ch.sent[5][2])

    def test_t5_section_content_from_record(self):
        # 1 F1, 2 QH2 (O1 T=1 H=0), 3 probe, 4 VERDICT, 5 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH2, PROBE2, VERDICT, NOTE], max_calls=5)
        s5 = section(ch.sent[4][2])
        self.assertIn("[РЕШЕНИЕ]", s5)
        self.assertIn("O1 T=1 H=0", s5)
        self.assertIn("V1", s5)
        self.assertIn("H1", s5)
        self.assertIn("опровергнута", s5)
        self.assertIn("USING V1", s5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
