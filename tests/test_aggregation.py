# -*- coding: utf-8 -*-
"""Локальный тест механики Aggregation (Tsarapina, зона 2).

Дизайн: AGGREGATION1_DESIGN.md. Наборы A–F строятся через
СУЩЕСТВУЮЩИЕ слои (action/result/experience/evaluation/update) на
синтетических эпизодах; затем aggregate() и проверки метрик.

G1 (A: exact dup ×6): компрессия 6→1 активного; refs 6/6 (M2);
decision equivalence (M3): S2 fix-a до и после; детерминизм (M5):
повторный прогон не создаёт новый агрегат (тот же id).
G2 (B: same action, разные эпизоды): 1 агрегат; refs 3/3.
G3 (C: same symptom, разные actions): агрегации НЕТ (2 группы по 1);
активных 2 (вариативность сохранена).
G4 (D: success+failure same action + declare_conflict): 2 агрегата;
конфликт перенесён; S3 на задаче симптома (M4).
G5 (E: success fix-a + failure fix-b, без declare): 2 группы по 1 —
агрегации нет; оба активны.
G6 (F: mixed A+B+C+D): прогон без сбоев; идемпотентность (повтор
ничего не создаёт).
G7: старые Experience/Result не удалены и не изменены; агрегатор не
импортирует llm/update/strategy (использует только knowledge+store).
"""
import json
import os
import re
import shutil
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregation import aggregation  # noqa: E402
from evaluation import evaluation  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tests", "tmp_aggregation")
GOAL = {"property": "service:tsasvc.state", "value": "active"}
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


