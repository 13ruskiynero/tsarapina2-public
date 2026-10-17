#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты парсера K0 (§7/§7.1/§7.2 замороженного протокола ред. 26).

Без вызовов модели. Запуск:
    python3 lab/autonomy/k0/code/tests/test_parser.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]        # .../k0/code
K0_DIR = THIS.parents[2]          # .../k0
sys.path.insert(0, str(CODE_DIR))

from world import Cell, load_battery  # noqa: E402
from parser import (  # noqa: E402
    MAX_NOTE_TEXT, MAX_QUESTION_TEXT, MAX_REJECT_REASON,
    REASON_ACTION_INVALID, REASON_DECISION_INVALID, REASON_DISTINGUISH_FAILED,
    REASON_PREDICT_INVALID,
    LabelRegistry, collect_windows, parse_line, parse_response,
    validate_f2, validate_forecast,
)

ARTIFACTS = K0_DIR / "artifacts"


def f2(text, registry=None, trials=("t01",), mode="K0-M1", last_probe=None):
    reg = registry if registry is not None else LabelRegistry.new()
    res = validate_f2(text, reg, known_trials=set(trials), mode=mode,
                      last_probe_cell=last_probe)
    return reg, res


def reg_with_hypotheses(cell):
    reg = LabelRegistry.new()
    reg.register_question(1, "почему объект исчезает?", "t01")
    reg.register_hypothesis(1, 1, "гипотеза 1", cell, "present")
    reg.register_hypothesis(2, 1, "гипотеза 2", cell, "present")
    reg.register_hypothesis(3, 1, "гипотеза 3", cell, "disappeared")
    return reg


def battery_predict_lines():
    items = load_battery(ARTIFACTS / "heldout_battery.json")
    return [f"PREDICT: {i.cell.as_text()} = present" for i in items]


class TestSyntax(unittest.TestCase):
    """§7: строгая грамматика строк."""

    def test_question_ok(self):
        l = parse_line("QUESTION Q1: почему исчезает O1? REF: t01")
        self.assertEqual(l.kind, "question")
        self.assertEqual(l.data["n"], 1)
        self.assertEqual(l.data["ref"], "t01")
        self.assertIsNone(l.error)

    def test_question_length_limit(self):
        base = "QUESTION Q1: {} REF: t01"
        ok = parse_line(base.format("x" * MAX_QUESTION_TEXT))
        self.assertIsNone(ok.error)
        over = parse_line(base.format("x" * (MAX_QUESTION_TEXT + 1)))
        self.assertEqual(over.error, "text_too_long")

    def test_question_missing_ref_unrecognized(self):
        self.assertEqual(parse_line("QUESTION Q1: без ссылки").kind, "unrecognized")

    def test_hypothesis_ok(self):
        l = parse_line("HYPOTHESIS H1 OF Q1: гипотеза PREDICT: O2 T=2 H=1 = present")
        self.assertEqual(l.kind, "hypothesis")
        self.assertEqual(l.data["cell"], Cell("O2", 2, 1))
        self.assertEqual(l.data["prediction"], "present")

    def test_hypothesis_without_predict_unrecognized(self):
        self.assertEqual(parse_line("HYPOTHESIS H1 OF Q1: только текст").kind, "unrecognized")

    def test_action_forms(self):
        a = parse_line("ACTION: probe O2 T=1 H=0")
        self.assertEqual((a.kind, a.data["action_kind"], a.data["cell"]),
                         ("action", "probe", Cell("O2", 1, 0)))
        self.assertEqual(parse_line("ACTION: repeat").data["action_kind"], "repeat")
        self.assertEqual(parse_line("ACTION: reset").data["action_kind"], "reset")

    def test_action_bad_descriptor(self):
        a = parse_line("ACTION: probe O5 T=2 H=0")
        self.assertIsNone(a.data["action_kind"])
        self.assertEqual(a.data["desc_error"], "descriptor_invalid")
        b = parse_line("ACTION: Probe O2 T=2 H=0")
        self.assertEqual(b.data["desc_error"], "descriptor_invalid")

    def test_keyword_case_strict(self):
        self.assertEqual(parse_line("action: reset").kind, "unrecognized")

    def test_wrappers_invalid(self):
        for raw in ["`ACTION: reset`", "- ACTION: reset", "\"ACTION: reset\"",
                    "**ACTION: reset**", "ACTION: reset"]:
            kind = parse_line(raw).kind
            if raw == "ACTION: reset":
                self.assertEqual(kind, "action")
            else:
                self.assertEqual(kind, "unrecognized", raw)

    def test_squeeze_spaces(self):
        a = parse_line("ACTION:  probe  O2  T=2  H=0")
        self.assertEqual(a.data["action_kind"], "probe")
        self.assertEqual(a.data["cell"], Cell("O2", 2, 0))

    def test_predict_ok_and_bad(self):
        p = parse_line("PREDICT: O1 T=2 H=0 = disappeared")
        self.assertIsNone(p.data.get("error"))
        bad = parse_line("PREDICT: O1 T=2 H=0 = maybe")
        self.assertEqual(bad.data["error"], "bad_predict")

    def test_verdict_malformed(self):
        l = parse_line("VERDICT: H1 maybe AFTER P1")
        self.assertEqual(l.kind, "verdict")
        self.assertTrue(l.data["malformed"])
        ok = parse_line("VERDICT: H1 supported AFTER P1")
        self.assertFalse(ok.data["malformed"])

    def test_decision_missing_using(self):
        d = parse_line("DECISION: probe O2 T=2 H=1")
        self.assertEqual(d.kind, "decision")
        self.assertEqual(d.data["using_error"], "missing_using")
        ok = parse_line("DECISION: probe O2 T=2 H=1 USING V1")
        self.assertEqual(ok.data["using_v"], 1)

    def test_rejected_lengths(self):
        base = "REJECTED: H1 REASON: {}"
        self.assertIsNone(parse_line(base.format("x" * MAX_REJECT_REASON)).error)
        self.assertEqual(parse_line(base.format("x" * (MAX_REJECT_REASON + 1))).error,
                         "reason_too_long")

    def test_note_lengths(self):
        self.assertIsNone(parse_line("NOTE: " + "x" * MAX_NOTE_TEXT).error)
        self.assertEqual(parse_line("NOTE: " + "x" * (MAX_NOTE_TEXT + 1)).error,
                         "text_too_long")

    def test_note_phase_flags(self):
        self.assertTrue(parse_line("NOTE: x", phase="F1").data.get("fatal_phase"))
        self.assertTrue(parse_line("NOTE: x", phase="F3").data.get("fatal_phase"))
        self.assertTrue(parse_line("NOTE: x", phase="F4").data.get("not_allowed"))
        self.assertIsNone(parse_line("NOTE: x", phase="F2").data.get("fatal_phase"))

    def test_final_ok(self):
        self.assertEqual(parse_line("FINAL: правило T=2 и p=A").kind, "final")

    def test_notes_ok(self):
        self.assertEqual(parse_line("NOTES: свободный текст").kind, "notes")

    def test_blank(self):
        self.assertEqual(parse_line("   ").kind, "blank")


