# -*- coding: utf-8 -*-
"""V-SWAP-G4: controlled model swap gemma3:4b → gemma4-e4b-heretic.

Пре-регистрация: SWAP_G4_DESIGN.md (этот же каталог). Протоколы
VERTICAL-1 (v1/v2) не изменяются; их драйверы, логи и данные не
трогаются.

Серии (bare-режим; единственный фактор — provider):
  v2 — невыводимый tsafix (lock), bare x3; baseline gemma3: 0/3.
  v1 — inactive (лечится start), bare x3; baseline gemma3: 3/3.

Запуск по секциям:
  python3 swap_g4_driver.py v2
  python3 swap_g4_driver.py v1

Лог: SWAP_G4_run.log (append). Stores: data_swap_g4_*.
"""
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
from llm import adapter  # noqa: E402
from storage.store import Store  # noqa: E402

SVC = "tsasvc"
LOCK = "/run/tsasvc.lock"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
PROVIDER = "gemma4"
MAX_ACTIONS = 5
EXP_DIR = os.path.join(BASE, "experiments", "vertical1")
RESULTS_LOG = os.path.join(EXP_DIR, "SWAP_G4_run.log")

# тексты задач — дословно как в сериях v1/v2 (чистота сравнения)
TASK_V1 = ("Сервис %s не работает (состояние inactive). Сервис "
           "нужно вернуть в состояние active. Доступные команды: "
           "systemctl start/stop/restart %s; диагностика: status, "
           "is-active, ss, ps, journalctl. Предложи действия." %
           (SVC, SVC))
TASK_V2 = ("Сервис %s не работает: не запускается (inactive). "
           "Верни сервис в состояние active. Доступные команды: "
           "systemctl start/stop/restart %s; диагностика: status, "
           "is-active, ss, ps, journalctl. Предложи действия." %
           (SVC, SVC))


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(RESULTS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def env_inactive():
    _run(["systemctl", "stop", SVC])


def env_active():
    _run(["systemctl", "start", SVC])


def env_broken():
    _run(["systemctl", "stop", SVC])
    open(LOCK, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def env_healthy():
    _run(["tsafix"])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "V-SWAP-G4"}
    store.append_action(a)
    return a


def propose_actions(store, task_text):
    """LLM-предложение через штатный контракт адаптера."""
    p = adapter.build_prompt(task_text)
    r = adapter.propose(PROVIDER, p, max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or c.get("type") == "observe":
                acts.append(mk_action(store, cmd, "bare/llm"))
    return r, acts


def run_actions_till_goal(store, actions, episode):
    results, evals = [], []
    for i, act in enumerate(actions[:MAX_ACTIONS]):
        res = executor.execute(store, act)
        results.append(res)
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        evals.append(ev)
        log({"ep": episode, "event": "action", "n": i + 1,
             "command": act["command"], "refused": res["refused"],
             "exit": res["exit_code"], "outcome": ev["outcome"]})
        if ev["outcome"] == "success":
            return results, evals, True
    return results, evals, False


def bare_episode(store, episode, task_text, env_fn):
    env_fn()
    r, acts = propose_actions(store, task_text)
    results, evals, ok = run_actions_till_goal(store, acts, episode)
    cands = []
    if r["ok"]:
        cands = [c["command"] for c in r["candidate_actions"]]
    log({"ep": episode, "system": "bare", "provider": PROVIDER,
         "success": ok, "executed": len(results), "proposed": len(acts),
         "llm_ok": r["ok"], "llm_error": r.get("error", ""),
         "llm_candidates": cands, "llm_meta": r.get("provider_meta"),
         "outcomes": [e["outcome"] for e in evals],
         "state_after_env": svc_state()})
    return ok


def fresh_store(name):
    d = os.path.join(EXP_DIR, "data_swap_g4_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def section_v2():
    print("== S-G4/v2: невыводимый tsafix, bare x3, provider=%s =="
          % PROVIDER, flush=True)
    env_healthy()
    assert svc_state() == "active", "полигон не поднялся"
    assert not os.path.exists(LOCK), "флаг не снят"
    st = fresh_store("v2_bare")
    res = []
    for i in range(1, 4):
        res.append(bare_episode(st, "g4_v2_bare_%d" % i, TASK_V2,
                                env_broken))
    kh = len({v["knowledge_id"] for v in st.read_knowledge_versions_all()})
    env_healthy()
    log({"event": "summary", "series": "v2_bare_g4",
         "results": [bool(x) for x in res], "knowledge_bare": kh,
         "state_after_env": svc_state(),
         "baseline_gemma3": [False, False, False]})


def section_v1():
    print("== S-G4/v1: inactive (start), bare x3, provider=%s =="
          % PROVIDER, flush=True)
    env_active()
    assert svc_state() == "active", "полигон не поднялся"
    st = fresh_store("v1_bare")
    res = []
    for i in range(1, 4):
        res.append(bare_episode(st, "g4_v1_bare_%d" % i, TASK_V1,
                                env_inactive))
    kh = len({v["knowledge_id"] for v in st.read_knowledge_versions_all()})
    env_active()
    log({"event": "summary", "series": "v1_bare_g4",
         "results": [bool(x) for x in res], "knowledge_bare": kh,
         "state_after_env": svc_state(),
         "baseline_gemma3": [True, True, True]})


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("v1", "v2"):
        print("usage: swap_g4_driver.py v1|v2", flush=True)
        sys.exit(2)
    print("== V-SWAP-G4 == design: SWAP_G4_DESIGN.md", flush=True)
    if sys.argv[1] == "v2":
        section_v2()
    else:
        section_v1()


if __name__ == "__main__":
    main()
