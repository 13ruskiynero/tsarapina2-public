# -*- coding: utf-8 -*-
"""INTEGRATION GATE v0.4 (06.09.2026) — Strategy v0.4 = v0.3
(contextual exploitation + insufficiency routing) + applicability
addressing (CA-1). Основной strategy.py изменён (v0.4); гейт
проверяет, что адресация (symptom, context) работает и НИЧЕГО из
доказанного v0.3 не сломано. Скрипты ca1_driver используются с
подменой suggest на ОСНОВНУЮ стратегию.

Пункты:
1. регрессия 9/9 (юнит-наборы — отдельным прогоном);
2. T1 reversed recency: ctx=absent → fix-a (fix-a2 свежее);
3. T2: ctx=present → fix-a2;
4. T3: 6/6 чередований, 1 действие, context_filter_used=true;
5. T4: known A 1 действие; AB fix-ab; C SEB (exploration → fix-c);
   S3 сохранён; swap; determinism;
6. T4e (критическое условие): Knowledge без ctx НЕ получает
   искусственный контекст и НЕ отбрасывается (legacy addressing).
"""
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "experiments",
                                "context_applicability1"))

from context_applicability1 import ca1_driver as C  # noqa: E402
from knowledge import knowledge as K  # noqa: E402
from strategy import strategy as S  # noqa: E402
from strategy import strategy  # noqa: E402

