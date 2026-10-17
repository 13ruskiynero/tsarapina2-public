#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты аудитора S1–S6 (§10 замороженного протокола ред. 26).

Журналы строятся в временных каталогах; комплект не затрагивается.
Запуск:
    python3 lab/autonomy/k0/code/tests/test_auditor.py -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]        # .../k0/code
sys.path.insert(0, str(CODE_DIR))

from world import Cell  # noqa: E402
from journal import Journal, read_journal, run_dir_for  # noqa: E402
from auditor import audit_journal, is_echo_content  # noqa: E402


def build_full(j, *, origin_q="agent", origin_h="agent", origin_p="agent",
               origin_v="agent", ref="t01",
               with_verdict=True, check="match", verdict_before_outcome=False,
               with_decision=True, decision_desc="probe O4 T=2 H=1",
               with_distinguish=True, with_pre=True, pre_after=False,
               masked=False):
    """Собрать синтетический журнал полной цепочки (по умолчанию — валидной)."""
    lb_q = "agent" if origin_q == "agent" else "driver"
    lb_h = "agent" if origin_h == "agent" else "driver"
    cell = Cell("O2", 2, 1)
    j.history_shown(101, [f"t{i:02d}" for i in range(1, 13)])
    j.question(1, "почему исчезает O2?", ref, origin=origin_q, label_by=lb_q)
    j.hypothesis(1, 1, "гипотеза 1", cell, "present", origin=origin_h, label_by=lb_h)
    j.hypothesis(2, 1, "гипотеза 2", cell, "present", origin=origin_h, label_by=lb_h)
    j.hypothesis(3, 1, "гипотеза 3", cell, "disappeared", origin=origin_h, label_by=lb_h)
    if pre_after:
        future = j.seq + 2
        ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=future,
                                p_label="P1", origin=origin_p)
        j.prediction_pre(cell, "present")           # предзапись ПОСЛЕ исполнения
    else:
        pre = j.prediction_pre(cell, "present") if with_pre else None
        ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre,
                                p_label="P1", origin=origin_p)
    if with_verdict and verdict_before_outcome:
        v = j.verdict("V1", 1, "supported", 1, origin=origin_v)
        if check:
            j.verdict_check(check, v["seq"])
    if with_distinguish:
        j.probe_outcome(cell, "disappeared" if masked else "present",
                        masked=masked, revealed=not masked,
                        distinguish_confirmed=["H1", "H2", "H3"], distinguish_ok=True)
    else:
        j.probe_outcome(cell, "disappeared" if masked else "present",
                        masked=masked, revealed=not masked)
    j.budget(1, 15, action_ref=ar["seq"])
    if with_verdict and not verdict_before_outcome:
        v = j.verdict("V1", 1, "supported", 1, origin=origin_v)
        if check:
            j.verdict_check(check, v["seq"])
    if with_decision:
        j.decision(decision_desc, 1)
        pre2 = j.prediction_pre(Cell("O4", 2, 1), "present")
        ar2 = j.action_requested("probe O4 T=2 H=1", prediction_ref=pre2, p_label="P2")
        j.probe_outcome(Cell("O4", 2, 1), "present", masked=False, revealed=True)
        j.budget(1, 14, action_ref=ar2["seq"])
    return j


class AuditCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", 101)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, **opts) -> "object":
        j = Journal(self.run).open()
        try:
            build_full(j, **opts)
        finally:
            j.close()
        from journal import read_journal
        return audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))


class TestFullChain(AuditCase):
    """§10: полная корректная цепочка — все разрезы true."""

    def test_full_valid_chain(self):
        r = self.make()
        for name in ("S1", "S2", "S3", "S4", "S5", "S6"):
            self.assertTrue(r.links[name].structural, name)
            self.assertTrue(r.links[name].agent, name)
        self.assertTrue(r.structural_full)
        self.assertTrue(r.agent_full)
        self.assertTrue(r.agent_valid_full)
        self.assertEqual(r.correct_s4, "match")
        self.assertFalse(r.not_checked)
        self.assertEqual(r.status_hint, "normal")

    def test_report_fields(self):
        r = self.make()
        d = r.as_dict()
        self.assertIn("links", d)
        self.assertEqual(len(r.open_questions), 4)
        self.assertTrue(r.s6_complete)   # установлено решением (K0_S6_DECISION_ACT.md)

    def test_s3_details(self):
        r = self.make()
        self.assertEqual(r.links["S3"].details["confirmed"], ["H1", "H2", "H3"])
        self.assertEqual(r.links["S4"].details["first_verdict"], "V1")


