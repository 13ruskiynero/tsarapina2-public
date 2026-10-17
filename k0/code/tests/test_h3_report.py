#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v37-A — офлайн-тесты классификатора H3 (scripts/h3_report.py).

Синтетические журналы/запросы/отклонения; модель не вызывается.
T1: цель пригодна; O1+O2, дублей нет → supports_H3.
T2: O1 есть, проба не в клетке цели → H3_partial.
T3: действия нет, дубли Q1/H1 есть → H3_not_supported (H2 НЕ подтверждена).
T4: цель непригодна → uninformative_goal; окно <3 → uninformative_data.
T5: ни действия, ни дублей, ни новых целей → unclassified.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(K0_DIR / "scripts"))

import h3_report  # noqa: E402


def row(seq, rtype, **kw):
    r = {"seq": seq, "type": rtype, "origin": "agent", "label_by": "agent"}
    r.update(kw)
    return r


def goal_rec(call=5, eligible=True, reason="", cell="O4 T=2 H=1"):
    return row(20, "goal", origin="goal", label_by="system", cell=cell,
               prediction="present", q="Q2", h="H2",
               eligible=eligible, reason=reason, call=call)


def reqs(calls, cell="O4 T=2 H=1"):
    return {n: {"phase": "F2", "hypotheses": [
        {"n": 1, "cell": "O3 T=2 H=0", "prediction": "present"},
        {"n": 2, "cell": cell, "prediction": "present"}]}
            for n in calls}


def rej(call, kind="question", requested="Q1"):
    return {"kind": kind, "requested": requested, "reason": "повтор",
            "call": f"{call:04d}_F2_a1"}


class TestH3Report(unittest.TestCase):
    def test_t1_supports_h3(self):
        rows = [goal_rec(),
                row(21, "action_requested", descriptor="probe O4 T=2 H=1",
                    call=7),
                row(22, "probe_outcome", cell="O4 T=2 H=1", outcome="present",
                    masked=False, revealed=True, call=7)]
        rep = h3_report.analyze(rows, reqs(range(6, 11)), [])
        self.assertEqual(rep["status"], "supports_H3")
        self.assertTrue(rep["O1_valid_action"])
        self.assertTrue(rep["O2_goal_cell_probe"])
        self.assertEqual(rep["O3_q1h1_duplicates"], 0)

    def test_t2_partial_other_cell(self):
        rows = [goal_rec(),
                row(21, "action_requested", descriptor="probe O3 T=1 H=2",
                    call=7),
                row(22, "probe_outcome", cell="O3 T=1 H=2", outcome="present",
                    masked=False, revealed=True, call=7)]
        rep = h3_report.analyze(rows, reqs(range(6, 11)), [])
        self.assertEqual(rep["status"], "H3_partial")

    def test_t3_loop_does_not_confirm_h2(self):
        rows = [goal_rec()]
        rej_list = [rej(6), rej(6, kind="hypothesis", requested="H1"),
                    rej(7), rej(7, kind="hypothesis", requested="H1")]
        rep = h3_report.analyze(rows, reqs(range(6, 11)), rej_list)
        self.assertEqual(rep["status"], "H3_not_supported")
        self.assertFalse(rep["O1_valid_action"])
        self.assertEqual(rep["O3_q1h1_duplicates"], 4)

    def test_t4_ineligible_goal(self):
        rows = [goal_rec(eligible=False, reason="already_probed")]
        rep = h3_report.analyze(rows, reqs(range(6, 11)), [])
        self.assertEqual(rep["status"], "uninformative_goal")
        self.assertEqual(rep["reason"], "already_probed")

    def test_t4b_short_window(self):
        rows = [goal_rec()]
        rep = h3_report.analyze(rows, reqs([6, 7]), [])
        self.assertEqual(rep["status"], "uninformative_data")

    def test_t5_unclassified(self):
        rows = [goal_rec()]
        rep = h3_report.analyze(rows, reqs(range(6, 11)), [])
        self.assertEqual(rep["status"], "unclassified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
