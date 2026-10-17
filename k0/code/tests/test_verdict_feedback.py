#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v34-A — офлайн-тесты секции [ВЕРДИКТ] (модель не вызывается).

Во всех сценариях сессия начинается с валидного F1 (9 строк), затем F2.
T1: после раскрытой пробы по клетке H1 без вердикта секция [ВЕРДИКТ] появляется
    в следующем промпте: H1, P1, клетка, прогноз, исход, «AFTER P1».
T2: после валидного VERDICT: H1 refuted AFTER P1 секция исчезает;
    в журнале — запись verdict + verdict_check=match.
T3: маскированная проба не создаёт секцию; ожидающая пара остаётся P1 (не P2).
T4: вердикт с неверной ссылкой (AFTER P9) отклоняется; секция остаётся.
T5: секция не появляется при несовпадении клетки пробы с клеткой H1
    (и до первой пробы вместо неё действует [СЛЕДУЮЩИЙ ШАГ]).
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
PROBE_OTHER = "PREDICT: O3 T=2 H=2 = disappeared\nACTION: probe O3 T=2 H=2"
NOTE = "NOTE: жду"


class VerdictCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, max_calls=6):
        run = run_dir_for(self.base, "K0-M1", SEED)
        ch = LoopbackChannel(queue)
        sess = Session(run, make_respond(ch, prompts.build_prompt), seed=SEED,
                       max_calls=max_calls)
        res = sess.run()
        return sess, res, run, ch


def section(prompt):
    i = prompt.find("[ВЕРДИКТ]")
    return "" if i < 0 else prompt[i:]


class TestVerdictFeedback(VerdictCase):
    def test_t1_section_after_revealed_probe(self):
        # вызовы: 1 F1, 2 QH, 3 probe, 4 NOTE (промпт после раскрытой P1)
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE, NOTE], max_calls=5)
        self.assertEqual(len(ch.sent), 5)
        s4 = section(ch.sent[3][2])
        self.assertIn("[ВЕРДИКТ]", s4)
        self.assertIn("P1", s4)
        self.assertIn("O3 T=2 H=0", s4)
        self.assertIn("disappeared", s4)        # раскрытый исход
        self.assertIn("прогноз: present", s4)
        self.assertIn("VERDICT: H1 supported", s4)
        self.assertIn("AFTER P1", s4)
        self.assertIn("отклоняется", s4)

    def test_t2_section_gone_after_valid_verdict(self):
        # 1 F1, 2 QH, 3 probe, 4 NOTE, 5 VERDICT, 6 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE, "VERDICT: H1 refuted AFTER P1", NOTE],
            max_calls=6)
        self.assertIn("[ВЕРДИКТ]", section(ch.sent[3][2]))   # до вердикта
        self.assertIn("[ВЕРДИКТ]", section(ch.sent[4][2]))   # промпт вызова вердикта
        self.assertNotIn("[ВЕРДИКТ]", ch.sent[5][2])          # после вердикта — нет
        rows = read_journal(run / "raw" / "journal.jsonl")
        v = [r for r in rows if r["type"] == "verdict"]
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["h_label"], "H1")
        self.assertEqual(v[0]["resolution"], "refuted")
        self.assertEqual(v[0]["after"], "P1")
        vc = [r for r in rows if r["type"] == "verdict_check"]
        self.assertEqual([x["value"] for x in vc], ["match"])

    def test_t3_masked_probe_not_a_trigger(self):
        # 1 F1, 2 QH, 3 probe (P1, revealed), 4 NOTE, 5 probe (P2, masked), 6 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, NOTE, PROBE_OTHER, NOTE], max_calls=6)
        s6 = section(ch.sent[5][2])
        self.assertIn("[ВЕРДИКТ]", s6)
        self.assertIn("P1", s6)                  # ожидающая пара — P1
        self.assertNotIn("P2", s6)               # маскированная P2 не создаёт шаг

    def test_t4_invalid_verdict_keeps_section_and_rejects(self):
        # 1 F1, 2 QH, 3 probe, 4 неверный VERDICT, 5 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_H1, "VERDICT: H1 refuted AFTER P9", NOTE], max_calls=5)
        self.assertIn("[ВЕРДИКТ]", section(ch.sent[4][2]))   # вердикт не принят
        self.assertTrue(any(x.get("kind") == "verdict" for x in sess.rejection_audit))

    def test_t5_cell_mismatch_no_section(self):
        # 1 F1, 2 QH, 3 probe по ДРУГОЙ клетке, 4 NOTE
        sess, res, run, ch = self.run_session(
            [F1, QH, PROBE_OTHER, NOTE], max_calls=4)
        self.assertIn("[СЛЕДУЮЩИЙ ШАГ]", ch.sent[2][2])      # P=0: шаг пробы (v32)
        self.assertNotIn("[ВЕРДИКТ]", ch.sent[3][2])          # клетка не совпала с H1


if __name__ == "__main__":
    unittest.main(verbosity=2)
