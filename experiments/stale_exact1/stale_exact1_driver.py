# -*- coding: utf-8 -*-
"""STALE-EXACT-1 driver (Tsarapina; FREEZE 06.09.2026).

Дизайн: STALE_EXACT1_DESIGN.md (frozen). Experimental: strategy_v5.
Основная Strategy v0.3 не меняется. Мир: extra — скрытое условие
(сенсор его не видит; симптом 'a' одинаков в старом и новом мире).

Механики F0..F3; на механику — чистые сторы:
  PRESERVE: (a) известный A = 1 действие; (b) return-A = 1 действие;
    (c) AB = 1 действие; (d) SEB-C: C1 гипотеза→exploration→fix-c,
    C2–C4 S2 fix-c; (e) S3 объявленного конфликта; (f) детерминизм;
  STALE: learn a (старый мир) → мир new → эпизод 1 (M1, сырой) →
    эпизод 2 (M2) → эпизод 3 (после fix-a2: S2, 1 действие);
  NOISE (M3): learn a → synthetic шум-failure → эпизод a (старый
    мир): не должно быть поиска.

События журнала: EXACT_SELECTED, ACTION_FAILED, ACTION_SUCCESS,
CONFLICT_DECLARED, EXPLORATION_GRANTED, S3_STOP. Сначала журнал,
потом механика, потом интерпретация.
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
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402
from strategy_v5 import suggest_v5, auto_declare_stale  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "STALE_EXACT1_run.log")
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-c"]


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def _clear_flags():
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)


def env_set(symptoms, world="old"):
    """symptoms: a/b/ab/c. world=new → скрытый extra (устаревание)."""
    _run(["systemctl", "stop", SVC])
    _clear_flags()
    flags = {"a": ["a"], "b": ["b"], "ab": ["a", "b"], "c": ["c"]}[symptoms]
    if world == "new" and symptoms == "a":
        flags = ["a", "extra"]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def symptom_now():
    from observer import polygon_sensor
    return polygon_sensor.sensor_symptom()[4]


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "STALE-EXACT-1"}
    store.append_action(a)
    return a


def _mk_episode_update(store, problem, facts, acts, outcomes):
    """Опыт + update по действиям эпизода (последнее действие —
    зафиксированное последствие)."""
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
        result_ref=last_res["result_id"], machine="stale-exact-1")
    experience.save(store, exp_full)
    out = outcomes[-1] if outcomes else "unknown"
    if out != "success":
        evs = store.read_evaluations(last_res["result_id"])
        out = evs[-1]["outcome"] if evs else "failure"
    k = update.apply(store, exp_full["experience_id"], out)
    return k["knowledge_id"] if k else None


def learn(store, symptom, fix, ep, world="old"):
    env_set(symptom, world=world)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem=problem, observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="stale-exact-1")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN", "symptom": symptom, "fix": fix,
         "world": world, "ok": ok})
    return ok


def synthetic_failure(store, symptom, cmd, ep):
    """Шум: мир ответил failure на правильное действие (мир не
    менялся). Опыт+знание failure."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = store.append_action({
        "schema_version": "0.1",
        "action_id": "act_sf_%s" % uuid.uuid4().hex[:8],
        "strategy_id": None, "proposed_by": "world/noise",
        "type": "command", "command": cmd,
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": now, "rationale": "noise"})
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
        machine="stale-exact-1")
    experience.save(store, exp)
    update.apply(store, exp["experience_id"], "failure")
    kid = None
    for v in store.read_knowledge_versions_all():
        kid = v["knowledge_id"]
    log({"ep": ep, "event": "ACTION_FAILED", "cmd": cmd, "kind": "noise"})
    return kid


