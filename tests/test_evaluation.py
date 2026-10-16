# -*- coding: utf-8 -*-
"""Обязательный тест Evaluation (Tsarapina, этап 7).

Правило (профессор):
> Evaluation не оценивает модель. Она оценивает соответствие
> результата цели действия.

V1. success: before inactive, action restart, after active → success.
V2. failure:  before inactive, action restart, after inactive →
    failure (выполнено, но не помогло).
V3. partial:  rc=1, но after=active (код и факты расходятся).
V4. refused:  result.refused → refused (политика).
V5. not_executed: exit_code=None (ошибка запуска) → not_executed.
V6. unknown:  goal-свойство отсутствует в снимках → unknown
    (НЕ failure, не «наверное получилось»).
V7. Result НЕ изменяется (остаётся outcome=unverified); вердикт —
    отдельная evaluation-запись; история не переписывается.
V8. evaluation не создаёт Knowledge и не импортирует llm.
V9. диагностика без цели: rc=0 + stdout → success (данные получены).
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import evaluation  # noqa: E402
from storage.store import Store  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tests", "tmp_evaluation")
GOAL_SSH = {"property": "service:ssh.state", "value": "active"}
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def _fresh_store():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    return Store(os.path.join(TMP, "tsarapina.db"), TMP)


def _mk_result(st, sb, sa, rc=0, refused=False, stdout="out"):
    rid = "res_ev_%s" % len(st.read_results() if hasattr(
        st, "read_results") else [])
    st.append_result({
        "schema_version": "0.1", "result_id": rid,
        "action_id": "act_ev_1",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_code": rc, "stdout": stdout, "stderr": "",
        "state_before": sb, "state_after": sa,
        "outcome": "unverified", "refused": refused})
    return rid


def v1_success():
    st = _fresh_store()
    rid = _mk_result(st, {"service:ssh.state": "inactive"},
                     {"service:ssh.state": "active"})
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V1: before inactive, after active → success",
          ev["outcome"] == "success")


def v2_failure():
    st = _fresh_store()
    rid = _mk_result(st, {"service:ssh.state": "inactive"},
                     {"service:ssh.state": "inactive"})
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V2: after inactive → failure (выполнено, но не помогло)",
          ev["outcome"] == "failure")


def v3_partial():
    st = _fresh_store()
    rid = _mk_result(st, {"service:ssh.state": "inactive"},
                     {"service:ssh.state": "active"}, rc=1)
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V3: rc=1, но факты достигли цели → partial", 
          ev["outcome"] == "partial")


def v4_refused():
    st = _fresh_store()
    rid = _mk_result(st, {}, {}, refused=True)
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V4: refused → refused", ev["outcome"] == "refused")


def v5_not_executed():
    st = _fresh_store()
    rid = _mk_result(st, {}, {}, rc=None)
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V5: exit_code=None → not_executed",
          ev["outcome"] == "not_executed")


def v6_unknown():
    st = _fresh_store()
    # goal-свойства нет в снимках (снимки про disk)
    rid = _mk_result(st, {"disk.free_kb": "100"}, {"disk.free_kb": "90"})
    ev = evaluation.evaluate(st, rid, GOAL_SSH)
    check("V6: свойства цели нет в данных → unknown (не failure)",
          ev["outcome"] == "unknown")


def v7_result_untouched():
    st = _fresh_store()
    rid = _mk_result(st, {"service:ssh.state": "inactive"},
                     {"service:ssh.state": "active"})
    evaluation.evaluate(st, rid, GOAL_SSH)
    evaluation.evaluate(st, rid, GOAL_SSH)  # повтор
    res = st.read_result(rid)
    check("V7a: Result не изменён (outcome=unverified)",
          res["outcome"] == "unverified")
    evs = st.read_evaluations(rid)
    check("V7b: вердикты — отдельные записи (%d)" % len(evs), len(evs) == 2)
    check("V7c: оба вердикта success и детерминированы",
          evs[0]["outcome"] == "success" and
          evs[0]["evaluation_id"] == evs[1]["evaluation_id"])


def v8_no_knowledge_no_llm():
    st = _fresh_store()
    rid = _mk_result(st, {"service:ssh.state": "inactive"},
                     {"service:ssh.state": "active"})
    evaluation.evaluate(st, rid, GOAL_SSH)
    kids = st.read_knowledge_versions_all()
    check("V8a: evaluation не создаёт Knowledge", len(kids) == 0)
    src = open(os.path.join(BASE, "evaluation", "evaluation.py"),
               encoding="utf-8").read()
    import re
    check("V8b: evaluation не импортирует llm/knowledge",
          not re.search(r"(import|from)\s+(llm|knowledge)", src))


def v9_diagnostic():
    st = _fresh_store()
    rid = _mk_result(st, {}, {}, rc=0, stdout="active")
    ev = evaluation.evaluate(st, rid, None)
    check("V9: диагностика rc=0+stdout → success", ev["outcome"] == "success")


def main():
    v1_success()
    v2_failure()
    v3_partial()
    v4_refused()
    v5_not_executed()
    v6_unknown()
    v7_result_untouched()
    v8_no_knowledge_no_llm()
    v9_diagnostic()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ EVALUATION: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
