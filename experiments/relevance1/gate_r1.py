# -*- coding: utf-8 -*-
"""INTEGRATION GATE R1 (Tsarapina, 06.09).

После включения R1 (symptom-match) в основную strategy.py:
1) полная регрессия тестов (baseline 19/19 и все слои) — вне скрипта;
2) ядро RELEVANCE-1 на ОСНОВНОЙ Strategy: learn-A, A x3, learn-B,
   B x3, ВОЗВРАТ A x3 (эталон 0/3 → цель 3/3), learn-AB, AB x3,
   UA-mini (S3-защита, fix-a2), swap x2 (qwen25), детерминизм.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy import strategy  # noqa: E402
import relevance1_driver as rd  # noqa: E402  (learn/env_set/...; LOG общий)
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from update import update  # noqa: E402

LOG = os.path.join(rd.EXP_DIR, "GATE_R1.log")


def _last_result(store, aid):
    path = os.path.join(os.path.dirname(store.obs_jsonl),
                        "results.jsonl")
    last = None
    for line in open(path, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("action_id") == aid:
            last = rec
    return last["result_id"] if last else None


def _last_eval(store, rid):
    evs = store.read_evaluations(rid)
    return evs[-1]["outcome"] if evs else "unknown"


def symptom_now():
    from observer import polygon_sensor
    return polygon_sensor.sensor_symptom()[4]


def solve_main(store, ep, symptoms, provider="gemma"):
    rd.env_set(symptoms)
    facts = observer.collect(store)
    problem = rd.problem_of(symptom_now())
    sug = strategy.suggest(store, {"problem": problem})
    sid = sug["strategy_id"]
    acts = []
    if sid == strategy.S2:
        for c in sug["candidate_actions"]:
            acts.append(rd.mk_action(store, c["command"],
                                     proposed_by="strategy/S2"))
    else:
        from llm import adapter
        task = ("Сервис tsasvc не работает (inactive), симптом: %s. "
                "Верни в active. Доступно: systemctl start/stop/"
                "restart tsasvc, диагностика." % symptom_now())
        r = adapter.propose(provider, adapter.build_prompt(task),
                            max_tokens=300, timeout=180)
        if r["ok"]:
            for c in r["candidate_actions"]:
                cmd = c.get("command", "")
                if "tsasvc" in cmd:
                    acts.append(rd.mk_action(store, cmd,
                                             proposed_by="tsarapina/llm"))
    rd.log({"ep": ep, "event": "strategy", "strategy": sid,
            "refs": sug["knowledge_refs"][:4],
            "relevance": [x.get("relevance") for x in sug["rationale"]
                          if x.get("rule") == "known_fix"]})
    outs, ok = rd.run_until_goal(store, acts, ep)
    if outs:
        act = acts[len(outs) - 1]
        rid = _last_result(store, act["action_id"])
        if rid:
            exp_full = experience.build(
                problem=problem, observations=facts,
                actions=[a["action_id"] for a in acts[:len(outs)]],
                result_ref=rid, machine="gate")
            experience.save(store, exp_full)
            update.apply(store, exp_full["experience_id"],
                         _last_eval(store, rid))
    kcount = len({v["knowledge_id"]
                  for v in store.read_knowledge_versions_all()})
    rd.log({"ep": ep, "event": "episode", "system": "main+R1",
            "symptoms": symptoms, "strategy": sid, "success": ok,
            "actions": len(outs), "knowledge_total": kcount,
            "state_after": rd.svc_state()})
    return ok, sid


def ua_mini(store):
    solve_main(store, "UA1", "a2")
    k_old = rd.last_a_success_kid(store)
    k_fail = rd.last_a_fail_kid(store)
    if k_old and k_fail and k_old != k_fail:
        knowledge.declare_conflict(store, k_old, k_fail)
        rd.log({"ep": "UA2", "event": "operator_conflict",
                "k1": k_old, "k2": k_fail})
    else:
        rd.log({"ep": "UA2", "event": "operator_conflict", "error":
                "не найдены", "k_old": k_old, "k_fail": k_fail})
    solve_main(store, "UA3", "a2")
    rd.learn(store, "UA4", "a2", "fix-a2")
    if k_old:
        knowledge.retract(store, k_old, by="operator",
                          note="среда изменилась: fix-a2")
    if k_fail and k_fail != k_old:
        knowledge.retract(store, k_fail, by="operator",
                          note="устарело после fix-a2")
    solve_main(store, "UA6", "a2")


def main():
    open(LOG, "w", encoding="utf-8").close()
    rd.LOG = LOG
    print("== INTEGRATION GATE R1 (main strategy + symptom-match) ==",
          flush=True)
    st = rd.fresh_store("tsar_gate")

    rd.learn(st, "G1", "a", "fix-a")
    for i in range(3):
        solve_main(st, "GA%d" % (i + 1), "a")
    rd.learn(st, "G2", "b", "fix-b")
    for i in range(3):
        solve_main(st, "GB%d" % (i + 1), "b")
    ret = []
    for i in range(3):
        ok, sid = solve_main(st, "GR%d" % (i + 1), "a")
        ret.append((ok, sid))
    rd.learn(st, "G3", "ab", "fix-ab")
    ab = []
    for i in range(3):
        ok, sid = solve_main(st, "GAB%d" % (i + 1), "ab")
        ab.append((ok, sid))
    ua_mini(st)
    sw = []
    for i in range(2):
        ok, sid = solve_main(st, "GSW%d" % (i + 1), "a",
                             provider="qwen25")
        sw.append((ok, sid))
    rd.env_set("a")
    p = rd.problem_of(symptom_now())
    s1 = strategy.suggest(st, {"problem": p}, save=False)
    s2 = strategy.suggest(st, {"problem": p}, save=False)
    det = s1["suggestion_id"] == s2["suggestion_id"]
    print("GATE: return_A=%s ab=%s swap=%s determinism=%s"
          % (ret, ab, sw, det), flush=True)
    rd.log({"event": "gate_final", "return_A": ret, "ab": ab,
            "swap": sw, "determinism": det})
    ok = all(x[0] for x in ret) and all(x[0] for x in ab) and \
        all(x[0] for x in sw) and det
    print("GATE R1: %s" % ("PASS" if ok else "FAIL"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
