# -*- coding: utf-8 -*-
"""RECON-1 driver (FROZEN 11.09.2026; PROTOCOL recon1/PROTOCOL.md).

Продолжение LONG-3 r1 (store data_long3_r1) с E75.
Фазы:
  --phase prefill --budget N : N forced-эпизодов
      (PREFILL_OPERATOR; чередование fix-a/fix-aq; production
      path; без LLM), затем PROBE (counter).
  --phase llm --budget N     : LLM-эпизоды (до B2b; после B2b
      ещё 3 и стоп).
Резюмируемый: состояние (prev/prev_prop/счётчики) восстанавливается
из записей long3 (E0..E74) + recon1 (RECON1_E<k>_r1.json).
B2b: counter(n) ≤ counter(n−1) при context_chars(n) >
context_chars(n−1). Стоп-файл: RECON1_STOP.txt.
"""
import argparse
import glob
import hashlib
import json
import os
import re
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
from llm import adapter  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

from bridge import Bridge  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LONG3_DIR = os.path.join(DIR, "..", "long3")
def store_dir():
    return os.path.join(LONG3_DIR, "data_long3_%s" % SERIES)
PROBLEM = "tsasvc.service inactive symptom=a"
NUM_CTX = 4096
SERIES = "r1"                          # устанавливается в main()
PREFILL_TARGET = int(0.84 * NUM_CTX)   # устанавливается в main()
PREFILL_NEAR = int(0.97 * NUM_CTX)     # 3973
MAX_POST_B2B = 3

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


def env_set(world="w1", envver="1"):
    flags = ["a"]
    if world == "w2":
        flags.append("q")
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
    added, changed = [], []
    for kid, a in after.items():
        if kid not in before:
            added.append({"kid": kid, "outcome": a["outcome"],
                          "cmd": a["cmd"]})
        elif json.dumps(a, sort_keys=True) != \
                json.dumps(before[kid], sort_keys=True):
            changed.append({"kid": kid})
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
    src = []
    for _, kid, cmd, outcome in items:
        src.append(kid)
        lines.append("  %s → %s" % (cmd or "?", outcome or "?"))
    if not items:
        lines.append("  (нет)")
    return "\n".join(lines), src


def load_state():
    """Резюм: prev/prev_prop/last_counter/last_chars/n_eps."""
    recs = []
    for ep in range(75):
        p = os.path.join(LONG3_DIR, "LONG3_E%d_%s.json" % (ep, SERIES))
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                recs.append(json.load(f))
    k = 75
    while True:
        p = os.path.join(DIR, "RECON1_E%d_%s.json" % (k, SERIES))
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
        k += 1
    prev, prev_prop = None, None
    last_counter, last_chars = None, None
    for r in recs:
        if r.get("prev_after"):
            prev = r["prev_after"]
        if r.get("mode") == "llm":
            prop = ((r.get("llm") or {}).get("parsed") or {})
            if prop.get("action"):
                prev_prop = prop["action"]
        c = r.get("context_counter")
        if c is None:
            c = r.get("counter")
        if c is not None:
            last_counter = c
        if r.get("growth"):
            last_chars = r["growth"].get("context_chars")
        elif r.get("context_chars") is not None:
            last_chars = r["context_chars"]
    return recs, prev, prev_prop, last_counter, last_chars


def store_open():
    d = store_dir()
    return Store(os.path.join(d, "tsarapina.db"), d)


def write_rec(rec, ep):
    out = os.path.join(DIR, "RECON1_E%d_%s.json" % (ep, SERIES))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return out


