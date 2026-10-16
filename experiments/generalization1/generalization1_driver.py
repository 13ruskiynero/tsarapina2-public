# -*- coding: utf-8 -*-
"""GENERALIZATION-1 driver (Tsarapina, зона 4; FREEZE 06.09.2026).

Дизайн: GENERALIZATION1_DESIGN.md (заморожен профессором).
Отдельная ветка: Knowledge/R1/Strategy v0.2 НЕ меняются.

Вопрос: может ли система получить успешное решение для нового C из
проверенных A/B без прямого знания C→action, если новое решение не
закодировано ни в Strategy, ни в Knowledge, ни в LLM prompt?

Процедура (до прогона, из дизайна):
  Ф1: обучение A/B/AB на tsar-контуре (валидность; стоп-критерий);
  Ф2: предтест голой LLM на C (fix-c вне словаря — иначе среда
      невалидна, прогон останавливается);
  Ф3: C×7 БЕЗ learn (H-L5-канон); результат по ходу НЕ
      интерпретируется (только лог фактов);
  Ф4: контроли: 4a bare C×7; 4b систематический перебор C×7;
      4c sanity learn-c → C (S2 fix-c); 4d swap qwen25 C×3.

Альтернативы происхождения (закрываются):
  1) LLM знала: предтест Ф2; 2) правило в Strategy: аудит кода
     (хэш strategy.py до прогона); 3) случайная попытка: перебор
     4b; 4) C в Knowledge до Ф3: автоматический аудит.
"""
import glob
import hashlib
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
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "GENERALIZATION1_run.log")
MAX_ACTS = 4
FIX = {"a": "fix-a", "b": "fix-b", "ab": "fix-ab", "c": "fix-c"}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-c"]


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(symptoms):
    """symptoms: 'a'|'b'|'ab'|'c'. Флаги очищаются явно (glob)."""
    subprocess.run(["systemctl", "stop", SVC], capture_output=True,
                   timeout=40)
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    flags = {"a": ["a"], "b": ["b"], "ab": ["a", "b"], "c": ["c"]}[symptoms]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    subprocess.run(["systemctl", "reset-failed", SVC], capture_output=True,
                   timeout=40)


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def symptom_now():
    from observer import polygon_sensor
    src, raw, subj, prop, value = polygon_sensor.sensor_symptom()
    return value


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "GENERALIZATION-1"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия." % symptom)


