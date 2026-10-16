# -*- coding: utf-8 -*-
"""MIN-MECHANISM-1 / CUT-2 driver (Tsarapina; FREEZE 12.09.2026).

Разрез Cut-2: SAME ACQUISITION → verified SUCCESS → {FULL, CAND2} →
R1–R9. CAND2 = persistent mapping + applicable_when (один
добавленный слой к Cut-1); mismatch → mechanical reject.

FULL-стор: v0.6.x+A1 + политика EE-2 + ctx_extra (Run-2 прибор).
CAND2-стор: mm1_cut2_mapping.MappingCut2; без recovery, без
Explore; condition = symptom-only.

Preflight (часть протокола, до первого R1):
  1) FULL: ctx_extra → applicable_when → S3/cm на mismatch;
  2) CAND2: record → applicable_when={E:...};
  3) CAND2: lookup → condition=symptom;
  4) CAND2: mismatch mechanically rejectable (E=present).

Запуск: python3 mm1_cut2_driver.py all|preflight|full|cand2
Логи: MM1_CUT2.log, MM1_CUT2_trace.jsonl; сторы data_cut2_*.
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

from mm1_cut2_mapping import MappingCut2  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
LOG = os.path.join(DIR, "MM1_CUT2.log")
TRACE = os.path.join(DIR, "MM1_CUT2_trace.jsonl")
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
         "rationale": "MIN-MECHANISM-1-CUT-2"}
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
        machine="min-mechanism-1-cut-2")
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
        sug = strategy.suggest(store, {"problem": problem}, by="cut2",
                               banned_commands=banned or None,
                               ctx_now=ctx)
        sid = sug.get("strategy_id")
        is_tr = sug.get("event") == "E2_TRANSITION"
        transition = transition or is_tr
        trace_suggest(ep, "FULL", world, ctx, problem, sug, is_tr)
        p2 = (sid == "S1" and not sug.get("exploration"))
        if is_tr or sug.get("exploration") or p2:
            p2_used = p2_used or p2
            tag = "cut2/p2-acq" if p2 else "cut2/explore"
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
            act = mk_action(store, cmd, "cut2/s2", ctx)
            ok_now, out = run_action(store, act, ep, "FULL", "cut2/s2")
            acts.append(act)
            outs.append(out)
            if ok_now:
                ok = True
                break
            banned.append(cmd)
            if not sug.get("hypothesis"):
                break
            continue
        r, llm_acts = llm_propose(store, "cut2/llm-fallback")
        trace({"ep": ep, "side": "FULL", "kind": "llm_fallback",
               "strategy_id": sid, "llm_ok": r.get("ok"),
               "candidates": [c.get("command") for c in
                              (r.get("candidate_actions") or [])]})
        for act in llm_acts[:MAX_ACTS]:
            ok_now, out = run_action(store, act, ep, "FULL",
                                     "cut2/llm-fallback")
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


def cut2_episode(store, cand, world, ep, extra=False):
    """CAND2-стор: mapping + applicability; mismatch → reject."""
    env_set(world, extra=extra)
    cond = symptom_now()
    obs = {"E": ctx_now()}
    entry = cand.lookup(cond)
    acts, outs = [], []
    ok = False
    rejected = False
    if entry is None:
        for bcmd in BIN:
            act = mk_action(store, bcmd, "cut2/acq-bin")
            ok_now, out = run_action(store, act, ep, "CAND2",
                                     "cut2/acq-bin")
            acts.append(act)
            outs.append(out)
            if ok_now:
                ok = True
                break
        if ok:
            cand.record(cond, acts[-1]["command"], "success", obs=obs)
    elif cand.applicable(entry, obs):
        act = mk_action(store, entry["action"], "cut2/mapping")
        ok_now, out = run_action(store, act, ep, "CAND2",
                                 "cut2/mapping")
        acts.append(act)
        outs.append(out)
        ok = ok_now
    else:
        rejected = True
    log({"ep": ep, "side": "CAND2", "event": "episode", "world": world,
         "condition": cond, "obs": obs, "lookup_hit": entry is not None,
         "applicable_when": (entry or {}).get("applicable_when"),
         "rejected": rejected,
         "action": acts[-1]["command"] if acts else None,
         "success": ok, "actions": len(acts), "outcomes": outs})
    trace({"ep": ep, "side": "CAND2", "kind": "episode_result",
           "world": world, "condition": cond, "obs": obs,
           "lookup_hit": entry is not None,
           "applicable_when": (entry or {}).get("applicable_when"),
           "rejected": rejected,
           "action": acts[-1]["command"] if acts else None,
           "success": ok, "actions": len(acts), "outcomes": outs})
    return ok, len(acts), rejected


def fresh_store(name):
    d = os.path.join(DIR, "data_cut2_%s" % name)
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
                                "symptom=a"}, by="cut2-preflight",
                           save=False, ctx_now=ctx_now())
    probe = {"strategy_id": sug.get("strategy_id"),
             "exploration": bool(sug.get("exploration")),
             "hypothesis": bool(sug.get("hypothesis"))}
    # --- (1) FULL-прибор: ctx_extra → applicable_when → S3/cm ---
    env_set("w1")
    st_i = fresh_store("preflight_instr")
    act_i = mk_action(st_i, "fix-a", "cut2/preflight-instr",
                      ctx="absent")
    res_i = executor.execute(st_i, act_i)
    ok_i = stable_active()
    facts_i = observer.collect(st_i)
    exp_i = experience.build(problem="tsasvc.service inactive symptom=a",
                             observations=facts_i,
                             actions=[act_i["action_id"]],
                             result_ref=res_i["result_id"],
                             machine="min-mechanism-1-cut-2-preflight")
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
                             by="cut2-instr", save=False,
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
    # --- (2..4) CAND2-прибор: record → aw; lookup; reject ---
    d2 = os.path.join(DIR, "data_cut2_preflight_map")
    if os.path.exists(d2):
        shutil.rmtree(d2)
    os.makedirs(d2)
    cand = MappingCut2(os.path.join(d2, "m.jsonl"))
    env_set("w1")
    obs_absent = {"E": ctx_now()}
    rec2 = cand.record("a", "fix-a", "success", obs=obs_absent)
    hit2 = cand.lookup("a")
    env_set("w1", extra=True)
    obs_present = {"E": ctx_now()}
    app_absent = cand.applicable(hit2, obs_absent) if hit2 else None
    rej_present = (not cand.applicable(hit2, obs_present)) if hit2 else None
    instr_cand = (rec2.get("applicable_when") == {"E": "absent"}
                  and hit2 is not None
                  and hit2.get("condition") == "a"
                  and app_absent is True and rej_present is True)
    log({"phase": "preflight_instrument_cand2",
         "record_aw": rec2.get("applicable_when"),
         "condition": hit2.get("condition") if hit2 else None,
         "applicable_on_absent": app_absent,
         "reject_on_present": rej_present,
         "instr_cand_ok": instr_cand})
    log({"phase": "preflight", "sensors_w1": s1, "fix_a_works": ok_a,
         "sensors_w2": s2, "fix_aq_works": ok_aq, "bin_positions": pos,
         "adapter_ok": r["ok"], "s1_probe": probe})
    env_set("w1")
    _run(["systemctl", "stop", SVC])
    good = (s1["E"] == "absent" and s1["symptom"] == "a" and ok_a
            and s2["symptom"] == "a" and ok_aq and r["ok"]
            and probe["strategy_id"] == "S1" and not probe["exploration"]
            and instr_full and instr_cand)
    print("PREFLIGHT: %s" % ("OK" if good else "FAIL"), flush=True)
    return good


def part_full():
    print("--- FULL SIDE (v0.6.x+A1) ---", flush=True)
    st = fresh_store("full")
    for name, world, extra in SCENES:
        tsar_episode(st, world, "full_%s" % name.lower(), extra=extra)


def part_cand2():
    print("--- CAND2 SIDE (mapping + applicability) ---", flush=True)
    st = fresh_store("mapping")
    cand = MappingCut2(os.path.join(DIR, "data_cut2_mapping",
                                    "mapping.jsonl"))
    for name, world, extra in SCENES:
        cut2_episode(st, cand, world, "cut2_%s" % name.lower(),
                     extra=extra)


def run_all():
    open(LOG, "w", encoding="utf-8").close()
    open(TRACE, "w", encoding="utf-8").close()
    print("== MIN-MECHANISM-1 / CUT-2 (FREEZE 12.09.2026) ==",
          flush=True)
    if not part_preflight():
        print("PREFLIGHT: FAIL — разрез не запускается.", flush=True)
        return
    part_full()
    part_cand2()
    log({"phase": "summary", "note": "MM1_CUT2_TABLE.md — после"})
    print("== DONE ==", flush=True)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("all", "preflight", "full", "cand2"):
        print("usage: mm1_cut2_driver.py all|preflight|full|cand2",
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
        part_cand2()


if __name__ == "__main__":
    main()
