# -*- coding: utf-8 -*-
"""VERTICAL-1 v2 driver — локальный causal test (Tsarapina).

Гипотеза H1 (профессор):
> Царапина помогает там, где базовая модель НЕ знает решения.

Среда: tsasvc с флагом-блокировкой /run/tsasvc.lock (демон падает
при старте, пока флаг есть). Лечение — tsafix (снять флаг + start):
команда, которую LLM не знает и не выведет из текста задачи.

Серии:
- BARE-TEST x3 (без обучающего эпизода): gemma перебирает
  start/restart → всё failure → не может вылечить;
- LEARN x1 (только Царапина): оператор-драйвер выполняет tsafix →
  проверенное последствие → опыт → evaluation success → знание K1;
- TSAR-TEST x3: контур → S2 (K1) → tsafix → success;
- SWAP x2: тот же контур с qwen2.5:3b (S2 без участия LLM).

Критерий (на слово профессора, H1): если Царапина после ОДНОГО
показанного эпизода решает задачу через S2, а bare продолжает
перебирать бесполезные действия, — внешнее приобретение знания
наблюдаемо и воспроизводимо.
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
from llm import adapter  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
LOCK = "/run/tsasvc.lock"
PROBLEM = "%s.service state=inactive (не запускается)" % SVC
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
TASK_TEXT = ("Сервис %s не работает: не запускается (inactive). "
             "Верни сервис в состояние active. Доступные команды: "
             "systemctl start/stop/restart %s; диагностика: status, "
             "is-active, ss, ps, journalctl. Предложи действия." %
             (SVC, SVC))
FIX = "tsafix"
EXP_DIR = os.path.join(BASE, "experiments", "vertical1")
RESULTS_LOG = os.path.join(EXP_DIR, "VERTICAL1_v2_run.log")
MAX_ACTIONS = 5


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(RESULTS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def env_broken():
    """Среда: флаг установлен + сервис остановлен (больной)."""
    subprocess.run(["systemctl", "stop", SVC], capture_output=True,
                   timeout=30)
    open(LOCK, "w").close()
    subprocess.run(["systemctl", "reset-failed", SVC], capture_output=True,
                   timeout=30)


def env_healthy():
    subprocess.run([FIX], capture_output=True, timeout=30)


def svc_state():
    p = _run(["systemctl", "is-active", SVC])
    return p.stdout.strip()


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "VERTICAL-1 v2"}
    store.append_action(a)
    return a


def propose_actions(provider, store, system):
    p = adapter.build_prompt(TASK_TEXT)
    r = adapter.propose(provider, p, max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or c.get("type") == "observe":
                acts.append(mk_action(store, cmd,
                                      proposed_by=system + "/llm"))
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


def bare_episode(store, episode, provider="gemma"):
    env_broken()
    r, acts = propose_actions(provider, store, "bare")
    results, evals, ok = run_actions_till_goal(store, acts, episode)
    log({"ep": episode, "system": "bare", "provider": provider,
         "success": ok, "executed": len(results),
         "proposed": len(acts),
         "outcomes": [e["outcome"] for e in evals],
         "state_after_env": svc_state()})
    return ok


def learn_episode(store, episode):
    """Обучающий эпизод: оператор-драйвер выполняет tsafix."""
    env_broken()
    facts = observer.collect(store)
    act = mk_action(store, FIX, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="vertical1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], ev["outcome"])
    log({"ep": episode, "event": "learn", "command": FIX,
         "outcome": ev["outcome"], "knowledge_created": bool(k),
         "experience_id": exp_full["experience_id"],
         "state_after_env": svc_state()})
    return ev["outcome"] == "success", bool(k)


def tsar_episode(store, episode, provider="gemma"):
    env_broken()
    facts = observer.collect(store)
    sug = strategy.suggest(store, {"problem": PROBLEM},
                           by="strategy/deterministic")
    sid = sug["strategy_id"]
    used_knowledge = sid == strategy.S2
    acts = []
    if sid == strategy.S2:
        for c in sug["candidate_actions"]:
            acts.append(mk_action(store, c["command"],
                                  proposed_by="strategy/S2"))
    else:
        r, llm_acts = propose_actions(provider, store, "tsarapina")
        acts = llm_acts
    log({"ep": episode, "event": "strategy", "strategy": sid,
         "knowledge_refs": sug["knowledge_refs"]})
    results, evals, ok = run_actions_till_goal(store, acts, episode)
    aids = [a["action_id"] for a in acts[:len(results)]] if results else []
    result_ref = results[-1]["result_id"] if results else None
    if result_ref:
        exp_full = experience.build(problem=PROBLEM, observations=facts,
                                    actions=aids, result_ref=result_ref,
                                    machine="vertical1")
        experience.save(store, exp_full)
        out = evals[-1]["outcome"]
        update.apply(store, exp_full["experience_id"], out)
    log({"ep": episode, "system": "tsarapina", "provider": provider,
         "strategy": sid, "used_knowledge": used_knowledge,
         "success": ok, "executed": len(results),
         "state_after_env": svc_state(),
         "knowledge_count": len({v["knowledge_id"] for v in
                                 store.read_knowledge_versions_all()})})
    return ok, used_knowledge


def fresh_store(name):
    d = os.path.join(EXP_DIR, "data_v2_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(RESULTS_LOG, "w", encoding="utf-8").close()
    print("== VERTICAL-1 v2 (H1: невыводимое решение) ==", flush=True)
    env_healthy()
    assert svc_state() == "active", "полигон не поднялся"
    assert not os.path.exists(LOCK), "флаг не снят"

    bt = fresh_store("bare")
    tt = fresh_store("tsar")

    print("--- BARE-TEST x3 (нет обучающего эпизода) ---", flush=True)
    bare_res = []
    for i in range(1, 4):
        bare_res.append(bare_episode(bt, "bare_v2_%d" % i, "gemma"))

    print("--- LEARN (Царапина, оператор показывает tsafix) ---",
          flush=True)
    learn_ok, k_ok = learn_episode(tt, "tsar_v2_learn")

    print("--- TSAR-TEST x3 (S2 через знание) ---", flush=True)
    tsar_res = []
    for i in range(1, 4):
        ok, used = tsar_episode(tt, "tsar_v2_%d" % i, "gemma")
        tsar_res.append((ok, used))

    print("--- SWAP x2 (qwen2.5:3b, тот же Knowledge) ---", flush=True)
    swap_res = []
    for i in range(1, 3):
        ok, used = tsar_episode(tt, "tsar_v2_swap_%d" % i, "qwen25")
        swap_res.append((ok, used))

    summary = {
        "bare_test": [bool(x) for x in bare_res],
        "learn": {"success": learn_ok, "knowledge_created": k_ok},
        "tsar_test": [[bool(x[0]), bool(x[1])] for x in tsar_res],
        "swap": [[bool(x[0]), bool(x[1])] for x in swap_res],
        "knowledge_bare": len({v["knowledge_id"]
                               for v in bt.read_knowledge_versions_all()}),
        "knowledge_tsar": len({v["knowledge_id"]
                               for v in tt.read_knowledge_versions_all()}),
    }
    log({"event": "summary", "data": summary})
    print("== SUMMARY ==", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    print("saved %s" % RESULTS_LOG, flush=True)


if __name__ == "__main__":
    main()
