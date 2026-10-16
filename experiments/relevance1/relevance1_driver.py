# -*- coding: utf-8 -*-
"""RELEVANCE-1 driver (Tsarapina). FREEZE 06.09.

Сетка комбинаций механики выбора (strategy_v2, флаги):
  R1        symptom-match
  R1+R2     + no-failure-action
  R1+R2+R3  + класс-с-максимумом-успехов (recency внутри)
Ядро-сценарий (эталон: Longitudinal-1 run-2):
  learn-A; tsar A x3; learn-B; tsar B x3;
  ВОЗВРАТ A x3 (эталон 0/3 — главный тест);
  learn-AB; tsar AB x3;
  UA-мини: a2 failure → conflict → S3-проверка → learn fix-a2 →
  retract → S2 fix-a2;
  swap x2 (qwen25); bare-контроль на возврате A.
Сетка не интерпретируется до завершения всех комбинаций.
"""
import json
import os
import re
import shutil
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "experiments", "longitudinal1"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from llm import adapter  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy_v2 as sv2  # noqa: E402
from update import update  # noqa: E402
from longitudinal1_driver import env_set, mk_action, svc_state, \
    symptom_now  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
EXP_DIR = os.path.join(BASE, "experiments", "relevance1")
MAX_ACTIONS = 4

COMBOS = [
    ("R1", {"r1": True, "r2": False, "r3": False}),
    ("R1R2", {"r1": True, "r2": True, "r3": False}),
    ("R1R2R3", {"r1": True, "r2": True, "r3": True}),
]

LOG = None


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def problem_of(symptom):
    return "tsasvc.service inactive symptom=%s" % symptom


def run_until_goal(store, acts, ep):
    out = []
    for i, act in enumerate(acts[:MAX_ACTIONS]):
        res = executor.execute(store, act)
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        out.append((act["command"], ev["outcome"]))
        log({"ep": ep, "event": "action", "n": i + 1,
             "command": act["command"], "refused": res["refused"],
             "exit": res["exit_code"], "outcome": ev["outcome"]})
        if ev["outcome"] == "success":
            return out, True
    return out, False


