#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты сессии/оркестратора K0 (§6/§12/§10). Без вызовов модели.

Все прогоны — во временных каталогах; «агент» — детерминированный скрипт.
Запуск:
    python3 lab/autonomy/k0/code/tests/test_session.py -v
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]        # .../k0/code
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(CODE_DIR))

from world import Cell, cell_outcome, load_battery  # noqa: E402
from journal import Journal, JournalError, read_journal, run_dir_for  # noqa: E402
from channel import make_respond  # noqa: E402
from auditor import audit_run  # noqa: E402
from session import Session, SessionError, STOP_FILE_REASON  # noqa: E402

ARTIFACTS = K0_DIR / "artifacts"
SEED = 101


def battery():
    return [item.cell for item in load_battery(ARTIFACTS / "heldout_battery.json")]


F1_ALL_PRESENT = "\n".join(f"PREDICT: {c.as_text()} = present" for c in sorted(battery()))
F3_CORRECT = "\n".join(f"PREDICT: {c.as_text()} = {cell_outcome(c)}" for c in sorted(battery()))

REG_TEXT = "\n".join([
    "QUESTION Q1: почему объекты исчезают? REF: t01",
    "HYPOTHESIS H1 OF Q1: правило T при материале A PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H2 OF Q1: скрытый признак p PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H3 OF Q1: материал m PREDICT: O2 T=2 H=1 = disappeared",
])
BLOCK1 = "PREDICT: O2 T=2 H=1 = disappeared\nACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2,H3"
BLOCK2 = "\n".join([
    "VERDICT: H1 supported AFTER P1",
    "DECISION: probe O4 T=2 H=1 USING V1",
    "PREDICT: O4 T=2 H=1 = present",
    "ACTION: probe O4 T=2 H=1",
])
FINAL_TEXT = "FINAL: объекты с материалом A исчезают при T=2, остальные нет."


class FullScript:
    """Полный сквозной сценарий: 16 действий (P1, P2, 14 reset), затем F3/F4."""

    def __init__(self, f4_response: str = FINAL_TEXT):
        self.calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}
        self.f4_response = f4_response

    def __call__(self, phase, ctx, attempt):
        self.calls[phase] += 1
        if phase == "F1":
            return F1_ALL_PRESENT
        if phase == "F2":
            i = self.calls["F2"]
            if i == 1:
                return REG_TEXT
            if i == 2:
                return BLOCK1
            if i == 3:
                return BLOCK2
            return "ACTION: reset"
        if phase == "F3":
            return F3_CORRECT
        if phase == "F4":
            return self.f4_response
        raise AssertionError(phase)


class SessionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", SEED)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        return read_journal(self.run / "raw" / "journal.jsonl")