# подмена: сценарии CA-1 идут на ОСНОВНОЙ Strategy v0.4
C.suggest = strategy.suggest

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %-44s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def main():
    print("== INTEGRATION GATE: Strategy v0.4 (CA-1 addressing) ==",
          flush=True)
    assert S.__file__.endswith("strategy.py"), "подмена не та"

    # L1/L2 + T1/T2/T3/SWAP/DET
    st = C.fresh_store("gate_main")
    ok, ctx1 = C.learn(st, "a", "fix-a", present=False, ep="g_L1")
    assert ok and ctx1 == "absent"
    ok, ctx2 = C.learn(st, "a", "fix-a2", present=True, ep="g_L2")
    assert ok and ctx2 == "present"

    sug, cmd, ok, ctx = C.episode(st, present=False, ep="g_T1")
    check("T1: ctx=absent → S2 fix-a (reversed recency)",
          ok and cmd == "fix-a" and sug["strategy_id"] == "S2"
          and sug.get("context_filter_used"))
    sug, cmd, ok, ctx = C.episode(st, present=True, ep="g_T2")
    check("T2: ctx=present → S2 fix-a2", ok and cmd == "fix-a2"
          and sug["strategy_id"] == "S2"
          and sug.get("context_filter_used"))
    seq = [False, True, False, True, False, True]
    t3 = []
    for i, pr in enumerate(seq):
        sug, cmd, ok, ctx = C.episode(st, present=pr,
                                      ep="g_T3_%d" % (i + 1))
        expect = "fix-a" if not pr else "fix-a2"
        t3.append(ok and cmd == expect and sug["strategy_id"] == "S2"
                  and sug.get("context_filter_used"))
    check("T3: чередование ×6, 1 действие, filter=true", all(t3))

    sug, cmd, ok, ctx = C.episode(st, present=False, ep="g_SWAP")
    check("SWAP: S2 fix-a (знание)", ok and cmd == "fix-a"
          and sug["strategy_id"] == "S2")
    s1 = strategy.suggest(st, {"problem": "tsasvc.service inactive "
                            "symptom=a"}, ctx_now="absent", save=False)
    s2 = strategy.suggest(st, {"problem": "tsasvc.service inactive "
                            "symptom=a"}, ctx_now="absent", save=False)
    check("DET: повторный suggest идентичен (v0.4)",
          s1["suggestion_id"] == s2["suggestion_id"]
          and s1["strategy_version"] == "0.4")

    # T4a known A
    stk = C.fresh_store("gate_known")
    C.learn(stk, "a", "fix-a", present=False, ep="gK_L1")
    sug, cmd, ok, ctx = C.episode(stk, present=False, ep="gK_A")
    check("T4a: known A → 1 действие fix-a", ok and cmd == "fix-a")

    # T4b AB
    stab = C.fresh_store("gate_ab")
    C.learn(stab, "ab", "fix-ab", present=False, ep="gAB_L1")
    C.env_set(present=False, symptom="ab")
    ctx = C.env_extra()
    problem = "tsasvc.service inactive symptom=%s" % C.symptom_now()
    sug = strategy.suggest(stab, {"problem": problem}, ctx_now=ctx,
                           by="gate-v04")
    cmd = sug["candidate_actions"][0]["command"] \
        if sug["strategy_id"] == "S2" and sug["candidate_actions"] else None
    check("T4b: AB → S2 fix-ab", cmd == "fix-ab"
          and sug["strategy_id"] == "S2")

    # T4c C: SEB (exploration) через основную стратегию
    stc = C.fresh_store("gate_c")
    C.learn(stc, "a", "fix-a", present=False, ep="gC_L1")
    C.learn(stc, "b", "fix-b", present=False, ep="gC_L2")
    ok_c, n_c = C.exploration_episode(stc, "gC_ep1")
    check("T4c: C → exploration → fix-c (%d действ.)" % n_c,
          ok_c and n_c >= 5)
    C.env_set(present=False, symptom="c")
    ctx = C.env_extra()
    problem = "tsasvc.service inactive symptom=%s" % C.symptom_now()
    sug = strategy.suggest(stc, {"problem": problem}, ctx_now=ctx,
                           by="gate-v04")
    cmd = sug["candidate_actions"][0]["command"] \
        if sug["strategy_id"] == "S2" and sug["candidate_actions"] else None
    check("T4c2: C после learn → S2 fix-c", cmd == "fix-c"
          and sug["strategy_id"] == "S2")

    # T4d S3
    sts = C.fresh_store("gate_s3")
    C.learn(sts, "a", "fix-a", present=False, ep="gS_L1")
    C.synthetic_failure(sts, "a", "fix-a", "absent", "gS_f")
    kids = [v["knowledge_id"] for v in sts.read_knowledge_versions_all()
            if v["status"] == "active"]
    k_s = min(kids, key=lambda k: sts.read_knowledge(k)["created_at"])
    k_f = max(kids, key=lambda k: sts.read_knowledge(k)["created_at"])
    K.declare_conflict(sts, k_s, k_f)
    C.env_set(present=False, symptom="a")
    ctx = C.env_extra()
    problem = "tsasvc.service inactive symptom=%s" % C.symptom_now()
    sug = strategy.suggest(sts, {"problem": problem}, ctx_now=ctx,
                           by="gate-v04")
    check("T4d: S3 объявленного конфликта сохранён",
          sug["strategy_id"] == "S3")

    # T4e legacy: знание БЕЗ ctx (старый стиль; поле отсутствует)
    stl = C.fresh_store("gate_legacy")
    C.env_set(present=False, symptom="a")
    facts = C.observer.collect(stl)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    a_leg = {
        "schema_version": "0.1",
        "action_id": "act_leg_%s" % time.time(),
        "strategy_id": None, "proposed_by": "operator/learn-legacy",
        "type": "command", "command": "fix-a",
        "args": {"goal": C.GOAL}, "permitted": True,
        "proposed_at": now, "rationale": "legacy (без ctx)"}
    stl.append_action(a_leg)
    res = C.executor.execute(stl, a_leg)
    exp = C.experience.build(
        problem="tsasvc.service inactive symptom=a",
        observations=facts, actions=[a_leg["action_id"]],
        result_ref=res["result_id"], machine="gate-v04")
    C.experience.save(stl, exp)
    C.update.apply(stl, exp["experience_id"], "success")
    # задача при ctx=present: legacy-знание (ctx отсутствует)
    C.env_set(present=True, symptom="a")
    ctx_now = C.env_extra()
    assert ctx_now == "present"
    problem = "tsasvc.service inactive symptom=a"
    sug = strategy.suggest(stl, {"problem": problem}, ctx_now=ctx_now,
                           by="gate-v04")
    cmd = sug["candidate_actions"][0]["command"] \
        if sug["strategy_id"] == "S2" and sug["candidate_actions"] else None
    ctx_of_k = None
    for kid in sug["knowledge_refs"]:
        rec = stl.read_knowledge(kid)
        ctx_of_k = S._ctx_extra_of(stl, rec)
    check("T4e: legacy-знание без ctx не отброшено, без "
          "искусственного ctx (S2, filter off)", sug["strategy_id"]
          == "S2" and cmd == "fix-a" and ctx_of_k is None
          and not sug.get("context_filter_used"))

    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== INTEGRATION GATE v0.4: %s ==="
          % ("PASS" if not failed else "FAIL (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