class TestRegistry(unittest.TestCase):
    """§7: сквозные последовательности меток, следующая = последняя + 1."""

    def test_sequence_repeat_skip(self):
        reg = LabelRegistry.new()
        ok, _ = reg.register_question(1, "t", "t01")
        self.assertTrue(ok)
        bad, why = reg.register_question(1, "t", "t01")
        self.assertFalse(bad)
        self.assertIn("повтор", why)
        bad2, why2 = reg.register_question(3, "t", "t01")
        self.assertFalse(bad2)
        self.assertIn("пропуск", why2)
        ok2, _ = reg.register_question(2, "t", "t02")
        self.assertTrue(ok2)

    def test_commit_probe_and_verdict_numbers(self):
        reg = LabelRegistry.new()
        self.assertEqual(reg.commit_probe(Cell("O1", 2, 1), "disappeared", True), 1)
        self.assertEqual(reg.commit_probe(Cell("O4", 2, 1), "present", True), 2)
        self.assertTrue(reg.has_p(2))
        self.assertEqual(reg.commit_verdict(1, "supported", 1), 1)
        self.assertTrue(reg.has_v(1))


class TestF2Blocks(unittest.TestCase):
    """§7.2: блоки [DECISION] PREDICT ACTION и коды action_rejected."""

    def test_probe_block_ok(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1")
        b = res.blocks[0]
        self.assertTrue(b.ok)
        self.assertEqual(b.plan["action"], "probe")
        self.assertEqual(b.plan["prediction"]["outcome"], "present")
        self.assertEqual(len(res.plans), 1)

    def test_probe_cell_mismatch(self):
        _, res = f2("PREDICT: O3 T=2 H=1 = present\nACTION: probe O2 T=2 H=1")
        b = res.blocks[0]
        self.assertFalse(b.ok)
        self.assertEqual(b.reason, REASON_PREDICT_INVALID)
        self.assertEqual(b.requested, "probe O2 T=2 H=1")

    def test_probe_missing_predict(self):
        _, res = f2("ACTION: probe O2 T=2 H=1")
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_probe_unparsable_predict(self):
        _, res = f2("PREDICT: O1 T=2 H=0 = maybe\nACTION: probe O2 T=2 H=1")
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_reset_ok_without_predict(self):
        _, res = f2("ACTION: reset")
        b = res.blocks[0]
        self.assertTrue(b.ok)
        self.assertEqual(b.plan["action"], "reset")
        self.assertIsNone(b.plan["prediction"])

    def test_reset_with_predict(self):
        _, res = f2("PREDICT: O1 T=2 H=0 = present\nACTION: reset")
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_reset_with_distinguish(self):
        _, res = f2("ACTION: reset DISTINGUISH: H1,H2")
        self.assertEqual(res.blocks[0].reason, REASON_ACTION_INVALID)

    def test_repeat_without_last_probe(self):
        _, res = f2("PREDICT: O1 T=2 H=1 = present\nACTION: repeat")
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_repeat_ok(self):
        last = Cell("O1", 2, 1)
        _, res = f2("PREDICT: O1 T=2 H=1 = disappeared\nACTION: repeat",
                    last_probe=last)
        b = res.blocks[0]
        self.assertTrue(b.ok)
        self.assertEqual(b.plan["action"], "repeat")
        self.assertEqual(b.plan["prediction"]["cell"], last)

    def test_repeat_cell_mismatch(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\nACTION: repeat",
                    last_probe=Cell("O1", 2, 1))
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_two_actions(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1\n"
                    "ACTION: probe O2 T=2 H=1")
        self.assertEqual(res.blocks[0].reason, REASON_ACTION_INVALID)

    def test_decision_ok(self):
        reg = LabelRegistry.new()
        reg.commit_verdict(1, "supported", 1)
        _, res = f2("DECISION: probe O2 T=2 H=1 USING V1\n"
                    "PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1", registry=reg)
        b = res.blocks[0]
        self.assertTrue(b.ok, b)
        self.assertEqual(b.plan["decision"], "probe O2 T=2 H=1")
        self.assertEqual(b.plan["using_v"], 1)

    def test_decision_descriptor_mismatch(self):
        reg = LabelRegistry.new()
        reg.commit_verdict(1, "supported", 1)
        _, res = f2("DECISION: probe O3 T=2 H=1 USING V1\n"
                    "PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1", registry=reg)
        self.assertEqual(res.blocks[0].reason, REASON_DECISION_INVALID)

    def test_decision_bad_verdict_ref(self):
        reg = LabelRegistry.new()
        _, res = f2("DECISION: probe O2 T=2 H=1 USING V9\n"
                    "PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1", registry=reg)
        self.assertEqual(res.blocks[0].reason, REASON_DECISION_INVALID)

    def test_decision_alone(self):
        reg = LabelRegistry.new()
        reg.commit_verdict(1, "supported", 1)
        _, res = f2("DECISION: reset USING V1", registry=reg)
        self.assertEqual(res.blocks[0].reason, REASON_DECISION_INVALID)

    def test_priority_predict_before_decision(self):
        reg = LabelRegistry.new()
        reg.commit_verdict(1, "supported", 1)
        _, res = f2("DECISION: probe O3 T=2 H=1 USING V1\n"
                    "PREDICT: O4 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1", registry=reg)
        self.assertEqual(res.blocks[0].reason, REASON_PREDICT_INVALID)

    def test_distinguish_ok_not_all_equal(self):
        reg = reg_with_hypotheses(Cell("O2", 2, 1))
        _, res = f2("PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2,H3",
                    registry=reg)
        b = res.blocks[0]
        self.assertTrue(b.ok, b)
        self.assertTrue(b.plan["distinguish"]["ok"])
        self.assertEqual(b.plan["distinguish"]["confirmed"], ["H1", "H2", "H3"])

    def test_distinguish_all_equal_fails(self):
        reg = reg_with_hypotheses(Cell("O2", 2, 1))
        _, res = f2("PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2",
                    registry=reg)
        b = res.blocks[0]
        self.assertEqual(b.reason, REASON_DISTINGUISH_FAILED)
        self.assertEqual(b.distinguish_confirmed, ("H1", "H2"))
        self.assertFalse(b.distinguish_ok)

    def test_distinguish_unknown_hypothesis(self):
        reg = reg_with_hypotheses(Cell("O2", 2, 1))
        _, res = f2("PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H4",
                    registry=reg)
        b = res.blocks[0]
        self.assertEqual(b.reason, REASON_DISTINGUISH_FAILED)
        self.assertEqual(b.distinguish_confirmed, ("H1",))

    def test_distinguish_wrong_cell_not_confirmed(self):
        reg = reg_with_hypotheses(Cell("O2", 2, 2))   # прогнозы на другой клетке
        _, res = f2("PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H3",
                    registry=reg)
        b = res.blocks[0]
        self.assertEqual(b.reason, REASON_DISTINGUISH_FAILED)
        self.assertEqual(b.distinguish_confirmed, ())

    def test_distinguish_bad_list(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\n"
                    "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1")
        self.assertEqual(res.blocks[0].reason, REASON_ACTION_INVALID)

    def test_note_between_predict_and_action_transparent(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\nNOTE: между строками\n"
                    "ACTION: probe O2 T=2 H=1")
        self.assertTrue(res.blocks[0].ok)

    def test_collect_windows_separated_by_other_lines(self):
        lines = parse_response("PREDICT: O2 T=2 H=1 = present\n"
                               "FINAL: конец\n"
                               "ACTION: probe O2 T=2 H=1", phase="F2")
        windows = collect_windows(lines)
        self.assertEqual(len(windows), 2)


class TestN8Blocks(unittest.TestCase):
    """N8 (дополнение №1 v1.0): границы блоков и «ранее записанный» вердикт."""

    def test_two_blocks_need_separator(self):
        text = ("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1\n"
                "QUESTION Q1: продолжение? REF: t01\n"
                "PREDICT: O4 T=2 H=1 = present\nACTION: probe O4 T=2 H=1")
        reg = LabelRegistry.new()
        res = validate_f2(text, reg, known_trials={"t01"})
        self.assertEqual(len(res.blocks), 2)
        self.assertTrue(res.blocks[0].ok)
        self.assertTrue(res.blocks[1].ok)

    def test_note_does_not_separate_blocks(self):
        # §7.2: NOTE «не разрывает соседство» — два блока через NOTE = один блок
        # → «более одной ACTION» → action_invalid (пункт v26 сохраняет силу)
        text = ("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1\n"
                "NOTE: между блоками\n"
                "PREDICT: O4 T=2 H=1 = present\nACTION: probe O4 T=2 H=1")
        reg = LabelRegistry.new()
        res = validate_f2(text, reg, known_trials={"t01"})
        self.assertEqual(len(res.blocks), 1)
        self.assertFalse(res.blocks[0].ok)
        self.assertEqual(res.blocks[0].reason, REASON_ACTION_INVALID)

    def _registry_with_past_probe(self):
        reg = LabelRegistry.new()
        reg.register_question(1, "почему?", "t01")
        reg.register_hypothesis(1, 1, "гипотеза", Cell("O2", 2, 1), "present")
        reg.commit_probe(Cell("O2", 2, 1), "present", revealed=True)
        return reg

    def test_decision_using_future_verdict_rejected(self):
        # USING V<n> — только «ранее записанный» (N8 п.7): вердикт ниже по
        # тексту ещё не записан на момент решения
        reg = self._registry_with_past_probe()
        text = ("DECISION: probe O4 T=2 H=1 USING V1\n"
                "PREDICT: O4 T=2 H=1 = present\n"
                "ACTION: probe O4 T=2 H=1\n"
                "FINAL: разделитель\n"
                "VERDICT: H1 supported AFTER P1")
        res = validate_f2(text, reg, known_trials={"t01"})
        self.assertEqual(res.blocks[0].reason, REASON_DECISION_INVALID)
        self.assertEqual(res.verdict_failures, [])       # сам вердикт валиден

    def test_decision_using_earlier_verdict_ok(self):
        reg = self._registry_with_past_probe()
        text = ("VERDICT: H1 supported AFTER P1\n"
                "DECISION: probe O4 T=2 H=1 USING V1\n"
                "PREDICT: O4 T=2 H=1 = present\n"
                "ACTION: probe O4 T=2 H=1")
        res = validate_f2(text, reg, known_trials={"t01"})
        self.assertTrue(res.blocks[0].ok, res.blocks[0])


class TestAtomicNotes(unittest.TestCase):
    """§7 (ред. 24–26): атомарность NOTE по ответу."""

    def test_notes_registered_when_clean(self):
        _, res = f2("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1\n"
                    "NOTE: первая\nNOTE: вторая")
        self.assertEqual([t for _, t in res.notes], ["первая", "вторая"])

    def test_notes_blocked_by_rejected_block(self):
        _, res = f2("ACTION: probe O2 T=2 H=1\nNOTE: не должна пройти")
        self.assertEqual(res.notes, [])
        self.assertTrue(res.blocks[0].reason)

    def test_notes_blocked_by_qh_failure(self):
        _, res = f2("QUESTION Q2: пропуск метки REF: t01\nNOTE: не пройдёт")
        self.assertTrue(res.qh_failures)
        self.assertEqual(res.notes, [])

    def test_notes_blocked_by_verdict_failure(self):
        _, res = f2("VERDICT: H9 supported AFTER P1\nNOTE: не пройдёт")
        self.assertTrue(res.verdict_failures)
        self.assertEqual(res.notes, [])

    def test_notes_blocked_by_unrecognized_line(self):
        _, res = f2("чепуха вне грамматики\nNOTE: не пройдёт")
        self.assertFalse(res.full_parse_ok)
        self.assertEqual(res.notes, [])

    def test_invalid_note_blocks_all_notes(self):
        # ред. 26: невалидная строка NOTE валит полный разбор и блокирует ВСЕ заметки
        long_note = "NOTE: " + "x" * (MAX_NOTE_TEXT + 1)
        _, res = f2(f"NOTE: валидная\n{long_note}")
        self.assertFalse(res.full_parse_ok)
        self.assertEqual(res.notes, [])

    def test_notes_blocked_by_mode_violation_k1b(self):
        _, res = f2("QUESTION Q1: агентский вопрос REF: t01\nNOTE: не пройдёт",
                    mode="K1b")
        self.assertTrue(res.mode_violations)
        self.assertEqual(res.notes, [])

    def test_note_registration_order(self):
        text = "NOTE: одна\nNOTE: два\nNOTE: три"
        _, res = f2(text)
        self.assertEqual([t for _, t in res.notes], ["одна", "два", "три"])


class TestForecast(unittest.TestCase):
    """§7.1: прогнозы батареи F1/F3 — ровно 9 клеток."""

    def _cells(self):
        return [i.cell for i in load_battery(ARTIFACTS / "heldout_battery.json")]

    def test_forecast_ok(self):
        text = "\n".join(battery_predict_lines())
        res = validate_forecast(parse_response(text, phase="F1"), self._cells())
        self.assertTrue(res.ok, res.problems)
        self.assertEqual(len(res.predictions), 9)

    def test_duplicate_cell(self):
        lines = battery_predict_lines()
        lines[1] = lines[0]
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)
        self.assertTrue(any("дубликат" in p for p in res.problems))

    def test_missing_cell(self):
        lines = battery_predict_lines()[:-1]
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)
        self.assertTrue(any("пропуск" in p for p in res.problems))

    def test_extra_cell(self):
        lines = battery_predict_lines()[:-1] + ["PREDICT: O1 T=0 H=0 = present"]
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)
        self.assertTrue(any("лишняя" in p for p in res.problems))

    def test_note_extra_line(self):
        lines = battery_predict_lines() + ["NOTE: лишняя строка"]
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)
        self.assertTrue(any("note" in p for p in res.problems))

    def test_action_extra_line(self):
        lines = battery_predict_lines() + ["ACTION: reset"]
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)

    def test_bad_predict(self):
        lines = battery_predict_lines()
        lines[0] = "PREDICT: O1 T=2 H=1 = maybe"
        res = validate_forecast(parse_response("\n".join(lines), phase="F1"), self._cells())
        self.assertFalse(res.ok)