def do_exploration(store, problem, facts, ep):
    """Систематический перебор BIN до устойчивого success (право
    искать после exploration-флага). Возвращает ok."""
    acts = []
    outcomes = []
    ok = False
    for bcmd in BIN:
        act = mk_action(store, bcmd, proposed_by="stale/explore")
        res = executor.execute(store, act)
        ok_now = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok_now else ev["outcome"]
        acts.append(act)
        outcomes.append(out)
        log({"ep": ep, "event": "ACTION_OK" if ok_now else
             "ACTION_FAILED", "cmd": bcmd, "explore": True,
             "outcome": out})
        if ok_now:
            ok = True
            break
    _mk_episode_update(store, problem, facts, acts, outcomes)
    return ok


def run_step(store, symptom, mech, ep, world="old", banned=None,
             declare_after_fail=False):
    """Один шаг: suggest_v5 → действие (если S2) → устойчивый исход.
    Возвращает dict-событие."""
    env_set(symptom, world=world)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest_v5(store, {"problem": problem}, mech=mech,
                     banned_commands=banned, by="stale-exact-1")
    sid = sug["strategy_id"]
    rec = {"ep": ep, "mech": mech, "world": world, "symptom": symptom,
           "strategy": sid,
           "hypothesis": sug.get("hypothesis"),
           "exploration": sug.get("exploration"),
           "conflict_stop": sug.get("conflict_stop")}
    if sid == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
        rule = sug["rationale"][0]["rule"] if sug["rationale"] else ""
        rec["cmd"] = cmd
        rec["event"] = ("EXACT_SELECTED" if rule == "known_fix"
                        else "HYPOTHESIS_SELECTED")
        log(rec)
        act = mk_action(store, cmd, proposed_by="stale/" + rule)
        res = executor.execute(store, act)
        ok = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok else ev["outcome"]
        log({"ep": ep, "event": "ACTION_OK" if ok else "ACTION_FAILED",
             "cmd": cmd, "outcome": out})
        last_kid = _mk_episode_update(store, problem, facts, [act], [out])
        if not ok and declare_after_fail and last_kid:
            pair = auto_declare_stale(store, last_kid,
                                      by="stale-exact-1/v1")
            if pair:
                log({"ep": ep, "event": "CONFLICT_DECLARED",
                     "pair": list(pair)})
        rec["ok"] = ok
        rec["outcome"] = out
        rec["action_count"] = 1
        return rec
    if sid == "S3":
        log({"ep": ep, "event": "S3_STOP",
             "rule": sug["rationale"][0]["rule"] if sug["rationale"]
             else "", "conflict_stop": sug.get("conflict_stop")})
        rec["ok"] = False
        rec["event"] = "S3_STOP"
        if sug.get("exploration"):
            log({"ep": ep, "event": "EXPLORATION_GRANTED",
                 "rule": "conflict_exploration"})
            ok = do_exploration(store, problem, facts, ep)
            rec["ok"] = ok
            rec["event"] = "EXPLORATION_DONE"
            rec["exploration"] = True
        return rec
    # S1 / exploration-флаг
    log({"ep": ep, "event": "S1_OBSERVE",
         "exploration": sug.get("exploration")})
    rec["ok"] = False
    rec["event"] = "S1"
    if sug.get("exploration"):
        log({"ep": ep, "event": "EXPLORATION_GRANTED",
             "rule": "insufficiency_exploration"})
        ok = do_exploration(store, problem, facts, ep)
        rec["ok"] = ok
        rec["event"] = "EXPLORATION_DONE"
        rec["exploration"] = True
    return rec


