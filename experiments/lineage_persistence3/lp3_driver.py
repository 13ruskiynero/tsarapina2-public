# -*- coding: utf-8 -*-
"""LP-3 driver (FROZEN 07.09.2026; measurement-only; v0.6 НЕ меняется).

Дизайн: LINEAGE_PERSISTENCE3_DESIGN.md (FROZEN); протокол: PROTOCOL.md.
Механика LP-2: failure-observation recorder (a) V-change / (b)
outcome_disagreement с source="verified failure" (все ветки); ветки:
F0 — v0.6-семантика; F1 — field-bearing pivot + перенос failure-obs
в obs (никогда в aw); F2 — failure-excluded lineage. F1 — выбранная
архитектурная семантика (объект контроля); F0/F2 — контрасты.

Последовательности:
  P1: w1, noise2, wY, noise, wY        (K1..K3)
  P2: w1, noise2, wY, noise, wY, noise, wY   (K1..K4)
Грид: 3 ветки x 2 последовательности x r1/r2 = 12 прогонов.
Регистрация: снапшоты после каждого шага; prior/pivot на success-
шагах; пробы w1/wY/noise/noise2 после финального шага.
"""
import argparse
import glob
import hashlib
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
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = None

SEQUENCES = {
    "P1": ["w1", "noise2", "wY", "noise", "wY"],
    "P2": ["w1", "noise2", "wY", "noise", "wY", "noise", "wY"],
}
PROBE_WORLDS = ["w1", "wY", "noise", "noise2"]

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
    "noise": (["a", "n"], "absent", "1"),
    "noise2": (["a", "n"], "absent", "2"),
}

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

_OUTCOME_RE = re.compile(r"outcome=(\w+)")

_ORIG_PRIOR_LINEAGE = update._prior_lineage
_ORIG_ACQUIRE = update._acquire
_ORIG_CREATE = knowledge.create


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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


def _outcome_of(v):
    m = _OUTCOME_RE.search(v.get("context") or "")
    return m.group(1) if m else None


def _sig(o):
    return json.dumps({k: v for k, v in sorted(o.items())
                       if k != "episode_refs"},
                      ensure_ascii=False, sort_keys=True)


# --- recorder (база записи; все ветки) ---------------------------------
def _failure_observations(store, exp_refs, outcome):
    if not exp_refs:
        return None
    exp = store.read_experience(exp_refs[0])
    if exp is None:
        return None
    sym = update._lineage_sym(exp)
    e_val = update._ctx_of_exp(store, exp)
    cmd = update._cmd_of(store, exp)
    if e_val is None:
        return None
    v_now = update._envver_of(exp)
    if v_now is None:
        return None
    rows = _ORIG_PRIOR_LINEAGE(store, sym, e_val, cmd)
    succ = [r for r in rows if (_outcome_of(r) or "") == "success"]
    seen = set()
    for r in succ:
        aw = r.get("applicable_when") or {}
        if "V" in aw:
            seen.add(str(aw["V"]))
        for o in (r.get("applicability_observations") or []):
            if o.get("signal") == "V":
                seen.update(str(x) for x in (o.get("values_seen") or []))
    if seen and v_now not in seen:
        return [{"signal": "V",
                 "values_seen": sorted(seen | {v_now}),
                 "relation": "disagreement",
                 "source": "verified failure",
                 "episode_refs": list(exp_refs)}]
    fb = [r for r in succ if r.get("applicable_when") is not None]
    if fb:
        aw = fb[-1].get("applicable_when") or {}
        vec = {"E": e_val}
        if v_now is not None:
            vec["V"] = v_now
        if aw and all(vec.get(k) == v for k, v in aw.items()):
            return [{"relation": "outcome_disagreement",
                     "condition": dict(aw),
                     "verdict": outcome or "",
                     "source": "verified failure",
                     "episode_refs": list(exp_refs)}]
    return None


