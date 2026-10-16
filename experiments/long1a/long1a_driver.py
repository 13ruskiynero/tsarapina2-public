# -*- coding: utf-8 -*-
"""LONG-1A driver (FROZEN 11.09.2026; PROTOCOL long1a/PROTOCOL.md).

Серия r1/r2: E0 seed(w1) | E1 LLM(w1) | E2 LLM(шум) | E3 LLM(шум)
| E4 LLM(w1) | E5 LLM(w1). Контекст расширен (OT-1): все известные
результаты задачи (symptom=a, любая команда). Запуск:
python3 long1a_driver.py --series r1
Записи: LONG1A_E<k>_<series>.json (append-only; серии независимы).
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
sys.path.insert(0, os.path.join(BASE, "experiments",
                               "strategy_llm_action"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

from bridge import Bridge  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"

EPISODES = [
    (0, "seed", "w1", None),
    (1, "llm", "w1", None),
    (2, "llm", "w1", "n"),
    (3, "llm", "w1", "n"),
    (4, "llm", "w1", None),
    (5, "llm", "w1", None),
]

LAYER_FILES = [
    "strategy/strategy.py", "strategy/exclusion.py",
    "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py", "llm/adapter.py",
]
_OUTCOME_RE = re.compile(r"outcome=(\w+)")


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


def env_set(world, noise):
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
        f.write("1")
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(series):
    d = os.path.join(DIR, "data_long1a_%s" % series)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def outcome_of(v):
    m = _OUTCOME_RE.search(v.get("context") or "")
    return m.group(1) if m else None


def obs_kinds(v):
    kinds = []
    for o in v.get("applicability_observations") or []:
        if o.get("source") == "verified failure":
            kinds.append("a" if o.get("signal") else "b")
        else:
            kinds.append("s")
    return kinds


def latest_versions(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    return latest


def snapshot(store):
    rows = {}
    for kid, v in latest_versions(store).items():
        addr = None
        try:
            a = strategy._addr_cmd_of(store, v)
            if a:
                addr = (sorted(a[0]) if hasattr(a[0], "__iter__")
                        else [a[0]], a[1], a[2])
        except Exception:
            pass
        rows[kid] = {"version": v["version"], "status": v["status"],
                     "outcome": outcome_of(v),
                     "aw": v.get("applicable_when"),
                     "obs": obs_kinds(v),
                     "exp": v.get("experience_refs"),
                     "gen": v.get("lineage_generation"),
                     "created_at": v.get("created_at"),
                     "syms": addr[0] if addr else None,
                     "cmd": addr[2] if addr else None}
    return rows


def kdiff(before, after):
    added, changed, retracted, conflicts = [], [], [], []
    for kid, a in after.items():
        b = before.get(kid)
        if b is None:
            added.append({"kid": kid, "outcome": a["outcome"],
                          "aw": a["aw"], "obs": a["obs"],
                          "exp": a["exp"], "gen": a["gen"],
                          "cmd": a["cmd"], "syms": a["syms"]})
            continue
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            changed.append({"kid": kid,
                            "fields": [k for k in a
                                       if a[k] != b.get(k)],
                            "outcome": a["outcome"], "aw": a["aw"],
                            "obs": a["obs"]})
        if a["status"] == "retracted" and b["status"] != "retracted":
            retracted.append(kid)
        if a["status"] == "conflicted" and b["status"] != "conflicted":
            conflicts.append(kid)
    removed = [k for k in before if k not in after]
    return {"added": added, "changed": changed, "retracted": retracted,
            "conflicted": conflicts, "restored": [], "removed": removed}


def build_context(store, prev):
    """OT-1: все известные результаты задачи (symptom=a, любая
    команда). kid/provenance в текст не попадают."""
    lines = ["Текущая задача: tsasvc.service inactive symptom=a"]
    if prev:
        lines.append("Предыдущий эпизод: %s → %s"
                     % (prev.get("command") or "—",
                        prev.get("outcome") or "—"))
    else:
        lines.append("Предыдущий эпизод: —")
    lines.append("Известные результаты (задача symptom=a):")
    items = []
    for kid, v in latest_versions(store).items():
        try:
            a = strategy._addr_cmd_of(store, v)
        except Exception:
            a = None
        if not a:
            continue
        syms = sorted(a[0]) if hasattr(a[0], "__iter__") else [a[0]]
        if ("a" in syms and a[1] == "absent"
                and v.get("status") in ("active", "conflicted")):
            items.append((v.get("created_at") or "", kid, a[2],
                          outcome_of(v)))
    items.sort(key=lambda x: (x[0], x[1]))
    src = []
    for _, kid, cmd, outcome in items:
        src.append(kid)
        lines.append("  %s → %s" % (cmd or "?", outcome or "?"))
    if not items:
        lines.append("  (нет)")
    return "\n".join(lines), src


def do_seed(store, ep_id):
    env_set("w1", None)
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1", "action_id": "act_long1a_%s"
           % uuid.uuid4().hex[:8], "strategy_id": None,
           "proposed_by": "operator/seed", "type": "command",
           "command": "fix-a", "args": {"goal": GOAL,
           "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "LONG-1A seed"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="long1a")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"action": "fix-a", "outcome": outcome,
            "result_id": res["result_id"],
            "refused": res.get("refused"),
            "experience_id": exp_full["experience_id"],
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def run_series(series):
    store = fresh_store(series)
    prev = None
    prev_llm_proposal = None
    for ep, mode, world, noise in EPISODES:
        audit_before = hash_layers()
        ep_id = "long1a_%s_E%d" % (series, ep)
        env_set(world, noise)
        facts = observer.collect(store)
        obs_now = {"E": polygon_sensor.sensor_envfact()[4],
                   "V": polygon_sensor.sensor_envver()[4]}
        sug_b = strategy.suggest(store, {"problem": PROBLEM},
                                 by="long1a", save=False,
                                 ctx_now="absent", obs_now=obs_now)
        state_b = snapshot(store)
        rec = {"series": series, "ep": ep, "mode": mode, "world": world,
               "noise": noise, "episode_id": ep_id,
               "observed": {"facts": len(facts), "obs_now": obs_now},
               "strategy_before": {
                   "strategy_id": sug_b.get("strategy_id"),
                   "knowledge_refs": sug_b.get("knowledge_refs")},
               "knowledge_state_before": state_b,
               "context": None, "context_source": [],
               "llm": None, "gates": [], "decision": None,
               "no_action_reason": None, "action": None, "result": None,
               "seed": None, "evaluation": None,
               "experience_id": None, "created_knowledge_id": None,
               "knowledge_diff": None, "knowledge_state_after": None,
               "strategy_after": None, "proposal_diff": None,
               "audit_before": audit_before}
        if mode == "seed":
            seed = do_seed(store, ep_id)
            rec["seed"] = seed
            rec["evaluation"] = seed["outcome"]
            rec["experience_id"] = seed["experience_id"]
            rec["created_knowledge_id"] = seed["created_knowledge_id"]
            rec["decision"] = "executed"
            prev = {"command": "fix-a", "outcome": seed["outcome"]}
        else:
            context, src = build_context(store, prev)
            rec["context"] = context
            rec["context_source"] = src
            bridge = Bridge(store)
            b = bridge.invoke(task=PROBLEM, context=context,
                              episode_id=ep_id, grant=True)
            rec["llm"] = {"provider": b["provider"],
                          "route": b["llm_meta"]["route"],
                          "raw": b["raw"], "parsed": b["parsed"],
                          "llm_error": b["llm_error"]}
            rec["gates"] = b["gates"]
            rec["decision"] = b["decision"]
            rec["no_action_reason"] = b["no_action_reason"]
            rec["action"] = b["action"]
            rec["result"] = b["result"]
            if b["executed"]:
                ok = stable_active()
                ev = evaluation.evaluate(store, b["result"]["result_id"],
                                         GOAL)
                outcome = "success" if ok else ev["outcome"]
                exp_full = experience.build(
                    problem=PROBLEM, observations=facts,
                    actions=[b["action"]["action_id"]],
                    result_ref=b["result"]["result_id"],
                    machine="long1a")
                experience.save(store, exp_full)
                k = update.apply(store, exp_full["experience_id"],
                                 outcome)
                rec["evaluation"] = outcome
                rec["experience_id"] = exp_full["experience_id"]
                rec["created_knowledge_id"] = (k.get("knowledge_id")
                                               if k else None)
                prev = {"command": b["parsed"]["action"],
                        "outcome": outcome}
            else:
                rec["evaluation"] = None
                prev = {"command": (b["parsed"] or {}).get("action"),
                        "outcome": "no_action(%s)"
                        % b["no_action_reason"]}
        state_a = snapshot(store)
        rec["knowledge_state_after"] = state_a
        rec["knowledge_diff"] = kdiff(state_b, state_a)
        sug_a = strategy.suggest(store, {"problem": PROBLEM},
                                 by="long1a", save=False,
                                 ctx_now="absent", obs_now=obs_now)
        rec["strategy_after"] = {
            "strategy_id": sug_a.get("strategy_id"),
            "knowledge_refs": sug_a.get("knowledge_refs")}
        cur = (rec["llm"] or {}).get("parsed") or {}
        cur_act = cur.get("action")
        if mode == "llm":
            if prev_llm_proposal is None:
                rec["proposal_diff"] = {"changed": None,
                                        "fields_changed": [],
                                        "prev": None, "cur": cur_act}
            else:
                rec["proposal_diff"] = {
                    "changed": cur_act != prev_llm_proposal,
                    "fields_changed": (["action"]
                                       if cur_act != prev_llm_proposal
                                       else []),
                    "prev": prev_llm_proposal, "cur": cur_act}
            prev_llm_proposal = cur_act
        rec["audit_after"] = hash_layers()
        out = os.path.join(DIR, "LONG1A_E%d_%s.json" % (ep, series))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print("saved %s; mode=%s decision=%s eval=%s added=%d "
              "ctx_src=%d audit=%s" % (
                  out, mode, rec["decision"], rec["evaluation"],
                  len(rec["knowledge_diff"]["added"]),
                  len(rec["context_source"]),
                  rec["audit_before"] == rec["audit_after"]),
              flush=True)
        assert rec["audit_before"] == rec["audit_after"], \
            "слои изменились (E%d)" % ep
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, choices=["r1", "r2"])
    args = ap.parse_args()
    run_series(args.series)


if __name__ == "__main__":
    main()
