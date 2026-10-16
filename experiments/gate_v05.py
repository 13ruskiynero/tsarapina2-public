# -*- coding: utf-8 -*-
"""INTEGRATION GATE v0.5 (06.09.2026) — Strategy v0.5 = v0.4
(contextual exploitation + insufficiency routing + applicability
addressing) + transition event E2 (TE-1: второй последовательный
non-success того же (адрес, команда) → право на exploration).
v0.4 baseline сохранён: strategy/strategy_v04_baseline.py (артефакт
сравнения; не импортируется). Основной strategy.py = v0.5.

Пункты:
1. регрессия 9/9 (юнит-наборы — отдельным прогоном);
2-6. полный набор gate_v04 (T1-T4e) на v0.5 — v0.4-поведение
     сохранено (в этих сценариях события E2 нет);
7. TE-часть (argv: te): stale → переход → перебор → fix-aq → S2;
   SINGLE/ALT 0 переходов; DOUBLE 1 ложный (цена +2); MIX 1
   (3-й w2-f); M4-structural 0 (разные команды не суммируются).
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "experiments",
                                "context_applicability1"))
sys.path.insert(0, os.path.join(BASE, "experiments",
                                "transition_event1"))

from context_applicability1 import ca1_driver as C  # noqa: E402
from knowledge import knowledge as K  # noqa: E402
from strategy import strategy as S  # noqa: E402
from strategy import strategy  # noqa: E402

# подмена: сценарии CA-1 идут на ОСНОВНОЙ Strategy v0.5
C.suggest = strategy.suggest

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %-44s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def te_run():
    """TE-часть гейта v0.5: переходы на ОСНОВНОЙ Strategy v0.5."""
    from transition_event1 import te1_driver as T
    # данные TE-гейта — в отдельный каталог (не трогаем артефакты TE1)
    T.DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "gate_v05_data")
    if not os.path.exists(T.DIR):
        os.makedirs(T.DIR)
    T.LOG = os.path.join(T.DIR, "GATE_V05_te.log")
    open(T.LOG, "w", encoding="utf-8").close()  # чистый лог прогона
    T.suggest_v7 = strategy.suggest  # основная v0.5 вместо ветки

    def results_rows():
        rows = []
        if not os.path.exists(T.LOG):
            return rows
        for line in open(T.LOG, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") == "RESULT":
                rows.append(r)
        return rows

    # прогон частей (механика поверх основной v0.5)
    T.part_base()
    T.part_stale()
    T.part_noise()
    T.part_m4()
    rows = results_rows()

    def series_rows(name):
        return [r for r in rows if r.get("series") == name]

    # base-свойства v0.4 на v0.5
    known = series_rows("KNOWN")
    ab = series_rows("AB")
    sebc = series_rows("SEBC")
    sebc2 = series_rows("SEBC2")
    s3rows = series_rows("S3")
    det = series_rows("DET")
    check("TE-base: KNOWN ok (1 действие)", bool(known)
          and known[0].get("ok") and known[0].get("n") == 1)
    check("TE-base: AB ok (fix-ab)", bool(ab) and ab[0].get("ok"))
    check("TE-base: SEBC → exploration → ok (≥5 действ.)",
          bool(sebc) and sebc[0].get("ok")
          and sebc[0].get("n", 0) >= 5)
    check("TE-base: SEBC2 S2 1 действие", bool(sebc2)
          and sebc2[0].get("ok") and sebc2[0].get("n") == 1)
    check("TE-base: S3 сохранён (без события)",
          bool(s3rows) and s3rows[0].get("strategy") == "S3"
          and not s3rows[0].get("transition"))
    check("TE-base: DET идентичен", bool(det) and det[0].get("same"))

    # stale: событие → восстановление
    st_rows = series_rows("STALE")
    trans_idx = [i for i, r in enumerate(st_rows)
                 if r.get("transition")]
    check("TE-stale: событие E2 произошло", len(trans_idx) >= 1)
    if st_rows:
        last_ok = [r for r in st_rows[-2:] if r.get("ok")
                   and r.get("n") == 1]
        check("TE-stale: после перехода S2 по 1 действию "
              "(%d из 2 последних)" % len(last_ok), len(last_ok) == 2)

    # noise-серии
    for name, expect in (("SINGLE", 0), ("ALT", 0), ("DOUBLE", 1),
                         ("MIX", 1)):
        rr = series_rows(name)
        ntr = sum(1 for r in rr if r.get("transition"))
        check("TE-noise[%s]: переходов = %d (ожидание %d)"
              % (name, ntr, expect), ntr == expect)
    dbl = series_rows("DOUBLE")
    if any(r.get("transition") for r in dbl):
        after = [r for r in dbl
                 if r.get("transition") and r.get("ok")]
        check("TE-noise[DOUBLE]: ложный переход завершён успешно "
              "(знание цело)", len(after) >= 1)
    # M4: разные команды не суммируются
    m4 = series_rows("M4")
    check("TE-M4: fix-a 1f + fix-b 1f — события НЕТ",
          bool(m4) and not m4[0].get("transition")
          and m4[0].get("strategy") == "S2")


def main():
    print("== INTEGRATION GATE: Strategy v0.5 (v0.4 + E2 transition) ==",
          flush=True)
    if sys.argv[1:] and sys.argv[1] == "te":
        te_run()
        return
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
    check("DET: повторный suggest идентичен (v0.5)",
          s1["suggestion_id"] == s2["suggestion_id"]
          and s1["strategy_version"] == "0.5")

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
    print("=== INTEGRATION GATE v0.5: %s ==="
          % ("PASS" if not failed else "FAIL (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