def _recorder_create(store, content, source, observer, experience_refs,
                     context=None, confidence=None, note=None,
                     transformations=None, applicable_when=None,
                     applicability_observations=None):
    outcome = None
    m = _OUTCOME_RE.search(context or "")
    if m:
        outcome = m.group(1)
    if (outcome is not None and outcome != "success"
            and not applicability_observations):
        fobs = _failure_observations(store, list(experience_refs or []),
                                     outcome)
        if fobs:
            applicability_observations = fobs
    return _ORIG_CREATE(store, content, source, observer, experience_refs,
                        context=context, confidence=confidence, note=note,
                        transformations=transformations,
                        applicable_when=applicable_when,
                        applicability_observations=applicability_observations)


# --- ветки --------------------------------------------------------------
def _f2_prior_lineage(store, sym, e_val, cmd):
    rows = _ORIG_PRIOR_LINEAGE(store, sym, e_val, cmd)
    return [r for r in rows if (_outcome_of(r) or "") == "success"]


def _f1_acquire(store, exp, cmd):
    """F1: pivot = последний field-bearing; failure-obs членов линии
    переносятся в obs нового знания (никогда в aw)."""
    sym = update._lineage_sym(exp)
    e_val = update._ctx_of_exp(store, exp)
    if e_val is None:
        return None, None

    def fb_only(s2, sy, e, c):
        return [r for r in _ORIG_PRIOR_LINEAGE(s2, sy, e, c)
                if r.get("applicable_when") is not None]
    prev = update._prior_lineage
    update._prior_lineage = fb_only
    try:
        aw, aobs = _ORIG_ACQUIRE(store, exp, cmd)
    finally:
        update._prior_lineage = prev
    if aw is None and aobs is None:
        return None, None
    rows = _ORIG_PRIOR_LINEAGE(store, sym, e_val, cmd)
    fail_rows = [r for r in rows if (_outcome_of(r) or "") != "success"]
    existing = [_sig(o) for o in (aobs or [])]
    for r in fail_rows:
        for o in (r.get("applicability_observations") or []):
            if o.get("signal") is not None and o["signal"] in (aw or {}):
                continue
            s = _sig(o)
            if s in existing:
                for eo in (aobs or []):
                    if _sig(eo) == s:
                        eo["episode_refs"] = sorted(
                            set(eo.get("episode_refs", []))
                            | set(o.get("episode_refs", [])))
                continue
            if aobs is None:
                aobs = []
            aobs.append(dict(o))
            existing.append(s)
    if aobs is not None and not aobs:
        aobs = None
    return aw, aobs


def _install(branch):
    knowledge.create = _recorder_create
    if branch == "F2":
        update._prior_lineage = _f2_prior_lineage
    elif branch == "F1":
        update._acquire = _f1_acquire


def env_set(world):
    flags, e, v = WORLD_DEF[world]
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.envver", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(v)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(name):
    d = os.path.join(DIR, "data_lp3_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def _capture_prior(store, exp_full, branch):
    sym = update._lineage_sym(exp_full)
    e_val = update._ctx_of_exp(store, exp_full)
    cmd = update._cmd_of(store, exp_full)
    rows = update._prior_lineage(store, sym, e_val, cmd)
    fb = [r for r in rows if r.get("applicable_when") is not None]
    if branch == "F1":
        pivot = fb[-1] if fb else None
    else:
        pivot = rows[-1] if rows else None
    return {"sym": sorted(sym) if hasattr(sym, "__iter__") else sym,
            "ctx": e_val, "cmd": cmd,
            "prior_ids": [r["knowledge_id"] for r in rows],
            "fb_existed": bool(fb),
            "pivot_id": pivot["knowledge_id"] if pivot else None,
            "pivot_has_aw": bool(pivot and pivot.get("applicable_when"))}


def learn(store, world, ep, branch):
    env_set(world)
    problem = "tsasvc.service inactive symptom=a"
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1",
           "action_id": "act_lp3_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": "fix-a",
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "LP-3"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="lp3")
    experience.save(store, exp_full)
    prior_info = None
    if outcome == "success":
        prior_info = _capture_prior(store, exp_full, branch)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"event": "STEP", "ep": ep, "world": world, "outcome": outcome,
            "ok": ok, "prior_info": prior_info,
            "created_knowledge_id": k.get("knowledge_id") if k else None}, k


