#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v36-A — офлайн-тесты механического классификатора возвратов (S3).

Хронология во всех тестах реалистичная: гипотеза → первая проба → принятый
вердикт → принятое решение USING V1 → события ПОСЛЕ окна S3.

T1: возврат после state_change объекта клетки — обоснован (state_change);
T2: возврат с PREDICT, отличающимся от наблюдённого исхода — обоснован;
T3: возврат с тем же PREDICT и без изменений состояния — необоснован;
T4: отклонённая попытка возврата в окне — считается отдельно, не возврат;
T5: возвратов в окне нет — критерий вакуумно (s3_note заполнен);
T6: оба основания одновременно — оба счётчика по 1, общий = 1 (без задвоения);
T7: отклонённая попытка ДО более поздней пробы той же клетки — состояние
    берётся на момент попытки;
T8: повтор клетки H1 ДО принятого вердикта — НЕ возврат в S3 (pre_window);
T9: решение, записанное ДО вердикта, не становится якорем окна S3.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(K0_DIR / "scripts"))

import s3_report  # noqa: E402


def row(seq, typ, **kw):
    d = {"seq": seq, "type": typ}
    d.update(kw)
    return d


def probe_rows(base, cell, outcome, pred):
    """prediction_pre / action_requested / probe_outcome; seq base, base+1, base+2."""
    return [
        row(base, "prediction_pre", cell=cell, outcome=pred),
        row(base + 1, "action_requested", label=f"P{base}",
            descriptor=f"probe {cell}", prediction_ref=base),
        row(base + 2, "probe_outcome", cell=cell, outcome=outcome,
            masked=False, revealed=True),
    ]


def base_rows():
    """Гипотеза (1), первая проба H1-клетки (2..4), вердикт V1 (8), решение (12)."""
    rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
    rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
    rows += [row(8, "verdict", label="V1", h_label="H1", resolution="refuted")]
    rows += [row(12, "decision", descriptor="probe O4 T=2 H=0", using="V1")]
    return rows


class TestS3Report(unittest.TestCase):
    def test_t1_state_change_justifies_return(self):
        rows = base_rows()
        rows += probe_rows(14, "O3 T=1 H=0", "disappeared", "disappeared")
        rows += [row(18, "state_change",
                     changes=[{"object_id": "O3", "from": "present",
                               "to": "disappeared"}])]
        rows += probe_rows(20, "O3 T=2 H=0", "disappeared", "present")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["h1_cell"], "O3 T=2 H=0")
        self.assertEqual(rep["window_anchor"], "decision")
        self.assertEqual(rep["window_start_seq"], 12)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_justified_state_change"], 1)
        self.assertEqual(rep["returns_unjustified"], 0)

    def test_t2_new_prediction_justifies_return(self):
        rows = base_rows()
        rows += probe_rows(14, "O3 T=2 H=0", "disappeared", "disappeared")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_justified_new_prediction"], 1)
        self.assertEqual(rep["returns_unjustified"], 0)

    def test_t3_same_prediction_without_change_is_unjustified(self):
        rows = base_rows()
        rows += probe_rows(14, "O3 T=2 H=0", "present", "present")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_unjustified"], 1)
        self.assertEqual(rep["s3_unjustified_returns"], 1)

    def test_t4_rejected_attempt_is_not_a_return(self):
        rows = base_rows()
        rows += [row(16, "action_rejected", requested="probe O3 T=2 H=0",
                     reason="predict_invalid")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 0)
        self.assertEqual(rep["attempts_rejected_total"], 1)
        self.assertEqual(rep["attempts_rejected_without_state_change"], 1)

    def test_t5_no_returns_vacuous(self):
        rows = base_rows()
        rows += probe_rows(14, "O4 T=2 H=0", "present", "present")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 0)
        self.assertTrue(rep["s3_note"])

    def test_t6_both_grounds_counted_independently(self):
        rows = base_rows()
        rows += probe_rows(14, "O3 T=1 H=0", "disappeared", "disappeared")
        rows += [row(18, "state_change",
                     changes=[{"object_id": "O3", "from": "present",
                               "to": "disappeared"}])]
        rows += probe_rows(20, "O3 T=2 H=0", "disappeared", "disappeared")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_justified_state_change"], 1)
        self.assertEqual(rep["returns_justified_new_prediction"], 1)
        self.assertEqual(rep["returns_justified_total"], 1)   # объединение, без задвоения
        self.assertEqual(rep["returns_unjustified"], 0)

    def test_t7_attempt_uses_state_at_attempt_time(self):
        # state_change (6) — между первой пробой (4) и попыткой (16);
        # позже (20..22) — ещё одна проба той же клетки. Корректный ответ для
        # попытки: состояние менялось до неё (True); дефект «будущего» дал бы
        # False, взяв последнюю пробу (22) как точку отсчёта.
        rows = base_rows()
        rows += [row(6, "state_change",
                     changes=[{"object_id": "O3", "from": "present",
                               "to": "disappeared"}])]
        rows += [row(16, "action_rejected", requested="probe O3 T=2 H=0",
                     reason="predict_invalid")]
        rows += probe_rows(20, "O3 T=2 H=0", "disappeared", "present")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["attempts_rejected_total"], 1)
        self.assertTrue(rep["attempts_detail"][0]["state_changed_since"])
        self.assertEqual(rep["returns_justified_state_change"], 1)

    def test_t8_repeat_before_verdict_is_not_a_return(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
        rows += probe_rows(10, "O3 T=2 H=0", "present", "present")   # до вердикта
        rows += [row(20, "verdict", label="V1", h_label="H1", resolution="refuted")]
        rows += [row(24, "decision", descriptor="probe O4 T=2 H=0", using="V1")]
        rows += probe_rows(26, "O4 T=2 H=0", "present", "present")
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["window_anchor"], "decision")
        self.assertEqual(rep["returns_executed"], 0)          # в окне возвратов нет
        self.assertEqual(rep["pre_window_repeats"], 1)        # повтор до окна — отдельно

    def test_t9_decision_before_verdict_not_an_anchor(self):
        # решение записано ДО вердикта: якорем быть не может; окно — от вердикта.
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")     # P1 (4)
        rows += [row(6, "decision", descriptor="probe O4 T=2 H=0", using="V1")]
        rows += probe_rows(8, "O3 T=2 H=0", "present", "present")     # до вердикта
        rows += [row(14, "verdict", label="V1", h_label="H1", resolution="refuted")]
        rows += probe_rows(16, "O3 T=2 H=0", "present", "present")    # после вердикта
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["window_anchor"], "verdict")
        self.assertEqual(rep["window_start_seq"], 14)
        self.assertEqual(rep["pre_window_repeats"], 1)                # проба seq 10
        self.assertEqual(rep["returns_executed"], 1)                  # проба seq 18


if __name__ == "__main__":
    unittest.main(verbosity=2)
