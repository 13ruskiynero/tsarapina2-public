# -*- coding: utf-8 -*-
"""SINGLE-ACTION-FIXATION-1 driver (Tsarapina; FREEZE 12.09.2026).

Вопрос: может ли plain Gemma4 сама выйти из повторяющегося
неуспешного corrective action после failure feedback?

Механика (см. SINGLE_ACTION_FIXATION1_DESIGN.md):
  Э1: принудительный systemctl start tsasvc (без LLM) → исход;
  далее до SUCCESS или MAX_EPISODES=8:
    если consecutive failures >= 2 → decision point: LLM получает
    фактическую ленту (эпизод → команда → исход) + счётчик и
    выбирает следующее corrective действие;
    иначе — авто-повтор последнего выбранного действия.

E2/memory/P2/CAND3 отсутствуют; operator 0; мир w2 (A′-полигон).

Запуск: python3 saf1_driver.py all|preflight
Логи: SAF1_run.log, SAF1_trace.jsonl; сторы data_saf1_*.
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
LOG = os.path.join(DIR, "SAF1_run.log")
TRACE = os.path.join(DIR, "SAF1_trace.jsonl")
PROVIDER = "gemma4"
MAX_EPISODES = 8
RUNS = 6
FIRST_ACTION = "systemctl start tsasvc"
WORLD = "w2"
WORLDS = {"w2": ["a", "q"]}
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
         "rationale": "SINGLE-ACTION-FIXATION-1"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия. %s"
            % (symptom, FRAME))


def dp_prompt(symptom, results, consec):
    lines = []
    for (ep, cmd, out, by) in results:
        lines.append("Эпизод %d: %s -> %s" % (ep, cmd, out))
    hist = "\n".join(lines)
    return (task_text(symptom) + "\n\n"
            "Результаты уже выполненных попыток в этой серии:\n"
            + hist + "\nПоследовательных неуспехов: %d. "
            "Предложи следующее действие." % consec)


def run_action(store, act, ep, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": "BARE-SAF1", "event": "action", "by": tag,
         "command": act["command"], "outcome": out,
         "refused": res.get("refused"), "exit": res.get("exit_code")})
    return ok_now, out


def dp_choose(store, symptom, results, consec, ep):
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(dp_prompt(symptom, results,
                                                       consec)),
                        max_tokens=300, timeout=180)
    cmd = None
    if r["ok"]:
        for c in r["candidate_actions"]:
            c2 = c.get("command", "")
            if "tsasvc" in c2 or "fix-" in c2:
                cmd = c2
                break
    trace({"ep": ep, "side": "BARE-SAF1", "kind": "dp_choice",
           "llm_ok": r.get("ok"), "chosen": cmd,
           "candidates": [c.get("command") for c in
                          (r.get("candidate_actions") or [])],
           "consec_before": consec})
    return cmd


def run_trajectory(idx):
    st = fresh_store("run%d" % idx)
    env_set(WORLD)
    results = []
    ep = 0
    consec = 0
    last_action = None
    while ep < MAX_EPISODES:
        choice_by = None
        if ep == 0:
            cmd = FIRST_ACTION
            choice_by = "forced"
        elif consec >= 2:
            cmd = dp_choose(st, symptom_now(), results, consec, ep + 1)
            choice_by = "dp-llm"
            if cmd is None:
                log({"ep": ep + 1, "side": "BARE-SAF1",
                     "event": "no_proposal", "by": "dp-llm"})
                results.append((ep + 1, "(no proposal)", "no_action",
                                "dp-llm"))
                ep += 1
                consec += 1
                continue
        else:
            cmd = last_action
            choice_by = "auto-repeat"
        ep += 1
        act = mk_action(st, cmd, "saf1/%s" % choice_by)
        ok, out = run_action(st, act, ep, "saf1/%s" % choice_by)
        results.append((ep, cmd, out, choice_by))
        last_action = cmd
        if ok:
            break
        consec = consec + 1 if choice_by != "dp-llm" else 1
    seq = [x[1] for x in results]
    outcomes = [x[2] for x in results]
    dp_choices = [x[1] for x in results if x[3] == "dp-llm"]
    first_change = None
    prev = FIRST_ACTION
    for (e2, c2, o2, by2) in results:
        if by2 == "dp-llm":
            if c2 != prev:
                first_change = e2
                break
            prev = c2
    success = "success" in outcomes
    summ = {"phase": "run_summary", "run": idx, "side": "BARE-SAF1",
            "success": success, "episodes": len(results),
            "sequence": seq, "outcomes": outcomes,
            "unique_commands": len(set(seq)),
            "dp_choices": dp_choices,
            "first_dp_change_episode": first_change,
            "actions_to_success":
                (outcomes.index("success") + 1) if success else None}
    log(summ)
    trace(dict(summ, kind="run_summary"))
    return summ


def fresh_store(name):
    d = os.path.join(DIR, "data_saf1_%s" % name)
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
    checks["start_partial_check_skip"] = True
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
    print("== SINGLE-ACTION-FIXATION-1 (FREEZE 12.09.2026) ==",
          flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — серия не запускается.", flush=True)
        return
    for i in range(1, RUNS + 1):
        print("--- RUN %d ---" % i, flush=True)
        run_trajectory(i)
    env_set(WORLD)
    _run(["systemctl", "stop", SVC])
    log({"phase": "summary", "note": "SAF1_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight"):
        print("usage: saf1_driver.py all|preflight", flush=True)
        return
    if args[0] == "all":
        run_all()
    else:
        part_preflight()


if __name__ == "__main__":
    main()