class TestFullChain(SessionCase):
    """Сквозной синтетический путь F1 → F2 → F3 → F4 → F5."""

    def _run(self, **opts):
        script = FullScript(**opts)
        sess = Session(self.run, script, seed=SEED)
        res = sess.run()
        return sess, script, res

    def test_status_and_calls(self):
        sess, script, res = self._run()
        self.assertEqual(res.status, "completed")
        self.assertEqual(sess.state, "DONE")
        self.assertEqual(script.calls, {"F1": 1, "F2": 17, "F3": 1, "F4": 1})
        self.assertTrue(res.final_present)
        # после завершения сессия не перезапускается
        with self.assertRaises(SessionError):
            sess.run()

    def test_journal_shape_and_budget(self):
        sess, script, res = self._run()
        rows = self.rows()
        types = [r["type"] for r in rows]
        self.assertEqual(rows[0]["type"], "history_shown")
        self.assertEqual(types.count("action_requested"), 16)
        self.assertEqual(types.count("probe_outcome"), 2)
        self.assertEqual(types.count("budget"), 16)
        self.assertEqual(types.count("prediction_before"), 9)
        self.assertEqual(types.count("prediction_after"), 9)
        self.assertEqual(types.count("question"), 1)
        self.assertEqual(types.count("hypothesis"), 3)
        self.assertEqual(types.count("verdict"), 1)
        self.assertEqual(types.count("verdict_check"), 1)
        self.assertEqual(types.count("decision"), 1)
        self.assertEqual(types.count("final"), 1)
        # бюджет: ровно 16 расходов по 1; остаток строго убывает до 0
        budgets = [r for r in rows if r["type"] == "budget"]
        self.assertTrue(all(r["cost"] == 1 for r in budgets))
        self.assertEqual([r["remaining"] for r in budgets], list(range(15, -1, -1)))
        # 17-й ход агенту не запрашивался (см. test_status_and_calls: F2 == 17)

    def test_verdict_check_match(self):
        sess, script, res = self._run()
        rows = self.rows()
        vc = [r for r in rows if r["type"] == "verdict_check"][0]
        self.assertEqual(vc["value"], "match")

    def test_audit_and_metrics(self):
        sess, script, res = self._run()
        self.assertIsNotNone(res.audit)
        a = res.audit
        self.assertTrue(a.structural_full)
        self.assertTrue(a.agent_full)
        self.assertTrue(a.agent_valid_full)
        self.assertEqual(a.correct_s4, "match")
        self.assertFalse(a.not_checked)
        self.assertTrue(a.s6_complete)       # решение 2026-10-15 (K0_S6_DECISION_ACT.md); A13 открыт
        self.assertEqual(res.metrics["n_E"], 7)
        self.assertAlmostEqual(res.metrics["acc_before"], 3 / 7, places=9)
        self.assertAlmostEqual(res.metrics["acc_after"], 1.0, places=9)
        self.assertAlmostEqual(res.metrics["improvement"], 4 / 7, places=9)
        self.assertTrue(res.metrics["o1_pass"])

    def test_context_no_leak_before_reveal(self):
        sess, script, res = self._run()
        ctxs = sess.sent_contexts
        f1 = [c for c in ctxs if c.phase == "F1"]
        self.assertEqual(len(f1), 1)
        self.assertEqual(f1[0].observations, ())
        # история наблюдений не содержит батарейных клеток
        batch = set(battery())
        for r in f1[0].history:
            self.assertNotIn(Cell(r["object_id"], r["T"], r["H"]), batch)
        f2 = [c for c in ctxs if c.phase == "F2"]
        self.assertEqual(f2[0].observations, ())                 # до проб — пусто
        self.assertIn(("O2 T=2 H=1", "present"), f2[2].observations)  # после исполнения P1 (ход 3)
        f3 = [c for c in ctxs if c.phase == "F3"][0]
        self.assertEqual({t[0] for t in f3.observations},
                         {"O2 T=2 H=1", "O4 T=2 H=1"})          # только раскрытые
        e_cells = {c.as_text() for c in battery()} - {"O2 T=2 H=1", "O4 T=2 H=1"}
        for t in f3.observations:
            self.assertNotIn(t[0], e_cells)

    def test_pre_record_not_rewritten_after_reveal(self):
        sess, script, res = self._run()
        rows = self.rows()
        pre = [r for r in rows if r["type"] == "prediction_pre"
               and r["cell"] == "O2 T=2 H=1"][0]
        self.assertEqual(pre["outcome"], "disappeared")          # прогноз агента (неверный)
        out = [r for r in rows if r["type"] == "probe_outcome"
               and r["cell"] == "O2 T=2 H=1"][0]
        self.assertEqual(out["outcome"], "present")              # фактический исход
        ar = [r for r in rows if r["type"] == "action_requested" and r["label"] == "P1"][0]
        self.assertLess(pre["seq"], ar["seq"])
        self.assertLess(ar["seq"], out["seq"])

    def test_artifacts_written(self):
        sess, script, res = self._run()
        for name in ("e_set.json", "forecasts.json", "metrics.json", "audit.json"):
            self.assertTrue((self.run / "derived" / name).exists(), name)

    def test_no_final_still_completes(self):
        sess, script, res = self._run(f4_response="NOTES: без итоговой формулировки")
        self.assertEqual(res.status, "completed")
        self.assertFalse(res.final_present)
        self.assertFalse(res.metrics["final_present"])
        rows = self.rows()
        self.assertEqual([r for r in rows if r["type"] == "final"], [])


class TestStopFile(SessionCase):
    """§12: STOP-файл — немедленная остановка; действия агента не исполняются."""

    def test_stop_halts_immediately(self):
        calls = {"n": 0}

        def respond(phase, ctx, attempt):
            calls["n"] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                (self.run / "STOP").write_text("", encoding="utf-8")
                return "ACTION: reset"
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, STOP_FILE_REASON)
        self.assertEqual(sess.state, "HALTED")
        self.assertEqual(calls["n"], 2)                     # F1 + первый F2-запрос
        rows = self.rows()
        types = [r["type"] for r in rows]
        self.assertEqual(types[-1], "stop")
        self.assertNotIn("action_requested", types)          # reset не исполнен
        with self.assertRaises(SessionError):
            sess.run()                                       # сессия не продолжается


