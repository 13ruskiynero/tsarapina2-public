# -*- coding: utf-8 -*-
"""LONGITUDINAL-1 driver (Tsarapina). FREEZE-протокол, 06.09.

Раскладка эпизодов зафиксирована в LONGITUDINAL1_PROTOCOL.md ДО
старта. tsar = полный контур; bare = голая gemma (без памяти);
learn = оператор-драйвер показывает fix. Среда: tsasvc v3
(демон падает, пока есть любой /run/tsasvc.lock.*); симптомы
a/b/c/ab(a b)/a2(a extra); лечения fix-a/b/c/ab/a2 (LLM их не знает).

Никаких изменений протокола после старта; дефекты не чинятся.
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
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
EXP_DIR = os.path.join(BASE, "experiments", "longitudinal1")
LOG = os.path.join(EXP_DIR, "LONGITUDINAL1_run.log")
MAX_ACTIONS = 4
FIX = {"a": "fix-a", "b": "fix-b", "c": "fix-c", "ab": "fix-ab",
       "a2": "fix-a2"}


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(symptoms):
    """Перевести среду в заданную болезнь. symptoms: 'a'|'b'|'c'|
    'ab'|'a2' (a2 = lock.a + lock.extra). Флаги очищаются ЯВНО
    (glob в subprocess без shell не раскрывается — дефект run-1)."""
    import glob
    import os
    subprocess.run(["systemctl", "stop", SVC], capture_output=True,
                   timeout=40)
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    flags = {"a": ["a"], "b": ["b"], "c": ["c"], "ab": ["a", "b"],
             "a2": ["a", "extra"]}[symptoms]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    subprocess.run(["systemctl", "reset-failed", SVC], capture_output=True,
                   timeout=40)


def symptom_now():
    """Симптом по факту сенсора (что ВИДИТ система)."""
    from observer import polygon_sensor
    src, raw, subj, prop, value = polygon_sensor.sensor_symptom()
    return value  # 'a'|'b'|'c'|'a b'|'a extra'|'none'


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "LONGITUDINAL-1"}
    store.append_action(a)
    return a


def problem_of(symptom):
    return "tsasvc.service inactive symptom=%s" % symptom


def llm_propose(store, provider, system):
    """LLM предлагает действия (bare и tsar-S1). fix-* НЕ
    упоминаются: задача — текст про сервис."""
    task = ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия."
            % symptom_now())
    r = adapter.propose(provider, adapter.build_prompt(task),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd:
                acts.append(mk_action(store, cmd, proposed_by=system))
    return r, acts


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


def learn(store, ep, symptoms, fix):
    """Оператор-драйвер показывает лечение."""
    env_set(symptoms)
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(problem=problem_of(symptom_now()),
                                observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="longitudinal1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], ev["outcome"])
    log({"ep": ep, "event": "learn", "symptoms": symptoms, "fix": fix,
         "outcome": ev["outcome"], "knowledge": bool(k)})
    return ev["outcome"] == "success"


def tsar_solve(store, ep, symptoms, provider="gemma"):
    env_set(symptoms)
    facts = observer.collect(store)
    problem = problem_of(symptom_now())
    sug = strategy.suggest(store, {"problem": problem},
                           by="strategy/deterministic")
    sid = sug["strategy_id"]
    acts = []
    if sid == strategy.S2:
        for c in sug["candidate_actions"]:
            acts.append(mk_action(store, c["command"],
                                  proposed_by="strategy/S2"))
    else:
        r, acts = llm_propose(store, provider, "tsarapina")
    log({"ep": ep, "event": "strategy", "strategy": sid,
         "refs": sug["knowledge_refs"][:6]})
    outs, ok = run_until_goal(store, acts, ep)
    result_ref = None
    if outs:
        # result последнего исполненного действия
        act = acts[len(outs) - 1]
        result_ref = _last_result(store, act["action_id"])
    if result_ref:
        exp_full = experience.build(
            problem=problem, observations=facts,
            actions=[a["action_id"] for a in acts[:len(outs)]],
            result_ref=result_ref, machine="longitudinal1")
        experience.save(store, exp_full)
        out = _last_eval(store, result_ref)
        update.apply(store, exp_full["experience_id"], out)
    kcount = len({v["knowledge_id"]
                  for v in store.read_knowledge_versions_all()})
    log({"ep": ep, "event": "episode", "system": "tsar", "provider":
         provider, "symptoms": symptoms, "strategy": sid,
         "success": ok, "actions": len(outs),
         "outcomes": [o[1] for o in outs],
         "knowledge_total": kcount, "state_after": svc_state()})
    return ok, sid


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


def bare_solve(store, ep, symptoms, provider="gemma"):
    env_set(symptoms)
    r, acts = llm_propose(store, provider, "bare")
    outs, ok = run_until_goal(store, acts, ep)
    log({"ep": ep, "event": "episode", "system": "bare",
         "provider": provider, "symptoms": symptoms, "success": ok,
         "actions": len(outs), "outcomes": [o[1] for o in outs],
         "proposed": len(acts), "state_after": svc_state()})
    return ok


def fresh_store(name):
    d = os.path.join(EXP_DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def last_a_success_kid(store):
    """Последнее active-знание УСПЕХА для symptom=a (для конфликта).
    «НЕ перевело» содержит подстроку «перевело» — исключается явно."""
    import re
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


def declare_conflict_op(store, ep, k1, k2):
    knowledge.declare_conflict(store, k1, k2)
    log({"ep": ep, "event": "operator_conflict", "k1": k1, "k2": k2})


def retract_op(store, ep, kid, note):
    knowledge.retract(store, kid, by="operator", note=note)
    log({"ep": ep, "event": "operator_retract", "kid": kid})


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== LONGITUDINAL-1 (FREEZE 06.09) ==", flush=True)
    # полигон здоров
    env_set("a"); fix = FIX["a"]
    _run([fix]); 
    assert svc_state() == "active", "полигон не поднялся"

    bt = fresh_store("bare")
    tt = fresh_store("tsar")

    def L(ep, fn):
        return fn(ep)

    # E1–E10: класс A
    L("E1", lambda e: learn(tt, e, "a", "fix-a"))
    for e in ("E2", "E3", "E4", "E5", "E6"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "a"))
    L("E7", lambda e: bare_solve(bt, e, "a"))
    for e in ("E8", "E9", "E10"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "a"))
    # E11–E20: класс B
    L("E11", lambda e: learn(tt, e, "b", "fix-b"))
    for e in ("E12", "E13", "E14", "E15", "E16"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "b"))
    L("E17", lambda e: bare_solve(bt, e, "b"))
    for e in ("E18", "E19", "E20"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "b"))
    # E21–E30: повторы вперемешку (H-L3: A после B)
    for ep, sysn, sym in [("E21", "tsar", "a"), ("E22", "bare", "a"),
                          ("E23", "tsar", "b"), ("E24", "bare", "b"),
                          ("E25", "tsar", "a"), ("E26", "tsar", "b"),
                          ("E27", "bare", "a"), ("E28", "tsar", "b"),
                          ("E29", "tsar", "a"), ("E30", "tsar", "b")]:
        if sysn == "tsar":
            tsar_solve(tt, ep, sym)
        else:
            bare_solve(bt, ep, sym)
    # E31–E40: комбинация AB
    L("E31", lambda e: learn(tt, e, "ab", "fix-ab"))
    for e in ("E32", "E33", "E34", "E35", "E36"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "ab"))
    L("E37", lambda e: bare_solve(bt, e, "ab"))
    for e in ("E38", "E39", "E40"):
        L(e, lambda ep=e: tsar_solve(tt, ep, "ab"))
    # E41–E50: НОВЫЕ C (held-out; никогда не показывалась)
    for ep, sysn in [("E41", "bare"), ("E42", "tsar"), ("E43", "bare"),
                     ("E44", "tsar"), ("E45", "tsar"), ("E46", "bare"),
                     ("E47", "tsar"), ("E48", "tsar"), ("E49", "tsar"),
                     ("E50", "tsar")]:
        if sysn == "tsar":
            tsar_solve(tt, ep, "c")
        else:
            bare_solve(bt, ep, "c")
    # Устаревание: мир A требует fix-a2 (lock.a + lock.extra)
    L("UA1", lambda e: tsar_solve(tt, e, "a2"))
    k_old = last_a_success_kid(tt)
    k_fail = None
    # K_fail — последнее знание с content «НЕ перевело» для symptom=a
    import re
    for v in reversed(sorted(tt.read_knowledge_versions_all(),
                             key=lambda v: v.get("created_at", ""))):
        if v["status"] == "active" and "НЕ перевело" in v.get("content",
                                                              ""):
            for eid in v.get("experience_refs", []):
                e = tt.read_experience(eid)
                if e and re.search(r"symptom=a(?: |$)",
                                   e.get("problem", "")):
                    k_fail = v["knowledge_id"]
                    break
        if k_fail:
            break
    if k_old and k_fail:
        declare_conflict_op(tt, "UA2", k_old, k_fail)
    else:
        log({"ep": "UA2", "event": "operator_conflict",
             "error": "k_old/k_fail не найдены", "k_old": k_old,
             "k_fail": k_fail})
    tsar_solve(tt, "UA3", "a2")   # ожидание S3 (защита)
    L("UA4", lambda e: learn(tt, e, "a2", "fix-a2"))
    if k_old:
        retract_op(tt, "UA5", k_old, "среда изменилась: fix-a2")
    if k_fail:
        retract_op(tt, "UA5b", k_fail, "устарело после fix-a2")
    tsar_solve(tt, "UA6", "a2")   # ожидание S2 fix-a2
    # Swap-контроль (M7)
    tsar_solve(tt, "SW1", "a", provider="qwen25")
    tsar_solve(tt, "SW2", "a", provider="qwen25")

    kb = len({v["knowledge_id"] for v in bt.read_knowledge_versions_all()})
    kt = len({v["knowledge_id"] for v in tt.read_knowledge_versions_all()})
    log({"event": "final", "knowledge_bare": kb, "knowledge_tsar": kt})
    print("== FINAL: knowledge bare=%d tsar=%d (log: %s) =="
          % (kb, kt, LOG), flush=True)


if __name__ == "__main__":
    main()