class TestS4Variants(AuditCase):
    """§10: S4 — вердикт/проверка; not_checked — процедурный дефект."""

    def test_no_verdict_negative(self):
        r = self.make(with_verdict=False)
        self.assertFalse(r.links["S4"].structural)
        self.assertFalse(r.structural_full)
        self.assertFalse(r.agent_valid_full)
        self.assertIsNone(r.correct_s4)
        self.assertFalse(r.not_checked)
        self.assertEqual(r.status_hint, "normal")   # обычный отрицательный результат

    def test_check_mismatch(self):
        r = self.make(check="mismatch")
        self.assertTrue(r.links["S4"].structural)
        self.assertEqual(r.correct_s4, "mismatch")
        self.assertFalse(r.agent_valid_full)
        self.assertFalse(r.not_checked)
        self.assertEqual(r.status_hint, "normal")   # отрицательный результат ревизии

    def test_check_missing_not_checked(self):
        r = self.make(check=None)
        self.assertTrue(r.links["S4"].structural)
        self.assertEqual(r.correct_s4, "not_checked")
        self.assertTrue(r.not_checked)
        self.assertFalse(r.agent_valid_full)
        self.assertEqual(r.status_hint, "inconclusive_not_checked")

    def test_verdict_before_outcome(self):
        r = self.make(verdict_before_outcome=True)
        self.assertFalse(r.links["S4"].structural)
        self.assertFalse(r.links["S6"].structural)
        self.assertIsNone(r.correct_s4)

    def test_verdict_on_masked_probe(self):
        r = self.make(masked=True)
        self.assertFalse(r.links["S4"].structural)   # исход не раскрыт агенту
        self.assertFalse(r.structural_full)


class TestOrigins(AuditCase):
    """§10: разрезы structural/agent; смешанные звенья."""

    def test_driver_chain_structural_only(self):
        r = self.make(origin_q="driver", origin_h="driver", origin_p="driver",
                      origin_v="driver", with_decision=False)
        self.assertTrue(r.links["S1"].structural)
        self.assertFalse(r.links["S1"].agent)
        self.assertFalse(r.links["S2"].agent)
        self.assertFalse(r.links["S3"].agent)
        self.assertFalse(r.links["S4"].agent)
        self.assertTrue(r.links["S6"].structural)
        self.assertFalse(r.links["S5"].structural)   # DECISION отсутствует
        # структурная полнота нарушена лишь отсутствием S5; S1–S4 — структурно
        self.assertFalse(r.agent_full)

    def test_driver_full_structural(self):
        r = self.make(origin_q="driver", origin_h="driver", origin_p="driver",
                      origin_v="driver", with_decision=False, with_verdict=False)
        # без вердикта/решения: structural тоже не полон — проверяем ключевое:
        self.assertFalse(r.agent_full)

    def test_mixed_hypotheses(self):
        # H2 от драйвера: S2 — не agent-origin (правило агрегации), S1 — agent
        j = Journal(self.run).open()
        try:
            j.history_shown(101, [f"t{i:02d}" for i in range(1, 13)])
            j.question(1, "вопрос?", "t01", origin="agent", label_by="agent")
            j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present",
                         origin="agent", label_by="agent")
            j.hypothesis(2, 1, "h2", Cell("O2", 2, 1), "disappeared",
                         origin="driver", label_by="driver")
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertTrue(r.links["S1"].agent)
        self.assertTrue(r.links["S2"].structural)
        self.assertFalse(r.links["S2"].agent)


