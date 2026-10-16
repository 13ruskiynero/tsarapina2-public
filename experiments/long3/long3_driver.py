# -*- coding: utf-8 -*-
"""LONG-3 / CONTEXT-THRESHOLD-1 driver (FROZEN 11.09.2026).

Продолжающаяся серия r1/r2; чекпоинты N=12/20/30/50/75; стоп по
первому mechanical boundary (B1/B2a/B2b/B3/B4; правила —
PROTOCOL §3). Резюмируемый запуск: --series r1 --upto 12|20|30|
50|75. Записи: LONG3_E<k>_<series>.json; при стопе —
LONG3_BOUNDARY_<series>.json. Гейт: при --upto>12 требуется
LONG3_CHECKPOINT12_<series>.json (создаёт long3_analyze
--checkpoint12).
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

LAYER_FILES = [
    "strategy/strategy.py", "strategy/exclusion.py",
    "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py", "llm/adapter.py",
]
_OUTCOME_RE = re.compile(r"outcome=(\w+)")


def ep_env(e):
    """Среды: E0 seed; цикл (4×w1, 3×noise, 4×w1) с E1."""
    if e == 0:
        return ("w1", None)
    k = (e - 1) % 11
    if k < 4:
        return ("w1", None)
    if k < 7:
        return ("w1", "n")
    return ("w1", None)


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
    d = os.path.join(DIR, "data_long3_%s" % series)
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
    added, changed, removed = [], [], []
    for kid, a in after.items():
        b = before.get(kid)
        if b is None:
            added.append({"kid": kid, "outcome": a["outcome"],
                          "aw": a["aw"], "obs": a["obs"],
                          "exp": a["exp"], "gen": a["gen"],
                          "cmd": a["cmd"], "syms": a["syms"]})
        elif json.dumps(a, sort_keys=True) != \
                json.dumps(b, sort_keys=True):
            changed.append({"kid": kid,
                            "fields": [k for k in a
                                       if a[k] != b.get(k)]})
    removed = [k for k in before if k not in after]
    return {"added": added, "changed": changed, "removed": removed}


def build_context(store, prev):
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
    src, cmds = [], []
    for _, kid, cmd, outcome in items:
        src.append(kid)
        cmds.append(cmd)
        lines.append("  %s → %s" % (cmd or "?", outcome or "?"))
    if not items:
        lines.append("  (нет)")
    text = "\n".join(lines)
    growth = {"context_source_ids": src,
              "context_source_n": len(set(src)),
              "context_chars": len(text),
              "context_lines": len(text.split("\n")),
              "unique_commands": len(set(cmds)),
              "dup_lines": len(cmds) - len(set(cmds)),
              "stored_knowledge_n": None,
              "transported_knowledge_n": len(set(src))}
    return text, src, growth


def do_seed(store, ep_id):
    env_set("w1", None)
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1", "action_id": "act_long3_%s"
           % uuid.uuid4().hex[:8], "strategy_id": None,
           "proposed_by": "operator/seed", "type": "command",
           "command": "fix-a", "args": {"goal": GOAL,
           "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "LONG-3 seed"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="long3")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"action": "fix-a", "outcome": outcome,
            "result_id": res["result_id"],
            "experience_id": exp_full["experience_id"],
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def boundary_path(series):
    return os.path.join(DIR, "LONG3_BOUNDARY_%s.json" % series)


def write_boundary(series, btype, ep, values):
    with open(boundary_path(series), "w", encoding="utf-8") as f:
        json.dump({"series": series, "type": btype, "ep": ep,
                   "values": values,
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
                  f, ensure_ascii=False, indent=1)
    print("BOUNDARY %s: %s @ E%d %s" % (series, btype, ep, values),
          flush=True)


def load_series(series):
    """Резюм: собрать prev/prev_proposal/first_seen из записей."""
    recs = []
    for ep in range(0, 200):
        p = os.path.join(DIR, "LONG3_E%d_%s.json" % (ep, series))
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    first_seen = {}
    prev = None
    prev_prop = None
    prev_counter = None
    for r in recs:
        for a in r["knowledge_diff"]["added"]:
            first_seen[a["kid"]] = r["ep"]
        if r.get("prev_after"):
            prev = r["prev_after"]
        if r["mode"] == "llm":
            prop = ((r.get("llm") or {}).get("parsed") or {})
            prev_prop = prop.get("action")
            if r.get("context_counter") is not None:
                prev_counter = r["context_counter"]
    return recs, prev, prev_prop, prev_counter, first_seen


def run_series(series, upto):
    bpath = boundary_path(series)
    if os.path.exists(bpath):
        with open(bpath, encoding="utf-8") as f:
            b = json.load(f)
        print("уже есть boundary: %s @ E%d — продолжение запрещено"
              % (b["type"], b["ep"]))
        return
    if upto > 12:
        cp = os.path.join(DIR, "LONG3_CHECKPOINT12_%s.json" % series)
        if not os.path.exists(cp):
            print("GATE: нет %s — checkpoint@12 не выполнен; "
                  "запуск N>12 запрещён" % cp)
            return
    recs, prev, prev_prop, prev_counter, first_seen = load_series(series)
    start = len(recs)
    if start == 0:
        store = fresh_store(series)
    else:
        d = os.path.join(DIR, "data_long3_%s" % series)
        store = Store(os.path.join(d, "tsarapina.db"), d)
    print("== LONG-3 %s: эпизоды E%d..E%d ==" % (series, start, upto - 1),
          flush=True)
    for ep in range(start, upto):
        world, noise = ep_env(ep)
        audit_before = hash_layers()
        ep_id = "long3_%s_E%d" % (series, ep)
        btype = None
        bvalues = {}
        rec = {"series": series, "ep": ep, "episode_id": ep_id,
               "world": world, "noise": noise, "mode":
               "seed" if ep == 0 else "llm",
               "audit_before": audit_before,
               "knowledge_state_before": None, "context": None,
               "context_source": [], "growth": None,
               "provider_meta": None, "context_counter": None,
               "b_checks": {"B1": None, "B2a": None, "B2b": None,
                            "B3": None, "B4": None},
               "llm": None, "gates": [], "decision": None,
               "no_action_reason": None, "action": None,
               "result": None, "seed": None, "evaluation": None,
               "experience_id": None, "created_knowledge_id": None,
               "knowledge_diff": None, "knowledge_state_after": None,
               "strategy_before": None, "strategy_after": None,
               "proposal_diff": None, "prev_after": None}
        try:
            env_set(world, noise)
            facts = observer.collect(store)
            obs_now = {"E": polygon_sensor.sensor_envfact()[4],
                       "V": polygon_sensor.sensor_envver()[4]}
            sug_b = strategy.suggest(store, {"problem": PROBLEM},
                                     by="long3", save=False,
                                     ctx_now="absent", obs_now=obs_now)
            rec["strategy_before"] = {
                "strategy_id": sug_b.get("strategy_id"),
                "knowledge_refs": sug_b.get("knowledge_refs")}
            state_b = snapshot(store)
            rec["knowledge_state_before"] = state_b
            if ep == 0:
                seed = do_seed(store, ep_id)
                rec["seed"] = seed
                rec["evaluation"] = seed["outcome"]
                rec["experience_id"] = seed["experience_id"]
                rec["created_knowledge_id"] = seed["created_knowledge_id"]
                rec["decision"] = "executed"
                prev = {"command": "fix-a", "outcome": seed["outcome"]}
            else:
                context, src, growth = build_context(store, prev)
                growth["stored_knowledge_n"] = len(state_b)
                growth["K_store_minus_K_context"] = (
                    growth["stored_knowledge_n"]
                    - growth["transported_knowledge_n"])
                rec["context"] = context
                rec["context_source"] = src
                rec["growth"] = growth
                # B1
                rec["b_checks"]["B1"] = \
                    growth["K_store_minus_K_context"] > 0
                # B3
                b3_bad = [k for k in src if first_seen.get(k, 10**9) >= ep]
                rec["b_checks"]["B3"] = bool(b3_bad)
                bridge = Bridge(store)
                b = bridge.invoke(task=PROBLEM, context=context,
                                  episode_id=ep_id, grant=True)
                rec["llm"] = {"provider": b["provider"],
                              "route": b["llm_meta"]["route"],
                              "raw": b["raw"], "parsed": b["parsed"],
                              "llm_error": b["llm_error"]}
                rec["provider_meta"] = b.get("provider_meta")
                pm = b.get("provider_meta") or {}
                counter = pm.get("prompt_eval_count")
                if counter is None:
                    counter = pm.get("prompt_tokens")
                rec["context_counter"] = counter
                rec["gates"] = b["gates"]
                rec["decision"] = b["decision"]
                rec["no_action_reason"] = b["no_action_reason"]
                rec["action"] = b["action"]
                rec["result"] = b["result"]
                # B2a / B2b
                rec["b_checks"]["B2a"] = bool(b["llm_error"])
                if (counter is not None and prev_counter is not None
                        and counter <= prev_counter
                        and growth["context_chars"] > 0):
                    rec["b_checks"]["B2b"] = True
                elif counter is None:
                    rec["b_checks"]["B2b"] = None
                else:
                    rec["b_checks"]["B2b"] = False
                if counter is not None:
                    prev_counter = counter
                if b["executed"]:
                    ok = stable_active()
                    ev = evaluation.evaluate(
                        store, b["result"]["result_id"], GOAL)
                    outcome = "success" if ok else ev["outcome"]
                    exp_full = experience.build(
                        problem=PROBLEM, observations=facts,
                        actions=[b["action"]["action_id"]],
                        result_ref=b["result"]["result_id"],
                        machine="long3")
                    experience.save(store, exp_full)
                    k = update.apply(store, exp_full["experience_id"],
                                     outcome)
                    rec["evaluation"] = outcome
                    rec["experience_id"] = exp_full["experience_id"]
                    rec["created_knowledge_id"] = (
                        k.get("knowledge_id") if k else None)
                    prev = {"command": b["parsed"]["action"],
                            "outcome": outcome}
                else:
                    prev = {"command": (b["parsed"] or {}).get("action"),
                            "outcome": "no_action(%s)"
                            % b["no_action_reason"]}
            state_a = snapshot(store)
            rec["knowledge_state_after"] = state_a
            rec["knowledge_diff"] = kdiff(state_b, state_a)
            for a in rec["knowledge_diff"]["added"]:
                first_seen.setdefault(a["kid"], ep)
            sug_a = strategy.suggest(store, {"problem": PROBLEM},
                                     by="long3", save=False,
                                     ctx_now="absent", obs_now=obs_now)
            rec["strategy_after"] = {
                "strategy_id": sug_a.get("strategy_id"),
                "knowledge_refs": sug_a.get("knowledge_refs")}
            cur = ((rec["llm"] or {}).get("parsed") or {}).get("action")
            if rec["mode"] == "llm" and prev_prop is not None:
                rec["proposal_diff"] = {"changed": cur != prev_prop,
                                        "prev": prev_prop, "cur": cur}
            if rec["mode"] == "llm":
                prev_prop = cur
            rec["prev_after"] = prev
            rec["audit_after"] = hash_layers()
            # B4 (частично): audit mismatch
            if rec["audit_after"] != rec["audit_before"]:
                rec["b_checks"]["B4"] = True
                btype = "B4"
                bvalues = {"reason": "audit mismatch"}
        except Exception as exc:  # B4: исключение при эпизоде
            rec["b_checks"]["B4"] = True
            btype = "B4"
            bvalues = {"reason": "exception: %s" % str(exc)[:200]}
            rec["audit_after"] = hash_layers()
        # запись эпизода
        out = os.path.join(DIR, "LONG3_E%d_%s.json" % (ep, series))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        bc = rec["b_checks"]
        g = rec["growth"] or {}
        print("saved %s; dec=%s eval=%s csn=%s chars=%s counter=%s "
              "B=%s" % (out, rec["decision"], rec["evaluation"],
                        g.get("context_source_n"),
                        g.get("context_chars"),
                        rec["context_counter"],
                        {k: v for k, v in bc.items()
                         if v}), flush=True)
        # boundary detection (приоритет: B2a > B2b > B1 > B3 > B4)
        if rec["b_checks"].get("B2a"):
            btype, bvalues = "B2a", {"llm_error":
                                     rec["llm"]["llm_error"][:200]}
        elif rec["b_checks"].get("B2b"):
            btype, bvalues = "B2b", {"counter": rec["context_counter"],
                                     "prev_counter": prev_counter}
        elif rec["b_checks"].get("B1"):
            btype, bvalues = "B1", {"K_store_minus_K_context":
                                    g.get("K_store_minus_K_context")}
        elif rec["b_checks"].get("B3"):
            btype, bvalues = "B3", {"offending": b3_bad}
        if btype:
            write_boundary(series, btype, ep, bvalues)
            print("серия остановлена на E%d (%s)" % (ep, btype))
            return
    print("== серия %s завершена до N=%d (boundary не наблюдался) =="
          % (series, upto), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, choices=["r1", "r2"])
    ap.add_argument("--upto", type=int, required=True,
                    choices=[12, 20, 30, 50, 75])
    args = ap.parse_args()
    run_series(args.series, args.upto)


if __name__ == "__main__":
    main()
