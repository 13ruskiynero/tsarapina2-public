# -*- coding: utf-8 -*-
"""MIN-EXPLORATION-1 driver (Tsarapina; FREEZE 12.09.2026).

Разделение E2 и BIN на A′-полигоне. Кандидаты:
  M1: E2 → LLM search (authorization; BIN нет);
  M2: E2 → BIN (LLM не вовлекается);
  M3: E2 → BIN с CAND3-провенансом (positive control).

До E2 одинаково у всех: Э1 start (forced) → partial;
Э2 start (auto-repeat) → failure → E2.
Search budget после E2: 8 эпизодов; MAX_EPISODES=10.
Memory absent; applicability held constant; operator 0.

Запуск: python3 mx1_driver.py all|preflight
Логи: MX1_run.log, MX1_trace.jsonl; сторы data_mx1_*.
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
LOG = os.path.join(DIR, "MX1_run.log")
TRACE = os.path.join(DIR, "MX1_trace.jsonl")
PROVIDER = "gemma4"
MAX_EPISODES = 10
FIRST_ACTION = "systemctl start tsasvc"
WORLD = "w2"
WORLDS = {"w2": ["a", "q"]}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-aq", "fix-c"]
CANDIDATES = ("M1", "M2", "M3")
REPS = (1, 2, 3)
FRAME = ("Если имеющихся свидетельств достаточно, предпринимай "
         "конкретное corrective действие, а не ограничивайся "
         "диагностикой; после действия оцени его результат.")
AUTH = ("Внимание: наблюдаются повторяющиеся неуспехи. "
        "Разрешается предложить альтернативное corrective действие, "
        "отличное от ранее неуспешных. Предложи следующее действие.")


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


def env_set(world):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in WORLDS[world]:
        open("/run/tsasvc.lock.%s" % f, "w").close()
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


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "MIN-EXPLORATION-1"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия. %s"
            % (symptom, FRAME))


def m1_prompt(symptom, results):
    lines = ["Эпизод %d: %s -> %s" % (e, c, o) for (e, c, o, by) in
             results]
    return (task_text(symptom) + "\n\nФактическая лента попыток:\n"
            + "\n".join(lines) + "\n\n" + AUTH)


def run_action(store, act, ep, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": "MX1", "event": "action", "by": tag,
         "command": act["command"], "outcome": out,
         "refused": res.get("refused"), "exit": res.get("exit_code")})
    return ok_now, out


def m1_choose(store, symptom, results, ep):
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(m1_prompt(symptom,
                                                       results)),
                        max_tokens=300, timeout=180)
    cmd = None
    if r["ok"]:
        for c in r["candidate_actions"]:
            c2 = c.get("command", "")
            if "tsasvc" in c2 or "fix-" in c2:
                cmd = c2
                break
    trace({"ep": ep, "side": "MX1", "kind": "m1_choice",
           "llm_ok": r.get("ok"), "chosen": cmd,
           "candidates": [c.get("command") for c in
                          (r.get("candidate_actions") or [])]})
    return cmd


def run_trajectory(cand, rep):
    tag = "%s_r%d" % (cand, rep)
    st = fresh_store(tag)
    env_set(WORLD)
    results = []
    ep = 0
    # --- до E2: Э1 forced, Э2 auto-repeat (одинаково у всех) ---
    for phase in ("forced", "pre-e2-repeat"):
        ep += 1
        act = mk_action(st, FIRST_ACTION, "mx1/%s" % phase)
        ok, out = run_action(st, act, ep, "mx1/%s" % phase)
        results.append((ep, FIRST_ACTION, out, phase))
        if ok:
            break
    # --- после E2: фаза поиска ---
    search_order = []
    if not any(r[2] == "success" for r in results):
        if cand == "M1":
            while ep < MAX_EPISODES:
                ep += 1
                cmd = m1_choose(st, symptom_now(), results, ep)
                if cmd is None:
                    log({"ep": ep, "side": "MX1", "event":
                         "no_proposal", "by": "m1-llm"})
                    results.append((ep, "(no proposal)", "no_action",
                                    "m1-llm"))
                    search_order.append("(no proposal)")
                    continue
                act = mk_action(st, cmd, "mx1/m1-llm")
                ok, out = run_action(st, act, ep, "mx1/m1-llm")
                results.append((ep, cmd, out, "m1-llm"))
                search_order.append(cmd)
                if ok:
                    break
        else:
            tag_by = "mx1/m2-bin" if cand == "M2" else "mx1/m3-bin"
            for bcmd in BIN:
                if ep >= MAX_EPISODES:
                    break
                ep += 1
                act = mk_action(st, bcmd, tag_by)
                ok, out = run_action(st, act, ep, tag_by)
                results.append((ep, bcmd, out, tag_by))
                search_order.append(bcmd)
                if ok:
                    break
    seq = [x[1] for x in results]
    outcomes = [x[2] for x in results]
    success = "success" in outcomes
    tried = {r[1] for r in results[:2]}
    first_alt = None
    for r in results[2:]:
        if r[1] not in tried:
            first_alt = r[1]
            break
        tried.add(r[1])
    unique_after = len({c for c in search_order if c != "(no proposal)"})
    if success:
        cls = "E2-successful"
    elif first_alt is not None:
        cls = "E1-attempted"
    else:
        cls = "E0-none"
    summ = {"phase": "run_summary", "cand": cand, "rep": rep,
            "success": success, "episodes": len(results),
            "sequence": seq, "outcomes": outcomes,
            "search_order": search_order,
            "exploration_started": first_alt is not None,
            "first_alternative_action": first_alt,
            "unique_commands_after_e2": unique_after,
            "class": cls, "e2_at_episode": 2,
            "actions_to_success":
                (outcomes.index("success") + 1) if success else None}
    log(summ)
    trace(dict(summ, kind="run_summary"))
    return summ


def fresh_store(name):
    d = os.path.join(DIR, "data_mx1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def part_preflight():
    print("--- PREFLIGHT ---", flush=True)
    checks = {}
    env_set(WORLD)
    checks["symptom"] = symptom_now()
    if not stable_active():
        _run(["fix-aq"])
    checks["fix_aq"] = stable_active()
    env_set(WORLD)
    r = adapter.propose(PROVIDER, adapter.build_prompt(task_text("a")),
                        max_tokens=300, timeout=180)
    checks["adapter_ok"] = bool(r["ok"])
    good = (checks["symptom"] == "a" and checks["fix_aq"]
            and checks["adapter_ok"])
    log({"phase": "preflight", "checks": checks,
         "probe_candidates": [c.get("command") for c in
                              (r.get("candidate_actions") or [])]})
    env_set(WORLD)
    _run(["systemctl", "stop", SVC])
    print("PREFLIGHT: %s" % ("OK" if good else "FAIL"), flush=True)
    return good


def run_all():
    open(LOG, "w", encoding="utf-8").close()
    open(TRACE, "w", encoding="utf-8").close()
    print("== MIN-EXPLORATION-1 (FREEZE 12.09.2026) ==", flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — серия не запускается.", flush=True)
        return
    for cand in CANDIDATES:
        for rep in REPS:
            print("--- %s / rep%d ---" % (cand, rep), flush=True)
            run_trajectory(cand, rep)
    env_set(WORLD)
    _run(["systemctl", "stop", SVC])
    log({"phase": "summary", "note": "MX1_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight"):
        print("usage: mx1_driver.py all|preflight", flush=True)
        return
    if args[0] == "all":
        run_all()
    else:
        part_preflight()


if __name__ == "__main__":
    main()
