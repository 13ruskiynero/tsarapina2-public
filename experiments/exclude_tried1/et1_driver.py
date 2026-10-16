# -*- coding: utf-8 -*-
"""EXCLUDE-TRIED-1 driver (Tsarapina; FREEZE 12.09.2026).

Вопрос: достаточно ли внешнего исключения уже проверенных действий
для успешной exploration, или нужен полный BIN-перебор?

Кандидаты:
  EXCLUDE-TRIED: после E2 — remaining = BIN \\ tested; LLM выбирает
    из remaining; выбранное исполняется; fail → tested; success →
    конец. Список remaining показывается без ранжирования.
  BIN: положительный контроль (механизм MX-1).

До E2 одинаково: Э1 start (forced) → partial; Э2 auto → failure → E2.
Budget: 8 эпизодов после E2; MAX_EPISODES=10.

Запуск: python3 et1_driver.py all|preflight
Логи: ET1_run.log, ET1_trace.jsonl; сторы data_et1_*.
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
LOG = os.path.join(DIR, "ET1_run.log")
TRACE = os.path.join(DIR, "ET1_trace.jsonl")
PROVIDER = "gemma4"
MAX_EPISODES = 10
FIRST_ACTION = "systemctl start tsasvc"
WORLD = "w2"
WORLDS = {"w2": ["a", "q"]}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-aq", "fix-c"]
CANDIDATES = ("EXCLUDE-TRIED", "BIN")
REPS = (1, 2, 3)
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
         "rationale": "EXCLUDE-TRIED-1"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия. %s"
            % (symptom, FRAME))


def et_prompt(symptom, results, remaining):
    lines = ["Эпизод %d: %s -> %s" % (e, c, o) for (e, c, o, by) in
             results]
    avail = ", ".join(remaining)
    return (task_text(symptom) + "\n\nФактическая лента попыток:\n"
            + "\n".join(lines)
            + "\n\nУже проверенные действия недоступны и исключены "
              "из выбора.\nДоступные действия: " + avail
            + ".\nВыбери следующее действие из доступных.")


def run_action(store, act, ep, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": "ET1", "event": "action", "by": tag,
         "command": act["command"], "outcome": out,
         "refused": res.get("refused"), "exit": res.get("exit_code")})
    return ok_now, out


def et_choose(store, symptom, results, remaining, ep):
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(et_prompt(symptom,
                                                       results,
                                                       remaining)),
                        max_tokens=300, timeout=180)
    cmd = None
    if r["ok"]:
        for c in r["candidate_actions"]:
            c2 = c.get("command", "")
            if c2 in remaining:
                cmd = c2
                break
        if cmd is None:
            for c in r["candidate_actions"]:
                c2 = c.get("command", "")
                if "tsasvc" in c2 or "fix-" in c2:
                    cmd = c2
                    break
    trace({"ep": ep, "side": "ET1", "kind": "et_choice",
           "llm_ok": r.get("ok"), "chosen": cmd,
           "remaining": remaining,
           "candidates": [c.get("command") for c in
                          (r.get("candidate_actions") or [])]})
    return cmd


def run_trajectory(cand, rep):
    tag = "%s_r%d" % (cand.lower(), rep)
    st = fresh_store(tag)
    env_set(WORLD)
    results = []
    tested = set()
    ep = 0
    for phase in ("forced", "pre-e2-repeat"):
        ep += 1
        act = mk_action(st, FIRST_ACTION, "et1/%s" % phase)
        ok, out = run_action(st, act, ep, "et1/%s" % phase)
        results.append((ep, FIRST_ACTION, out, phase))
        tested.add(FIRST_ACTION)
        if ok:
            break
    search_order = []
    out_of_space = 0
    if not any(r[2] == "success" for r in results):
        if cand == "BIN":
            for bcmd in BIN:
                if ep >= MAX_EPISODES:
                    break
                ep += 1
                act = mk_action(st, bcmd, "et1/bin")
                ok, out = run_action(st, act, ep, "et1/bin")
                results.append((ep, bcmd, out, "bin"))
                search_order.append(bcmd)
                if ok:
                    break
        else:
            while ep < MAX_EPISODES:
                remaining = [c for c in BIN if c not in tested]
                if not remaining:
                    break
                ep += 1
                cmd = et_choose(st, symptom_now(), results, remaining,
                                ep)
                if cmd is None or cmd not in remaining:
                    out_of_space += 1
                    log({"ep": ep, "side": "ET1", "event":
                         "out_of_space", "proposal": cmd})
                    results.append((ep, "(out of space)", "no_action",
                                    "et-llm"))
                    continue
                act = mk_action(st, cmd, "et1/et-llm")
                ok, out = run_action(st, act, ep, "et1/et-llm")
                results.append((ep, cmd, out, "et-llm"))
                search_order.append(cmd)
                tested.add(cmd)
                if ok:
                    break
    seq = [x[1] for x in results]
    outcomes = [x[2] for x in results]
    success = "success" in outcomes
    first_alt = None
    tried0 = {r[1] for r in results[:2]}
    for r in results[2:]:
        if r[1] not in tried0:
            first_alt = r[1]
            break
        tried0.add(r[1])
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
            "actions_after_e2": len(search_order),
            "exploration_started": first_alt is not None,
            "first_alternative_action": first_alt,
            "unique_commands_after_e2": len(set(search_order)),
            "out_of_space": out_of_space,
            "class": cls, "e2_at_episode": 2,
            "actions_to_success":
                (outcomes.index("success") + 1) if success else None}
    log(summ)
    trace(dict(summ, kind="run_summary"))
    return summ


def fresh_store(name):
    d = os.path.join(DIR, "data_et1_%s" % name)
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
    print("== EXCLUDE-TRIED-1 (FREEZE 12.09.2026) ==", flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — серия не запускается.", flush=True)
        return
    for cand in CANDIDATES:
        for rep in REPS:
            print("--- %s / rep%d ---" % (cand, rep), flush=True)
            run_trajectory(cand, rep)
    env_set(WORLD)
    _run(["systemctl", "stop", SVC])
    log({"phase": "summary", "note": "ET1_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight"):
        print("usage: et1_driver.py all|preflight", flush=True)
        return
    if args[0] == "all":
        run_all()
    else:
        part_preflight()


if __name__ == "__main__":
    main()