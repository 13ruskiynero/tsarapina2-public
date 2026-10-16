# -*- coding: utf-8 -*-
"""VERTICAL-1 driver (Tsarapina, первый вертикальный эксперимент).

Протокол: experiments/VERTICAL1_PROTOCOL.md (заморожен 07.09).
Среда: systemd-юнит-имитатор tsasvc (НЕ реальный ssh).
Системы: bare (голая Gemma, без памяти) vs tsarapina (полный
контур). Один executor/evaluation — одинаковая «рука» и «линейка».

Серии: D0 (3 эпизода, пустое знание) + D1 (3 эпизода, повтор после
накопления) на каждую систему; затем model swap (qwen2.5:3b, 2
эпизода) — контур с тем же Knowledge.

Запись эпизода — JSON-строки в лог; хранилища: data_bare/ и
data_tsar/ (отдельные).
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
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from llm import adapter  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
PROBLEM = "%s.service state=inactive" % SVC
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
TASK_TEXT = ("Сервис %s не работает (состояние inactive). Сервис "
             "нужно вернуть в состояние active. Доступные команды: "
             "systemctl start/stop/restart %s; диагностика: status, "
             "is-active, ss, ps, journalctl. Предложи действия." %
             (SVC, SVC))
EXP_DIR = os.path.join(BASE, "experiments", "vertical1")
N_D0 = 3
N_D1 = 3
MAX_ACTIONS = 5
RESULTS_LOG = os.path.join(EXP_DIR, "VERTICAL1_run.log")


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(RESULTS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _sysctl(*args):
    subprocess.run(["systemctl"] + list(args), capture_output=True,
                   text=True, timeout=30)


def env_inactive():
    """Среда: tsasvc остановлен (контролируемый эпизод)."""
    _sysctl("stop", SVC)


def env_active():
    _sysctl("start", SVC)


def svc_state():
    p = subprocess.run(["systemctl", "is-active", SVC],
                       capture_output=True, text=True, timeout=15)
    return p.stdout.strip()


def mk_action(store, command, proposed_by, aid=None):
    a = {
        "schema_version": "0.1",
        "action_id": aid or ("act_%s" % uuid.uuid4().hex[:8]),
        "strategy_id": None, "proposed_by": proposed_by,
        "type": "command", "command": command,
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rationale": "эксперимент VERTICAL-1",
    }
    store.append_action(a)
    return a


def propose_actions(provider, store, system):
    """LLM-предложения (bare и первый tsar-эпизод)."""
    p = adapter.build_prompt(TASK_TEXT)
    r = adapter.propose(provider, p, max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or c.get("type") == "observe":
                acts.append(mk_action(store, cmd, proposed_by=system + "/llm"))
    return r, acts


def run_actions_till_goal(store, actions, episode):
    """Выполнять действия по очереди, пока goal не достигнут."""
    results = []
    evals = []
    for i, act in enumerate(actions[:MAX_ACTIONS]):
        res = executor.execute(store, act)
        results.append(res)
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        evals.append(ev)
        log({"ep": episode, "event": "action", "n": i + 1,
             "command": act["command"], "refused": res["refused"],
             "exit": res["exit_code"], "outcome": ev["outcome"],
             "result_id": res["result_id"]})
        if ev["outcome"] == "success":
            return results, evals, True
    return results, evals, False


# ---------------- bare ----------------

def run_bare_episode(store, episode, provider="gemma"):
    env_inactive()
    r, acts = propose_actions(provider, store, "bare")
    results, evals, ok = run_actions_till_goal(store, acts, episode)
    final_state = svc_state()
    log({"ep": episode, "system": "bare", "provider": provider,
         "state_env_before": "inactive", "state_env_after": final_state,
         "proposed": len(acts), "executed": len(results),
         "success": ok, "llm_ok": r["ok"],
         "llm_error": r.get("error", ""),
         "outcomes": [e["outcome"] for e in evals]})
    return ok, results, evals


# ---------------- tsarapina ----------------

def run_tsar_episode(store, episode, provider="gemma"):
    """Полный контур. Возвращает (success, использовано ли S2)."""
    env_inactive()
    facts = observer.collect(store)
    sug = strategy.suggest(store, {"problem": PROBLEM},
                           by="strategy/deterministic")
    sid = sug["strategy_id"]
    used_knowledge = sid == strategy.S2
    acts = []
    if sid == strategy.S2:
        # детерминированное знание: действия из опыта знания
        for c in sug["candidate_actions"]:
            acts.append(mk_action(store, c["command"],
                                  proposed_by="strategy/S2"))
    else:
        # S1/S3: знание отсутствует/конфликт → LLM-план
        r, llm_acts = propose_actions(provider, store, "tsarapina")
        acts = llm_acts
    log({"ep": episode, "event": "strategy", "strategy": sid,
         "knowledge_refs": sug["knowledge_refs"],
         "snapshot": [(s["knowledge_id"], s["version"])
                      for s in sug["knowledge_snapshot"]]})
    results, evals, ok = run_actions_till_goal(store, acts, episode)
    # полный опыт (наблюдения + действия + результат)
    aids = [a["action_id"] for a in acts[:len(results)]] if results else []
    result_ref = results[-1]["result_id"] if results else None
    if result_ref:
        exp_full = experience.build(
            problem=PROBLEM, observations=facts, actions=aids,
            result_ref=result_ref, machine="vertical1")
        experience.save(store, exp_full)
        out = evals[-1]["outcome"]
        k = update.apply(store, exp_full["experience_id"], out)
        log({"ep": episode, "event": "update", "outcome": out,
             "experience_id": exp_full["experience_id"],
             "knowledge_created": bool(k)})
    final_state = svc_state()
    log({"ep": episode, "system": "tsarapina", "provider": provider,
         "state_env_before": "inactive", "state_env_after": final_state,
         "strategy": sid, "used_knowledge": used_knowledge,
         "proposed": len(acts), "executed": len(results),
         "success": ok, "knowledge_count": len({
             v["knowledge_id"] for v in store.read_knowledge_versions_all()}),
         "outcomes": [e["outcome"] for e in evals]})
    return ok, used_knowledge, results, evals


def fresh_store(name):
    d = os.path.join(EXP_DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(RESULTS_LOG, "w", encoding="utf-8").close()
    print("== VERTICAL-1 ==", flush=True)
    print("protocol: VERTICAL1_PROTOCOL.md (frozen 07.09)", flush=True)
    print("environment: %s (simulated; real ssh untouched)" % SVC,
          flush=True)

    # sanity: полигон живой
    env_active()
    time.sleep(0.5)
    assert svc_state() == "active", "полигон не поднялся"

    bt = fresh_store("bare")
    tt = fresh_store("tsar")

    print("--- D0: bare x%d, tsarapina x%d ---" % (N_D0, N_D0), flush=True)
    bare_d0 = []
    for i in range(1, N_D0 + 1):
        ok, _, _ = run_bare_episode(bt, "bare_d0_%d" % i, "gemma")
        bare_d0.append(ok)
    tsar_d0 = []
    for i in range(1, N_D0 + 1):
        ok, used, _, _ = run_tsar_episode(tt, "tsar_d0_%d" % i, "gemma")
        tsar_d0.append((ok, used))

    print("--- D1: повтор задачи (у tsarapina накоплено знание) ---",
          flush=True)
    bare_d1 = []
    for i in range(1, N_D1 + 1):
        ok, _, _ = run_bare_episode(bt, "bare_d1_%d" % i, "gemma")
        bare_d1.append(ok)
    tsar_d1 = []
    for i in range(1, N_D1 + 1):
        ok, used, _, _ = run_tsar_episode(tt, "tsar_d1_%d" % i, "gemma")
        tsar_d1.append((ok, used))

    print("--- MODEL SWAP: tsarapina + qwen2.5:3b (тот же Knowledge) ---",
          flush=True)
    swap = []
    for i in range(1, 3):
        ok, used, _, _ = run_tsar_episode(tt, "tsar_swap_%d" % i, "qwen25")
        swap.append((ok, used))

    # ---- итоговая сводка (механика; интерпретация — в REPORT) ----
    def acts_of(stores):
        return len(stores)  # заглушка

    summary = {
        "bare_d0": [bool(x) for x in bare_d0],
        "tsar_d0": [[bool(x[0]), bool(x[1])] for x in tsar_d0],
        "bare_d1": [bool(x) for x in bare_d1],
        "tsar_d1": [[bool(x[0]), bool(x[1])] for x in tsar_d1],
        "swap_qwen25": [[bool(x[0]), bool(x[1])] for x in swap],
        "knowledge_tsar": len({v["knowledge_id"]
                               for v in tt.read_knowledge_versions_all()}),
        "knowledge_bare": len({v["knowledge_id"]
                               for v in bt.read_knowledge_versions_all()}),
    }
    log({"event": "summary", "data": summary})
    print("== SUMMARY ==", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    print("saved %s" % RESULTS_LOG, flush=True)


if __name__ == "__main__":
    main()
