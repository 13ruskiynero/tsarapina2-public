# -*- coding: utf-8 -*-
"""CA-1 driver (Tsarapina; FREEZE 06.09.2026).

Дизайн: CONTEXT_APPLICABILITY1_DESIGN.md (frozen). Ветка:
context_applicability1/strategy_v6.py; основная Strategy v0.3 не
меняется. ctx_now читается драйвером (envfact-сенсор) и передаётся
в suggest_v6; ctx знания — по цепочке knowledge→опыт→последнее
действие→args.ctx_extra; КАЖДОЕ действие фиксирует ctx_extra
(условие, при котором последствие проверялось).

Сценарии (по протоколу):
- L1: learn fix-a при ctx=absent; L2: learn fix-a2 при ctx=present
  (L2 ПОЗЖЕ L1 — recency-перевёртыш);
- T1: задача a при ctx=absent → ожидание S2 fix-a (1 действие);
- T2: задача a при ctx=present → ожидание S2 fix-a2 (1 действие);
- T3: чередование absent/present ×6 → 1 действие каждый раз;
- T4: known A (только L1) 1 действие; AB 1 действие fix-ab;
  C → exploration → fix-c (SEB v0.3); S3 объявленного конфликта
  (два знания ОДНОГО ctx) сохранён; swap: S2 после знания;
  determinism: повтор suggest идентичен.
Критерии PASS/BOUNDARY — в CONTEXT_APPLICABILITY1_DESIGN.md.
Сначала журнал, потом вердикт.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402
from strategy_v6 import suggest  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "CA1_run.log")
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-c"]
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %-40s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(present=False, symptom="a"):
    """Мир: symptom + (extra если present). extra наблюдаем envfact."""
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    flags = {"a": ["a"], "b": ["b"], "ab": ["a", "b"], "c": ["c"]}[symptom]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    if present:
        open("/run/tsasvc.lock.extra", "w").close()
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def env_extra():
    return polygon_sensor.sensor_envfact()[4]


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]


def mk_action(store, command, proposed_by, ctx):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "CA-1"}
    store.append_action(a)
    return a


def save_episode(store, problem, facts, acts, outcomes):
    """Опыт по действиям эпизода; update по последнему."""
    if not acts:
        return None
    last_res = None
    p = os.path.join(os.path.dirname(store.obs_jsonl), "results.jsonl")
    for line in open(p, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("action_id") == acts[-1]["action_id"]:
            last_res = rec
    if last_res is None:
        return None
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[a["action_id"] for a in acts],
        result_ref=last_res["result_id"], machine="ca1")
    experience.save(store, exp_full)
    out = outcomes[-1] if outcomes else "unknown"
    if out != "success":
        evs = store.read_evaluations(last_res["result_id"])
        out = evs[-1]["outcome"] if evs else "failure"
    update.apply(store, exp_full["experience_id"], out)
    return exp_full["experience_id"]


def learn(store, symptom, fix, present, ep):
    env_set(present=present, symptom=symptom)
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn", ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem=problem, observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="ca1")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN", "symptom": symptom, "fix": fix,
         "ctx": ctx, "ok": ok})
    return ok, ctx


def episode(store, present, ep, expect=None):
    """Задача симптом a: suggest_v6(ctx) → действие → исход."""
    env_set(present=present, symptom="a")
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest(store, {"problem": problem}, ctx_now=ctx,
                  by="ca1")
    sid = sug["strategy_id"]
    cmd = None
    if sid == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
    rule = sug["rationale"][0]["rule"] if sug["rationale"] else ""
    log({"ep": ep, "event": "SUGGEST", "strategy": sid, "cmd": cmd,
         "ctx": ctx, "rule": rule,
         "filter_used": sug.get("context_filter_used")})
    if sid != "S2" or cmd is None:
        log({"ep": ep, "event": "EPISODE", "strategy": sid, "cmd": None,
             "ok": False})
        return sug, None, False, ctx
    act = mk_action(store, cmd, proposed_by="ca1/%s" % ep, ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok else ev["outcome"]
    save_episode(store, problem, observer.collect(store), [act], [out])
    log({"ep": ep, "event": "EPISODE", "strategy": sid, "cmd": cmd,
         "ok": ok, "outcome": out, "ctx": ctx})
    return sug, cmd, ok, ctx


def exploration_episode(store, ep, present=False):
    """Задача c: SEB-механика v0.3 (гипотеза → exploration → перебор)."""
    env_set(present=present, symptom="c")
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    banned = []
    acts = []
    outcomes = []
    ok = False
    sug1 = suggest(store, {"problem": problem}, ctx_now=ctx, by="ca1",
                   banned_commands=banned)
    log({"ep": ep, "event": "SUGGEST", "strategy": sug1["strategy_id"],
         "rule": sug1["rationale"][0]["rule"] if sug1["rationale"] else "",
         "hypothesis": sug1.get("hypothesis"),
         "exploration": sug1.get("exploration"), "ctx": ctx})
    if sug1["strategy_id"] == "S2" and sug1.get("candidate_actions"):
        cmd = sug1["candidate_actions"][0]["command"]
        act = mk_action(store, cmd, proposed_by="ca1/hyp", ctx=ctx)
        res = executor.execute(store, act)
        ok_now = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok_now else ev["outcome"]
        acts.append(act)
        outcomes.append(out)
        log({"ep": ep, "event": "ACTION", "cmd": cmd, "outcome": out,
             "hypothesis": True})
        if ok_now:
            ok = True
        else:
            banned.append(cmd)
            sug2 = suggest(store, {"problem": problem}, ctx_now=ctx,
                           by="ca1", banned_commands=banned)
            if sug2.get("exploration"):
                log({"ep": ep, "event": "EXPLORATION_GRANTED"})
                for bcmd in BIN:
                    act = mk_action(store, bcmd,
                                    proposed_by="ca1/explore", ctx=ctx)
                    res = executor.execute(store, act)
                    ok_now = stable_active()
                    ev = evaluation.evaluate(store, res["result_id"],
                                             GOAL)
                    out = "success" if ok_now else ev["outcome"]
                    acts.append(act)
                    outcomes.append(out)
                    log({"ep": ep, "event": "ACTION", "cmd": bcmd,
                         "outcome": out, "explore": True})
                    if ok_now:
                        ok = True
                        break
    save_episode(store, problem, facts, acts, outcomes)
    log({"ep": ep, "event": "EPISODE", "strategy": "SEB", "cmd": None,
         "ok": ok, "actions": len(acts)})
    return ok, len(acts)


def fresh_store(name):
    d = os.path.join(DIR, "data_ca_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def synthetic_failure(store, symptom, cmd, ctx, ep):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = store.append_action({
        "schema_version": "0.1",
        "action_id": "act_sf_%s" % uuid.uuid4().hex[:8],
        "strategy_id": None, "proposed_by": "world/noise",
        "type": "command", "command": cmd,
        "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
        "proposed_at": now, "rationale": "ca1-synth"})
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
        machine="ca1")
    experience.save(store, exp)
    update.apply(store, exp["experience_id"], "failure")
    log({"ep": ep, "event": "SYNTH_FAILURE", "cmd": cmd, "ctx": ctx})


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== CONTEXT-APPLICABILITY-1 (FREEZE 06.09.2026) ==", flush=True)

    # --- основной стор: L1/L2 + T1/T2/T3 + swap + determinism ---
    st = fresh_store("main")
    ok, ctx1 = learn(st, "a", "fix-a", present=False, ep="L1")
    assert ok and ctx1 == "absent"
    ok, ctx2 = learn(st, "a", "fix-a2", present=True, ep="L2")
    assert ok and ctx2 == "present"
    # T1: ctx absent → fix-a (перевёртыш: fix-a2 свежее)
    sug, cmd, ok, ctx = episode(st, present=False, ep="T1")
    check("T1: ctx=absent → S2 fix-a (не fix-a2, recency-перевёртыш)",
          ok and cmd == "fix-a" and sug["strategy_id"] == "S2")
    # T2: ctx present → fix-a2
    sug, cmd, ok, ctx = episode(st, present=True, ep="T2")
    check("T2: ctx=present → S2 fix-a2", ok and cmd == "fix-a2"
          and sug["strategy_id"] == "S2")
    # T3: чередование ×6
    seq = [False, True, False, True, False, True]
    t3 = []
    for i, pr in enumerate(seq):
        sug, cmd, ok, ctx = episode(st, present=pr,
                                    ep="T3_%d" % (i + 1))
        expect = "fix-a" if not pr else "fix-a2"
        t3.append(ok and cmd == expect and sug["strategy_id"] == "S2")
    check("T3: чередование ×6 → правильный контекстный выбор, "
          "1 действие", all(t3))
    # swap: S2 после знания (модель не участвует)
    sug, cmd, ok, ctx = episode(st, present=False, ep="SWAP")
    check("SWAP: S2 fix-a (знание, не модель)", ok and cmd == "fix-a"
          and sug["strategy_id"] == "S2")
    # determinism
    s1 = suggest(st, {"problem": "tsasvc.service inactive symptom=a"},
                 ctx_now="absent", save=False)
    s2 = suggest(st, {"problem": "tsasvc.service inactive symptom=a"},
                 ctx_now="absent", save=False)
    check("DET: повторный suggest идентичен",
          s1["suggestion_id"] == s2["suggestion_id"])

    # --- T4a: known A (только L1-знание) ---
    stk = fresh_store("known")
    ok, _ = learn(stk, "a", "fix-a", present=False, ep="K_L1")
    sug, cmd, ok, ctx = episode(stk, present=False, ep="K_A")
    check("T4a: known A → 1 действие fix-a", ok and cmd == "fix-a")

    # --- T4b: AB ---
    stab = fresh_store("ab")
    ok, _ = learn(stab, "ab", "fix-ab", present=False, ep="AB_L1")
    env_set(present=False, symptom="ab")
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest(stab, {"problem": problem}, ctx_now=ctx, by="ca1")
    cmd = sug["candidate_actions"][0]["command"] \
        if sug["strategy_id"] == "S2" and sug["candidate_actions"] \
        else None
    check("T4b: AB → S2 fix-ab", cmd == "fix-ab"
          and sug["strategy_id"] == "S2")

    # --- T4c: C → exploration (SEB v0.3 сохранён) ---
    stc = fresh_store("c")
    ok, _ = learn(stc, "a", "fix-a", present=False, ep="C_L1")
    ok, _ = learn(stc, "b", "fix-b", present=False, ep="C_L2")
    ok_c, n_c = exploration_episode(stc, "C_ep1")
    check("T4c: C → exploration → fix-c (%d действий)" % n_c,
          ok_c and n_c >= 5)
    env_set(present=False, symptom="c")
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest(stc, {"problem": problem}, ctx_now=ctx, by="ca1")
    cmd = sug["candidate_actions"][0]["command"] \
        if sug["strategy_id"] == "S2" and sug["candidate_actions"] \
        else None
    check("T4c2: C после learn-c → S2 fix-c", cmd == "fix-c"
          and sug["strategy_id"] == "S2")

    # --- T4d: S3 объявленного конфликта (один ctx) ---
    sts = fresh_store("s3")
    ok, _ = learn(sts, "a", "fix-a", present=False, ep="S3_L1")
    synthetic_failure(sts, "a", "fix-a", "absent", "S3_f")
    kids = [v["knowledge_id"] for v in sts.read_knowledge_versions_all()
            if v["status"] == "active"]
    k_s = min(kids, key=lambda k: sts.read_knowledge(k)["created_at"])
    k_f = max(kids, key=lambda k: sts.read_knowledge(k)["created_at"])
    knowledge.declare_conflict(sts, k_s, k_f)
    env_set(present=False, symptom="a")
    ctx = env_extra()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest(sts, {"problem": problem}, ctx_now=ctx, by="ca1")
    check("T4d: S3 объявленного конфликта сохранён",
          sug["strategy_id"] == "S3")

    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== CA-1: %s ===" % ("PASS" if not failed
                                else "BOUNDARY/FAIL (%d)" % len(failed)))
    print("saved %s" % LOG, flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
