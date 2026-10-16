# -*- coding: utf-8 -*-
"""TE-1 driver (Tsarapina; FREEZE 06.09.2026). Ветка transition_event1.

База v0.4 + experimental strategy_v7 (переход по событию E2:
2-й последовательный non-success того же (адрес, команда) →
exploration). Прогон частями: python3 te1_driver.py base|stale|noise|m4
(общий лог TE1_run.log). Порядок анализа: сырые траектории →
событие → восстановление → noise → остальное → вердикт.

Миры: w1=[a], w2=[a,q] (q скрыт; fix-aq лечит), noise=[a,n].
BIN (перебор): start, restart, fix-a, fix-b, fix-ab, fix-a2,
fix-aq, fix-c.
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
from strategy_v7 import suggest_v7  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "TE1_run.log")
WORLDS = {"w1": ["a"], "w2": ["a", "q"], "noise": ["a", "n"],
          "b": ["b"], "c": ["c"], "ab": ["a", "b"]}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-aq", "fix-c"]
TRACK = []


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(world):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in WORLDS[world]:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def ctx_now():
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
         "rationale": "TE-1"}
    store.append_action(a)
    return a


def save_episode(store, problem, facts, act, result_id, outcome):
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=result_id,
        machine="te-1")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"], outcome)


def learn(store, world, fix, ep):
    env_set(world)
    ctx = ctx_now()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn", ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    save_episode(store, problem, facts, act, res["result_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "series": "LEARN", "event": "LEARN", "world": world,
         "fix": fix, "ok": ok, "ctx": ctx})
    return ok


def suggest_and_execute(store, world, ep, series):
    """Эпизод: раунды suggest_v7: (a) E2-transition/exploration →
    SEB-перебор до устойчивого success; (b) S2-гипотеза → действие;
    banned-накопление (маршрут SEB). Возвращает (ok, n, transition)."""
    env_set(world)
    ctx = ctx_now()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    banned = []
    acts = []
    outcomes = []
    ok = False
    transition = False
    for _ in range(4):
        sug = suggest_v7(store, {"problem": problem}, ctx_now=ctx,
                         by="te-1", banned_commands=banned)
        sid = sug["strategy_id"]
        transition = transition or bool(
            sug.get("event") == "E2_TRANSITION")
        log({"ep": ep, "series": series, "event": "SUGGEST",
             "strategy": sid,
             "rule": sug["rationale"][0]["rule"]
             if sug["rationale"] else "",
             "exploration": sug.get("exploration"),
             "hypothesis": sug.get("hypothesis"),
             "transition": bool(sug.get("event") == "E2_TRANSITION"),
             "ctx": ctx})
        if transition or sug.get("exploration"):
            # SEB-перебор до устойчивого success (право искать)
            outcomes = []
            for bcmd in BIN:
                act = mk_action(store, bcmd, proposed_by="te1/explore",
                                ctx=ctx)
                res = executor.execute(store, act)
                ok_now = stable_active()
                ev = evaluation.evaluate(store, res["result_id"], GOAL)
                out = "success" if ok_now else ev["outcome"]
                acts.append(act)
                outcomes.append(out)
                log({"ep": ep, "series": series, "event": "EXPLORE",
                     "cmd": bcmd, "outcome": out})
                if ok_now:
                    ok = True
                    break
            break
        if sid == "S2" and sug.get("candidate_actions"):
            cmd = sug["candidate_actions"][0]["command"]
            act = mk_action(store, cmd, proposed_by="te1/s2", ctx=ctx)
            res = executor.execute(store, act)
            ok_now = stable_active()
            ev = evaluation.evaluate(store, res["result_id"], GOAL)
            out = "success" if ok_now else ev["outcome"]
            acts.append(act)
            outcomes.append(out)
            log({"ep": ep, "series": series, "event": "ACTION",
                 "cmd": cmd, "outcome": out,
                 "hypothesis": sug.get("hypothesis")})
            if ok_now:
                ok = True
                break
            banned.append(cmd)
            if not sug.get("hypothesis"):
                # обычный S2 (exact): эпизод = 1 действие; повтора нет
                break
            continue  # гипотеза не удалась → раунд exploration
        log({"ep": ep, "series": series, "event": "NO_ACTION",
             "strategy": sid})
        break
    if acts:
        save_episode(store, problem, facts, acts[-1],
                     _last_result(store, acts[-1]["action_id"]),
                     "success" if ok else outcomes[-1])
    TRACK.append((series, "s" if ok else "f"))
    return ok, len(acts), transition


def _last_result(store, aid):
    p = os.path.join(os.path.dirname(store.obs_jsonl), "results.jsonl")
    last = None
    for line in open(p, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("action_id") == aid:
            last = rec
    return last["result_id"] if last else None


def fresh_store(name):
    d = os.path.join(DIR, "data_te1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def part_base():
    print("--- BASE (свойства v0.4 на контуре с механикой) ---",
          flush=True)
    # known A
    st = fresh_store("base_known")
    learn(st, "w1", "fix-a", "bA_L1")
    ok, n, tr = suggest_and_execute(st, "w1", "bA_1", "KNOWN")
    log({"series": "KNOWN", "event": "RESULT", "ok": ok, "n": n,
         "transition": tr})
    # AB
    st2 = fresh_store("base_ab")
    learn(st2, "ab", "fix-ab", "bAB_L1")
    ok, n, tr = suggest_and_execute(st2, "ab", "bAB_1", "AB")
    log({"series": "AB", "event": "RESULT", "ok": ok, "n": n,
         "transition": tr, "cmd_fix_ab": True})
    # SEB-C: learn a (w1), b (b-мир) → задача c
    st3 = fresh_store("base_c")
    learn(st3, "w1", "fix-a", "bC_L1")
    learn(st3, "b", "fix-b", "bC_L2")
    ok, n, tr = suggest_and_execute(st3, "c", "bC_1", "SEBC")
    log({"series": "SEBC", "event": "RESULT", "ok": ok, "n": n,
         "transition": tr})
    ok, n, tr = suggest_and_execute(st3, "c", "bC_2", "SEBC2")
    log({"series": "SEBC2", "event": "RESULT", "ok": ok, "n": n})
    # S3
    st4 = fresh_store("base_s3")
    learn(st4, "w1", "fix-a", "bS_L1")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = st4.append_action({
        "schema_version": "0.1",
        "action_id": "act_s3f_%s" % time.time(),
        "strategy_id": None, "proposed_by": "world/noise",
        "type": "command", "command": "fix-a",
        "args": {"goal": GOAL, "ctx_extra": "absent"},
        "permitted": True, "proposed_at": now, "rationale": "te1-s3"})
    rid = st4.append_result({
        "schema_version": "0.1",
        "result_id": "res_s3f_%s" % time.time(),
        "action_id": aid, "executed_at": now, "exit_code": 0,
        "stdout": "x", "stderr": "",
        "state_before": {"service:tsasvc.state": "inactive"},
        "state_after": {"service:tsasvc.state": "inactive"},
        "outcome": "unverified"})
    exp4 = experience.build(
        problem="tsasvc.service inactive symptom=a",
        observations=[], actions=[aid], result_ref=rid, machine="te-1")
    experience.save(st4, exp4)
    update.apply(st4, exp4["experience_id"], "failure")
    kids = [v["knowledge_id"] for v in
            st4.read_knowledge_versions_all() if v["status"] == "active"]
    k_s = min(kids, key=lambda k: st4.read_knowledge(k)["created_at"])
    k_f = max(kids, key=lambda k: st4.read_knowledge(k)["created_at"])
    knowledge.declare_conflict(st4, k_s, k_f)
    env_set("w1")
    ctx = ctx_now()
    sug = suggest_v7(st4, {"problem": "tsasvc.service inactive "
                          "symptom=a"}, ctx_now=ctx, save=False)
    log({"series": "S3", "event": "RESULT", "strategy": sug["strategy_id"],
         "transition": sug.get("event") == "E2_TRANSITION"})
    # determinism
    s1 = suggest_v7(st4, {"problem": "tsasvc.service inactive "
                      "symptom=a"}, ctx_now="absent", save=False)
    s2 = suggest_v7(st4, {"problem": "tsasvc.service inactive "
                      "symptom=a"}, ctx_now="absent", save=False)
    log({"series": "DET", "event": "RESULT",
         "same": s1["suggestion_id"] == s2["suggestion_id"]})


def part_stale():
    print("--- STALE (событие на 2-м f → exploration → fix-aq) ---",
          flush=True)
    st = fresh_store("stale")
    learn(st, "w1", "fix-a", "st_L1")
    for i in (1, 2):
        ok, n, tr = suggest_and_execute(st, "w2", "st_f%d" % i, "STALE")
        log({"series": "STALE", "event": "RESULT", "i": i, "ok": ok,
             "n": n, "transition": tr})
    # 3-й эпизод: событие уже собрано на 2-м? событие сработало в
    # эпизоде 2 (после 2-го f история f,f) — переход был в эпизоде 2.
    # Эпизоды 3-5: после learn fix-aq → S2
    for i in (3, 4, 5):
        ok, n, tr = suggest_and_execute(st, "w2", "st_%d" % i, "STALE")
        log({"series": "STALE", "event": "RESULT", "i": i, "ok": ok,
             "n": n, "transition": tr})


def part_noise():
    print("--- NOISE (single / double / alt / mix) ---", flush=True)
    # single
    st = fresh_store("noise_single")
    learn(st, "w1", "fix-a", "ns_L1")
    for w, ep in (("w1", "ns_s1"), ("w1", "ns_s2"), ("noise", "ns_f1"),
                  ("w1", "ns_s3"), ("w1", "ns_s4")):
        ok, n, tr = suggest_and_execute(st, w, ep, "SINGLE")
        log({"series": "SINGLE", "event": "RESULT", "ep": ep, "ok": ok,
             "n": n, "transition": tr})
    # double
    st2 = fresh_store("noise_double")
    learn(st2, "w1", "fix-a", "nd_L1")
    for w, ep in (("w1", "nd_s1"), ("w1", "nd_s2"), ("noise", "nd_f1"),
                  ("noise", "nd_f2"), ("w1", "nd_s3"), ("w1", "nd_s4"),
                  ("w1", "nd_s5")):
        ok, n, tr = suggest_and_execute(st2, w, ep, "DOUBLE")
        log({"series": "DOUBLE", "event": "RESULT", "ep": ep, "ok": ok,
             "n": n, "transition": tr})
    # alt
    st3 = fresh_store("noise_alt")
    learn(st3, "w1", "fix-a", "na_L1")
    for w, ep in (("w1", "na_s1"), ("noise", "na_f1"), ("w1", "na_s2"),
                  ("noise", "na_f2"), ("w1", "na_s3"), ("w1", "na_s4")):
        ok, n, tr = suggest_and_execute(st3, w, ep, "ALT")
        log({"series": "ALT", "event": "RESULT", "ep": ep, "ok": ok,
             "n": n, "transition": tr})
    # mix
    st4 = fresh_store("noise_mix")
    learn(st4, "w1", "fix-a", "nm_L1")
    for w, ep in (("w1", "nm_s1"), ("noise", "nm_f1"), ("w1", "nm_s2"),
                  ("w2", "nm_f1"), ("w2", "nm_f2"), ("w2", "nm_f3"),
                  ("w2", "nm_s3")):
        ok, n, tr = suggest_and_execute(st4, w, ep, "MIX")
        log({"series": "MIX", "event": "RESULT", "ep": ep, "ok": ok,
             "n": n, "transition": tr})


def part_m4():
    print("--- M4 (не-success разных команд не суммируются) ---",
          flush=True)
    st = fresh_store("m4")
    learn(st, "w1", "fix-a", "m4_L1")
    # эпизод w2: fix-a → f (1-й не-success fix-a)
    ok, n, tr = suggest_and_execute(st, "w2", "m4_f1", "M4")
    # синтетический не-success команды fix-b (тот же адрес)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    aid = st.append_action({
        "schema_version": "0.1",
        "action_id": "act_m4b_%s" % time.time(),
        "strategy_id": None, "proposed_by": "world",
        "type": "command", "command": "fix-b",
        "args": {"goal": GOAL, "ctx_extra": "absent"},
        "permitted": True, "proposed_at": now, "rationale": "m4"})
    rid = st.append_result({
        "schema_version": "0.1",
        "result_id": "res_m4b_%s" % time.time(),
        "action_id": aid, "executed_at": now, "exit_code": 0,
        "stdout": "x", "stderr": "",
        "state_before": {"service:tsasvc.state": "inactive"},
        "state_after": {"service:tsasvc.state": "inactive"},
        "outcome": "unverified"})
    exp = experience.build(
        problem="tsasvc.service inactive symptom=a",
        observations=[], actions=[aid], result_ref=rid, machine="te-1")
    experience.save(st, exp)
    update.apply(st, exp["experience_id"], "failure")
    # теперь история: fix-a [s,f], fix-b [f] — события нет
    sug = suggest_v7(st, {"problem": "tsasvc.service inactive "
                      "symptom=a"}, ctx_now="absent", save=False)
    log({"series": "M4", "event": "RESULT",
         "strategy": sug["strategy_id"],
         "transition": sug.get("event") == "E2_TRANSITION",
         "note": "ожидание: без события (fix-a: 1 f; fix-b: 1 f)"})


def main():
    parts = sys.argv[1:] or ["base", "stale", "noise", "m4"]
    if not os.path.exists(LOG):
        open(LOG, "w", encoding="utf-8").close()
    print("== TE-1 (FREEZE 06.09.2026); parts: %s ==" % parts, flush=True)
    for part in parts:
        {"base": part_base, "stale": part_stale, "noise": part_noise,
         "m4": part_m4}[part]()
    print("saved %s" % LOG, flush=True)


if __name__ == "__main__":
    main()