def llm_propose(store, provider, system, symptom="c"):
    r = adapter.propose(provider, adapter.build_prompt(task_text(symptom)),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or "fix-" in cmd:
                acts.append(mk_action(store, cmd, proposed_by=system))
    return r, acts


def add_learn(store, symptom, fix, ep):
    """learn: оператор показывает fix (проверенное последствие)."""
    env_set(symptom)
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn")
    res = executor.execute(store, act)
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem="tsasvc.service inactive symptom=%s" % symptom_now(),
        observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="generalization1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], ev["outcome"])
    log({"phase": ep, "event": "learn", "symptom": symptom, "fix": fix,
         "outcome": ev["outcome"], "knowledge": bool(k)})
    return ev["outcome"] == "success"


def tsar_episode(store, symptom, ep, provider="gemma"):
    """Контур решает эпизод (symptom); мир отвечает по правилу
    (fix-X → success). Без learn: знание может отсутствовать."""
    env_set(symptom)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = strategy.suggest(store, {"problem": problem},
                           by="strategy/deterministic")
    sid = sug["strategy_id"]
    acts = []
    if sid == strategy.S2:
        for c in sug["candidate_actions"]:
            acts.append(mk_action(store, c["command"],
                                  proposed_by="strategy/S2"))
    else:
        r, acts = llm_propose(store, provider, "tsarapina", symptom)
    outs = []
    ok = False
    for i, act in enumerate(acts[:MAX_ACTS]):
        res = executor.execute(store, act)
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        outs.append((act["command"], ev["outcome"]))
        log({"phase": ep, "event": "action", "n": i + 1,
             "command": act["command"], "outcome": ev["outcome"]})
        if ev["outcome"] == "success":
            ok = True
            break
    if outs:
        act_last = acts[len(outs) - 1]
        last_res = None
        for line in open(os.path.join(os.path.dirname(store.obs_jsonl),
                                      "results.jsonl"),
                         encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("action_id") == act_last["action_id"]:
                last_res = rec
        if last_res:
            exp_full = experience.build(
                problem=problem, observations=facts,
                actions=[a["action_id"] for a in acts[:len(outs)]],
                result_ref=last_res["result_id"], machine="generalization1")
            experience.save(store, exp_full)
            evs = store.read_evaluations(last_res["result_id"])
            out = evs[-1]["outcome"] if evs else "unknown"
            update.apply(store, exp_full["experience_id"], out)
    kcount = len({v["knowledge_id"]
                  for v in store.read_knowledge_versions_all()})
    log({"phase": ep, "event": "episode", "system": "tsar",
         "provider": provider, "symptom": symptom, "strategy": sid,
         "success": ok, "actions": len(outs),
         "outcomes": [o[1] for o in outs], "knowledge_total": kcount})
    return ok, sid, [o[0] for o in outs]


def bare_episode(store, symptom, ep, provider="gemma"):
    """Голая LLM: история/знания не используются вовсе."""
    env_set(symptom)
    r, acts = llm_propose(store, provider, "bare", symptom)
    outs = []
    ok = False
    for i, act in enumerate(acts[:MAX_ACTS]):
        res = executor.execute(store, act)
        ev = evaluation.evaluate(store, res["result_id"], GOAL)
        outs.append((act["command"], ev["outcome"]))
        log({"phase": ep, "event": "action", "n": i + 1,
             "command": act["command"], "outcome": ev["outcome"]})
        if ev["outcome"] == "success":
            ok = True
            break
    log({"phase": ep, "event": "episode", "system": "bare",
         "provider": provider, "symptom": symptom, "success": ok,
         "actions": len(outs), "outcomes": [o[1] for o in outs],
         "proposed": len(acts)})
    return ok, [o[0] for o in outs]


def brute_episode(symptom, ep, order=BIN, max_steps=12):
    """Систематический перебор команд (контроль «случайная попытка»)."""
    env_set(symptom)
    for i, cmd in enumerate(order[:max_steps]):
        p = _run(cmd.split())
        state = svc_state()
        ok = state == "active"
        log({"phase": ep, "event": "brute", "n": i + 1, "command": cmd,
             "exit": p.returncode, "state_after": state, "success": ok})
        if ok:
            return True, i + 1
    return False, min(len(order), max_steps)


def fresh_store(name):
    d = os.path.join(DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def phase1_train(store, ep_prefix):
    """Обучение A/B/AB + решения (валидность контура)."""
    res = {}
    assert add_learn(store, "a", FIX["a"], "%s_a_learn" % ep_prefix)
    ok1, sid, acts = tsar_episode(store, "a", "%s_a_1" % ep_prefix)
    ok2, _, _ = tsar_episode(store, "a", "%s_a_2" % ep_prefix)
    res["a"] = [ok1, ok2, sid]
    assert add_learn(store, "b", FIX["b"], "%s_b_learn" % ep_prefix)
    ok3, sid, _ = tsar_episode(store, "b", "%s_b_1" % ep_prefix)
    ok4, _, _ = tsar_episode(store, "b", "%s_b_2" % ep_prefix)
    res["b"] = [ok3, ok4, sid]
    assert add_learn(store, "ab", FIX["ab"], "%s_ab_learn" % ep_prefix)
    ok5, sid, _ = tsar_episode(store, "ab", "%s_ab_1" % ep_prefix)
    ok6, _, _ = tsar_episode(store, "ab", "%s_ab_2" % ep_prefix)
    res["ab"] = [ok5, ok6, sid]
    return res


def audit_knowledge_c(store):
    """Альтернатива 4: прямого знания C (symptom=c) в Knowledge нет?"""
    for v in store.read_knowledge_versions_all():
        if v["status"] not in ("active", "conflicted"):
            continue
        for eid in v.get("experience_refs", []):
            exp = store.read_experience(eid)
            if exp and "symptom=c" in exp.get("problem", ""):
                return False, v["knowledge_id"]
    return True, None


def pre_test_llm():
    """Ф2: голая LLM на C. fix-c не должен появиться ни у одной."""
    out = {}
    for prov in ("gemma", "qwen25"):
        rows = []
        for i in range(3):
            r = adapter.propose(prov, adapter.build_prompt(task_text("c")),
                                max_tokens=300, timeout=180)
            found = "fix-c" in (r["raw"] or "")
            rows.append({"found_fix_c": found,
                         "raw_head": (r["raw"] or "")[:120]})
            log({"phase": "F2", "provider": prov, "q": i + 1,
                 "found_fix_c": found, "ok": r["ok"]})
        out[prov] = rows
    return out


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== GENERALIZATION-1 (FREEZE 06.09.2026) ==", flush=True)

    # аудит Strategy (альтернатива 2): хэш замороженной Strategy v0.2
    strat_src = open(os.path.join(BASE, "strategy", "strategy.py"),
                     encoding="utf-8").read()
    strat_sha = hashlib.sha256(strat_src.encode()).hexdigest()[:16]
    log({"phase": "audit", "strategy_sha256": strat_sha,
         "note": "Strategy v0.2 не менялась (R1 заморожен); правил "
                 "переноса в коде нет (аудит до прогона)"})

    # Ф2: предтест LLM (альтернатива 1) — ДО обучения/прогона C
    pre = pre_test_llm()
    bad = any(x["found_fix_c"] for rows in pre.values() for x in rows)
    log({"phase": "F2", "verdict": "CONTREXAMPLE" if bad else "CLEAN"})
    if bad:
        print("КОНТРПРИМЕР СРЕДЫ: LLM называет fix-c. Стоп.", flush=True)
        return

    # Ф1: обучение (валидность контура)
    st = fresh_store("tsar")
    log({"phase": "F1", "event": "start"})
    t1 = phase1_train(st, "F1")
    log({"phase": "F1", "event": "done", "res": t1})
    ok_all = all(all(t1[k][:2]) for k in ("a", "b", "ab"))
    log({"phase": "F1", "verdict": "OK" if ok_all else "INVALID"})
    if not ok_all:
        print("Ф1: контур не решает A/B/AB — прогон невалиден.", flush=True)
        return

    # аудит Knowledge (альтернатива 4): C отсутствует до Ф3
    clean, kid = audit_knowledge_c(st)
    log({"phase": "audit", "knowledge_c_before": "CLEAN"
         if clean else "FOUND:%s" % kid})
    if not clean:
        print("Аудит Knowledge: symptom=c уже есть — стоп.", flush=True)
        return

    # Ф3: C×7 без learn (результат не интерпретируется по ходу)
    log({"phase": "F3", "event": "start"})
    f3 = []
    for i in range(1, 8):
        ok, sid, acts = tsar_episode(st, "c", "F3_C%d" % i)
        f3.append({"ep": i, "ok": ok, "strategy": sid, "acts": acts})
    log({"phase": "F3", "event": "done", "data": f3})

    # Ф4a: bare C×7 (чистый стор; тот же промпт)
    bst = fresh_store("bare")
    f4a = []
    for i in range(1, 8):
        ok, acts = bare_episode(bst, "c", "F4a_C%d" % i)
        f4a.append({"ep": i, "ok": ok, "acts": acts})
    log({"phase": "F4a", "event": "done", "data": f4a})

    # Ф4b: систематический перебор C×7 (контроль удачи)
    f4b = []
    for i in range(1, 8):
        ok, steps = brute_episode("c", "F4b_C%d" % i)
        f4b.append({"ep": i, "ok": ok, "steps": steps})
    log({"phase": "F4b", "event": "done", "data": f4b})

    # Ф4c: sanity: learn-c → эпизод C (S2 fix-c)
    sst = fresh_store("sanity")
    t1s = phase1_train(sst, "F4c_tr")
    add_learn(sst, "c", FIX["c"], "F4c_c_learn")
    ok_s, sid_s, acts_s = tsar_episode(sst, "c", "F4c_C")
    log({"phase": "F4c", "event": "done", "ok": ok_s,
         "strategy": sid_s, "acts": acts_s})

    # Ф4d: swap qwen25: история A/B/AB + C×3
    qst = fresh_store("swap")
    t1q = phase1_train(qst, "F4d_tr")
    f4d = []
    for i in range(1, 4):
        ok, sid, acts = tsar_episode(qst, "c", "F4d_C%d" % i,
                                     provider="qwen25")
        f4d.append({"ep": i, "ok": ok, "strategy": sid, "acts": acts})
    log({"phase": "F4d", "event": "done", "data": f4d})

    summary = {
        "F2_pre_test": pre,
        "F1": t1,
        "audit": {"strategy_sha256": strat_sha, "knowledge_c": clean},
        "F3_Cx7": f3,
        "F4a_bare": f4a,
        "F4b_brute": f4b,
        "F4c_sanity": {"ok": ok_s, "strategy": sid_s, "acts": acts_s},
        "F4d_swap": f4d,
    }
    log({"event": "summary", "data": summary})
    print("== SUMMARY ==", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    print("saved %s" % LOG, flush=True)


if __name__ == "__main__":
    main()