class TestKReached(SessionCase):
    """§12: «K достигнут (проб не осталось)» — нормальное завершение F2."""

    def test_k_reached_completes_cycle(self):
        cells = sorted(battery())
        calls = {"F2": 0, "F1": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                c = cells[calls["F2"] - 1]
                return f"PREDICT: {c.as_text()} = present\nACTION: probe {c.as_text()}"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        self.assertEqual(calls["F2"], 9)                     # ровно 9 проб — K достигнут
        rows = self.rows()
        self.assertEqual([r["type"] for r in rows].count("probe_outcome"), 9)
        eset = res.metrics
        self.assertEqual(eset["n_E"], 0)
        self.assertFalse(eset["e_min_ok"])
        self.assertFalse(eset["o1_pass"])
        self.assertIsNone(eset["acc_before"])


class TestInvalidResponses(SessionCase):
    """A20: невалидные ответы не исполняются; предохранитель F2."""

    def test_invalid_f2_guard(self):
        calls = {"n": 0}

        def respond(phase, ctx, attempt):
            calls["n"] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            return "чепуха вне грамматики"

        sess = Session(self.run, respond, seed=SEED, max_invalid_f2=3)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "too_many_invalid_f2")
        self.assertEqual(calls["n"], 4)                      # F1 + 3 мусорных F2
        rows = self.rows()
        self.assertNotIn("action_requested", [r["type"] for r in rows])

    def test_invalid_final_f1(self):
        def respond(phase, ctx, attempt):
            return "чепуха вне грамматики"

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "invalid_final F1")
        rows = self.rows()
        fs = [r for r in rows if r["type"] == "forecast_status"]
        self.assertEqual([(r["phase"], r["attempt"], r["status"]) for r in fs],
                         [("F1", 1, "invalid_retry"), ("F1", 2, "invalid_retry"),
                          ("F1", 3, "invalid_final")])
        self.assertTrue((self.run / "derived" / "forecasts.json").exists())
        self.assertEqual(rows[-1]["type"], "stop")