class TestS1S2S3S5Negatives(AuditCase):
    """Различные негативы структурных условий."""

    def test_s1_bad_ref(self):
        r = self.make(ref="t99")
        self.assertFalse(r.links["S1"].structural)

    def test_s2_single_hypothesis(self):
        j = Journal(self.run).open()
        try:
            j.history_shown(101, ["t01"])
            j.question(1, "вопрос?", "t01")
            j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertFalse(r.links["S2"].structural)   # одна гипотеза < 2

    def test_s3_requires_distinguish(self):
        r = self.make(with_distinguish=False)
        self.assertFalse(r.links["S3"].structural)
        self.assertTrue(r.links["S4"].structural)

    def test_s3_inconsistency_with_record(self):
        # Запись probe_outcome утверждает distinguish_ok=true, но прогнозы
        # гипотез совпадают — аудитор фиксирует расхождение.
        j = Journal(self.run).open()
        try:
            j.history_shown(101, ["t01"])
            j.question(1, "вопрос?", "t01")
            j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")
            j.hypothesis(2, 1, "h2", Cell("O2", 2, 1), "present")  # одинаковые!
            pre = j.prediction_pre(Cell("O2", 2, 1), "present")
            ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre, p_label="P1")
            j.probe_outcome(Cell("O2", 2, 1), "present", False, True,
                            distinguish_confirmed=["H1", "H2"], distinguish_ok=True)
            j.budget(1, 15, action_ref=ar["seq"])
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertFalse(r.links["S3"].structural)
        self.assertTrue(r.links["S3"].details.get("inconsistency"))

    def test_s5_decision_missing(self):
        r = self.make(with_decision=False)
        self.assertFalse(r.links["S5"].structural)

    def test_s5_descriptor_mismatch(self):
        r = self.make(decision_desc="probe O3 T=2 H=1")
        self.assertFalse(r.links["S5"].structural)


class TestS6(AuditCase):
    """§10: S6 — предзапись/порядок/воскрешение (см. открытые компоненты)."""

    def test_pre_missing(self):
        r = self.make(with_pre=False)
        self.assertFalse(r.links["S6"].structural)
        self.assertFalse(r.links["S3"].structural)
        self.assertTrue(r.links["S6"].details["pre_before_action"] is False)

    def test_pre_after_action(self):
        r = self.make(pre_after=True)
        self.assertFalse(r.links["S6"].structural)
        self.assertFalse(r.links["S6"].details["pre_before_action"])

    def test_reuse_refuted_hypothesis(self):
        j = Journal(self.run).open()
        try:
            j.history_shown(101, ["t01"])
            j.question(1, "вопрос?", "t01")
            j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")
            j.hypothesis(2, 1, "h2", Cell("O2", 2, 1), "disappeared")
            pre = j.prediction_pre(Cell("O2", 2, 1), "present")
            ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre, p_label="P1")
            j.probe_outcome(Cell("O2", 2, 1), "present", False, True,
                            distinguish_confirmed=["H1", "H2"], distinguish_ok=True)
            j.budget(1, 15, action_ref=ar["seq"])
            v = j.verdict("V1", 2, "refuted", 1)          # H2 опровергнута
            j.verdict_check("match", v["seq"])
            # новая проба снова использует H2 (после refuted)
            pre2 = j.prediction_pre(Cell("O4", 2, 1), "present")
            ar2 = j.action_requested("probe O4 T=2 H=1", prediction_ref=pre2, p_label="P2")
            j.probe_outcome(Cell("O4", 2, 1), "present", False, True,
                            distinguish_confirmed=["H1", "H2"], distinguish_ok=True)
            j.budget(1, 14, action_ref=ar2["seq"])
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertFalse(r.links["S6"].structural)
        self.assertFalse(r.links["S6"].details["reuse_refuted"])
        self.assertTrue(r.links["S6"].details["reuse_problems"])

    def test_reuse_refuted_in_new_verdict(self):
        # «воскрешение» через НОВЫЙ вердикт на опровергнутую гипотезу
        cell = Cell("O2", 2, 1)
        j = Journal(self.run).open()
        try:
            j.history_shown(101, ["t01"])
            j.question(1, "вопрос?", "t01")
            j.hypothesis(1, 1, "гипотеза 1", cell, "present")
            j.hypothesis(2, 1, "гипотеза 2", cell, "present")
            pre = j.prediction_pre(cell, "present")
            ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre, p_label="P1")
            j.probe_outcome(cell, "present", False, True)
            j.budget(1, 15, action_ref=ar["seq"])
            v1 = j.verdict("V1", 2, "refuted", 1)              # H2 опровергнута
            j.verdict_check("match", v1["seq"])
            pre2 = j.prediction_pre(Cell("O4", 2, 1), "present")
            ar2 = j.action_requested("probe O4 T=2 H=1", prediction_ref=pre2, p_label="P2")
            j.probe_outcome(Cell("O4", 2, 1), "present", False, True)
            j.budget(1, 14, action_ref=ar2["seq"])
            v2 = j.verdict("V2", 2, "supported", 2)            # снова H2 → нарушение
            j.verdict_check("match", v2["seq"])
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertFalse(r.links["S6"].structural)
        self.assertFalse(r.links["S6"].details["reuse_refuted"])
        self.assertIn({"verdict": "V2", "hypothesis": "H2"},
                      r.links["S6"].details["reuse_problems"])

    def test_echo_violation_caught_in_journal(self):
        # N4: при наличии текстового содержания вердикта эхо ловится аудитором
        cell = Cell("O2", 2, 1)
        j = Journal(self.run).open()
        try:
            j.history_shown(101, ["t01"])
            j.question(1, "вопрос?", "t01")
            j.hypothesis(1, 1, "гипотеза 1", cell, "present")
            pre = j.prediction_pre(cell, "present")
            ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre, p_label="P1")
            j.probe_outcome(cell, "present", False, True)
            j.budget(1, 15, action_ref=ar["seq"])
            j._append("verdict", "agent", "driver", label="V1", h_label="H1",
                      resolution="supported", after="P1", content_text="present")
        finally:
            j.close()
        from journal import read_journal
        r = audit_journal(read_journal(self.run / "raw" / "journal.jsonl"))
        self.assertFalse(r.links["S6"].structural)
        self.assertEqual(r.links["S6"].details["echo"]["violations"], ["V1"])