def snapshot(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        addr = None
        try:
            a = strategy._addr_cmd_of(store, v)
            addr = (sorted(a[0]) if a else [], a[1] if a else None,
                    a[2] if a else None)
        except Exception:
            pass
        rows.append({
            "knowledge_id": v["knowledge_id"],
            "version": v["version"],
            "status": v["status"],
            "created_at": v.get("created_at"),
            "content": v.get("content"),
            "applicable_when": v.get("applicable_when"),
            "applicability_observations": v.get(
                "applicability_observations"),
            "experience_refs": v.get("experience_refs"),
            "lineage": {"sym": addr[0], "ctx": addr[1], "cmd": addr[2]}
            if addr else None,
        })
    rows.sort(key=lambda r: r["knowledge_id"])
    return rows


def probe(store, world):
    env_set(world)
    obs = {"E": polygon_sensor.sensor_envfact()[4],
           "V": polygon_sensor.sensor_envver()[4]}
    problem = "tsasvc.service inactive symptom=a"
    sug = strategy.suggest(store, {"problem": problem}, ctx_now=obs["E"],
                           obs_now=obs, by="lp3")
    return {"world": world, "obs": obs, "strategy_id": sug["strategy_id"],
            "candidate_commands": [a["command"]
                                   for a in sug["candidate_actions"]],
            "knowledge_refs": sug.get("knowledge_refs"),
            "rationale": [r.get("rule") for r in sug["rationale"]]}


def run_sequence(branch, name, rep):
    st = fresh_store("%s_%s_%s" % (branch, name, rep))
    rec = {"branch": branch, "sequence": name, "rep": rep, "steps": []}
    for i, world in enumerate(SEQUENCES[name], start=1):
        step_rec, k = learn(st, world, "%s_%s_%s_m%d" % (branch, name, rep,
                                                         i), branch)
        step_rec["snapshot"] = snapshot(st)
        rec["steps"].append(step_rec)
    rec["probes"] = [probe(st, w) for w in PROBE_WORLDS]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", required=True, choices=["F0", "F1", "F2"])
    args = ap.parse_args()
    branch = args.branch
    global LOG
    LOG = os.path.join(DIR, "LP3_run_%s.log" % branch)
    open(LOG, "w", encoding="utf-8").close()
    _install(branch)
    audit_before = hash_layers()
    print("== LP-3 %s (FROZEN 07.09.2026; measurement-only; v0.6 не "
          "меняется) ==" % branch, flush=True)
    runs = []
    for name in ("P1", "P2"):
        for rep in ("r1", "r2"):
            runs.append(run_sequence(branch, name, rep))
    audit_after = hash_layers()
    same = audit_before == audit_after
    with open(os.path.join(DIR, "LP3_records_%s.json" % branch), "w",
              encoding="utf-8") as f:
        json.dump({"branch": branch, "audit_before": audit_before,
                   "audit_after": audit_after, "runs": runs},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(DIR, "LP3_audit_%s.txt" % branch), "w",
              encoding="utf-8") as f:
        for rel in sorted(set(audit_before) | set(audit_after)):
            f.write("%s before=%s after=%s\n"
                    % (rel, audit_before.get(rel), audit_after.get(rel)))
        f.write("LAYERS_UNCHANGED=%s\n" % same)
    print("saved LP3_records_%s.json (%d прогонов); layers unchanged: %s"
          % (branch, len(runs), same), flush=True)
    assert same, "слои v0.6 изменились во время LP-3 (%s)" % branch


if __name__ == "__main__":
    main()