def mk_episode(store, symptom, command, outcome, state_before="inactive",
               state_after=None):
    """Синтетический эпизод через существующие слои. Возвращает eid.
    По умолчанию: success — inactive→active; failure — состояние НЕ
    изменилось (inactive→inactive); rc=0 для success/failure
    (действие выполнено), rc=1 — только при явном state_after
    (partial: код и факты расходятся)."""
    aid = store.append_action({
        "schema_version": "0.1",
        "action_id": "act_%s" % uuid.uuid4().hex[:10],
        "strategy_id": None, "proposed_by": "test",
        "type": "command", "command": command,
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rationale": "test"})
    sb = {"service:tsasvc.state": state_before}
    if state_after is None:
        state_after = state_before if outcome == "failure" else "active"
    sa = {"service:tsasvc.state": state_after}
    rc = 0 if outcome in ("success", "failure") else 1
    rid = store.append_result({
        "schema_version": "0.1",
        "result_id": "res_%s" % uuid.uuid4().hex[:10],
        "action_id": aid, "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_code": rc, "stdout": "x", "stderr": "",
        "state_before": sb, "state_after": sa, "outcome": "unverified"})
    exp = experience.build(problem="tsasvc.service inactive symptom=%s"
                                   % symptom,
                           observations=[], actions=[aid],
                           result_ref=rid, machine="agg-test")
    experience.save(store, exp)
    ev = evaluation.evaluate(store, rid, GOAL)
    update.apply(store, exp["experience_id"], ev["outcome"])
    return exp["experience_id"]


def _active_count(store):
    """Число АКТИВНЫХ знаний = по ПОСЛЕДНИМ версиям (исторические
    версии не считаются: они остаются в истории с прежним
    статусом)."""
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    return sum(1 for v in latest.values()
               if v["status"] in ("active", "conflicted"))


def _latest(store, kid):
    best = None
    for v in store.read_knowledge_versions_all():
        if v["knowledge_id"] == kid:
            if best is None or v["version"] > best["version"]:
                best = v
    return best


def _suggest_cmd(store, symptom):
    sug = strategy.suggest(store, {"problem": "tsasvc.service inactive "
                               "symptom=%s" % symptom},
                           by="strategy/deterministic")
    if sug["strategy_id"] == strategy.S2 and sug["candidate_actions"]:
        return sug["candidate_actions"][0].get("command")
    return "S%s" % sug["strategy_id"]


def g1_exact_duplicates():
    st = _fresh_store()
    eids = [mk_episode(st, "a", "fix-a", "success") for _ in range(6)]
    n_before = _active_count(st)
    r = aggregation.aggregate(st)
    n_after = _active_count(st)
    check("G1a: компрессия 6->1 активного", r["active_before"] == 6
          and n_after == 1 and len(r["created"]) == 1)
    agg = _latest(st, r["created"][0])
    check("G1b: refs агрегата = 6/6 (M2 coverage)",
          sorted(agg["experience_refs"]) == sorted(eids))
    check("G1c: decision equivalence (S2 fix-a до и после)",
          _suggest_cmd(st, "a") == "fix-a")
    # детерминизм/идемпотентность
    r2 = aggregation.aggregate(st)
    check("G1d: повторный прогон не создаёт новый агрегат",
          len(r2["created"]) == 0)
    n3 = _active_count(st)
    check("G1e: активных после повтора по-прежнему 1", n3 == 1)
    check("G1f: исходные superseded, но версии целы",
          len(st.read_knowledge_versions_all()) >= 6 * 2 + 1)


def g2_same_action_diff_episodes():
    st = _fresh_store()
    eids = [mk_episode(st, "a", "fix-a", "success",
                       state_before="inactive", state_after="active")
            for _ in range(3)]
    r = aggregation.aggregate(st)
    check("G2a: 3 эпизода -> 1 агрегат (same action)",
          len(r["created"]) == 1)
    agg = _latest(st, r["created"][0])
    check("G2b: refs 3/3 сохранены", sorted(agg["experience_refs"]) ==
          sorted(eids))
    check("G2c: decision fix-a", _suggest_cmd(st, "a") == "fix-a")


def g3_same_symptom_diff_actions():
    st = _fresh_store()
    mk_episode(st, "a", "fix-a", "success")
    mk_episode(st, "a", "fix-b", "success")
    r = aggregation.aggregate(st)
    check("G3a: нет агрегации (группы по 1)", len(r["created"]) == 0)
    check("G3b: активных 2 (вариативность сохранена)",
          _active_count(st) == 2)


def g4_conflict_preserved():
    st = _fresh_store()
    # D-набор: повторы обеих сторон (2×success, 2×failure), иначе
    # агрегировать нечего (группы по 1)
    mk_episode(st, "a", "fix-a", "success")
    mk_episode(st, "a", "fix-a", "failure", state_after="inactive")
    mk_episode(st, "a", "fix-a", "success")
    mk_episode(st, "a", "fix-a", "failure", state_after="inactive")
    # объявить конфликт между последними активными знаниями (s/f)
    kids = sorted({v["knowledge_id"] for v in
                   st.read_knowledge_versions_all()},
                  key=lambda k: _latest(st, k)["created_at"])
    k_s, k_f = kids[-2], kids[-1]
    knowledge.declare_conflict(st, k_s, k_f)
    r = aggregation.aggregate(st)
    check("G4a: два агрегата (success и failure группы)",
          len(r["created"]) == 2)
    check("G4b: конфликт перенесён на агрегаты",
          len(r["conflicts_transferred"]) >= 1)
    # S3-защита сохраняется: задача симптома a → конфликт → S3
    sug = strategy.suggest(st, {"problem": "tsasvc.service inactive "
                             "symptom=a"}, by="strategy/deterministic")
    check("G4c: S3-защита после агрегации (M4)",
          sug["strategy_id"] == strategy.S3)
    check("G4d: обе стороны конфликта активны и трассируемы",
          _active_count(st) == 2)


def g5_complex_conflict():
    st = _fresh_store()
    mk_episode(st, "a", "fix-a", "success")
    mk_episode(st, "a", "fix-b", "failure", state_after="inactive")
    r = aggregation.aggregate(st)
    check("G5a: агрегации нет (2 группы по 1)", len(r["created"]) == 0)
    check("G5b: оба знания активны (разные действия)",
          _active_count(st) == 2)


def g6_mixed():
    st = _fresh_store()
    # A: 4× fix-a success
    for _ in range(4):
        mk_episode(st, "a", "fix-a", "success")
    # B: 2× fix-b success (same action, diff episodes)
    for _ in range(2):
        mk_episode(st, "b", "fix-b", "success")
    # D: 2× fix-a failure
    for _ in range(2):
        mk_episode(st, "a", "fix-a", "failure", state_after="inactive")
    before = _active_count(st)
    r = aggregation.aggregate(st)
    check("G6a: mixed-прогон без сбоев (created>=3)",
          len(r["created"]) >= 3)
    check("G6b: активных стало меньше", r["active_after"] < before)
    # идемпотентность
    r2 = aggregation.aggregate(st)
    check("G6c: повтор ничего не создаёт", len(r2["created"]) == 0
          and len(r2["conflicts_transferred"]) == 0)


def g7_evidence_intact_no_imports():
    st = _fresh_store()
    eids = [mk_episode(st, "a", "fix-a", "success") for _ in range(3)]
    exps_before = {e: st.read_experience(e) for e in eids}
    res_before = {}
    for eid in eids:
        exp = st.read_experience(eid)
        if exp.get("result_ref"):
            res_before[exp["result_ref"]] = st.read_result(exp["result_ref"])
    aggregation.aggregate(st)
    exps_after = {e: st.read_experience(e) for e in eids}
    check("G7a: Experience не изменены", exps_before == exps_after)
    res_after = {}
    for eid in eids:
        exp = st.read_experience(eid)
        if exp.get("result_ref"):
            res_after[exp["result_ref"]] = st.read_result(exp["result_ref"])
    check("G7b: Result не изменены", res_before == res_after)
    src = open(os.path.join(BASE, "aggregation", "aggregation.py"),
               encoding="utf-8").read()
    bad = [w for w in ("llm", "update", "strategy", "executor")
           if re.search(r"(import|from)\s+%s" % w, src)]
    check("G7c: агрегатор не импортирует llm/update/strategy/executor",
          not bad)


def main():
    g1_exact_duplicates()
    g2_same_action_diff_episodes()
    g3_same_symptom_diff_actions()
    g4_conflict_preserved()
    g5_complex_conflict()
    g6_mixed()
    g7_evidence_intact_no_imports()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ЛОКАЛЬНЫЙ ТЕСТ МЕХАНИКИ AGGREGATION: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)"
             % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
