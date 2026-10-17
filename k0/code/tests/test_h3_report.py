# -*- coding: utf-8 -*-
"""Тесты классификатора H3 (scripts/h3_report.py) — v37-A, ред. 3.

Исправление по замечанию повторного ревью: действия и связанные записи
пробы/бюджета находятся НА ВЫЗОВЕ В ОКНЕ (6), а не на вызове внедрения (5).
Добавлен T6: действие ДО окна не влияет на классификацию.

T1  supports_H3: действие в окне (call 6), раскрытая проба ровно в клетке цели.
T2  H3_partial: действие в окне, проба в ДРУГОЙ клетке.
T2b unclassified: действие исполнено (call 6), но пробы нет.
T2c unclassified: проба в клетке цели на call 6, но НЕ раскрыта (masked).
T3  H3_not_supported: действий нет, повторные регистрации Q1/H1 есть.
T4  uninformative_goal: цель непригодна.
T4b uninformative_data: окно короче 3.
T4c окно по порядку подряд: разрыв видимости цели усекает окно.
T4d uninformative_behavior: действий нет, O3=0, но есть O4>0.
T5  uninformative_no_goal: записи goal нет.
T6  действие до окна (call 5) не попадает в pairs_in и не влияет на статус.
"""
import sys
import unittest
from pathlib import Path

K0_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(K0_DIR / "scripts"))

import h3_report  # noqa: E402

GOAL_CALL = 5                       # вызов, в ответе на который принято решение
FIRST_WINDOW_CALL = GOAL_CALL + 1   # 6 — первый вызов окна W


def goal(call=GOAL_CALL, eligible=True, cell="O4 T=2 H=1", reason=""):
    return {"seq": 10, "type": "goal", "call": call, "cell": cell,
            "prediction": "present", "eligible": eligible, "reason": reason}


def action(call, descriptor="probe O4 T=2 H=0", seq=20):
    return {"seq": seq, "type": "action_requested", "call": call,
            "descriptor": descriptor}


def budget(action_seq, seq=30, call=None):
    return {"seq": seq, "type": "budget", "call": call, "action_ref": action_seq}


def probe(cell="O4 T=2 H=1", revealed=True, seq=40, call=FIRST_WINDOW_CALL):
    return {"seq": seq, "type": "probe_outcome", "call": call, "cell": cell,
            "outcome": "present", "revealed": revealed, "masked": not revealed}


def reqs(goal_cell="O4 T=2 H=1", calls=(6, 7, 8), phase="F2", include_goal=True):
    out = {}
    for n in calls:
        hyps = []
        if include_goal:
            hyps.append({"n": 2, "cell": goal_cell, "prediction": "present",
                         "status": "open"})
        out[n] = {"phase": phase, "hypotheses": hyps}
    return out


def in_window_action(seq=20, call=FIRST_WINDOW_CALL, descriptor="probe O4 T=2 H=0"):
    """Действие, исполненное на вызове В ОКНЕ (6) — корректная фикстура."""
    return action(call=call, descriptor=descriptor, seq=seq)


class TestH3Report(unittest.TestCase):
    def test_t1_supports_h3(self):
        rows = [goal(), in_window_action(), budget(20, call=6), probe()]
        rep = h3_report.analyze(rows, reqs(), [])
        self.assertEqual(rep["status"], "supports_H3")
        self.assertEqual(rep["window"], [6, 7, 8])
        self.assertTrue(rep["O1_valid_action"])
        self.assertTrue(rep["O2_goal_cell_probe"])
        self.assertEqual(rep["O3_q1h1_duplicates"], 0)

    def test_t2_partial_other_cell(self):
        rows = [goal(), in_window_action(),
                budget(20, call=6), probe(cell="O3 T=2 H=0")]
        rep = h3_report.analyze(rows, reqs(), [])
        self.assertEqual(rep["status"], "H3_partial")
        self.assertFalse(rep["O2_goal_cell_probe"])

    def test_t2b_action_without_probe_unclassified(self):
        rows = [goal(), in_window_action(descriptor="reset"),
                budget(20, call=6)]
        rep = h3_report.analyze(rows, reqs(), [])
        self.assertEqual(rep["status"], "unclassified")
        self.assertEqual(rep["probes_in_window"], 0)

    def test_t2c_masked_goal_probe_unclassified(self):
        rows = [goal(), in_window_action(), budget(20, call=6),
                probe(revealed=False)]
        rep = h3_report.analyze(rows, reqs(), [])
        self.assertEqual(rep["status"], "unclassified")
        self.assertFalse(rep["O2_goal_cell_probe"])
        self.assertEqual(rep["goal_cell_probes_masked"], 1)

    def test_t3_not_supported(self):
        rej = [{"call": c, "requested": r, "kind": k}
               for c in (6, 7, 8) for r, k in (("Q1", "question"),
                                               ("H1", "hypothesis"))]
        rep = h3_report.analyze([goal()], reqs(), rej)
        self.assertEqual(rep["status"], "H3_not_supported")
        self.assertEqual(rep["O3_q1h1_duplicates"], 6)

    def test_t4_ineligible(self):
        rep = h3_report.analyze([goal(eligible=False, reason="already_probed")],
                                reqs(), [])
        self.assertEqual(rep["status"], "uninformative_goal")
        self.assertEqual(rep["reason"], "already_probed")

    def test_t4b_short_window(self):
        rep = h3_report.analyze([goal()], reqs(calls=(5,)), [])
        self.assertEqual(rep["status"], "uninformative_data")
        self.assertEqual(rep["window"], [])

    def test_t4c_window_must_be_contiguous(self):
        rep = h3_report.analyze([goal()], reqs(calls=(6, 8)), [])
        self.assertEqual(rep["status"], "uninformative_data")
        self.assertEqual(rep["window"], [6])

    def test_t4d_no_action_with_o4_uninformative(self):
        rej = [{"call": 7, "requested": "Q2", "kind": "question"}]
        rep = h3_report.analyze([goal()], reqs(), rej)
        self.assertEqual(rep["status"], "uninformative_behavior")
        self.assertFalse(rep["O1_valid_action"])
        self.assertEqual(rep["O4_new_goal_attempts"], 1)

    def test_t5_no_goal_journal(self):
        rep = h3_report.analyze([], reqs(), [])
        self.assertEqual(rep["status"], "uninformative_no_goal")

    def test_t6_action_before_window_ignored(self):
        # действие и раскрытая проба цели — НА ВЫЗОВЕ 5 (вне окна [6,7,8])
        rows = [goal(call=5),
                action(call=5, descriptor="probe O4 T=2 H=1", seq=20),
                budget(20, call=5),
                probe(call=5, revealed=True, seq=40)]
        rep = h3_report.analyze(rows, reqs(), [])
        self.assertFalse(rep["O1_valid_action"])
        self.assertEqual(rep["pairs_in_window"], 0)
        self.assertEqual(rep["status"], "unclassified")


if __name__ == "__main__":
    unittest.main()