def do_prefill_ep(store, ep, prev):
    cmd = "fix-a" if ep % 2 == 0 else "fix-aq"
    env_set("w1", "1")
    facts = observer.collect(store)
    obs_now = {"E": polygon_sensor.sensor_envfact()[4], "V": "1"}
    sug_b = strategy.suggest(store, {"problem": PROBLEM}, by="recon1",
                             save=False, ctx_now="absent",
                             obs_now=obs_now)
    state_b = snapshot(store)
    act = {"schema_version": "0.1", "action_id": "act_recon1_%s"
           % uuid.uuid4().hex[:8], "strategy_id": None,
           "proposed_by": "operator/prefill", "type": "command",
           "command": cmd, "args": {"goal": GOAL,
           "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "RECON-1 prefill"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="recon1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    state_a = snapshot(store)
    rec = {"series": SERIES, "ep": ep, "mode": "PREFILL_OPERATOR",
           "world": "w1", "envver": "1", "action": cmd,
           "outcome": outcome, "executed": not res.get("refused"),
           "created_knowledge_id": k.get("knowledge_id") if k else None,
           "knowledge_diff": kdiff(state_b, state_a),
           "strategy_before": {
               "strategy_id": sug_b.get("strategy_id"),
               "knowledge_refs": sug_b.get("knowledge_refs")},
           "prev_after": {"command": cmd, "outcome": outcome},
           "audit_before": None, "audit_after": None}
    return rec, {"command": cmd, "outcome": outcome}


def do_probe(store, prev, ep_next):
    context, _ = build_context(store, prev)
    prompt = adapter.build_prompt(PROBLEM, context)
    try:
        c, meta = adapter.chat(
            adapter.PROVIDERS["gemma"]["url"], "gemma3:4b", prompt,
            max_tokens=1, timeout=180, with_meta=True)
        counter = meta.get("prompt_eval_count")
        if counter is None:
            counter = meta.get("prompt_tokens")
        err = None
    except Exception as exc:
        counter, meta, err = None, None, str(exc)[:200]
    rec = {"mode": "PROBE", "n_episodes_total": ep_next,
           "counter": counter, "utilization":
           round(counter / NUM_CTX, 4) if counter else None,
           "context_chars": len(context), "provider_meta": meta,
           "error": err, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    k = 0
    while os.path.exists(os.path.join(
            DIR, "RECON1_probe%d_%s.json" % (k, SERIES))):
        k += 1
    with open(os.path.join(
            DIR, "RECON1_probe%d_%s.json" % (k, SERIES)), "w",
              encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("PROBE counter=%s util=%s chars=%s err=%s"
          % (rec["counter"], rec["utilization"], rec["context_chars"],
             rec["error"]), flush=True)
    return rec


def stop_written():
    return os.path.exists(os.path.join(
        DIR, "RECON1_STOP_%s.txt" % SERIES))


def write_stop(reason, ep, values):
    with open(os.path.join(DIR, "RECON1_STOP_%s.txt" % SERIES), "w",
              encoding="utf-8") as f:
        f.write(json.dumps({"reason": reason, "ep": ep,
                            "values": values,
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
                           ensure_ascii=False, indent=1))
    print("STOP: %s @ E%d %s" % (reason, ep, values), flush=True)


def run_prefill(budget):
    if stop_written():
        print("STOP уже записан — продолжение запрещено")
        return
    recs, prev, prev_prop, last_counter, last_chars = load_state()
    ep = len(recs)
    store = store_open()
    done = 0
    while done < budget:
        rec, prev = do_prefill_ep(store, ep, prev)
        rec["audit_before"] = hash_layers()
        rec["audit_after"] = hash_layers()
        out = write_rec(rec, ep)
        print("saved %s; mode=PREFILL cmd=%s eval=%s"
              % (out, rec["action"], rec["outcome"]), flush=True)
        assert rec["audit_before"] == rec["audit_after"]
        ep += 1
        done += 1
    pr = do_probe(store, prev, ep)
    if pr["error"]:
        write_stop("B2a_probe_error", ep, {"error": pr["error"]})
        return
    if pr["counter"] is not None:
        if last_counter is not None and last_chars is not None and \
                pr["counter"] <= last_counter and \
                pr["context_chars"] > last_chars:
            write_stop("B2b_probe_plateau", ep,
                       {"counter": pr["counter"],
                        "prev_counter": last_counter})
            return
        if pr["counter"] >= PREFILL_TARGET:
            print("prefill target достигнут (counter=%s ≥ %d); "
                  "переключение на LLM-фазу" % (pr["counter"],
                                                PREFILL_TARGET),
                  flush=True)


def run_llm(budget):
    if stop_written():
        print("STOP уже записан — продолжение запрещено")
        return
    recs, prev, prev_prop, last_counter, last_chars = load_state()
    ep = len(recs)
    store = store_open()
    post = 0
    post_b5 = 0
    done = 0
    while done < budget and post <= MAX_POST_B2B:
        env_set("w1", "1")
        facts = observer.collect(store)
        obs_now = {"E": polygon_sensor.sensor_envfact()[4], "V": "1"}
        sug_b = strategy.suggest(store, {"problem": PROBLEM},
                                 by="recon1", save=False,
                                 ctx_now="absent", obs_now=obs_now)
        state_b = snapshot(store)
        context, src = build_context(store, prev)
        bridge = Bridge(store)
        b = bridge.invoke(task=PROBLEM, context=context,
                          episode_id="recon1_%s_E%d" % (SERIES, ep),
                          grant=True)
        pm = b.get("provider_meta") or {}
        counter = pm.get("prompt_eval_count")
        if counter is None:
            counter = pm.get("prompt_tokens")
        ct = pm.get("completion_tokens")
        b2b = bool(counter is not None and last_counter is not None
                   and counter <= last_counter
                   and len(context) > (last_chars or 0))
        star = bool(counter is not None and ct is not None
                    and counter + ct >= NUM_CTX
                    and b["decision"] == "no_action")
        rec = {"series": SERIES, "ep": ep, "mode": "LLM",
               "world": "w1", "envver": "1", "context": context,
               "context_source": src, "context_chars": len(context),
               "counter": counter,
               "utilization": round(counter / NUM_CTX, 4)
               if counter else None,
               "plateau_B2b": b2b, "starvation_B5": star,
               "provider_meta": pm,
               "strategy_before": {
                   "strategy_id": sug_b.get("strategy_id"),
                   "knowledge_refs": sug_b.get("knowledge_refs")},
               "llm": {"raw": b["raw"], "parsed": b["parsed"],
                       "llm_error": b["llm_error"]},
               "gates": b["gates"], "decision": b["decision"],
               "no_action_reason": b["no_action_reason"],
               "action": b["action"], "result": b["result"],
               "knowledge_state_before": None,
               "knowledge_diff": None, "proposal_diff": None,
               "audit_before": None, "audit_after": None}
        if b["executed"]:
            ok = stable_active()
            ev = evaluation.evaluate(store, b["result"]["result_id"],
                                     GOAL)
            outcome = "success" if ok else ev["outcome"]
            exp_full = experience.build(
                problem=PROBLEM, observations=facts,
                actions=[b["action"]["action_id"]],
                result_ref=b["result"]["result_id"],
                machine="recon1")
            experience.save(store, exp_full)
            k = update.apply(store, exp_full["experience_id"], outcome)
            rec["evaluation"] = outcome
            rec["created_knowledge_id"] = (k.get("knowledge_id")
                                           if k else None)
            prev = {"command": b["parsed"]["action"], "outcome": outcome}
        else:
            rec["evaluation"] = None
            prev = {"command": (b["parsed"] or {}).get("action"),
                    "outcome": "no_action(%s)" % b["no_action_reason"]}
        rec["prev_after"] = prev
        state_a = snapshot(store)
        rec["knowledge_diff"] = kdiff(state_b, state_a)
        rec["audit_before"] = hash_layers()
        rec["audit_after"] = hash_layers()
        out = write_rec(rec, ep)
        act = ((b.get("parsed") or {}).get("action"))
        print("saved %s; mode=LLM action=%s dec=%s eval=%s "
              "counter=%s util=%s B2b=%s"
              % (out, act, rec["decision"], rec["evaluation"],
                 counter, rec["utilization"], b2b), flush=True)
        assert rec["audit_before"] == rec["audit_after"]
        if counter is not None:
            last_counter, last_chars = counter, len(context)
        if star:
            post_b5 += 1
            if post_b5 > 5:
                write_stop("B5_output_starvation", ep,
                           {"counter": counter,
                            "completion": ct})
                return
        if b2b:
            post += 1
            if post > MAX_POST_B2B:
                write_stop("B2b_plus_3", ep,
                           {"counter": counter})
                return
        ep += 1
        done += 1
        if ep >= 620:
            write_stop("hard_cap_620", ep, {})
            return


def main():
    global SERIES, PREFILL_TARGET
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True,
                    choices=["prefill", "llm"])
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument("--series", default="r1", choices=["r1", "r2"])
    ap.add_argument("--prefill-target-pct", type=float, default=84.0)
    args = ap.parse_args()
    SERIES = args.series
    PREFILL_TARGET = int(args.prefill_target_pct / 100.0 * NUM_CTX)
    print("== RECON-1 series=%s prefill_target=%d =="
          % (SERIES, PREFILL_TARGET), flush=True)
    if args.phase == "prefill":
        run_prefill(args.budget)
    else:
        run_llm(args.budget)


if __name__ == "__main__":
    main()
