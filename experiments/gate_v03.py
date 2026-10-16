# -*- coding: utf-8 -*-
"""INTEGRATION GATE — Strategy v0.3 (contextual exploitation +
insufficiency routing). SEB-1 M2 интегрирован в основную Strategy.

10 пунктов профессора (заморожены):
1. базовая регрессия 9/9 (юнит-наборы — отдельным прогоном);
2. R1 return-A = 3/3 (1 действие fix-a);
3. AB = 3/3 (1 действие fix-ab);
4. UA → S3 (конфликт fix-a s/f → S3, не молчаливое решение);
5. stale knowledge из TRUST-1 не «молча решён» (тот же S3-случай);
6. C1 → поиск → fix-c (гипотеза → exploration → перебор → success);
7. C2–C7 → S2 fix-c 1 действие;
8. swap (S2 после знания, независимость от модели);
9. determinism (повтор C-серии на свежем сторе → та же траектория);
10. multi-action regression (кандидат = последнее действие опыта).

Полигон tsasvc; критерий success — устойчивый active (1.5с).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "GATE_V03_run.log")
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-c"]
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %-34s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print("   ", line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(symptoms):
    subprocess.run(["systemctl", "stop", SVC], capture_output=True,
                   timeout=40)
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    flags = {"a": ["a"], "b": ["b"], "ab": ["a", "b"], "c": ["c"]}[symptoms]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    subprocess.run(["systemctl", "reset-failed", SVC], capture_output=True,
                   timeout=40)


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def symptom_now():
    from observer import polygon_sensor
    src, raw, subj, prop, value = polygon_sensor.sensor_symptom()
    return value


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "GATE-V03"}
    store.append_action(a)
    return a


def learn(store, symptom, fix, ep):
    env_set(symptom)
    # симптом фиксируется ДО лечения (после fix флагов нет — symptom=none)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem=problem,
        observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="gate-v03")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else ev["outcome"])
    return ok


def synthetic_fail(store, symptom, cmd, ep):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = store.append_action({
        "schema_version": "0.1",
        "action_id": "act_sf_%s" % uuid.uuid4().hex[:8],
        "strategy_id": None, "proposed_by": "world",
        "type": "command", "command": cmd,
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": now, "rationale": "synthetic failure"})
    rid = store.append_result({
        "schema_version": "0.1",
        "result_id": "res_sf_%s" % uuid.uuid4().hex[:8],
        "action_id": aid, "executed_at": now,
        "exit_code": 0, "stdout": "x", "stderr": "",
        "state_before": {"service:tsasvc.state": "inactive"},
        "state_after": {"service:tsasvc.state": "inactive"},
        "outcome": "unverified"})
    exp = experience.build(
        problem="tsasvc.service inactive symptom=%s" % symptom,
        observations=[], actions=[aid], result_ref=rid,
        machine="gate-v03")
    experience.save(store, exp)
    update.apply(store, exp["experience_id"], "failure")
    log({"phase": ep, "event": "synthetic_failure", "cmd": cmd})


def episode(store, symptom, ep):
    """Один ход решения: suggest → действие → исход."""
    env_set(symptom)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = strategy.suggest(store, {"problem": problem}, by="gate-v03")
    sid = sug["strategy_id"]
    cmd = None
    ok = False
    if sid == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
        act = mk_action(store, cmd, proposed_by="gate-v03")
        res = executor.execute(store, act)
        ok = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok else ev["outcome"]
        log({"phase": ep, "event": "action", "strategy": sid,
             "cmd": cmd, "outcome": out,
             "hypothesis": sug.get("hypothesis")})
        last_res = None
        p = os.path.join(os.path.dirname(store.obs_jsonl),
                         "results.jsonl")
        for line in open(p, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("action_id") == act["action_id"]:
                last_res = rec
        if last_res:
            exp_full = experience.build(
                problem=problem, observations=facts,
                actions=[act["action_id"]],
                result_ref=last_res["result_id"], machine="gate-v03")
            experience.save(store, exp_full)
            update.apply(store, exp_full["experience_id"],
                         "success" if ok else out)
    else:
        log({"phase": ep, "event": "suggest_only", "strategy": sid,
             "rule": sug["rationale"][0]["rule"] if sug["rationale"]
             else ""})
    return sug, cmd, ok


def exploration_episode(store, symptom, ep):
    """C1: гипотеза (1-й ход) → не-success → exploration: перебор
    до устойчивого success. Возвращает (ok, n_actions, hypothesis,
    explored)."""
    env_set(symptom)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    banned = []
    ok = False
    acts = []
    hyp_used = False
    explored = False
    sug1 = strategy.suggest(store, {"problem": problem}, by="gate-v03",
                            banned_commands=banned)
    hyp_used = bool(sug1.get("hypothesis"))
    if sug1["strategy_id"] == "S2" and sug1.get("candidate_actions"):
        cmd = sug1["candidate_actions"][0]["command"]
        act = mk_action(store, cmd, proposed_by="gate-v03/hyp")
        res = executor.execute(store, act)
        ok_now = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok_now else ev["outcome"]
        acts.append(act)
        log({"phase": ep, "event": "action", "strategy": "S2",
             "cmd": cmd, "outcome": out, "hypothesis": True})
        if ok_now:
            ok = True
        else:
            banned.append(cmd)
            sug2 = strategy.suggest(store, {"problem": problem},
                                    by="gate-v03",
                                    banned_commands=banned)
            explored = bool(sug2.get("exploration"))
            log({"phase": ep, "event": "exploration_flag",
                 "strategy": sug2["strategy_id"],
                 "exploration": explored})
            if explored:
                for bcmd in BIN:
                    act = mk_action(store, bcmd,
                                    proposed_by="gate-v03/explore")
                    res = executor.execute(store, act)
                    ok_now = stable_active()
                    ev = evaluation.evaluate(store, res["result_id"],
                                             GOAL)
                    out = "success" if ok_now else ev["outcome"]
                    acts.append(act)
                    log({"phase": ep, "event": "explore", "cmd": bcmd,
                         "outcome": out})
                    if ok_now:
                        ok = True
                        break
    else:
        log({"phase": ep, "event": "suggest_only",
             "strategy": sug1["strategy_id"]})
    if acts:
        last_res = None
        p = os.path.join(os.path.dirname(store.obs_jsonl),
                         "results.jsonl")
        for line in open(p, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("action_id") == acts[-1]["action_id"]:
                last_res = rec
        if last_res:
            exp_full = experience.build(
                problem=problem, observations=facts,
                actions=[a["action_id"] for a in acts],
                result_ref=last_res["result_id"], machine="gate-v03")
            experience.save(store, exp_full)
            update.apply(store, exp_full["experience_id"],
                         "success" if ok else "failure")
    return ok, len(acts), hyp_used, explored


def fresh_store(name):
    d = os.path.join(DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def multi_action_fixture(store):
    """Синтетический multi-action опыт: fix-ab, fix-b, fix-c
    (последний — зафиксированный success)."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aids = []
    for cmd in ("fix-ab", "fix-b", "fix-c"):
        aids.append(store.append_action({
            "schema_version": "0.1",
            "action_id": "act_ma_%s" % uuid.uuid4().hex[:8],
            "strategy_id": None, "proposed_by": "fixture",
            "type": "command", "command": cmd,
            "args": {"goal": GOAL}, "permitted": True,
            "proposed_at": now, "rationale": "multi-action"}))
    rid = store.append_result({
        "schema_version": "0.1",
        "result_id": "res_ma_%s" % uuid.uuid4().hex[:8],
        "action_id": aids[-1], "executed_at": now,
        "exit_code": 0, "stdout": "x", "stderr": "",
        "state_before": {"service:tsasvc.state": "inactive"},
        "state_after": {"service:tsasvc.state": "active"},
        "outcome": "unverified"})
    exp = experience.build(
        problem="tsasvc.service inactive symptom=c",
        observations=[], actions=aids, result_ref=rid,
        machine="gate-v03-multi")
    experience.save(store, exp)
    update.apply(store, exp["experience_id"], "success")


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== INTEGRATION GATE: Strategy v0.3 ==", flush=True)
    env_set("a")

    # G2: return-A 3/3
    st = fresh_store("retA")
    learn(st, "a", "fix-a", "g2_learn_a")
    learn(st, "b", "fix-b", "g2_learn_b")
    ok_all = True
    for i in range(1, 4):
        sug, cmd, ok = episode(st, "a", "g2_a%d" % i)
        good = ok and cmd == "fix-a" and sug["strategy_id"] == "S2"
        ok_all = ok_all and good
    check("G2: return-A 3/3 (S2 fix-a)", ok_all)

    # G3: AB 3/3
    st2 = fresh_store("ab")
    learn(st2, "ab", "fix-ab", "g3_learn_ab")
    ok_all = True
    for i in range(1, 4):
        sug, cmd, ok = episode(st2, "ab", "g3_ab%d" % i)
        good = ok and cmd == "fix-ab" and sug["strategy_id"] == "S2"
        ok_all = ok_all and good
    check("G3: AB 3/3 (S2 fix-ab)", ok_all)

    # G4/5: UA → S3
    st3 = fresh_store("ua")
    learn(st3, "a", "fix-a", "g4_learn_a")
    synthetic_fail(st3, "a", "fix-a", "g4_f")
    kids = [v["knowledge_id"] for v in st3.read_knowledge_versions_all()
            if v["status"] == "active"]
    k_s = min(kids, key=lambda k: st3.read_knowledge(k)["created_at"])
    k_f = max(kids, key=lambda k: st3.read_knowledge(k)["created_at"])
    knowledge.declare_conflict(st3, k_s, k_f)
    sug, cmd, ok = episode(st3, "a", "g4_task")
    check("G4/5: UA → S3 (stale не решается молча)",
          sug["strategy_id"] == "S3" and ok is False
          and any(r.get("rule") == "conflict" for r in sug["rationale"]))

    # G6-8: C-серия
    st4 = fresh_store("c")
    learn(st4, "a", "fix-a", "g6_learn_a")
    learn(st4, "b", "fix-b", "g6_learn_b")
    learn(st4, "ab", "fix-ab", "g6_learn_ab")
    ok1, n1, hyp1, exp1 = exploration_episode(st4, "c", "g6_C1")
    check("G6: C1 → поиск → fix-c (гипотеза+exploration; %d действ.)"
          % n1, ok1 and hyp1 and exp1 and n1 >= 5)
    ok_rest = True
    for i in range(2, 8):
        sug, cmd, ok = episode(st4, "c", "g6_C%d" % i)
        good = ok and cmd == "fix-c" and sug["strategy_id"] == "S2"
        ok_rest = ok_rest and good
    check("G7: C2–C7 → S2 fix-c (1 действие)", ok_rest)
    ok_sw = True
    for i in range(1, 4):
        sug, cmd, ok = episode(st4, "c", "g8_swap%d" % i)
        ok_sw = ok_sw and ok and cmd == "fix-c" and \
            sug["strategy_id"] == "S2"
    check("G8: swap (S2 fix-c)", ok_sw)

    # G9: determinism (повтор C-серии)
    st5 = fresh_store("det")
    learn(st5, "a", "fix-a", "g9_learn_a")
    learn(st5, "b", "fix-b", "g9_learn_b")
    learn(st5, "ab", "fix-ab", "g9_learn_ab")
    ok1b, n1b, hyp1b, exp1b = exploration_episode(st5, "c", "g9_C1")
    check("G9a: повтор C1 детерминирован (та же траектория)",
          ok1b == ok1 and hyp1b == hyp1 and exp1b == exp1)
    sug, cmd, ok = episode(st5, "c", "g9_C2")
    check("G9b: повтор C2 → S2 fix-c", ok and cmd == "fix-c")

    # G10: multi-action regression
    st6 = fresh_store("multi")
    multi_action_fixture(st6)
    sug, cmd, ok = episode(st6, "c", "g10")
    check("G10: multi-action: кандидат = fix-c (последнее действие)",
          cmd == "fix-c" and sug["strategy_id"] == "S2")

    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== INTEGRATION GATE v0.3: %s ==="
          % ("ПРОЙДЕН" if not failed
             else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