def exploration_episode(store, symptom, mech, ep, world="old"):
    """F3/SEB: эпизод с перебором при exploration-флаге."""
    env_set(symptom, world=world)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    banned = []
    acts = []
    outcomes = []
    ok = False
    explored = False
    sug1 = suggest_v5(store, {"problem": problem}, mech=mech,
                      banned_commands=None, by="stale-exact-1")
    if sug1["strategy_id"] == "S2" and sug1.get("candidate_actions"):
        cmd = sug1["candidate_actions"][0]["command"]
        rule = sug1["rationale"][0]["rule"] if sug1["rationale"] else ""
        log({"ep": ep, "event": "EXACT_SELECTED" if rule == "known_fix"
             else "HYPOTHESIS_SELECTED", "cmd": cmd})
        act = mk_action(store, cmd, proposed_by="stale/" + rule)
        res = executor.execute(store, act)
        ok_now = stable_active()
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out = "success" if ok_now else ev["outcome"]
        acts.append(act)
        outcomes.append(out)
        log({"ep": ep, "event": "ACTION_OK" if ok_now else
             "ACTION_FAILED", "cmd": cmd, "outcome": out})
        if ok_now:
            ok = True
        else:
            banned.append(cmd)
            sug2 = suggest_v5(store, {"problem": problem}, mech=mech,
                              banned_commands=banned,
                              by="stale-exact-1")
            if sug2.get("exploration"):
                explored = True
                log({"ep": ep, "event": "EXPLORATION_GRANTED",
                     "rule": sug2["rationale"][-1]["rule"]})
                for bcmd in BIN:
                    act = mk_action(store, bcmd,
                                    proposed_by="stale/explore")
                    res = executor.execute(store, act)
                    ok_now = stable_active()
                    ev = evaluation.evaluate(store, res["result_id"],
                                             GOAL)
                    out = "success" if ok_now else ev["outcome"]
                    acts.append(act)
                    outcomes.append(out)
                    log({"ep": ep, "event": "ACTION_OK" if ok_now else
                         "ACTION_FAILED", "cmd": bcmd, "explore": True,
                         "outcome": out})
                    if ok_now:
                        ok = True
                        break
            elif sug2["strategy_id"] == "S3":
                log({"ep": ep, "event": "S3_STOP"})
            else:
                log({"ep": ep, "event": "S1_OBSERVE"})
    else:
        log({"ep": ep, "event": "S1_OBSERVE",
             "strategy": sug1["strategy_id"]})
    _mk_episode_update(store, problem, facts, acts, outcomes)
    return ok, len(acts), explored