class TestN8MultiBlock(SessionCase):
    """N8 (дополнение №1 v1.0): несколько блоков действий в одном ответе F2."""

    def _run_script(self, f2_map, **kwargs):
        calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                i = calls["F2"]
                if i in f2_map:
                    return f2_map[i]
                return "ACTION: reset"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED, **kwargs)
        res = sess.run()
        return sess, calls, res

    def test_two_blocks_executed_in_order(self):
        text2 = ("PREDICT: O2 T=2 H=1 = present\n"
                 "ACTION: probe O2 T=2 H=1\n"
                 "QUESTION Q2: продолжение исследования? REF: t01\n"
                 "PREDICT: O4 T=2 H=1 = present\n"
                 "ACTION: probe O4 T=2 H=1")
        sess, calls, res = self._run_script({1: REG_TEXT, 2: text2})
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        types = [r["type"] for r in rows]
        self.assertEqual(types.count("probe_outcome"), 2)
        self.assertEqual(types.count("action_requested"), 16)
        by_seq = {r["seq"]: r for r in rows}
        p1 = [r for r in rows if r["type"] == "action_requested" and r["label"] == "P1"][0]
        p2 = [r for r in rows if r["type"] == "action_requested" and r["label"] == "P2"][0]
        pre1 = by_seq[p1["prediction_ref"]]
        pre2 = by_seq[p2["prediction_ref"]]
        self.assertEqual(pre1["cell"], "O2 T=2 H=1")
        self.assertEqual(pre2["cell"], "O4 T=2 H=1")
        self.assertLess(pre1["seq"], p1["seq"])
        self.assertLess(p1["seq"], pre2["seq"])          # порядок появления блоков
        self.assertLess(pre2["seq"], p2["seq"])
        o1 = [r for r in rows if r["type"] == "probe_outcome" and r["cell"] == "O2 T=2 H=1"][0]
        o2 = [r for r in rows if r["type"] == "probe_outcome" and r["cell"] == "O4 T=2 H=1"][0]
        self.assertLess(o1["seq"], o2["seq"])

    def test_second_block_invalid_partial_execution(self):
        text2 = ("PREDICT: O2 T=2 H=1 = present\n"
                 "ACTION: probe O2 T=2 H=1\n"
                 "QUESTION Q2: продолжение? REF: t01\n"
                 "ACTION: probe O4 T=2 H=1\n"
                 "NOTE: не должна пройти")
        sess, calls, res = self._run_script({1: REG_TEXT, 2: text2})
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        types = [r["type"] for r in rows]
        self.assertEqual(types.count("probe_outcome"), 1)          # блок 1 исполнен
        rej = [r for r in rows if r["type"] == "action_rejected"]
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0]["reason"], "predict_invalid")      # блок 2 отвергнут
        self.assertEqual(rej[0]["requested"], "probe O4 T=2 H=1")
        self.assertEqual(types.count("note"), 0)                   # атомарность NOTE

    def test_budget_stop_between_blocks(self):
        last = ("ACTION: reset\n"
                "QUESTION Q2: да? REF: t01\n"
                "PREDICT: O2 T=2 H=1 = present\n"
                "ACTION: probe O2 T=2 H=1")
        sess, calls, res = self._run_script({17: last})
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        budgets = [r for r in rows if r["type"] == "budget"]
        self.assertEqual(len(budgets), 16)
        self.assertEqual(budgets[-1]["remaining"], 0)
        descs = [r.get("descriptor") for r in rows if r["type"] == "action_requested"]
        self.assertNotIn("probe O2 T=2 H=1", descs)                # блок 2 не исполнен
        self.assertEqual([r for r in rows if r["type"] == "probe_outcome"], [])

    def test_decision_using_future_verdict_session(self):
        hop2 = "PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1"
        hop3 = ("DECISION: probe O3 T=2 H=1 USING V1\n"
                "PREDICT: O3 T=2 H=1 = present\n"
                "ACTION: probe O3 T=2 H=1\n"
                "FINAL: разделитель\n"
                "VERDICT: H1 supported AFTER P1")
        sess, calls, res = self._run_script({1: REG_TEXT, 2: hop2, 3: hop3})
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        rej = [r for r in rows if r["type"] == "action_rejected"]
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0]["reason"], "decision_invalid")     # V1 объявлен ниже
        self.assertEqual(rej[0]["requested"], "probe O3 T=2 H=1")
        descs = [r.get("descriptor") for r in rows if r["type"] == "action_requested"]
        self.assertNotIn("probe O3 T=2 H=1", descs)                # блок не исполнен
        self.assertEqual(len([r for r in rows if r["type"] == "verdict"]), 1)  # вердикт записан
        vc = [r for r in rows if r["type"] == "verdict_check"]
        self.assertEqual(len(vc), 1)
        self.assertEqual(vc[0]["value"], "match")


class TestErrorsAndDamage(SessionCase):
    """Ошибки и частично записанные журналы: остановка, без «ремонта»."""

    def test_partial_record_detected(self):
        j = Journal(self.run).open()
        j.note("ок")
        j.close()
        p = self.run / "raw" / "journal.jsonl"
        with open(p, "a", encoding="utf-8") as f:
            f.write('{"seq": 2, "type": "que')
        with self.assertRaises(JournalError):
            read_journal(p)
        with self.assertRaises(JournalError):
            audit_run(self.run)

    def test_failed_session_not_resumable(self):
        def respond(phase, ctx, attempt):
            raise RuntimeError("обрыв канала")

        sess = Session(self.run, respond, seed=SEED)
        with self.assertRaises(SessionError):
            sess.run()
        self.assertEqual(sess.state, "FAILED")
        with self.assertRaises(SessionError):
            sess.run()

    def test_nonempty_run_dir_refused(self):
        j = Journal(self.run).open()
        j.note("чужой прогон")
        j.close()
        p = self.run / "raw" / "journal.jsonl"
        before = p.read_bytes()

        def respond(phase, ctx, attempt):
            return FINAL_TEXT

        sess = Session(self.run, respond, seed=SEED)
        with self.assertRaises(SessionError):
            sess.run()
        self.assertEqual(sess.state, "FAILED")
        self.assertEqual(p.read_bytes(), before)             # журнал не изменён