class TestModeK0M1(unittest.TestCase):
    """§7/§8: в K0-M1 агентские Q/H — норма; нарушений режима нет."""

    def test_qh_normal_in_k0m1(self):
        reg, res = f2("QUESTION Q1: почему исчезает O1? REF: t01\n"
                      "HYPOTHESIS H1 OF Q1: скрытый признак PREDICT: O1 T=2 H=1 = disappeared")
        self.assertEqual(res.mode_violations, [])
        self.assertEqual(res.qh_failures, [])
        self.assertTrue(reg.has_q(1))
        self.assertTrue(reg.has_h(1))

    def test_verdict_requires_revealed_probe(self):
        reg = reg_with_hypotheses(Cell("O2", 2, 1))
        reg.commit_probe(Cell("O2", 2, 1), "present", revealed=False)  # маска
        _, res = f2("VERDICT: H1 supported AFTER P1", registry=reg)
        self.assertTrue(res.verdict_failures)
        reg2 = reg_with_hypotheses(Cell("O2", 2, 1))
        reg2.commit_probe(Cell("O2", 2, 1), "present", revealed=True)
        _, res2 = f2("VERDICT: H1 supported AFTER P1", registry=reg2)
        self.assertEqual(res2.verdict_failures, [])
        self.assertTrue(reg2.has_v(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
