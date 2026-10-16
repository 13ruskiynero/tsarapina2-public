# -*- coding: utf-8 -*-
"""AA-1 driver (FROZEN 10.09.2026; measurement-only; v0.6.x не меняется).

Дизайн: APPLICABILITY_ADDRESSING1_DESIGN.md (FROZEN); протокол:
applicability_addressing1/PROTOCOL.md (FROZEN).

Ветки: A0 — live strategy.py; A1 — strategy_aa.py (no-failure-action:
failure-знания исключены из S2-пула ДО matching; пусто → S3).
Режимы: B | R@E4 | S@E4 (R/S — simulated, как EP-1: R = исключение K
из prior_lineage-чтений и suggest; S = только из suggest; K =
последний verified-success член L; постоянно в горизонте).
Истории: N1D, NaD, NpD, N1V, SV, SD, SM, NSD, E6S (полигон EP-1).

Клетка: python3 aa1_driver.py --cell "A0|B|N1D|r1"
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

W1 = ("w1", None)
W2 = ("w2", None)
NOISE = ("w1", "n")

HISTORIES = {
    "N1D": [("f", NOISE, "1"), ("s", W1, "1"), ("s", W1, "1")],
    "NaD": [("f", NOISE, "1"), ("s", W1, "1"), ("f", NOISE, "1"),
            ("s", W1, "1"), ("f", NOISE, "1"), ("s", W1, "1")],
    "NpD": [("f", NOISE, "1"), ("f", NOISE, "1"), ("f", NOISE, "1"),
            ("s", W1, "1")],
    "N1V": [("f", NOISE, "2"), ("s", W1, "1"), ("s", W1, "1")],
    "SV": [("f", W2, "2"), ("f", W2, "2"), ("f", W2, "2")],
    "SD": [("f", W2, "1"), ("f", W2, "1"), ("f", W2, "1")],
    "SM": [("f", W2, "1"), ("f", W2, "2"), ("f", W2, "1")],
    "NSD": [("f", NOISE, "1"), ("s", W1, "1"), ("f", W2, "1"),
            ("f", W2, "1")],
    "E6S": [("f", W2, "1"), ("f", W2, "1"), ("f", W2, "1")],
}
E6_HISTS = ("E6S",)

MODES = ("B", "R@E4", "S@E4")

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


def load_strategy(branch):
    if branch == "A0":
        from strategy import strategy as st
        return st
    spec = importlib.util.spec_from_file_location(
        "strategy_aa_mod", os.path.join(DIR, "strategy_aa.py"))
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
    d = os.path.join(DIR, "data_aa1_%s" % cell)
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
                "kinds": obs_kinds(v), "gen": v.get("lineage_generation"),
            })
    members.sort(key=lambda m: (m["created_at"], m["kid"]))
    return members


def detect_e4(members):
    """E4: последние 2 члена L — failure с (b)-записями."""
    if len(members) < 2:
        return False
    a, b = members[-2], members[-1]
    if a["outcome"] == "success" or b["outcome"] == "success":
        return False
    return ("b" in b["kinds"] and "b" in a["kinds"])


def _install_retract(kid):
    """R: исключить kid из prior_lineage-чтений (simulated)."""
    orig = _ORIG_PRIOR_LINEAGE

    def wrapper(store, sym, e_val, cmd):
        return [r for r in orig(store, sym, e_val, cmd)
                if r.get("knowledge_id") != kid]
    update._prior_lineage = wrapper


def _do_action(store, cmd, ep, kind):
    facts = observer.collect(store)
    act = {"schema_version": "0.1",
           "action_id": "act_aa1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "AA-1-%s" % kind}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="aa1")
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
    sug = st.suggest(store, {"problem": PROBLEM}, by="aa1",
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
    assert branch in ("A0", "A1") and mode in MODES, cell
    st = load_strategy(branch)
    store = fresh_store(cell)
    rec = {"cell": cell, "branch": branch, "mode": mode, "history": hist,
           "rep": rep, "learn": [], "steps": [], "trigger": None,
           "intervention": None, "checks": [], "line_trace": [],
           "audit_before": hash_layers(), "final_snapshot": None}
    with open(os.path.join(DIR, "strategy_aa.py"), "rb") as f:
        rec["branch_module_sha"] = hashlib.sha256(f.read()).hexdigest()[:16]

    if hist in E6_HISTS:
        learn_episode(store, "w1", "1", "fix-a", 0)
        learn_episode(store, "w1", "2", "fix-a", 0)
        rec["learn"] = [{"cmd": "fix-a", "envver": "1"},
                        {"cmd": "fix-a", "envver": "2"}]
    else:
        learn_episode(store, "w1", "1", "fix-a", 0)
        rec["learn"] = [{"cmd": "fix-a", "envver": "1"}]

    state = {"exclude_kid": None, "intervened": False}
    for i, (aim, (world, noise), envver) in enumerate(
            [tuple(s) for s in HISTORIES[hist]], start=1):
        if mode != "B" and not state["intervened"]:
            mem = line_members(store, st)
            if detect_e4(mem):
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                state["intervened"] = True
                state["exclude_kid"] = kid
                right = "R" if mode.startswith("R") else "S"
                if right == "R" and kid:
                    _install_retract(kid)
                rec["trigger"] = {"event": "E4", "step": i - 1,
                                  "at": "before-step-%d" % i}
                rec["intervention"] = {"right": right, "kid": kid,
                                       "at": "before-step-%d" % i}
        step = check_episode(store, st, world, noise, envver, i, state)
        rec["steps"].append(step)
        rec["line_trace"].append(
            [{k: m[k] for k in ("kid", "outcome", "aw", "kinds")}
             for m in line_members(store, st)])
        if (rec["intervention"] and rec["intervention"].get("at")
                == "before-step-%d" % i):
            sug = st.suggest(store, {"problem": PROBLEM}, by="aa1-chk",
                             save=False, ctx_now="absent",
                             obs_now={"E": "absent", "V": envver})
            rec["checks"].append({
                "step": i, "granted_excluded": step.get("excluded") is True,
                "selected_ref": (sug.get("knowledge_refs") or [None])[0],
                "exclude_kid": rec["intervention"].get("kid")})
    rec["final_snapshot"] = snapshot_all(store)
    rec["audit_after"] = hash_layers()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    cell = args.cell
    assert cell.count("|") == 3, "cell: BRANCH|MODE|HIST|rep"
    rec = run_cell(cell)
    out = os.path.join(DIR, "AA1_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved %s; steps=%d; trigger=%s; intervention=%s; audit=%s"
          % (out, len(rec["steps"]), rec["trigger"],
             rec["intervention"],
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"


if __name__ == "__main__":
    main()
