#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты журнала K0 (§11; контракты §3/§7). Без вызовов модели.

Все тесты пишут ТОЛЬКО во временные каталоги (tempfile); рабочий комплекс
не затрагивается. Запуск:
    python3 lab/autonomy/k0/code/tests/test_journal.py -v
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
from journal import (  # noqa: E402
    Journal, JournalError, read_journal, run_dir_for, stop_requested,
    write_derived_once,
)


class TestJournalBasics(unittest.TestCase):
    """§11: структура каталогов, append-only, seq, запрет перезаписи."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", 101)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_creates_layout(self):
        j = Journal(self.run).open()
        for sub in ("raw", "raw/calls", "derived", "passport"):
            self.assertTrue((self.run / sub).is_dir(), sub)
        j.close()

    def test_append_read_seq(self):
        j = Journal(self.run).open()
        j.history_shown(101, ["t01", "t02"])
        j.note("первая")
        j.note("вторая")
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["seq"] for r in rows], [1, 2, 3])
        self.assertEqual(rows[0]["type"], "history_shown")
        self.assertEqual(rows[0]["origin"], "none")
        self.assertEqual(rows[2]["type"], "note")
        self.assertEqual(rows[2]["origin"], "agent")
        self.assertEqual(rows[2]["label_by"], "none")

    def test_no_rewrite_on_reopen(self):
        j = Journal(self.run).open()
        j.note("x")
        j.close()
        with self.assertRaises(JournalError):
            Journal(self.run).open()

    def test_write_requires_open(self):
        with self.assertRaises(JournalError):
            Journal(self.run).note("без open")

    def test_registration_records(self):
        j = Journal(self.run).open()
        j.question(1, "текст?", "t01")
        j.hypothesis(1, 1, "гип", Cell("O2", 2, 1), "present")
        j.rejected(1, "не подходит")
        j.decision("probe O2 T=2 H=1", 1)
        j.final("правило")
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual(rows[0]["label"], "Q1")
        self.assertEqual(rows[0]["label_by"], "agent")
        self.assertEqual(rows[1]["label"], "H1")
        self.assertEqual(rows[1]["of"], "Q1")
        self.assertEqual(rows[1]["cell"], "O2 T=2 H=1")
        self.assertEqual(rows[2]["label_by"], "none")
        self.assertEqual(rows[3]["using"], "V1")
        self.assertEqual(rows[4]["type"], "final")

    def test_fact_records_origin_none(self):
        j = Journal(self.run).open()
        j.mode_violation("question", 3)
        j.stop("бюджет исчерпан")
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual(rows[0]["origin"], "none")
        self.assertEqual(rows[0]["reason"], "invalid_mode")
        self.assertEqual(rows[1]["type"], "stop")


class TestActionContracts(unittest.TestCase):
    """§3/§7/§11 (ред. 23): контракты исполнений и записей."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", 101)
        self.cell = Cell("O2", 2, 1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_probe_cycle(self):
        j = Journal(self.run).open()
        s_pre = j.prediction_pre(self.cell, "present")
        self.assertIsInstance(s_pre, int)
        ar = j.action_requested("probe O2 T=2 H=1", prediction_ref=s_pre, p_label="P1")
        j.probe_outcome(self.cell, "present", masked=False, revealed=True)
        j.budget(1, 15, action_ref=ar["seq"])
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["type"] for r in rows],
                         ["prediction_pre", "action_requested", "probe_outcome", "budget"])
        self.assertEqual(rows[1]["label"], "P1")
        self.assertEqual(rows[1]["label_by"], "driver")
        self.assertEqual(rows[1]["prediction_ref"], s_pre)
        self.assertEqual(rows[3]["action_ref"], ar["seq"])
        self.assertEqual(rows[3]["cost"], 1)
        self.assertEqual(rows[3]["remaining"], 15)

    def test_reset_cycle(self):
        j = Journal(self.run).open()
        ar = j.action_requested("reset", prediction_ref=None, p_label=None)
        self.assertEqual(ar["label_by"], "none")
        self.assertIsNone(ar["label"])
        j.state_change(action_ref=ar["seq"], restored=["O1"])
        j.budget(1, 14, action_ref=ar["seq"])
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        sc = rows[1]
        self.assertEqual(sc["type"], "state_change")
        self.assertEqual(sc["restored"], ["O1"])
        self.assertEqual(sc["action_ref"], ar["seq"])
        self.assertNotIn("prediction_ref", rows[0])

    def test_probe_transition_state_change(self):
        # форма changes для переходов probe/repeat — допущение A8
        j = Journal(self.run).open()
        s_pre = j.prediction_pre(Cell("O1", 2, 1), "disappeared")
        ar = j.action_requested("probe O1 T=2 H=1", prediction_ref=s_pre, p_label="P1")
        j.state_change(action_ref=ar["seq"],
                       changes=[{"object_id": "O1", "from": "present", "to": "disappeared"}])
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual(rows[2]["changes"][0]["object_id"], "O1")

    def test_rejection_creates_no_execution_records(self):
        j = Journal(self.run).open()
        j.action_rejected("probe O2 T=2 H=1", "predict_invalid")
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["type"] for r in rows], ["action_rejected"])
        self.assertNotIn("budget", [r["type"] for r in rows])

    def test_distinguish_fields(self):
        j = Journal(self.run).open()
        j.probe_outcome(self.cell, "present", masked=False, revealed=True,
                        distinguish_confirmed=["H1", "H2"], distinguish_ok=True)
        j.action_rejected("probe O2 T=2 H=1", "distinguish_failed",
                          distinguish_confirmed=["H1"], distinguish_ok=False)
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual(rows[0]["distinguish_confirmed"], ["H1", "H2"])
        self.assertTrue(rows[0]["distinguish_ok"])
        self.assertEqual(rows[1]["distinguish_confirmed"], ["H1"])
        self.assertFalse(rows[1]["distinguish_ok"])
        # обычная проба без DISTINGUISH — полей нет (контракт §10)
        j2 = Journal(run_dir_for(self.base, "K0-M1", 202)).open()
        j2.probe_outcome(self.cell, "present", masked=False, revealed=True)
        j2.close()
        rows2 = read_journal(run_dir_for(self.base, "K0-M1", 202) / "raw" / "journal.jsonl")
        self.assertNotIn("distinguish_ok", rows2[0])

    def test_verdict_and_check(self):
        j = Journal(self.run).open()
        v = j.verdict("V1", 1, "supported", 1)
        j.verdict_check("match", verdict_ref=v["seq"])
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["type"] for r in rows], ["verdict", "verdict_check"])
        self.assertEqual(rows[1]["verdict_ref"], v["seq"])
        self.assertEqual(rows[0]["label_by"], "driver")

    def test_verdict_check_invalid_value(self):
        j = Journal(self.run).open()
        with self.assertRaises(JournalError):
            j.verdict_check("maybe", 1)
        j.close()

    def test_forecast_status_values(self):
        j = Journal(self.run).open()
        j.forecast_status("F1", 1, "ok")
        j.forecast_status("F1", 2, "invalid_retry")
        j.forecast_status("F3", 2, "invalid_final")
        with self.assertRaises(JournalError):
            j.forecast_status("F1", 1, "wrong")
        j.close()
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["status"] for r in rows],
                         ["ok", "invalid_retry", "invalid_final"])


class TestDerivedAndStop(unittest.TestCase):
    """§11: derived (ничто не перезаписывается) и STOP-файл."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", 101)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_derived_once(self):
        p = write_derived_once(self.run, "e_set.json", {"E": ["O2 T=2 H=1"]})
        self.assertTrue(p.exists())
        with self.assertRaises(JournalError):
            write_derived_once(self.run, "e_set.json", {"E": []})

    def test_stop_flag(self):
        self.assertFalse(stop_requested(self.run))
        (self.run).mkdir(parents=True, exist_ok=True)
        (self.run / "STOP").write_text("", encoding="utf-8")
        self.assertTrue(stop_requested(self.run))


if __name__ == "__main__":
    unittest.main(verbosity=2)