class TestEdgeCases(AuditCase):
    """Границы: пустой журнал; открытые компоненты S6."""

    def test_empty_journal(self):
        r = audit_journal([])
        self.assertFalse(r.structural_full)
        self.assertFalse(r.agent_full)
        self.assertFalse(r.agent_valid_full)
        self.assertIsNone(r.correct_s4)
        self.assertEqual(r.status_hint, "normal")
        for name in ("S1", "S2", "S3", "S4", "S5", "S6"):
            self.assertFalse(r.links[name].structural, name)
        # S6 без предмета проверки — структурно не выполнен (аналог правила
        # §10 «нет вердикта → structural(S4)=false»); флаг vacuous виден в деталях
        self.assertTrue(r.links["S6"].details.get("vacuous"))

    def test_s6_open_components_reported(self):
        r = self.make()
        comps = r.links["S6"].details["open_components"]
        self.assertNotIn("echo_norm_proposed_0.1-draft", comps)  # норма утверждена (v1.0)
        self.assertIn("explicit_revision_not_defined", comps)
        self.assertEqual(r.links["S6"].details["echo"]["norm"], "addendum-1.0")


class TestEchoContent(unittest.TestCase):
    """N4 (A12, дополнение №1 v1.0): узкое определение «эха текста»."""

    def test_exact_match_is_echo(self):
        self.assertTrue(is_echo_content("present", ["present"]))
        self.assertTrue(is_echo_content("O2 T=2 H=1 = present",
                                        ["O2 T=2 H=1 = present"]))

    def test_normalization_case_and_spaces(self):
        self.assertTrue(is_echo_content(" Present ", ["present"]))
        self.assertTrue(is_echo_content("o2 t=2   h=1 = present",
                                        ["O2 T=2 H=1 = present"]))

    def test_statement_is_not_echo(self):
        self.assertFalse(is_echo_content("гипотеза H1 supported", ["present"]))
        self.assertFalse(is_echo_content("present, но это не подтверждает H1",
                                         ["present"]))

    def test_empty_and_mismatch(self):
        self.assertFalse(is_echo_content("", ["present"]))
        self.assertFalse(is_echo_content("disappeared", ["present"]))