class TestLabelEcho(SessionCase):
    """§7 «эхо меток»: актуальные последние номера Q/H/P/V в контексте."""

    def test_echo_labels_in_context(self):
        script = FullScript()
        sess = Session(self.run, script, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        f1 = [c for c in sess.sent_contexts if c.phase == "F1"][0]
        self.assertEqual(f1.last_labels, (0, 0, 0, 0))
        f2 = [c for c in sess.sent_contexts if c.phase == "F2"]
        self.assertEqual(f2[0].last_labels, (0, 0, 0, 0))     # до регистраций
        self.assertEqual(f2[1].last_labels, (1, 3, 0, 0))     # после Q1,H1..H3
        self.assertEqual(f2[2].last_labels, (1, 3, 1, 0))     # после P1
        self.assertEqual(f2[3].last_labels, (1, 3, 2, 1))     # после V1 и P2
        self.assertEqual(f2[0].observations, ())
        self.assertEqual(f2[1].observations, ())              # эхо не несёт исходов
        f4 = [c for c in sess.sent_contexts if c.phase == "F4"][0]
        self.assertEqual(f4.last_labels, (1, 3, 2, 1))

    def test_agent_uses_echo_for_next_labels(self):
        class EchoScript:
            def __init__(self):
                self.calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

            def __call__(self, phase, ctx, attempt):
                self.calls[phase] += 1
                if phase == "F1":
                    return F1_ALL_PRESENT
                if phase == "F2":
                    i = self.calls["F2"]
                    if i == 1:
                        return REG_TEXT
                    if i == 2:
                        q, h, p, v = ctx.last_labels
                        return (f"HYPOTHESIS H{h + 1} OF Q{q}: продолжение по эху "
                                "PREDICT: O2 T=2 H=1 = present\n"
                                "PREDICT: O2 T=2 H=1 = present\n"
                                "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2,H3")
                    return "ACTION: reset"
                if phase == "F3":
                    return F3_CORRECT
                if phase == "F4":
                    return FINAL_TEXT
                raise AssertionError(phase)

        sess = Session(self.run, EchoScript(), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        labels = [r["label"] for r in rows if r["type"] == "hypothesis"]
        self.assertEqual(labels, ["H1", "H2", "H3", "H4"])    # H4 построена по эху
        f2 = [c for c in sess.sent_contexts if c.phase == "F2"]
        self.assertEqual(f2[2].last_labels, (1, 4, 1, 0))     # эхо обновилось


class TestCallLogAndPassport(SessionCase):
    """§11: raw/calls (сырые пары запрос/ответ) и passport/."""

    def _full_run(self, f4_response=FINAL_TEXT):
        script = FullScript(f4_response=f4_response)
        sess = Session(self.run, script, seed=SEED)
        res = sess.run()
        return sess, script, res

    def test_requests_and_responses_saved(self):
        self._full_run()
        d = self.run / "raw" / "calls"
        files = sorted(p.name for p in d.iterdir())
        req = [f for f in files if f.endswith(".request.txt")]
        resp = [f for f in files if f.endswith(".response.txt")]
        meta = [f for f in files if f.endswith(".meta.json")]
        self.assertEqual(len(req), 20)                        # 20 вызовов
        self.assertEqual(len(resp), 20)
        self.assertEqual(len(meta), 20)                       # O1: мета на попытку
        self.assertEqual(len(files), 60)
        first_req = json.loads((d / "0001_F1_a1.request.txt").read_text(encoding="utf-8"))
        self.assertEqual(first_req["phase"], "F1")
        self.assertEqual(first_req["last_labels"], [0, 0, 0, 0])
        self.assertEqual((d / "0001_F1_a1.response.txt").read_text(encoding="utf-8"),
                         F1_ALL_PRESENT)
        self.assertEqual((d / "0020_F4_a1.response.txt").read_text(encoding="utf-8"),
                         FINAL_TEXT)
        m1 = json.loads((d / "0001_F1_a1.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(m1["class"], "answered")

    def test_request_without_response_on_channel_error(self):
        def respond(phase, ctx, attempt):
            raise RuntimeError("обрыв канала")

        sess = Session(self.run, respond, seed=SEED)
        with self.assertRaises(SessionError):
            sess.run()
        d = self.run / "raw" / "calls"
        self.assertTrue((d / "0001_F1_a1.request.txt").exists())
        self.assertFalse((d / "0001_F1_a1.response.txt").exists())

    def test_passport_completed(self):
        self._full_run()
        pp = json.loads((self.run / "passport" / "passport.json").read_text(encoding="utf-8"))
        self.assertEqual(pp["series"], "K0-M3")
        self.assertEqual(pp["seed"], SEED)
        self.assertEqual(pp["status"], "completed")
        self.assertEqual(pp["respond_calls"], 20)
        self.assertEqual(pp["n_E"], 7)
        self.assertEqual(pp["malformed"], 0)
        self.assertEqual(pp["protocol_version"], "v33")
        self.assertEqual(pp["protocol_sha256"],
                         hashlib.sha256((K0_DIR / "K0_PROTOCOL_v33.md").read_bytes()).hexdigest())
        self.assertEqual(pp["protocol_base_sha256"],
                         hashlib.sha256((K0_DIR / "K0_PROTOCOL.md").read_bytes()).hexdigest())

    def test_passport_halted(self):
        def respond(phase, ctx, attempt):
            if phase == "F1":
                return F1_ALL_PRESENT
            (self.run / "STOP").write_text("", encoding="utf-8")
            return "ACTION: reset"

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        pp = json.loads((self.run / "passport" / "passport.json").read_text(encoding="utf-8"))
        self.assertEqual(pp["status"], "halted")
        self.assertEqual(pp["stop_reason"], STOP_FILE_REASON)

    def test_malformed_counter(self):
        calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                if calls["F2"] == 1:
                    return "ACTION: probe O2 T=2 H=1"         # нет PREDICT → отказ
                return "ACTION: reset"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        rej = [r for r in rows if r["type"] == "action_rejected"]
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0]["reason"], "predict_invalid")
        self.assertEqual(rej[0]["requested"], "probe O2 T=2 H=1")
        self.assertEqual(res.metrics["malformed"], 1)         # §7: счётчик = число action_rejected
        pp = json.loads((self.run / "passport" / "passport.json").read_text(encoding="utf-8"))
        self.assertEqual(pp["malformed"], 1)
        # N6 (дополнение №1): отказы действий НЕ дублируются в rejections.json
        rej = json.loads((self.run / "derived" / "rejections.json").read_text(encoding="utf-8"))
        self.assertEqual(rej, [])


class TestAddendumNorms(SessionCase):
    """Нормы дополнения №1 v1.0: N1/N2 (клетка) и N6 (rejections.json)."""

    def test_verdict_no_cell_match_not_checked(self):
        calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                i = calls["F2"]
                if i == 1:
                    return REG_TEXT
                if i == 2:
                    return ("PREDICT: O4 T=2 H=1 = present\n"
                            "ACTION: probe O4 T=2 H=1")      # проба не на клетке гипотез
                if i == 3:
                    return "VERDICT: H1 supported AFTER P1"
                return "ACTION: reset"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        rows = self.rows()
        self.assertEqual(len([r for r in rows if r["type"] == "verdict"]), 1)
        self.assertEqual(len([r for r in rows if r["type"] == "verdict_check"]), 0)
        self.assertEqual(res.audit.correct_s4, "not_checked")
        self.assertTrue(res.audit.not_checked)
        self.assertEqual(res.audit.status_hint, "inconclusive_not_checked")

    def test_rejections_json(self):
        calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                i = calls["F2"]
                if i == 1:
                    return REG_TEXT
                if i == 2:
                    return ("QUESTION Q3: третий вопрос REF: t01\n"   # пропуск Q2 → отказ
                            "VERDICT: H9 supported AFTER P1\n"        # H9 нет → отказ
                            "ACTION: reset")
                return "ACTION: reset"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        rej = json.loads((self.run / "derived" / "rejections.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(len(rej), 2)
        self.assertEqual(sorted(r["kind"] for r in rej), ["question", "verdict"])
        q_entry = [r for r in rej if r["kind"] == "question"][0]
        self.assertTrue(q_entry["reason"].startswith("пропуск"))
        self.assertEqual(q_entry["call"], "0003_F2_a1")
        self.assertEqual(q_entry["phase"], "F2")
        self.assertFalse(q_entry["created"])
        v_entry = [r for r in rej if r["kind"] == "verdict"][0]
        self.assertTrue(v_entry["reason"])


class MetaChannel:
    """Канал с управляемыми метаданными (для токен-лимитов O1)."""

    def __init__(self, queue, meta=None):
        self.queue = list(queue)
        self.meta = meta
        self.sent = []
        self.last_meta = None

    def send(self, phase, attempt, prompt):
        self.sent.append((phase, attempt, prompt))
        self.last_meta = self.meta
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestO1Limits(SessionCase):
    """O1: стопы по токенам/вызовам/времени (мета-счётчики канала)."""

    def test_prompt_over_limit(self):
        ch = MetaChannel([F1_ALL_PRESENT], meta={"prompt_eval_count": 5000, "eval_count": 10})
        sess = Session(self.run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "prompt_over_limit")

    def test_token_budget_exhausted(self):
        ch = MetaChannel([F1_ALL_PRESENT], meta={"prompt_eval_count": 60, "eval_count": 60})
        sess = Session(self.run, make_respond(ch), seed=SEED, max_total_tokens=100)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "token_budget_exhausted")
        metas = sorted((self.run / "raw" / "calls").glob("*.meta.json"))
        rec = json.loads(metas[0].read_text(encoding="utf-8"))
        self.assertEqual(rec["prompt_eval_count"], 60)        # мета записана до стопа

    def test_missing_counts_when_required(self):
        ch = MetaChannel([F1_ALL_PRESENT], meta=None)
        sess = Session(self.run, make_respond(ch), seed=SEED,
                       require_token_counts=True)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "token_counts_missing")

    def test_call_limit(self):
        ch = MetaChannel([F1_ALL_PRESENT, "ACTION: reset"])
        sess = Session(self.run, make_respond(ch), seed=SEED, max_calls=2)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "call_limit")
        self.assertEqual(len(ch.sent), 2)

    def test_time_limit(self):
        ch = MetaChannel([F1_ALL_PRESENT])
        sess = Session(self.run, make_respond(ch), seed=SEED, max_seconds=0.0)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "time_limit")


