# -*- coding: utf-8 -*-
"""ROBUST-ADVANTAGE-1 driver (Tsarapina; FREEZE 12.09.2026).

Проверка confound: сдвигается ли bare при усиленном action framing?
Меняется ТОЛЬКО bare prompt (одна инструкция; без подсказок).
CAND3 не перезапускается (anchor MA1).
6 сцен × 2 реплики × 2 повторности = 24 bare runs.

Запуск: python3 rb1_driver.py all|preflight
Логи: RB1_run.log, RB1_trace.jsonl; сторы data_rb1_*.
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
sys.path.insert(0, BASE)

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from llm import adapter  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
LOG = os.path.join(DIR, "RB1_run.log")
TRACE = os.path.join(DIR, "RB1_trace.jsonl")
PROVIDER = "gemma4"
MAX_ACTS = 4
WORLDS = {"w1": ["a"], "w2": ["a", "q"], "b": ["b"], "c": ["c"],
          "noise": ["a", "n"]}
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
SERIES = ((1, 1), (1, 2), (2, 1), (2, 2))
FRAME = ("Если имеющихся свидетельств достаточно, предпринимай "
         "конкретное corrective действие, а не ограничивайся "
         "диагностикой; после действия оцени его результат.")


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


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]


def ctx_now():
    return polygon_sensor.sensor_envfact()[4]


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "ROBUST-ADVANTAGE-1"}
    store.append_action(a)
    return a


def task_text(symptom, frame=False):
    base = ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия." % symptom)
    if frame:
        base = base + " " + FRAME
    return base


def action_type(cmd):
    c = cmd.lower()
    if ("fix-" in c) or ("restart" in c) or ("start" in c) or \
            ("stop" in c):
        return "corrective"
    return "diagnostic"


def run_action(store, act, ep, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": "BARE-FRAME", "event": "action", "by": tag,
         "command": act["command"], "type": action_type(act["command"]),
         "outcome": out, "refused": res.get("refused"),
         "exit": res.get("exit_code")})
    return ok_now, out


def bare_episode(store, world, ep, extra=False):
    env_set(world, extra=extra)
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(task_text(symptom_now(),
                                                       frame=True)),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or "fix-" in cmd:
                acts.append(mk_action(store, cmd, "rb1/bare-llm-framed"))
    outs = []
    ok = False
    for act in acts[:MAX_ACTS]:
        ok_now, out = run_action(store, act, ep, "rb1/bare-llm-framed")
        outs.append(out)
        if ok_now:
            ok = True
            break
    rec = {"ep": ep, "side": "BARE-FRAME", "event": "episode",
           "world": world, "success": ok, "actions": len(outs),
           "outcomes": outs, "llm_ok": r.get("ok"),
           "llm_error": r.get("error", ""),
           "candidates": [c.get("command") for c in
                          (r.get("candidate_actions") or [])],
           "candidate_types": [action_type(c.get("command", ""))
                               for c in
                               (r.get("candidate_actions") or [])],
           "first_action_type": (action_type(acts[0]["command"])
                                 if acts else None),
           "first_command": (acts[0]["command"] if acts else None)}
    log(rec)
    trace(dict(rec, kind="episode_result"))
    return ok, len(outs), rec["first_action_type"]


def fresh_store(name):
    d = os.path.join(DIR, "data_rb1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def run_scene(scene, eps, rep, sub):
    tag = "%s_r%ds%d" % (scene.lower(), rep, sub)
    st = fresh_store(tag)
    results = []
    for i, (world, extra) in enumerate(eps, start=1):
        ok, n, ft = bare_episode(st, world, "rb1_%s_e%d" % (tag, i),
                                 extra=extra)
        results.append((ok, n, ft))
    log({"phase": "scene_summary", "side": "BARE-FRAME", "scene": scene,
         "rep": rep, "sub": sub,
         "success": [x[0] for x in results],
         "actions": [x[1] for x in results],
         "first_types": [x[2] for x in results]})
    return results


def part_preflight():
    print("--- PREFLIGHT ---", flush=True)
    checks = {}
    for w in ("w1", "w2", "b", "c", "noise"):
        env_set(w)
        checks["symptom_" + w] = symptom_now()
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
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(task_text("a",
                                                       frame=True)),
                        max_tokens=300, timeout=180)
    adapter_ok = bool(r["ok"])
    good = (checks["symptom_w1"] == "a" and checks["symptom_w2"] == "a"
            and checks["symptom_b"] == "b" and checks["symptom_c"] == "c"
            and checks["fix_a"] and checks["fix_aq"] and checks["fix_b"]
            and checks["fix_c"] and adapter_ok)
    log({"phase": "preflight", "checks": checks,
         "adapter_ok": adapter_ok,
         "frame_probe_candidates": [c.get("command") for c in
                                    (r.get("candidate_actions") or [])]})
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    print("PREFLIGHT: %s" % ("OK" if good else "FAIL"), flush=True)
    return good


def run_all():
    open(LOG, "w", encoding="utf-8").close()
    open(TRACE, "w", encoding="utf-8").close()
    print("== ROBUST-ADVANTAGE-1 (FREEZE 12.09.2026) ==", flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — серия не запускается.", flush=True)
        return
    for rep, sub in SERIES:
        for scene, eps in SCENES:
            print("--- BARE-FRAME / %s / r%d s%d ---"
                  % (scene, rep, sub), flush=True)
            run_scene(scene, eps, rep, sub)
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    log({"phase": "summary", "note": "RB1_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight"):
        print("usage: rb1_driver.py all|preflight", flush=True)
        return
    if args[0] == "all":
        run_all()
    else:
        part_preflight()


if __name__ == "__main__":
    main()
