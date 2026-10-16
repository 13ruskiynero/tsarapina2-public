# -*- coding: utf-8 -*-
"""SEB-1 driver (Tsarapina, зона 5; FREEZE 06.09.2026).

Дизайн: SEB1_DESIGN.md (заморожен). Ветка strategy_v4; основная
Strategy v0.2 не меняется.

Для каждой механики M0/M1/M2/M3 на чистых сторах:
- ИСТОРИЯ: learn a/b/ab + решения (exploit-эталон: 1 действие);
- RETURN-A: learn a, learn b, задача a → S2 fix-a (1 действие);
- NOISE: знакомый a: success, синтетический шум-failure fix-a,
  success → задача a → fix-a (1 действие; exact не уходит в
  exploration);
- C×7: история A/B/AB, симптом c без learn (SEB-объект);
- SWAP: qwen25 C×3 после C-успеха (S2 fix-c).

Критерий успеха эпизода — УСТОЙЧИВЫЙ active (через 1.5с после
действия; урок Type=simple из G1). Exploration = систематический
перебор BIN (фиксированный порядок) до устойчивого success.
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

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402
from strategy_v4 import suggest_v4  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "SEB1_run.log")
MAX_ACTS = 14
FIX = {"a": "fix-a", "b": "fix-b", "ab": "fix-ab", "c": "fix-c"}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-c"]
MECHS = ["M0", "M1", "M2", "M3"]


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
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


def symptom_now():
    from observer import polygon_sensor
    src, raw, subj, prop, value = polygon_sensor.sensor_symptom()
    return value


def stable_active():
    """Устойчивый active: активен сейчас и через 1.5с."""
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "SEB-1"}
    store.append_action(a)
    return a


def add_learn(store, symptom, fix, ep):
    """learn: оператор показывает fix. СИМПТОМ фиксируется ДО
    лечения (provenance-дефект: опыт, построенный после execute,
    получал symptom=none — исправлено единообразно; см. RELEVANCE-1)."""
    env_set(symptom)
    sym = symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ok = stable_active()
    out = "success" if ok else "failure"
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem="tsasvc.service inactive symptom=%s" % sym,
        observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="seb1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"],
                     "success" if ok else ev["outcome"])
    log({"phase": ep, "event": "learn", "symptom": symptom,
         "problem_symptom": sym, "fix": fix,
         "stable_ok": ok, "outcome": out, "knowledge": bool(k)})
    return ok


def _save_episode(store, problem, facts, acts, outcomes):
    """Опыт+update по действиям эпизода; outcome успеха/последнего."""
    if not acts:
        return None
    # результат последнего действия
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
        result_ref=last_res["result_id"], machine="seb1")
    experience.save(store, exp_full)
    final_out = outcomes[-1] if outcomes else "unknown"
    if final_out == "success":
        out = "success"
    else:
        evs = store.read_evaluations(last_res["result_id"])
        out = evs[-1]["outcome"] if evs else "failure"
    k = update.apply(store, exp_full["experience_id"], out)
    return exp_full["experience_id"]


def run_seb_episode(store, symptom, mech, ep, max_acts=MAX_ACTS):
    """Эпизод под механикой. Возвращает (ok, actions, log_out)."""
    env_set(symptom)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    banned = []
    acts = []
    outcomes = []
    ok = False
    explored = False
    hypothesis_used = False
    loop_log = []
    for _ in range(max_acts):
        sug = suggest_v4(store, {"problem": problem}, mech=mech,
                         banned_commands=banned, save=True)
        sid = sug["strategy_id"]
        if sug.get("exploration"):
            explored = True
            log({"phase": ep, "event": "exploration_start", "mech": mech})
            for cmd in BIN:
                act = mk_action(store, cmd, proposed_by="strategy/explore")
                res = executor.execute(store, act)
                ok_now = stable_active()
                ev = evaluation.evaluate(store, res["result_id"], GOAL)
                out = "success" if ok_now else ev["outcome"]
                acts.append(act)
                outcomes.append(out)
                log({"phase": ep, "event": "action", "n": len(acts),
                     "command": cmd, "outcome": out, "explore": True})
                if ok_now:
                    ok = True
                    break
            break
        if sid == "S2" and sug.get("candidate_actions"):
            cmd = sug["candidate_actions"][0]["command"]
            hyp = sug.get("hypothesis", False)
            if hyp:
                hypothesis_used = True
            act = mk_action(store, cmd,
                            proposed_by="strategy/S2%s"
                            % ("/hypothesis" if hyp else ""))
            res = executor.execute(store, act)
            ok_now = stable_active()
            ev = evaluation.evaluate(store, res["result_id"], GOAL)
            out = "success" if ok_now else ev["outcome"]
            acts.append(act)
            outcomes.append(out)
            log({"phase": ep, "event": "action", "n": len(acts),
                 "command": cmd, "outcome": out,
                 "hypothesis": hyp, "rule":
                 sug["rationale"][0]["rule"] if sug["rationale"] else ""})
            if ok_now:
                ok = True
                break
            # не-success: бан (M1/M3) или повтор-стоп (M0/M2:
            # следующая итерация M2 даст exploration)
            banned.append(cmd)
            # M0: recency-повтор не даёт прогресса — стоп при повторе
            # уже испробованной в этом эпизоде команды
            if mech == "M0" and cmd in [x["command"] for x in acts]:
                break
            continue
        if sid in ("S1", "S3"):
            loop_log.append({"strategy": sid,
                             "rule": sug["rationale"][0]["rule"]
                             if sug["rationale"] else ""})
            break
        break
    eid = _save_episode(store, problem, facts, acts, outcomes)
    log({"phase": ep, "event": "episode", "mech": mech, "symptom": symptom,
         "success": ok, "explored": explored,
         "hypothesis_used": hypothesis_used,
         "actions": len(acts), "outcomes": outcomes,
         "loop": loop_log, "knowledge_total":
         len({v["knowledge_id"] for v in
              store.read_knowledge_versions_all()})})
    return ok, [a["command"] for a in acts], explored, hypothesis_used


def history_train(store, mech, ep_pref):
    """История A/B/AB: learn + решения; exploit-эталон 1 действие."""
    out = {}
    assert add_learn(store, "a", FIX["a"], "%s_a_learn" % ep_pref)
    for i in (1, 2):
        ok, acts, exp_, hyp_ = run_seb_episode(store, "a", mech,
                                               "%s_a_%d" % (ep_pref, i))
        out["a%d" % i] = {"ok": ok, "actions": len(acts)}
    assert add_learn(store, "b", FIX["b"], "%s_b_learn" % ep_pref)
    for i in (1, 2):
        ok, acts, exp_, hyp_ = run_seb_episode(store, "b", mech,
                                               "%s_b_%d" % (ep_pref, i))
        out["b%d" % i] = {"ok": ok, "actions": len(acts)}
    assert add_learn(store, "ab", FIX["ab"], "%s_ab_learn" % ep_pref)
    for i in (1, 2):
        ok, acts, exp_, hyp_ = run_seb_episode(store, "ab", mech,
                                               "%s_ab_%d" % (ep_pref, i))
        out["ab%d" % i] = {"ok": ok, "actions": len(acts)}
    return out


def synthetic_failure(store, symptom, cmd, ep):
    """Синтетический шум-эпизод: мир ответил failure на правильное
    действие (без полигона). Для noise-сценария."""
    from storage.store import Store as _S
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = store.append_action({
        "schema_version": "0.1",
        "action_id": "act_noise_%s" % uuid.uuid4().hex[:8],
        "strategy_id": None, "proposed_by": "world/noise",
        "type": "command", "command": cmd,
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": now, "rationale": "noise control"})
    sb = {"service:tsasvc.state": "inactive"}
    rid = store.append_result({
        "schema_version": "0.1",
        "result_id": "res_noise_%s" % uuid.uuid4().hex[:8],
        "action_id": aid, "executed_at": now,
        "exit_code": 0, "stdout": "x", "stderr": "",
        "state_before": sb, "state_after": {"service:tsasvc.state":
                                            "inactive"},
        "outcome": "unverified"})
    exp = experience.build(
        problem="tsasvc.service inactive symptom=%s" % symptom,
        observations=[], actions=[aid], result_ref=rid,
        machine="seb1-noise")
    experience.save(store, exp)
    update.apply(store, exp["experience_id"], "failure")
    log({"phase": ep, "event": "noise_failure", "symptom": symptom,
         "cmd": cmd})


def run_return_a(mech):
    st = _fresh_store("returnA_%s" % mech)
    add_learn(st, "a", FIX["a"], "ra_a_learn")
    add_learn(st, "b", FIX["b"], "ra_b_learn")
    ok, acts, exp_, hyp_ = run_seb_episode(st, "a", mech, "ra_a_task")
    return {"ok": ok, "actions": len(acts), "acts": acts}


def run_noise(mech):
    st = _fresh_store("noise_%s" % mech)
    add_learn(st, "a", FIX["a"], "no_a_learn")
    ok1, acts1, _, _ = run_seb_episode(st, "a", mech, "no_a_s1")
    synthetic_failure(st, "a", "fix-a", "no_a_f")
    ok2, acts2, _, _ = run_seb_episode(st, "a", mech, "no_a_s2")
    ok3, acts3, _, _ = run_seb_episode(st, "a", mech, "no_a_task")
    return {"s1": {"ok": ok1, "n": len(acts1)},
            "after_noise_task": {"ok": ok3, "n": len(acts3),
                                 "acts": acts3}}


def run_c(mech):
    st = _fresh_store("c_%s" % mech)
    hist = history_train(st, mech, "C_hist")
    c = []
    for i in range(1, 8):
        ok, acts, exp_, hyp_ = run_seb_episode(st, "c", mech, "C_C%d" % i)
        c.append({"ep": i, "ok": ok, "actions": len(acts),
                  "explored": exp_, "hypothesis": hyp_, "acts": acts})
    swap = []
    for i in range(1, 4):
        ok, acts, exp_, hyp_ = run_seb_episode(
            st, "c", mech, "C_swap%d" % i, )  # провайдер не нужен: S2
        swap.append({"ep": i, "ok": ok, "actions": len(acts),
                     "acts": acts})
    return {"history": hist, "C": c, "swap": swap}


def _fresh_store(name):
    d = os.path.join(DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== SEB-1 (FREEZE 06.09.2026) ==", flush=True)
    results = {}
    for mech in MECHS:
        print("--- %s ---" % mech, flush=True)
        ra = run_return_a(mech)
        no = run_noise(mech)
        c = run_c(mech)
        results[mech] = {"return_a": ra, "noise": no, "C": c}
    log({"event": "summary", "data": results})
    print("== SUMMARY ==", flush=True)
    for mech in MECHS:
        r = results[mech]
        print("%s: return_a=%s actions; noise task=%s actions; "
              "C=[%s]; swap=[%s]"
              % (mech,
                 r["return_a"]["actions"],
                 r["noise"]["after_noise_task"]["n"],
                 ",".join("%d:%s" % (x["ep"], "OK" if x["ok"]
                                     else "no(%d)" % x["actions"])
                          for x in r["C"]["C"]),
                 ",".join("OK" if x["ok"] else "no" for x in r["C"]["swap"])))
    print("saved %s" % LOG, flush=True)


if __name__ == "__main__":
    main()
