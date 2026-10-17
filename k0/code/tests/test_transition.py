#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v32 — офлайн-тесты перехода «регистрация → действие», привязанного к H1.

Проверяют:
  T1: после принятой Q1/H1 (P=0) промпт F2 содержит секцию «[СЛЕДУЮЩИЙ ШАГ]»,
      построенную ПО ЗАПИСИ гипотезы: метка H1, её клетка и прогноз
      (без гипотез/после первой пробы секции нет).
  T2: корректный блок действия (PREDICT + ACTION: probe) проходит существующий
      валидатор и исполняется сразу после принятой регистрации; секция присутствует
      в реально отправленном промпте этого вызова.
  T3: отклонённая повторная регистрация НЕ блокирует корректное действие в том же
      ответе (регистрация не является единственным вариантом поведения).
  T4: проба по инструкции исполняется ИМЕННО в клетке зарегистрированной H1
      (клетка исхода = клетка H1; исход раскрыт; инструкция содержит эту клетку).
Тесты предохранителя v30 (R1–R4) — отдельно, в test_recovery.py; здесь не дублируются.
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
from session import AgentContext, Session  # noqa: E402
from world import load_battery, load_history  # noqa: E402
import prompts  # noqa: E402

ARTIFACTS = K0_DIR / "artifacts"
SEED = 101
BATTERY = tuple(sorted(i.cell.as_text()
                       for i in load_battery(ARTIFACTS / "heldout_battery.json")))
HISTORY = tuple(load_history(ARTIFACTS / "history_101.jsonl"))
F1 = "\n".join(f"PREDICT: {c} = present" for c in BATTERY)

QH = ("QUESTION Q1: что происходит с O1 при T=0 H=2? REF: t01\n"
      "HYPOTHESIS H1 OF Q1: O1 при T=0 H=2 остаётся present. "
      "PREDICT: O1 T=0 H=2 = present")
PROBE_OK = "PREDICT: O1 T=0 H=2 = present\nACTION: probe O1 T=0 H=2"
DUP_AND_PROBE = ("QUESTION Q1: повтор про O2. REF: t01\n"
                 "HYPOTHESIS H1 OF Q1: повторная гипотеза. "
                 "PREDICT: O2 T=1 H=0 = present\n"
                 "PREDICT: O2 T=1 H=0 = present\n"
                 "ACTION: probe O2 T=1 H=0")
QH_O3 = ("QUESTION Q1: что происходит с O3 при T=2 H=0? REF: t07\n"
         "HYPOTHESIS H1 OF Q1: O3 при T=2 H=0 исчезает. "
         "PREDICT: O3 T=2 H=0 = disappeared")
PROBE_O3 = "PREDICT: O3 T=2 H=0 = disappeared\nACTION: probe O3 T=2 H=0"

H1_OK = ({"n": 1, "cell": "O3 T=2 H=0", "prediction": "present"},)


def ctx_for(labels, hypotheses=()):
    return AgentContext(
        phase="F2", history=HISTORY, observations=(), rejections=(),
        budget_remaining=16, last_probe=None, notes=(), battery=(),
        last_labels=labels, hypotheses=tuple(hypotheses))