class TestS4Aggregation(unittest.TestCase):
    """N3 (A14, дополнение №1): свёртка вердиктов not_checked > mismatch > match."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _two_verdicts(self, v1_check="match", v2_check="match"):
        run = run_dir_for(self.base, "K0-AUD", 501)
        j = Journal(run).open()
        j.history_shown(101, [f"t{i:02d}" for i in range(1, 13)])
        j.question(1, "q?", "t01")
        j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")
        j.hypothesis(2, 1, "h2", Cell("O4", 2, 1), "present")
        pre1 = j.prediction_pre(Cell("O2", 2, 1), "present")
        ar1 = j.action_requested("probe O2 T=2 H=1", prediction_ref=pre1, p_label="P1")
        j.probe_outcome(Cell("O2", 2, 1), "present", masked=False, revealed=True)
        j.budget(1, 15, ar1["seq"])
        v1 = j.verdict("V1", 1, "supported", 1)
        if v1_check:
            j.verdict_check(v1_check, v1["seq"])
        pre2 = j.prediction_pre(Cell("O4", 2, 1), "present")
        ar2 = j.action_requested("probe O4 T=2 H=1", prediction_ref=pre2, p_label="P2")
        j.probe_outcome(Cell("O4", 2, 1), "present", masked=False, revealed=True)
        j.budget(1, 14, ar2["seq"])
        v2 = j.verdict("V2", 2, "supported", 2)
        if v2_check:
            j.verdict_check(v2_check, v2["seq"])
        j.close()
        return run

    def _audit(self, v1_check, v2_check):
        run = self._two_verdicts(v1_check, v2_check)
        return audit_journal(read_journal(run / "raw" / "journal.jsonl"))

    def test_all_match(self):
        r = self._audit("match", "match")
        self.assertTrue(r.links["S4"].structural)
        self.assertEqual(r.correct_s4, "match")

    def test_any_mismatch(self):
        r = self._audit("match", "mismatch")
        self.assertEqual(r.correct_s4, "mismatch")

    def test_missing_check_prioritized(self):
        r = self._audit("match", None)
        self.assertEqual(r.correct_s4, "not_checked")
        self.assertTrue(r.not_checked)

    def test_missing_and_mismatch_prioritizes_missing(self):
        r = self._audit(None, "mismatch")
        self.assertEqual(r.correct_s4, "not_checked")   # not_checked > mismatch

    def test_per_verdict_details_preserved(self):
        r = self._audit("match", None)
        by_label = {x["label"]: x for x in r.links["S4"].details["verdicts"]
                    if x["structural"]}
        self.assertEqual(by_label["V1"]["check_reason"], "match")
        self.assertEqual(by_label["V2"]["check_reason"], "not_checked_missing")


class TestS4CellMatch(unittest.TestCase):
    """N1/N2 (A21/A18, дополнение №1): прогноз на другой клетке → not_checked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_cell_match(self):
        run = run_dir_for(self.base, "K0-AUD", 502)
        j = Journal(run).open()
        j.history_shown(101, [f"t{i:02d}" for i in range(1, 13)])
        j.question(1, "q?", "t01")
        j.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")   # прогноз на O2
        pre = j.prediction_pre(Cell("O4", 2, 1), "present")
        ar = j.action_requested("probe O4 T=2 H=1", prediction_ref=pre, p_label="P1")
        j.probe_outcome(Cell("O4", 2, 1), "present", masked=False, revealed=True)
        j.budget(1, 15, ar["seq"])
        j.verdict("V1", 1, "supported", 1)   # записи verdict_check нет
        j.close()
        r = audit_journal(read_journal(run / "raw" / "journal.jsonl"))
        self.assertTrue(r.links["S4"].structural)
        self.assertEqual(r.correct_s4, "not_checked")
        self.assertEqual(r.links["S4"].details["verdicts"][0]["check_reason"],
                         "not_checked_no_cell_match")
        self.assertTrue(r.not_checked)
        self.assertEqual(r.status_hint, "inconclusive_not_checked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
