# -*- coding: utf-8 -*-
"""MIN-MECHANISM-1 / CUT-3 driver (Tsarapina; FREEZE 12.09.2026).

Cut-3: SAME ACQUISITION → verified SUCCESS → {FULL, CAND3} → R1–R9.
CAND3 = persistent mapping + applicable_when + E2:
  - E2 = 2 последовательных non-success применения → сигнал;
  - E2 разрешает тот же общий BIN (acquisition mechanism);
  - E2 не выбирает действие; новое — только из BIN;
  - записи не удаляются; lookup — последняя.

Trace: раздельные поля e2_detected / exploration_authorized /
exploration_started / acquisition_steps / new_knowledge /
fail_streak_before.

Preflight (до первого R1): FULL-прибор; CAND3 applicability;
CAND3 E2 dry-run (2 non-success → E2; new record; оба сохранены).

Запуск: python3 mm1_cut3_driver.py all|preflight|full|cand3
Логи: MM1_CUT3.log, MM1_CUT3_trace.jsonl; сторы data_cut3_*.
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
sys.path.insert(0, DIR)

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from llm import adapter  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

from mm1_cut3_mapping import MappingCut3  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
LOG = os.path.join(DIR, "MM1_CUT3.log")
TRACE = os.path.join(DIR, "MM1_CUT3_trace.jsonl")
PROVIDER = "gemma4"
MAX_ACTS = 4
MAX_ROUNDS = 4
WORLDS = {"w1": ["a"], "w2": ["a", "q"]}
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-a2", "fix-aq", "fix-c"]
SCENES = [("R1", "w1", False), ("R2", "w1", False), ("R3", "w1", True),
          ("R4", "w1", False), ("R5", "w2", False), ("R6", "w2", False),
          ("R7", "w2", False), ("R8", "w2", False), ("R9", "w1", False)]


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


def ctx_now():
    return polygon_sensor.sensor_envfact()[4]


def envver_now():
    return polygon_sensor.sensor_envver()[4]


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]


def lock_set():
    return sorted(os.path.basename(p) for p in
                  glob.glob("/run/tsasvc.lock.*"))


def mk_action(store, command, proposed_by, ctx=None):
    args = {"goal": GOAL}
    if ctx is not None:
        args["ctx_extra"] = ctx
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": args, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "MIN-MECHANISM-1-CUT-3"}
    store.append_action(a)
    return a


def task_text(symptom):
    return ("Сервис tsasvc не работает: не запускается (inactive), "
            "симптом: %s. Верни сервис в состояние active. Доступно: "
            "systemctl start/stop/restart tsasvc, диагностика (status, "
            "is-active, journalctl, ls). Предложи действия." % symptom)


def _last_result(store, aid):
    p = os.path.join(os.path.dirname(store.obs_jsonl), "results.jsonl")
    last = None
    for line in open(p, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("action_id") == aid:
            last = rec
    return last["result_id"] if last else None


def save_episode(store, problem, facts, acts, outcomes, ok):
    if not acts:
        return None
    last = acts[-1]
    rid = _last_result(store, last["action_id"])
    if not rid:
        return None
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[last["action_id"]], result_ref=rid,
        machine="min-mechanism-1-cut-3")
    experience.save(store, exp_full)
    out = "success" if ok else (outcomes[-1] if outcomes else "unknown")
    k = update.apply(store, exp_full["experience_id"], out)
    return k


def trace_suggest(ep, side, world, ctx, problem, sug, event):
    trace({"ep": ep, "side": side, "kind": "suggest", "world": world,
           "E": ctx, "V": envver_now(), "symptom": symptom_now(),
           "lock_set": lock_set(), "problem": problem,
           "strategy_id": sug.get("strategy_id"),
           "rules": [r.get("rule") for r in (sug.get("rationale") or [])],
           "hypothesis": bool(sug.get("hypothesis")),
           "exploration": bool(sug.get("exploration")),
           "event": "E2_TRANSITION" if event else None,
           "ctx_now": sug.get("ctx_now"),
           "ctx_mismatch": sug.get("ctx_mismatch"),
           "strategy_version": sug.get("strategy_version"),
           "selected_K": sug.get("knowledge_refs"),
           "suggestion_id": sug.get("suggestion_id"),
           "candidate_actions": [c.get("command") for c in
                                 (sug.get("candidate_actions") or [])]})


def llm_propose(store, system):
    r = adapter.propose(PROVIDER,
                        adapter.build_prompt(task_text(symptom_now())),
                        max_tokens=300, timeout=180)
    acts = []
    if r["ok"]:
        for c in r["candidate_actions"]:
            cmd = c.get("command", "")
            if "tsasvc" in cmd or "fix-" in cmd:
                acts.append(mk_action(store, cmd, proposed_by=system,
                                      ctx=ctx_now()))
    return r, acts


def run_action(store, act, ep, side, tag):
    res = executor.execute(store, act)
    ok_now = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    out = "success" if ok_now else ev["outcome"]
    log({"ep": ep, "side": side, "event": "action", "by": tag,
         "command": act["command"], "outcome": out,
         "refused": res.get("refused"), "exit": res.get("exit_code")})
    return ok_now, out


def tsar_episode(store, world, ep, extra=False):
    """FULL-стор: v0.6.x+A1 + политика EE-2 + ctx_extra."""
    env_set(world, extra=extra)
    ctx = ctx_now()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    banned = []
    acts, outs = [], []
    ok = False
    transition = False
    p2_used = False
    for _ in range(MAX_ROUNDS):
        sug = strategy.suggest(store, {"problem": problem}, by="cut3",
                               banned_commands=banned or None,
                               ctx_now=ctx)
        sid = sug.get("strategy_id")
        is_tr = sug.get("event") == "E2_TRANSITION"
        transition = transition or is_tr
        trace_suggest(ep, "FULL", world, ctx, problem, sug, is_tr)
        p2 = (sid == "S1" and not sug.get("exploration"))
        if is_tr or sug.get("exploration") or p2:
            p2_used = p2_used or p2
            tag = "cut3/p2-acq" if p2 else "cut3/explore"
            for bcmd in BIN:
                act = mk_action(store, bcmd, tag, ctx)
                ok_now, out = run_action(store, act, ep, "FULL", tag)
                acts.append(act)
                outs.append(out)
                if ok_now:
                    ok = True
                    break
            break
        if sid == "S2" and sug.get("candidate_actions"):
            cmd = sug["candidate_actions"][0]["command"]
            act = mk_action(store, cmd, "cut3/s2", ctx)
            ok_now, out = run_action(store, act, ep, "FULL", "cut3/s2")
            acts.append(act)
            outs.append(out)
            if ok_now:
                ok = True
                break
            banned.append(cmd)
            if not sug.get("hypothesis"):
                break
            continue
        r, llm_acts = llm_propose(store, "cut3/llm-fallback")
        trace({"ep": ep, "side": "FULL", "kind": "llm_fallback",
               "strategy_id": sid, "llm_ok": r.get("ok"),
               "candidates": [c.get("command") for c in
                              (r.get("candidate_actions") or [])]})
        for act in llm_acts[:MAX_ACTS]:
            ok_now, out = run_action(store, act, ep, "FULL",
                                     "cut3/llm-fallback")
            acts.append(act)
            outs.append(out)
            if ok_now:
                ok = True
                break
        break
    kres = save_episode(store, problem, facts, acts, outs, ok)
    kcount = len({v["knowledge_id"]
                  for v in store.read_knowledge_versions_all()})
    log({"ep": ep, "side": "FULL", "event": "episode", "world": world,
         "E": ctx, "success": ok, "actions": len(acts), "outcomes": outs,
         "transition": transition, "p2_used": p2_used,
         "knowledge_delta": bool(kres), "knowledge_total": kcount})
    trace({"ep": ep, "side": "FULL", "kind": "episode_result",
           "success": ok, "actions": len(acts), "outcomes": outs,
           "transition": transition, "p2_used": p2_used,
           "knowledge_delta": bool(kres), "knowledge_total": kcount})
    return ok, len(acts), transition


def cut3_episode(store, cand, world, ep, extra=False):
    """CAND3: mapping + applicability + E2 (E2 только разрешает BIN)."""
    env_set(world, extra=extra)
    cond = symptom_now()
    obs = {"E": ctx_now()}
    entry = cand.lookup(cond)
    streak_before = cand.fail_streak(cond)
    acts, outs = [], []
    ok = False
    rejected = False
    e2_detected = False
    expl_auth = False
    expl_started = False
    acq_steps = []
    new_k = None
    if entry is None:
        for bcmd in BIN:
            act = mk_action(store, bcmd, "cut3/acq-bin")
            ok_now, out = run_action(store, act, ep, "CAND3",
                                     "cut3/acq-bin")
            acts.append(act)
            outs.append(out)
            acq_steps.append(bcmd)
            if ok_now:
                ok = True
                break
        if ok:
            new_k = cand.record(cond, acts[-1]["command"], "success",
                                obs=obs, source="acquisition")
            cand.note_success(cond)
    elif cand.should_transition(cond):
        e2_detected = True
        expl_auth = True
        expl_started = True
        for bcmd in BIN:
            act = mk_action(store, bcmd, "cut3/e2-explore")
            ok_now, out = run_action(store, act, ep, "CAND3",
                                     "cut3/e2-explore")
            acts.append(act)
            outs.append(out)
            acq_steps.append(bcmd)
            if ok_now:
                ok = True
                break
        if ok:
            new_k = cand.record(cond, acts[-1]["command"], "success",
                                obs=obs, source="e2-exploration")
            cand.note_success(cond)
    elif cand.applicable(entry, obs):
        act = mk_action(store, entry["action"], "cut3/mapping")
        ok_now, out = run_action(store, act, ep, "CAND3",
                                 "cut3/mapping")
        acts.append(act)
        outs.append(out)
        ok = ok_now
        if ok:
            cand.note_success(cond)
        else:
            cand.note_non_success(cond)
    else:
        rejected = True
    rec = {"ep": ep, "side": "CAND3", "event": "episode", "world": world,
           "condition": cond, "obs": obs, "lookup_hit": entry is not None,
           "entry_action": entry.get("action") if entry else None,
           "rejected": rejected,
           "e2_detected": e2_detected,
           "exploration_authorized": expl_auth,
           "exploration_started": expl_started,
           "acquisition_steps": acq_steps,
           "new_knowledge": new_k,
           "fail_streak_before": streak_before,
           "action": acts[-1]["command"] if acts else None,
           "success": ok, "actions": len(acts), "outcomes": outs}
    log(rec)
    trace(dict(rec, kind="episode_result"))
    return ok, len(acts)


def fresh_store(name):
    d = os.path.join(DIR, "data_cut3_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def part_preflight():
    print("--- PREFLIGHT ---", flush=True)
    env_set("w1")
    s1 = {"E": ctx_now(), "V": envver_now(), "symptom": symptom_now()}
    _run(["fix-a"])
    ok_a = stable_active()
    env_set("w2")
    s2 = {"E": ctx_now(), "V": envver_now(), "symptom": symptom_now()}
    _run(["fix-aq"])
    ok_aq = stable_active()
    pos = {}
    for w in ("w1", "w2"):
        env_set(w)
        hit = None
        for i, cmd in enumerate(BIN, start=1):
            _run(cmd.split())
            if stable_active():
                hit = [i, cmd]
                break
        pos[w] = hit
    r = adapter.propose(PROVIDER, adapter.build_prompt("проверка связи"),
                        max_tokens=300, timeout=180)
    env_set("w1")
    st = fresh_store("preflight")
    sug = strategy.suggest(st, {"problem": "tsasvc.service inactive "
                                "symptom=a"}, by="cut3-preflight",
                           save=False, ctx_now=ctx_now())
    probe = {"strategy_id": sug.get("strategy_id"),
             "exploration": bool(sug.get("exploration")),
             "hypothesis": bool(sug.get("hypothesis"))}
    # --- (1) FULL-прибор: ctx_extra → applicable_when → S3/cm ---
    env_set("w1")
    st_i = fresh_store("preflight_instr")
    act_i = mk_action(st_i, "fix-a", "cut3/preflight-instr",
                      ctx="absent")
    res_i = executor.execute(st_i, act_i)
    ok_i = stable_active()
    facts_i = observer.collect(st_i)
    exp_i = experience.build(problem="tsasvc.service inactive symptom=a",
                             observations=facts_i,
                             actions=[act_i["action_id"]],
                             result_ref=res_i["result_id"],
                             machine="min-mechanism-1-cut-3-preflight")
    experience.save(st_i, exp_i)
    k_i = update.apply(st_i, exp_i["experience_id"], "success")
    kid_i = k_i.get("knowledge_id") if isinstance(k_i, dict) else k_i
    aw_i = None
    for v in st_i.read_knowledge_versions_all():
        if v.get("knowledge_id") == kid_i:
            aw_i = v.get("applicable_when")
    env_set("w1", extra=True)
    sug_i = strategy.suggest(st_i, {"problem": "tsasvc.service "
                                    "inactive symptom=a"},
                             by="cut3-instr", save=False,
                             ctx_now="present")
    instr_full = (act_i["args"].get("ctx_extra") == "absent"
                  and aw_i is not None and ok_i
                  and sug_i.get("strategy_id") == "S3"
                  and bool(sug_i.get("ctx_mismatch")))
    log({"phase": "preflight_instrument_full",
         "ctx_extra_in_action": act_i["args"].get("ctx_extra"),
         "applicable_when": aw_i,
         "suggest_sid": sug_i.get("strategy_id"),
         "suggest_cm": bool(sug_i.get("ctx_mismatch")),
         "fix_a_ok": ok_i, "instr_full_ok": instr_full})
    # --- (2..3) CAND3: applicability + E2 dry-run ---
    d3 = os.path.join(DIR, "data_cut3_preflight_map")
    if os.path.exists(d3):
        shutil.rmtree(d3)
    os.makedirs(d3)
    cand3 = MappingCut3(os.path.join(d3, "m.jsonl"))
    rec3a = cand3.record("a", "fix-a", "success", obs={"E": "absent"},
                         source="preflight")
    cand3.note_non_success("a")
    cand3.note_non_success("a")
    e2_det = cand3.should_transition("a")
    hit_pre = cand3.lookup("a")
    app3 = cand3.applicable(hit_pre, {"E": "absent"}) if hit_pre else None
    rej3 = (not cand3.applicable(hit_pre, {"E": "present"})) \
        if hit_pre else None
    rec3b = cand3.record("a", "fix-aq", "success", obs={"E": "absent"},
                         source="e2-exploration")
    cand3.note_success("a")
    hit3 = cand3.lookup("a")
    both = ({e["action"] for e in cand3.entries} == {"fix-a", "fix-aq"})
    instr_e2 = (rec3a.get("applicable_when") == {"E": "absent"}
                and e2_det and app3 is True and rej3 is True
                and hit3 is not None and hit3.get("action") == "fix-aq"
                and both)
    log({"phase": "preflight_instrument_e2",
         "record_aw": rec3a.get("applicable_when"),
         "e2_detected": e2_det,
         "exploration_authorized": e2_det,
         "applicable_on_absent": app3,
         "reject_on_present": rej3,
         "lookup_after_new": hit3.get("action") if hit3 else None,
         "both_preserved": both,
         "instr_e2_ok": instr_e2})
    log({"phase": "preflight", "sensors_w1": s1, "fix_a_works": ok_a,
         "sensors_w2": s2, "fix_aq_works": ok_aq, "bin_positions": pos,
         "adapter_ok": r["ok"], "s1_probe": probe})
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    good = (s1["E"] == "absent" and s1["symptom"] == "a" and ok_a
            and s2["symptom"] == "a" and ok_aq and r["ok"]
            and probe["strategy_id"] == "S1" and not probe["exploration"]
            and instr_full and instr_e2)
    print("PREFLIGHT: %s" % ("OK" if good else "FAIL"), flush=True)
    return good


def part_full():
    print("--- FULL SIDE (v0.6.x+A1) ---", flush=True)
    st = fresh_store("full")
    for name, world, extra in SCENES:
        tsar_episode(st, world, "full_%s" % name.lower(), extra=extra)


def part_cand3():
    print("--- CAND3 SIDE (mapping + applicability + E2) ---",
          flush=True)
    st = fresh_store("mapping")
    cand = MappingCut3(os.path.join(DIR, "data_cut3_mapping",
                                    "mapping.jsonl"))
    for name, world, extra in SCENES:
        cut3_episode(st, cand, world, "cut3_%s" % name.lower(),
                     extra=extra)


def run_all():
    open(LOG, "w", encoding="utf-8").close()
    open(TRACE, "w", encoding="utf-8").close()
    print("== MIN-MECHANISM-1 / CUT-3 (FREEZE 12.09.2026) ==",
          flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — разрез не запускается.", flush=True)
        return
    part_full()
    part_cand3()
    log({"phase": "summary", "note": "MM1_CUT3_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight", "full", "cand3"):
        print("usage: mm1_cut3_driver.py all|preflight|full|cand3",
              flush=True)
        return
    a = args[0]
    if a == "all":
        run_all()
    elif a == "preflight":
        part_preflight()
    elif a == "full":
        part_full()
    else:
        part_cand3()


if __name__ == "__main__":
    main()