class TestM1Context(SessionCase):
    """M1: заметки подаются в F2/F3; NOTES и лишние данные — нет."""

    def test_notes_flow(self):
        calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

        def respond(phase, ctx, attempt):
            calls[phase] += 1
            if phase == "F1":
                return F1_ALL_PRESENT
            if phase == "F2":
                i = calls["F2"]
                if i == 1:
                    return (REG_TEXT + "\nNOTE: заметка агента №1\n"
                            "NOTES: свободный текст не для памяти")
                if i == 2:
                    return ("PREDICT: O2 T=2 H=1 = present\n"
                            "ACTION: probe O2 T=2 H=1")
                return "ACTION: reset"
            if phase == "F3":
                return F3_CORRECT
            if phase == "F4":
                return FINAL_TEXT
            raise AssertionError(phase)

        sess = Session(self.run, respond, seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        ctxs = sess.sent_contexts
        f1 = [c for c in ctxs if c.phase == "F1"][0]
        self.assertEqual(f1.notes, ())
        self.assertEqual(len(f1.battery), 9)
        f2 = [c for c in ctxs if c.phase == "F2"]
        self.assertEqual(f2[0].notes, ())                  # до первой заметки
        self.assertEqual(f2[0].battery, ())                # перечня батареи в F2 нет
        self.assertEqual(f2[1].notes, ("заметка агента №1",))
        f3 = [c for c in ctxs if c.phase == "F3"][0]
        self.assertEqual(f3.notes, ("заметка агента №1",))
        self.assertNotIn("свободный текст", " ".join(f3.notes))   # NOTES не в память
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        notes = [r for r in rows if r["type"] == "note"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["text"], "заметка агента №1")
        self.assertNotIn("NOTES", [r["type"] for r in rows])


class TestContextMonitor(SessionCase):
    """Мониторинг объёма промпта: предупреждение при приближении к C1 (>3900)."""

    def test_warning_threshold(self):
        sess = Session(self.run, lambda *a: "x", seed=SEED)

        class BigPrompt:
            last_prompt = "x" * 12000      # ≈4000 токенов (bytes/3.0)

        sess.respond = BigPrompt()
        sess._note_prompt_size()
        self.assertEqual(sess.context_approx[-1], 4000)
        self.assertEqual(len(sess.context_warns), 1)
        self.assertEqual(sess.context_warns[0]["approx_tokens"], 4000)

    def test_no_warning_for_small(self):
        sess = Session(self.run, lambda *a: "x", seed=SEED)

        class SmallPrompt:
            last_prompt = "x" * 300        # ≈100 токенов

        sess.respond = SmallPrompt()
        sess._note_prompt_size()
        self.assertEqual(sess.context_approx[-1], 100)
        self.assertEqual(sess.context_warns, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