def fresh_store(name):
    d = os.path.join(DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def preserve(mech):
    """Критерии «Сохраняем» на механику."""
    out = {}
    st = fresh_store("preserve_%s" % mech)
    # (a) известный A
    learn(st, "a", "fix-a", "%s_learn_a" % mech)
    r = run_step(st, "a", mech, "%s_A1" % mech)
    out["A"] = r.get("ok") and r.get("cmd") == "fix-a" and \
        r.get("strategy") == "S2" and r.get("action_count") == 1
    # (b) return-A
    learn(st, "b", "fix-b", "%s_learn_b" % mech)
    r = run_step(st, "a", mech, "%s_retA" % mech)
    out["return_A"] = r.get("ok") and r.get("cmd") == "fix-a" and \
        r.get("strategy") == "S2"
    # (c) AB
    learn(st, "ab", "fix-ab", "%s_learn_ab" % mech)
    r = run_step(st, "ab", mech, "%s_AB" % mech)
    out["AB"] = r.get("ok") and r.get("cmd") == "fix-ab"
    # (d) SEB-C: C1 (exploration для F3-мира; SEB-мех в v5 даёт
    # exploration на отсутствии exact) и C2 (S2)
    ok1, n1, exp1 = exploration_episode(st, "c", mech, "%s_C1" % mech)
    r = run_step(st, "c", mech, "%s_C2" % mech)
    out["SEB_C"] = ok1 and r.get("ok") and r.get("cmd") == "fix-c" and \
        r.get("strategy") == "S2"
    # (e) S3 объявленного конфликта
    st2 = fresh_store("s3_%s" % mech)
    learn(st2, "a", "fix-a", "%s_s3_learn" % mech)
    kf = synthetic_failure(st2, "a", "fix-a", "%s_s3_f" % mech)
    ks = None
    for v in st2.read_knowledge_versions_all():
        if v["status"] == "active" and v["knowledge_id"] != kf:
            ks = v["knowledge_id"]
    knowledge.declare_conflict(st2, kf, ks)
    r = run_step(st2, "a", mech, "%s_s3_task" % mech)
    out["S3_declared"] = r.get("strategy") == "S3"
    # (f) determinism
    s1 = suggest_v5(st, {"problem": "tsasvc.service inactive "
                      "symptom=a"}, mech=mech, save=False)
    s2 = suggest_v5(st, {"problem": "tsasvc.service inactive "
                      "symptom=a"}, mech=mech, save=False)
    out["determinism"] = s1["suggestion_id"] == s2["suggestion_id"]
    log({"ep": "preserve_%s" % mech, "event": "PRESERVE_RESULT",
         "data": out})
    return out


def stale_scenario(mech):
    """M1/M2: устаревание."""
    out = {}
    st = fresh_store("stale_%s" % mech)
    learn(st, "a", "fix-a", "%s_st_learn" % mech)
    declare_on = mech in ("F1", "F2", "F3")
    r1 = run_step(st, "a", mech, "%s_st_ep1" % mech, world="new",
                  declare_after_fail=declare_on)
    out["ep1"] = {"ok": r1.get("ok"), "cmd": r1.get("cmd"),
                  "event": r1.get("event")}
    r2 = run_step(st, "a", mech, "%s_st_ep2" % mech, world="new",
                  declare_after_fail=declare_on)
    out["ep2"] = {"ok": r2.get("ok"), "cmd": r2.get("cmd"),
                  "event": r2.get("event"),
                  "exploration": r2.get("exploration")}
    if r2.get("ok"):
        r3 = run_step(st, "a", mech, "%s_st_ep3" % mech, world="new")
        out["ep3"] = {"ok": r3.get("ok"), "cmd": r3.get("cmd"),
                      "strategy": r3.get("strategy")}
    log({"ep": "stale_%s" % mech, "event": "STALE_RESULT", "data": out})
    return out


def noise_scenario(mech):
    """M3: шум (мир старый; fix-a правильный)."""
    out = {}
    st = fresh_store("noise_%s" % mech)
    learn(st, "a", "fix-a", "%s_no_learn" % mech)
    declare_on = mech in ("F1", "F2", "F3")
    kf = synthetic_failure(st, "a", "fix-a", "%s_no_f" % mech)
    if declare_on:
        ks = None
        for v in st.read_knowledge_versions_all():
            if v["status"] == "active" and v["knowledge_id"] != kf:
                ks = v["knowledge_id"]
        if ks:
            pair = auto_declare_stale(st, kf, by="stale-exact-1/v1")
            if pair is None:
                knowledge.declare_conflict(st, kf, ks)
            log({"ep": "%s_no" % mech, "event": "CONFLICT_DECLARED",
                 "kind": "noise"})
    r = run_step(st, "a", mech, "%s_no_task" % mech)
    out["after_noise"] = {"ok": r.get("ok"), "cmd": r.get("cmd"),
                          "event": r.get("event"),
                          "strategy": r.get("strategy"),
                          "exploration": r.get("exploration")}
    log({"ep": "noise_%s" % mech, "event": "NOISE_RESULT", "data": out})
    return out


def main():
    mechs = sys.argv[1].split(",") if len(sys.argv) > 1 else \
        ["F0", "F1", "F2", "F3"]
    open(LOG, "w", encoding="utf-8").close()
    print("== STALE-EXACT-1 (FREEZE 06.09.2026) ==", flush=True)
    env_set("a")  # полигон в чистое состояние
    results = {}
    for mech in mechs:
        print("--- %s ---" % mech, flush=True)
        pres = preserve(mech)
        stale = stale_scenario(mech)
        noise = noise_scenario(mech)
        results[mech] = {"preserve": pres, "stale": stale,
                         "noise": noise}
    log({"event": "summary", "data": results})
    print("== SUMMARY ==", flush=True)
    for mech in mechs:
        r = results[mech]
        print("%s preserve=%s stale_ep1=%s stale_ep2=%s noise=%s"
              % (mech,
                 r["preserve"],
                 r["stale"]["ep1"],
                 r["stale"]["ep2"],
                 r["noise"]["after_noise"]), flush=True)
    print("saved %s" % LOG, flush=True)


if __name__ == "__main__":
    main()
