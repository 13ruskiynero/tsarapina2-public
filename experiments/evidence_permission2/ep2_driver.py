# -*- coding: utf-8 -*-
"""EP-2A driver (FROZEN 10.09.2026; ред. 1; measurement-only; v0.6.x
не меняется).

Дизайн: EVIDENCE_PERMISSION2_DESIGN.md; протокол:
evidence_permission2/PROTOCOL.md (ред. 1: trigger-partition C4/C5;
C4 вырожден — лемма; проектные C4-клетки S6bV3/E6N-V3 идут как
C5(a), класс фиксирует классификатор).

Клетка: --cell "A1|R@C5|E6S|r1"  (branch|mode|hist|rep)
  mode: B | {R|S}@{C1|C2|C3|C5|C6}
Режимы R/S — AA-1-семантика (simulated; K = последний verified-
success; постоянно в горизонте). Триггеры — PROTOCOL §3; class_actual
пишется классификатором (§1). Unit-тесты классификатора:
--unit-class (синтетика, без прогонов).
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"

W1 = "w1"
W2 = "w2"

HISTORIES = {
    "SD": ([("w1", "1")],
           [("f", "1", W2, None), ("f", "1", W2, None),
            ("f", "1", W2, None)]),
    "SD4": ([("w1", "1")],
            [("f", "1", W2, None)] * 4),
    "N1D": ([("w1", "1")],
            [("f", "1", W1, "n"), ("s", "1", W1, None),
             ("s", "1", W1, None)]),
    "NpD": ([("w1", "1")],
            [("f", "1", W1, "n"), ("f", "1", W1, "n"),
             ("f", "1", W1, "n"), ("s", "1", W1, None)]),
    "S6bV3": ([("w1", "1"), ("w1", "2")],
              [("f", "3", W2, None), ("f", "3", W2, None),
               ("f", "3", W2, None)]),
    "E6N-V3": ([("w1", "1"), ("w1", "2")],
               [("f", "3", W1, "n"), ("s", "1", W1, None),
                ("s", "1", W1, None)]),
    "E6S": ([("w1", "1"), ("w1", "2")],
            [("f", "1", W2, None), ("f", "1", W2, None),
             ("f", "1", W2, None)]),
    "E6N": ([("w1", "1"), ("w1", "2")],
            [("f", "1", W1, "n"), ("s", "1", W1, None),
             ("s", "1", W1, None)]),
    "C6N": ([("w1", "1")],
            [("f", "1", W1, "n"), ("s", "1", W1, None),
             ("f", "1", W1, "n"), ("s", "1", W1, None)]),
}
CONFS = ("C1", "C2", "C3", "C5", "C6")

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

_OUTCOME_RE = re.compile(r"outcome=(\w+)")
_ORIG_PRIOR_LINEAGE = update._prior_lineage


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def hash_layers():
    out = {}
    for rel in LAYER_FILES:
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()[:16]
    return out


def load_strategy():
    spec = importlib.util.spec_from_file_location(
        "strategy_aa_mod", os.path.join(DIR, "..", "applicability_addressing1",
                                         "strategy_aa.py"))
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)
    return st


def env_set(world, noise, envver):
    flags = ["a"]
    if world == "w2":
        flags.append("q")
    if noise == "n":
        flags.append("n")
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(envver)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(cell):
    d = os.path.join(DIR, "data_ep2_%s" % cell)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def outcome_of_row(r):
    m = _OUTCOME_RE.search(r.get("context") or "")
    return m.group(1) if m else None


def obs_kinds(r):
    kinds = []
    for o in r.get("applicability_observations") or []:
        if o.get("source") == "verified failure":
            kinds.append("a" if o.get("signal") else "b")
        else:
            kinds.append("s")
    return kinds


def v_vals_of(r):
    vals = set()
    aw = r.get("applicable_when") or {}
    if "V" in aw:
        vals.add(str(aw["V"]))
    for o in r.get("applicability_observations") or []:
        if o.get("signal") == "V":
            vals.update(str(x) for x in (o.get("values_seen") or []))
    return vals


def row_of(store, kid):
    for v in store.read_knowledge_versions_all():
        if v["knowledge_id"] == kid:
            return v
    return None


def line_members(store, st, cmd="fix-a"):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    members = []
    for v in latest.values():
        if v.get("status") not in ("active", "conflicted"):
            continue
        try:
            a = st._addr_cmd_of(store, v)
        except Exception:
            a = None
        if not a:
            continue
        syms = sorted(a[0]) if hasattr(a[0], "__iter__") else [a[0]]
        if "a" in syms and a[1] == "absent" and a[2] == cmd:
            members.append({
                "kid": v["knowledge_id"], "created_at": v.get("created_at"),
                "outcome": outcome_of_row(v), "aw": v.get("applicable_when"),
                "kinds": obs_kinds(v), "v_vals": sorted(v_vals_of(v)),
                "gen": v.get("lineage_generation"),
            })
    members.sort(key=lambda m: (m["created_at"], m["kid"]))
    return members


def fresh_failures(members):
    last_succ = -1
    for i, m in enumerate(members):
        if m["outcome"] == "success":
            last_succ = i
    fresh = members[last_succ + 1:]
    return fresh


def conflict_present(members):
    vals = set()
    for m in members:
        if m["outcome"] == "success":
            vals.update(m.get("v_vals") or [])
    return len(vals) >= 2


def last_failure_has_a(members):
    for m in reversed(members):
        if m["outcome"] != "success":
            return "a" in m["kinds"]
    return False


def classifier(members):
    """Trigger-partition (PROTOCOL §1): conflict → C5 (a/b); иначе
    (a) → C4; иначе None."""
    if conflict_present(members):
        return "C5a" if last_failure_has_a(members) else "C5b"
    if last_failure_has_a(members):
        return "C4"
    return None


def recovery_present(members):
    """f → s → f: есть success-член после первого failure-члена."""
    first_fail = None
    for i, m in enumerate(members):
        if m["outcome"] != "success":
            first_fail = i
            break
    if first_fail is None:
        return False
    for m in members[first_fail + 1:]:
        if m["outcome"] == "success":
            return True
    return False


def trigger_check(conf, members):
    fresh = fresh_failures(members)
    if not fresh or fresh[-1]["outcome"] == "success":
        return False
    if conf == "C1":
        return len(fresh) == 1
    if conf == "C2":
        return len(fresh) == 2
    if conf == "C3":
        return len(fresh) == 3
    if conf == "C5":
        return conflict_present(members)
    if conf == "C6":
        return recovery_present(members)
    return False


def _install_retract(kid):
    orig = _ORIG_PRIOR_LINEAGE

    def wrapper(store, sym, e_val, cmd):
        return [r for r in orig(store, sym, e_val, cmd)
                if r.get("knowledge_id") != kid]
    update._prior_lineage = wrapper


def _do_action(store, cmd, ep, kind):
    facts = observer.collect(store)
    act = {"schema_version": "0.1",
           "action_id": "act_ep2_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "EP2-%s" % kind}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="ep2")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"step": ep, "mode": kind, "action": cmd, "outcome": outcome,
            "ok": ok, "strategy_id": None,
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def learn_episode(store, world, envver, cmd, ep):
    env_set(world, None, envver)
    return _do_action(store, cmd, ep, "learn")


def check_episode(store, st, world, noise, envver, ep, state):
    env_set(world, noise, envver)
    sug = st.suggest(store, {"problem": PROBLEM}, by="ep2",
                     ctx_now="absent",
                     obs_now={"E": "absent", "V": envver})
    sid = sug.get("strategy_id")
    refs = list(sug.get("knowledge_refs") or [])
    acts = [a for a in (sug.get("candidate_actions") or [])
            if a.get("type") == "command"]
    excl = state.get("exclude_kid")
    excluded = bool(excl and refs and refs[0] == excl)
    ref_row = row_of(store, refs[0]) if refs else None
    rec = {"step": ep, "world": world, "noise": noise, "envver": envver,
           "strategy_id": sid, "knowledge_refs": refs,
           "ref_outcome": outcome_of_row(ref_row) if ref_row else None,
           "excluded": excluded}
    if excluded or sid == "S3" or not acts:
        rec.update({"mode": "S3", "action": None, "outcome": None,
                    "excluded_kid": excl if excluded else None})
        return rec
    cmd = acts[0].get("command")
    rec["mode"] = "S2"
    res = _do_action(store, cmd, ep, "S2")
    rec.update({"action": res["action"], "outcome": res["outcome"],
                "ok": res["ok"],
                "created_knowledge_id": res["created_knowledge_id"]})
    return rec


def snapshot_all(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        rows.append({
            "knowledge_id": v["knowledge_id"], "version": v["version"],
            "status": v["status"], "schema_version": v.get("schema_version"),
            "context": v.get("context"),
            "lineage_generation": v.get("lineage_generation"),
            "applicable_when": v.get("applicable_when"),
            "applicability_observations": v.get(
                "applicability_observations"),
            "experience_refs": v.get("experience_refs"),
        })
    rows.sort(key=lambda r: r["knowledge_id"])
    return rows


def run_cell(cell):
    branch, mode, hist, rep = cell.split("|")
    assert branch == "A1" and hist in HISTORIES, cell
    right, conf = (None, None)
    if mode != "B":
        right, conf = mode.split("@")
        assert right in ("R", "S") and conf in CONFS, cell
    st = load_strategy()
    store = fresh_store(cell)
    learn_steps, verify_steps = HISTORIES[hist]
    rec = {"cell": cell, "branch": branch, "mode": mode, "history": hist,
           "rep": rep, "right": right, "conf": conf, "learn": [],
           "steps": [], "trigger": None, "intervention": None,
           "checks": [], "line_trace": [],
           "audit_before": hash_layers(), "final_snapshot": None}
    with open(os.path.join(DIR, "..", "applicability_addressing1",
                           "strategy_aa.py"), "rb") as f:
        rec["branch_module_sha"] = hashlib.sha256(f.read()).hexdigest()[:16]

    for lw, lv in learn_steps:
        learn_episode(store, lw, lv, "fix-a", 0)
        rec["learn"].append({"world": lw, "envver": lv, "cmd": "fix-a"})

    state = {"exclude_kid": None, "intervened": False}
    for i, (aim, envver, world, noise) in enumerate(verify_steps, start=1):
        if mode != "B" and not state["intervened"]:
            mem = line_members(store, st)
            if trigger_check(conf, mem):
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                state["intervened"] = True
                state["exclude_kid"] = kid
                if right == "R" and kid:
                    _install_retract(kid)
                rec["trigger"] = {
                    "conf": conf, "step": i - 1,
                    "at": "before-step-%d" % i,
                    "class_actual": classifier(mem),
                    "conflict": conflict_present(mem),
                    "last_kinds":
                        fresh_failures(mem)[-1]["kinds"]
                        if fresh_failures(mem) else None}
                rec["intervention"] = {"right": right, "kid": kid,
                                       "at": "before-step-%d" % i}
        step = check_episode(store, st, world, noise, envver, i, state)
        rec["steps"].append(step)
        rec["line_trace"].append(
            [{k: m[k] for k in ("kid", "outcome", "aw", "kinds")}
             for m in line_members(store, st)])
        if (rec["intervention"] and rec["intervention"].get("at")
                == "before-step-%d" % i):
            sug = st.suggest(store, {"problem": PROBLEM}, by="ep2-chk",
                             save=False, ctx_now="absent",
                             obs_now={"E": "absent", "V": envver})
            rec["checks"].append({
                "step": i, "granted_excluded": step.get("excluded") is True,
                "selected_ref": (sug.get("knowledge_refs") or [None])[0],
                "exclude_kid": rec["intervention"].get("kid")})
    rec["final_snapshot"] = snapshot_all(store)
    rec["audit_after"] = hash_layers()
    return rec


def unit_class():
    """Unit-тесты классификатора (синтетика; PROTOCOL §7.2)."""
    def M(outcome, aw=None, kinds=None, v_vals=None):
        return {"outcome": outcome, "aw": aw, "kinds": kinds or [],
                "v_vals": v_vals or []}
    cases = [
        ("C5b (conflict, b-запись)",
         [M("success", {"E": "absent", "V": "1"}, [], ["1"]),
          M("success", {"E": "absent"}, ["s"], ["1", "2"]),
          M("partial", None, ["b"], [])],
         "C5b"),
        ("boundary: conflict + (a) → C5",
         [M("success", {"E": "absent", "V": "1"}, [], ["1"]),
          M("success", {"E": "absent"}, ["s"], ["1", "2"]),
          M("partial", None, ["a"], ["1", "2", "3"])],
         "C5a"),
        ("C4-ветвь: (a), без конфликта",
         [M("success", {"E": "absent", "V": "1"}, [], ["1"]),
          M("partial", None, ["a"], ["1", "2"])],
         "C4"),
        ("нет C4/C5: (b), без конфликта",
         [M("success", {"E": "absent", "V": "1"}, [], ["1"]),
          M("partial", None, ["b"], [])],
         None),
    ]
    ok = True
    for name, mem, want in cases:
        got = classifier(mem)
        stat = "PASS" if got == want else "FAIL"
        ok = ok and got == want
        print("%s: %s -> %s (want %s)" % (stat, name, got, want))
    print("UNIT_CLASS_ALL_PASS=%s" % ok)
    assert ok, "unit-тесты классификатора провалены"


def class_smoke(hist):
    """Реальный классификационный смоук (PROTOCOL §7.3): learn-фаза +
    1-й failure-эпизод, без вмешательств; печатает class_actual."""
    st = load_strategy()
    store = fresh_store("smoke_%s" % hist)
    learn_steps, verify_steps = HISTORIES[hist]
    for lw, lv in learn_steps:
        learn_episode(store, lw, lv, "fix-a", 0)
    aim, envver, world, noise = verify_steps[0]
    step = check_episode(store, st, world, noise, envver, 1,
                         {"exclude_kid": None})
    mem = line_members(store, st)
    cls = classifier(mem)
    print(json.dumps({
        "hist": hist, "step1_mode": step.get("mode"),
        "step1_outcome": step.get("outcome"),
        "conflict": conflict_present(mem), "class_actual": cls,
        "line": [{k: m[k] for k in ("outcome", "aw", "kinds")}
                 for m in mem]}, ensure_ascii=False), flush=True)
    return cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell")
    ap.add_argument("--unit-class", action="store_true")
    ap.add_argument("--class-smoke", metavar="HIST")
    args = ap.parse_args()
    if args.unit_class:
        unit_class()
        return
    if args.class_smoke:
        class_smoke(args.class_smoke)
        return
    assert args.cell, "--cell или --unit-class"
    cell = args.cell
    assert cell.count("|") == 3, "cell: BRANCH|MODE|HIST|rep"
    rec = run_cell(cell)
    out = os.path.join(DIR, "EP2_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved %s; steps=%d; trigger=%s; class=%s; audit=%s"
          % (out, len(rec["steps"]),
             rec["trigger"]["at"] if rec["trigger"] else None,
             rec["trigger"]["class_actual"] if rec["trigger"] else None,
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"


if __name__ == "__main__":
    main()
