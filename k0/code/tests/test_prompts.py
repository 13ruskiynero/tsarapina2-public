#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты шаблонов промптов K0 (F1–F4; офлайн, без модели).

Проверяют: состав секций по акту K0_CONTEXT_ACT.md, лексикон-аудит
(отсутствие подсказок), отсутствие лишних данных, бюджет размера на
типовом наполнении. Запуск:
    python3 lab/autonomy/k0/code/tests/test_prompts.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(CODE_DIR))

from world import load_battery, load_history  # noqa: E402
from session import AgentContext  # noqa: E402
import prompts  # noqa: E402

ARTIFACTS = K0_DIR / "artifacts"
BATTERY = tuple(sorted(c.as_text() for c in
                       [i.cell for i in load_battery(ARTIFACTS / "heldout_battery.json")]))
HISTORY = tuple(load_history(ARTIFACTS / "history_101.jsonl"))


def make_ctx(phase="F2", **kw):
    default = dict(
        phase=phase,
        history=HISTORY,
        observations=(("O2 T=2 H=1", "present"), ("O4 T=2 H=1", "present")),
        rejections=({"requested": "probe O3 T=0 H=0", "reason": "predict_invalid"},),
        budget_remaining=14,
        last_probe="O4 T=2 H=1",
        notes=("заметка один", "заметка два"),
        battery=BATTERY if phase in ("F1", "F3") else (),
        last_labels=(1, 3, 2, 1),
    )
    default.update(kw)
    return AgentContext(**default)


class TestLexicon(unittest.TestCase):

    def test_static_text_clean(self):
        self.assertEqual(prompts.lexicon_findings(prompts.static_text()), [])

    def test_catches_hints(self):
        for bad in ("при T=2 исчезает", "скрытый параметр", "материал A важен"):
            self.assertTrue(prompts.lexicon_findings(bad), bad)


class TestF1(unittest.TestCase):

    def test_sections(self):
        text = prompts.build_f1(make_ctx("F1"))
        self.assertIn("[ФАЗА 1", text)
        self.assertIn(prompts.HIST_HEAD, text)
        self.assertIn(prompts.BATT_HEAD, text)
        self.assertIn("PREDICT:", text)
        self.assertNotIn(prompts.OBS_HEAD, text)      # наблюдений в F1 нет
        self.assertNotIn(prompts.NOTE_HEAD, text)     # заметок в F1 нет
        self.assertNotIn(prompts.REJ_HEAD, text)

    def test_battery_listed(self):
        text = prompts.build_f1(make_ctx("F1"))
        for cell in BATTERY:
            self.assertIn(cell, text)
        for r in HISTORY:
            self.assertIn(r["trial_id"], text)


class TestF2(unittest.TestCase):

    def test_sections(self):
        text = prompts.build_f2(make_ctx())
        self.assertIn("[ФАЗА 2", text)
        self.assertIn("Бюджет: 14", text)
        self.assertIn(prompts.OBS_HEAD, text)
        self.assertIn(prompts.REJ_HEAD, text)
        self.assertIn(prompts.NOTE_HEAD, text)
        self.assertIn("заметка два", text)
        self.assertIn("Q=1, H=3, P=2, V=1", text)
        self.assertIn("[ПОСЛЕДНЯЯ ПРОБА] O4 T=2 H=1", text)
        self.assertIn("ACTION: reset", text)
        self.assertIn("NOTE:", text)

    def test_optional_sections_absent_when_empty(self):
        text = prompts.build_f2(make_ctx(observations=(), rejections=(), notes=(),
                                         last_probe=None))
        self.assertNotIn(prompts.OBS_HEAD, text)
        self.assertNotIn(prompts.REJ_HEAD, text)
        self.assertNotIn(prompts.NOTE_HEAD, text)
        self.assertNotIn("[ПОСЛЕДНЯЯ ПРОБА]", text)

    def test_no_battery_list_in_f2(self):
        text = prompts.build_f2(make_ctx())
        self.assertNotIn(prompts.BATT_HEAD, text)

    def test_size_budget_typical(self):
        text = prompts.build_f2(make_ctx())
        from measure_prompts import count_tokens, server_wrap
        got = count_tokens(server_wrap(text))
        if got is None:
            self.assertLess(len(text.encode("utf-8")), 6000)   # прокси без токенизатора
        else:
            self.assertLess(got[0], 4000)                      # §12: ≤4000 токенов


class TestF3F4(unittest.TestCase):

    def test_f3_has_experience(self):
        text = prompts.build_f3(make_ctx("F3"))
        self.assertIn(prompts.OBS_HEAD, text)
        self.assertIn("O2 T=2 H=1 -> present", text)
        self.assertIn(prompts.NOTE_HEAD, text)
        self.assertIn(prompts.BATT_HEAD, text)

    def test_f4_final_line(self):
        text = prompts.build_f4(make_ctx("F4", battery=()))
        self.assertIn("FINAL: <текст>", text)
        self.assertIn(prompts.OBS_HEAD, text)

    def test_dispatch(self):
        ctx = make_ctx()
        self.assertEqual(prompts.build_prompt(ctx, "F2", 1), prompts.build_f2(ctx))
        with self.assertRaises(ValueError):
            prompts.build_prompt(ctx, "F9", 1)


class TestCanaryPath(unittest.TestCase):
    """Канареечный промпт строится РОВНО тем же путём, что промпт сессии
    (фикс канарейки, решение 2026-10-16)."""

    def test_canary_matches_session_path(self):
        import run_first
        from session import AgentContext
        from world import load_history
        history = tuple(load_history(ARTIFACTS / "history_101.jsonl"))
        battery = tuple(item.cell.as_text()
                        for item in load_battery(ARTIFACTS / "heldout_battery.json"))
        ctx = AgentContext(phase="F1", history=history, battery=battery)
        self.assertEqual(run_first.f1_prompt(), prompts.build_prompt(ctx, "F1", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
