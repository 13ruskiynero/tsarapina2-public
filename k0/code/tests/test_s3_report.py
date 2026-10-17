#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v36-A — офлайн-тесты механического классификатора возвратов (S3).

Проверяется scripts/s3_report.py на синтетических журналах (модель не вызывается):
T1: возврат после state_change объекта клетки — обоснован (state_change);
T2: возврат с PREDICT, отличающимся от наблюдённого исхода — обоснован;
T3: возврат с тем же PREDICT и без изменений состояния — необоснован;
T4: отклонённая попытка возврата считается отдельно и НЕ считается возвратом;
T5: возвратов нет — критерий вакуумно (s3_note заполнен).
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
    """Готовит пары prediction_pre/action_requested/probe_outcome с seq base..base+2."""
    return [
        row(base, "prediction_pre", cell=cell, outcome=pred),
        row(base + 1, "action_requested", label=f"P{base}",
            descriptor=f"probe {cell}", prediction_ref=base),
        row(base + 2, "probe_outcome", cell=cell, outcome=outcome,
            masked=False, revealed=True),
    ]


class TestS3Report(unittest.TestCase):
    def test_t1_state_change_justifies_return(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
        rows += probe_rows(10, "O3 T=1 H=0", "disappeared", "disappeared")
        rows += [row(20, "state_change",
                     changes=[{"object_id": "O3", "from": "present",
                               "to": "disappeared"}])]
        rows += probe_rows(21, "O3 T=2 H=0", "disappeared", "present")
        rows += [row(90, "verdict", h_label="H1", resolution="refuted")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["h1_cell"], "O3 T=2 H=0")
        self.assertEqual(rep["probes"], 3)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_justified_state_change"], 1)
        self.assertEqual(rep["returns_unjustified"], 0)

    def test_t2_new_prediction_justifies_return(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
        rows += probe_rows(10, "O3 T=2 H=0", "disappeared", "disappeared")
        rows += [row(90, "verdict", h_label="H1", resolution="refuted")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_justified_new_prediction"], 1)
        self.assertEqual(rep["returns_unjustified"], 0)

    def test_t3_same_prediction_without_change_is_unjustified(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
        rows += probe_rows(10, "O3 T=2 H=0", "present", "present")
        rows += [row(90, "verdict", h_label="H1", resolution="refuted")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 1)
        self.assertEqual(rep["returns_unjustified"], 1)
        self.assertEqual(rep["s3_unjustified_returns"], 1)

    def test_t4_rejected_attempt_is_not_a_return(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O3 T=2 H=0", "present", "present")
        rows += [row(10, "action_rejected", requested="probe O3 T=2 H=0",
                     reason="predict_invalid")]
        rows += [row(90, "verdict", h_label="H1", resolution="refuted")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 0)
        self.assertEqual(rep["attempts_rejected_total"], 1)
        self.assertEqual(rep["attempts_rejected_without_state_change"], 1)

    def test_t5_no_returns_vacuous(self):
        rows = [row(1, "hypothesis", label="H1", cell="O3 T=2 H=0")]
        rows += probe_rows(2, "O4 T=2 H=0", "present", "present")
        rows += [row(90, "verdict", h_label="H1", resolution="refuted")]
        rep = s3_report.analyze(rows)
        self.assertEqual(rep["returns_executed"], 0)
        self.assertTrue(rep["s3_note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