class TestT1PromptHint(unittest.TestCase):
    """T1: секция следующего шага строится из записи H1 и только при P=0."""

    def test_t1_hint_after_registration(self):
        text = prompts.build_f2(ctx_for((1, 1, 0, 0), H1_OK))
        self.assertIn("[СЛЕДУЮЩИЙ ШАГ]", text)
        self.assertIn("H1", text)
        self.assertIn("O3 T=2 H=0", text)
        self.assertIn("PREDICT: O3 T=2 H=0 = present", text)
        self.assertIn("ACTION: probe O3 T=2 H=0", text)
        self.assertIn("Повторная регистрация не нужна", text)
        self.assertIn("Проверь именно эту клетку", text)

    def test_t1_absent_without_hypotheses(self):
        text = prompts.build_f2(ctx_for((1, 1, 0, 0)))
        self.assertNotIn("[СЛЕДУЮЩИЙ ШАГ]", text)

    def test_t1_absent_before_registration(self):
        text = prompts.build_f2(ctx_for((0, 0, 0, 0)))
        self.assertNotIn("[СЛЕДУЮЩИЙ ШАГ]", text)

    def test_t1_absent_after_first_probe(self):
        text = prompts.build_f2(ctx_for((1, 1, 1, 0), H1_OK))
        self.assertNotIn("[СЛЕДУЮЩИЙ ШАГ]", text)

    def test_t1_static_text_audited(self):
        self.assertIn("[СЛЕДУЮЩИЙ ШАГ]", prompts.static_text())
        self.assertEqual(prompts.lexicon_findings(prompts.static_text()), [])

    def test_t1_size_budget(self):
        from measure_prompts import count_tokens, server_wrap
        got = count_tokens(server_wrap(prompts.build_f2(ctx_for((1, 1, 0, 0), H1_OK))))
        if got is not None:
            self.assertLess(got[0], 4000)   # §12: ≤4000 токенов


class TestT2T3Session(unittest.TestCase):
    """T2/T3/T4: исполнение по существующему валидатору (скриптовый канал)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_session(self, queue, max_calls):
        run = run_dir_for(self.base, "K0-M1", SEED)
        ch = LoopbackChannel(queue)
        # та же сборка промпта, что в живом прогоне (run_first): prompts.build_prompt
        sess = Session(run, make_respond(ch, prompts.build_prompt), seed=SEED,
                       max_calls=max_calls)
        res = sess.run()
        return sess, res, run, ch

    def test_t2_valid_action_passes_after_registration(self):
        queue = [F1, QH, PROBE_OK]
        sess, res, run, ch = self.run_session(queue, max_calls=3)
        rows = read_journal(run / "raw" / "journal.jsonl")
        types = [r["type"] for r in rows]
        self.assertEqual(types.count("question"), 1)
        self.assertEqual(types.count("hypothesis"), 1)
        self.assertEqual(types.count("probe_outcome"), 1)   # действие исполнено
        self.assertEqual(types.count("action_rejected"), 0)
        sent_prompt = ch.sent[2][2]                          # промпт вызова действия
        self.assertIn("[СЛЕДУЮЩИЙ ШАГ]", sent_prompt)

    def test_t3_refused_registration_does_not_block_action(self):
        queue = [F1, QH, DUP_AND_PROBE]
        sess, res, run, ch = self.run_session(queue, max_calls=3)
        rows = read_journal(run / "raw" / "journal.jsonl")
        types = [r["type"] for r in rows]
        self.assertEqual(types.count("probe_outcome"), 1)   # действие исполнено
        self.assertEqual(types.count("action_rejected"), 0)
        self.assertEqual(types.count("question"), 1)        # повтор не зарегистрирован
        self.assertEqual(types.count("hypothesis"), 1)
        self.assertTrue(any("повтор или уменьшение" in (x.get("reason") or "")
                            for x in sess.rejection_audit))

    def test_t4_probe_matches_hypothesis_cell(self):
        """v32: инструкция опирается на запись H1; проба — именно по её клетке."""
        queue = [F1, QH_O3, PROBE_O3]
        sess, res, run, ch = self.run_session(queue, max_calls=3)
        rows = read_journal(run / "raw" / "journal.jsonl")
        po = [r for r in rows if r["type"] == "probe_outcome"]
        self.assertEqual(len(po), 1)
        self.assertEqual(po[0]["cell"], "O3 T=2 H=0")       # клетка = клетка H1
        self.assertTrue(po[0]["revealed"])
        sent_prompt = ch.sent[2][2]
        self.assertIn("[СЛЕДУЮЩИЙ ШАГ]", sent_prompt)
        self.assertIn("Проверь именно эту клетку", sent_prompt)
        self.assertIn("O3 T=2 H=0", sent_prompt)
        self.assertIn("H1", sent_prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
