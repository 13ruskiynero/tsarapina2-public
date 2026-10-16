# -*- coding: utf-8 -*-
"""MIN-ADVANTAGE-1 driver (Tsarapina; FREEZE 12.09.2026).

Вопрос: сохраняет ли CAND3 практическое преимущество над plain
Gemma4 на paired сценах (6 сцен × 2 стороны × 2 реплики = 24 runs)?

Стороны:
  CAND3 — persistent mapping + applicable_when + E2 + P2 BIN
          (mm1_cut3_mapping.MappingCut3, без изменений);
  BARE  — Gemma4 → proposal → executor → result (без памяти).

Сцены (миры по эпизодам):
  A [w1,w1]; B [b,b]; C [c,c]; A' [w1,w1,w2,w2,w2,w2];
  NOISE [w1,w1,noise,w1,noise,noise,w1,w1];
  NOCHANGE [w1,w1,w1,w1].

Запуск: python3 ma1_driver.py all|preflight
Логи: MA1_run.log, MA1_trace.jsonl; сторы data_ma1_*.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(DIR))
MM1 = os.path.join(BASE, "experiments", "min_mechanism1")
sys.path.insert(0, BASE)
sys.path.insert(0, MM1)

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from llm import adapter  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from mm1_cut3_mapping import MappingCut3  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
LOG = os.path.join(DIR, "MA1_run.log")
TRACE = os.path.join(DIR, "MA1_trace.jsonl")
PROVIDER = "gemma4"
MAX_ACTS = 4
WORLDS = {"w1": ["a"], "w2": ["a", "q"], "b": ["b"], "c": ["c"],
          "noise": ["a", "n"]}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-aq", "fix-c"]
SCENES = [
    ("A", [("w1", False), ("w1", False)]),
    ("B", [("b", False), ("b", False)]),
    ("C", [("c", False), ("c", False)]),
    ("AP", [("w1", False), ("w1", False), ("w2", False),
            ("w2", False), ("w2", False), ("w2", False)]),
    ("NOISE", [("w1", False), ("w1", False), ("noise", False),
               ("w1", False), ("noise", False), ("noise", False),
               ("w1", False), ("w1", False)]),
    ("NOCHANGE", [("w1", False), ("w1", False), ("w1", False),
                  ("w1", False)]),
]
SIDES = ("CAND3", "BARE")
REPS = (1, 2)


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def trace(rec):
    with open(TRACE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(world, extra=False):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in WORLDS[world]:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    if extra:
        open("/run/tsasvc.lock.extra", "w").close()
    if os.path.exists("/run/tsasvc.envver"):
        os.remove("/run/tsasvc.envver")
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


def envver_now():
    return polygon_sensor.sensor_envver()[4]


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "MIN-ADVANTAGE-1"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия." % symptom)


def run_action(store, act, ep, side, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": side, "event": "action", "by": tag,
         "command": act["command"], "outcome": out,
         "refused": res.get("refused"), "exit": res.get("exit_code")})
    return ok_now, out


# --- CAND3-сторона (эпизод; логика MM1 Cut-3, без изменений) ---

def cand3_episode(store, cand, world, ep, extra=False):
    env_set(world, extra=extra)
    cond = symptom_now()
    obs = {"E": ctx_now()}
    entry = cand.lookup(cond)
    streak_before = cand.fail_streak(cond)
    acts, outs = [], []
    ok = False
    rejected = False
    e2_detected = False
    expl_auth = False
    expl_started = False
    acq_steps = []
    new_k = None
    if entry is None:
        for bcmd in BIN:
            act = mk_action(store, bcmd, "ma1/acq-bin")
            ok_now, out = run_action(store, act, ep, "CAND3",
                                     "ma1/acq-bin")
            acts.append(act)
            outs.append(out)
            acq_steps.append(bcmd)
            if ok_now:
                ok = True
                break
        if ok:
            new_k = cand.record(cond, acts[-1]["command"], "success",
                                obs=obs, source="acquisition")
            cand.note_success(cond)
    elif cand.should_transition(cond):
        e2_detected = True
        expl_auth = True
        expl_started = True
        for bcmd in BIN:
            act = mk_action(store, bcmd, "ma1/e2-explore")
            ok_now, out = run_action(store, act, ep, "CAND3",
                                     "ma1/e2-explore")
            acts.append(act)
            outs.append(out)
            acq_steps.append(bcmd)
            if ok_now:
                ok = True
                break
        if ok:
            new_k = cand.record(cond, acts[-1]["command"], "success",
                                obs=obs, source="e2-exploration")
            cand.note_success(cond)
    elif cand.applicable(entry, obs):
        act = mk_action(store, entry["action"], "ma1/mapping")
        ok_now, out = run_action(store, act, ep, "CAND3",
                                 "ma1/mapping")
        acts.append(act)
        outs.append(out)
        ok = ok_now
        if ok:
            cand.note_success(cond)
        else:
            cand.note_non_success(cond)
    else:
        rejected = True
    rec = {"ep": ep, "side": "CAND3", "event": "episode", "world": world,
           "condition": cond, "obs": obs, "lookup_hit": entry is not None,
           "entry_action": entry.get("action") if entry else None,
           "rejected": rejected,
           "e2_detected": e2_detected,
           "exploration_authorized": expl_auth,
           "exploration_started": expl_started,
           "acquisition_steps": acq_steps,
           "new_knowledge": new_k,
           "fail_streak_before": streak_before,
           "action": acts[-1]["command"] if acts else None,
           "success": ok, "actions": len(acts), "outcomes": outs}
    log(rec)
    trace(dict(rec, kind="episode_result"))
    return ok, len(acts)


# --- BARE-сторона (Gemma4 без памяти) ---

def bare_episode(store, world, ep, extra=False):
    env_set(world, extra=extra)
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(task_text(symptom_now())),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or "fix-" in cmd:
                acts.append(mk_action(store, cmd, "ma1/bare-llm"))
    outs = []
    ok = False
    for act in acts[:MAX_ACTS]:
        ok_now, out = run_action(store, act, ep, "BARE", "ma1/bare-llm")
        outs.append(out)
        if ok_now:
            ok = True
            break
    rec = {"ep": ep, "side": "BARE", "event": "episode", "world": world,
           "success": ok, "actions": len(outs), "outcomes": outs,
           "llm_ok": r.get("ok"), "llm_error": r.get("error", ""),
           "candidates": [c.get("command") for c in
                          (r.get("candidate_actions") or [])]}
    log(rec)
    trace(dict(rec, kind="episode_result"))
    return ok, len(outs)


def fresh_store(name):
    d = os.path.join(DIR, "data_ma1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def run_scene(side, scene, eps, rep):
    tag = "%s_%s_r%d" % (side.lower(), scene.lower(), rep)
    st = fresh_store(tag)
    results = []
    if side == "CAND3":
        cand = MappingCut3(os.path.join(DIR, "data_ma1_%s" % tag,
                                        "mapping.jsonl"))
        for i, (world, extra) in enumerate(eps, start=1):
            ok, n = cand3_episode(st, cand, world,
                                  "%s_e%d" % (tag, i), extra=extra)
            results.append((ok, n))
    else:
        for i, (world, extra) in enumerate(eps, start=1):
            ok, n = bare_episode(st, world, "%s_e%d" % (tag, i),
                                 extra=extra)
            results.append((ok, n))
    log({"phase": "scene_summary", "side": side, "scene": scene,
         "rep": rep, "success": [x[0] for x in results],
         "actions": [x[1] for x in results]})
    return results


def part_preflight():
    print("--- PREFLIGHT ---", flush=True)
    checks = {}
    for w in ("w1", "w2", "b", "c", "noise"):
        env_set(w)
        checks["symptom_" + w] = symptom_now()
        checks["E_" + w] = ctx_now()
    env_set("w1")
    _run(["fix-a"])
    checks["fix_a"] = stable_active()
    env_set("w2")
    _run(["fix-aq"])
    checks["fix_aq"] = stable_active()
    env_set("b")
    _run(["fix-b"])
    checks["fix_b"] = stable_active()
    env_set("c")
    _run(["fix-c"])
    checks["fix_c"] = stable_active()
    env_set("noise")
    _run(["fix-a"])
    checks["fix_a_on_noise"] = stable_active()
    pos = {}
    for w in ("w1", "w2", "b", "c"):
        env_set(w)
        hit = None
        for i, cmd in enumerate(BIN, start=1):
            _run(cmd.split())
            if stable_active():
                hit = [i, cmd]
                break
        pos[w] = hit
    r = adapter.propose(PROVIDER, adapter.build_prompt("проверка связи"),
                        max_tokens=300, timeout=180)
    adapter_ok = bool(r["ok"])
    d3 = os.path.join(DIR, "data_ma1_preflight_map")
    if os.path.exists(d3):
        shutil.rmtree(d3)
    os.makedirs(d3)
    cand = MappingCut3(os.path.join(d3, "m.jsonl"))
    rec = cand.record("a", "fix-a", "success", obs={"E": "absent"},
                      source="preflight")
    cand.note_non_success("a")
    cand.note_non_success("a")
    e2 = cand.should_transition("a")
    cand.record("a", "fix-aq", "success", obs={"E": "absent"},
                source="e2-exploration")
    both = ({e["action"] for e in cand.entries} == {"fix-a", "fix-aq"})
    instr_ok = (rec.get("applicable_when") == {"E": "absent"}
                and e2 and both)
    good = (checks["symptom_w1"] == "a" and checks["symptom_w2"] == "a"
            and checks["symptom_b"] == "b" and checks["symptom_c"] == "c"
            and checks["symptom_noise"] == "a"
            and checks["fix_a"] and checks["fix_aq"] and checks["fix_b"]
            and checks["fix_c"] and not checks["fix_a_on_noise"]
            and adapter_ok and instr_ok)
    log({"phase": "preflight", "checks": checks, "bin_positions": pos,
         "adapter_ok": adapter_ok, "cand3_instr_ok": instr_ok})
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    print("PREFLIGHT: %s" % ("OK" if good else "FAIL"), flush=True)
    return good


def run_all():
    open(LOG, "w", encoding="utf-8").close()
    open(TRACE, "w", encoding="utf-8").close()
    print("== MIN-ADVANTAGE-1 (FREEZE 12.09.2026) ==", flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — серия не запускается.", flush=True)
        return
    for rep in REPS:
        for scene, eps in SCENES:
            for side in SIDES:
                print("--- %s / %s / rep%d ---" % (side, scene, rep),
                      flush=True)
                run_scene(side, scene, eps, rep)
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    log({"phase": "summary", "note": "MA1_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight"):
        print("usage: ma1_driver.py all|preflight", flush=True)
        return
    if args[0] == "all":
        run_all()
    else:
        part_preflight()


if __name__ == "__main__":
    main()