def _last_result(store, aid):
    path = os.path.join(os.path.dirname(store.obs_jsonl),
                        "results.jsonl")
    if not os.path.exists(path):
        return None
    last = None
    for line in open(path, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("action_id") == aid:
            last = rec
    return last["result_id"] if last else None


def _last_eval(store, rid):
    evs = store.read_evaluations(rid)
    return evs[-1]["outcome"] if evs else "unknown"


def _finalize_episode(store, ep, problem, facts, acts, n_out):
    """Опыт + update после серии действий (как longitudinal)."""
    if not n_out:
        return
    act = acts[n_out - 1]
    result_ref = _last_result(store, act["action_id"])
    if not result_ref:
        return
    exp_full = experience.build(problem=problem, observations=facts,
                                actions=[a["action_id"]
                                         for a in acts[:n_out]],
                                result_ref=result_ref,
                                machine="relevance1")
    experience.save(store, exp_full)
    out = _last_eval(store, result_ref)
    update.apply(store, exp_full["experience_id"], out)


def learn(store, ep, symptoms, fix):
    env_set(symptoms)
    # симптом фиксируется ДО лечения (после fix флагов нет — дефект
    # первого прогона: learn-опыты получали symptom=none)
    problem = problem_of(symptom_now())
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(problem=problem,
                                observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="relevance1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], ev["outcome"])
    log({"ep": ep, "event": "learn", "symptoms": symptoms, "fix": fix,
         "outcome": ev["outcome"], "knowledge": bool(k)})
    return ev["outcome"] == "success"


def solve(store, ep, symptoms, flags, provider="gemma"):
    env_set(symptoms)
    facts = observer.collect(store)
    problem = problem_of(symptom_now())
    sug = sv2.suggest(store, {"problem": problem}, flags=flags,
                      by="strategy/relevance1")
    sid = sug["strategy_id"]
    acts = []
    if sid == sv2.S2:
        for c in sug["candidate_actions"]:
            acts.append(mk_action(store, c["command"],
                                  proposed_by="strategy/S2"))
    else:
        task = ("Сервис tsasvc не работает (inactive), симптом: %s. "
                "Верни в active. Доступно: systemctl start/stop/"
                "restart tsasvc, диагностика." % symptom_now())
        r = adapter.propose(provider, adapter.build_prompt(task),
                            max_tokens=300, timeout=180)
        if r["ok"]:
            for c in r["candidate_actions"]:
                cmd = c.get("command", "")
                if "tsasvc" in cmd:
                    acts.append(mk_action(store, cmd,
                                          proposed_by="tsarapina/llm"))
    log({"ep": ep, "event": "strategy", "strategy": sid,
         "refs": sug["knowledge_refs"][:5]})
    outs, ok = run_until_goal(store, acts, ep)
    _finalize_episode(store, ep, problem, facts, acts, len(outs))
    kcount = len({v["knowledge_id"]
                  for v in store.read_knowledge_versions_all()})
    log({"ep": ep, "event": "episode", "system": "tsar-v2",
         "flags": flags, "provider": provider, "symptoms": symptoms,
         "strategy": sid, "success": ok, "actions": len(outs),
         "outcomes": [o[1] for o in outs],
         "knowledge_total": kcount, "state_after": svc_state()})
    return ok, sid


def solve_bare(store, ep, symptoms, provider="gemma"):
    env_set(symptoms)
    task = ("Сервис tsasvc не работает (inactive), симптом: %s. "
            "Верни в active. Доступно: systemctl start/stop/restart "
            "tsasvc, диагностика." % symptom_now())
    r = adapter.propose(provider, adapter.build_prompt(task),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd:
                acts.append(mk_action(store, cmd, proposed_by="bare"))
    outs, ok = run_until_goal(store, acts, ep)
    log({"ep": ep, "event": "episode", "system": "bare",
         "symptoms": symptoms, "success": ok, "actions": len(outs),
         "outcomes": [o[1] for o in outs]})
    return ok


def last_a_success_kid(store):
    cands = []
    for v in store.read_knowledge_versions_all():
        if v["status"] != "active":
            continue
        content = v.get("content", "")
        if "НЕ перевело" in content or "перевело" not in content:
            continue
        for eid in v.get("experience_refs", []):
            e = store.read_experience(eid)
            if e and re.search(r"symptom=a(?: |$)", e.get("problem", "")):
                cands.append(v)
    if not cands:
        return None
    cands.sort(key=lambda v: v.get("created_at", ""))
    return cands[-1]["knowledge_id"]


def last_a_fail_kid(store):
    for v in reversed(sorted(store.read_knowledge_versions_all(),
                             key=lambda v: v.get("created_at", ""))):
        if v["status"] == "active" and "НЕ перевело" in v.get(
                "content", ""):
            for eid in v.get("experience_refs", []):
                e = store.read_experience(eid)
                if e and re.search(r"symptom=a(?: |$)",
                                   e.get("problem", "")):
                    return v["knowledge_id"]
    return None


def ua_mini(store, flags):
    solve(store, "UA1", "a2", flags)          # failure → K_fail
    k_old = last_a_success_kid(store)
    k_fail = last_a_fail_kid(store)
    if k_old and k_fail and k_old != k_fail:
        knowledge.declare_conflict(store, k_old, k_fail)
        log({"ep": "UA2", "event": "operator_conflict",
             "k1": k_old, "k2": k_fail})
    else:
        log({"ep": "UA2", "event": "operator_conflict", "error":
             "не найдены", "k_old": k_old, "k_fail": k_fail})
    solve(store, "UA3", "a2", flags)          # S3-проверка
    learn(store, "UA4", "a2", "fix-a2")
    if k_old:
        knowledge.retract(store, k_old, by="operator",
                          note="среда изменилась: fix-a2")
    if k_fail and k_fail != k_old:
        knowledge.retract(store, k_fail, by="operator",
                          note="устарело после fix-a2")
    solve(store, "UA6", "a2", flags)          # S2 fix-a2


def fresh_store(name):
    d = os.path.join(EXP_DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def run_combo(cname, flags):
    global LOG
    LOG = os.path.join(EXP_DIR, "RELEVANCE1_run_%s.log" % cname)
    open(LOG, "w", encoding="utf-8").close()
    print("===== COMBO %s =====" % cname, flush=True)
    st = fresh_store("tsar_%s" % cname)
    bt = fresh_store("bare_%s" % cname)

    learn(st, "E1", "a", "fix-a")
    for i in range(3):
        solve(st, "A%d" % (i + 1), "a", flags)
    learn(st, "E2", "b", "fix-b")
    for i in range(3):
        solve(st, "B%d" % (i + 1), "b", flags)
    # bare-контроль на возврате A (без памяти)
    solve_bare(bt, "BARE-RET", "a")
    # ГЛАВНЫЙ ТЕСТ: возврат A после обучения B
    ret = []
    for i in range(3):
        ok, sid = solve(st, "RA%d" % (i + 1), "a", flags)
        ret.append((ok, sid))
    learn(st, "E3", "ab", "fix-ab")
    ab = []
    for i in range(3):
        ok, sid = solve(st, "AB%d" % (i + 1), "ab", flags)
        ab.append((ok, sid))
    ua_mini(st, flags)
    sw = []
    for i in range(2):
        ok, sid = solve(st, "SW%d" % (i + 1), "a", flags,
                        provider="qwen25")
        sw.append((ok, sid))
    kt = len({v["knowledge_id"]
              for v in st.read_knowledge_versions_all()})
    log({"event": "final", "combo": cname, "return_A": ret,
         "ab": ab, "swap": sw, "knowledge_tsar": kt})
    print("combo %s: return_A=%s ab=%s swap=%s knowledge=%d"
          % (cname, ret, ab, sw, kt), flush=True)


def main():
    if os.path.exists(EXP_DIR) is False:
        os.makedirs(EXP_DIR)
    for cname, flags in COMBOS:
        run_combo(cname, flags)
    print("== RELEVANCE-1 сетка завершена (3 комбинации) ==",
          flush=True)


if __name__ == "__main__":
    main()
