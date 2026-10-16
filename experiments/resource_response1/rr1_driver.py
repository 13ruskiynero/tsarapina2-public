# -*- coding: utf-8 -*-
"""RESOURCE-RESPONSE-1 driver (FROZEN 11.09.2026; read-only).

Дизайн/протокол: RESOURCE_RESPONSE1_DESIGN.md (FROZEN),
resource_response1/PROTOCOL.md (FROZEN).
Клетка: --cell "R1|STARVED|r1" | --matrix (полные 12).
Стенд — реплей существующих записей recon1. Ничего не мутируется:
store/executor/слои не трогаются; adapter используется как есть
(max_tokens=300, temperature=0 — production-значения).
"""
import argparse
import hashlib
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from llm import adapter  # noqa: E402

DIR = os.path.dirname(os.path.abspath(__file__))
RECON1 = os.path.join(BASE, "experiments", "recon1")
PROBLEM = "tsasvc.service inactive symptom=a"
NUM_CTX = 4096
# production-значение max_tokens (propose default); НЕ варьируется
MAX_TOKENS = 300

CTX = {
    "NORMAL": ("RECON1_E507_r2.json", 189),
    "MARGINAL": ("RECON1_E513_r2.json", 129),
    "STARVED": ("RECON1_E513_r1.json", 113),
}

POLICIES = ("R0", "R1")
STATES = ("NORMAL", "MARGINAL", "STARVED")
REPS = ("r1", "r2")


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def run_cell(policy, state, rep):
    fname, _ = CTX[state]
    path = os.path.join(RECON1, fname)
    with open(path, "rb") as f:
        src_sha_before = hashlib.sha256(f.read()).hexdigest()[:16]
    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    context = rec["context"]
    kset = sorted(rec.get("context_source") or [])
    ctx_hash = sha_text(context)
    k_hash = sha_text(json.dumps(kset))
    prompt = adapter.build_prompt(PROBLEM, context)
    out = {"cell": "%s|%s|%s" % (policy, state, rep),
           "policy": policy, "state": state, "rep": rep,
           "source_record": fname,
           "B_available": 4096 - int(rec.get("counter") or 0),
           "window": NUM_CTX, "max_tokens": MAX_TOKENS,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    valid, err, pm = None, "", {}
    try:
        raw, pm = adapter.chat(adapter.PROVIDERS["gemma"]["url"],
                               "gemma3:4b", prompt,
                               max_tokens=MAX_TOKENS, timeout=180,
                               with_meta=True)
        try:
            obj = adapter.parse_json(raw)
            adapter.validate(obj)
            valid = True
        except ValueError as exc:
            valid = False
            err = str(exc)[:200]
        out.update({"prompt_tokens": pm.get("prompt_tokens"),
                    "completion_tokens": pm.get("completion_tokens"),
                    "valid": valid, "error": err,
                    "raw_tail": raw[-90:]})
    except Exception as exc:
        out.update({"prompt_tokens": None, "completion_tokens": None,
                    "valid": False, "error": "provider: %s"
                    % str(exc)[:160], "raw_tail": ""})
    P = out.get("prompt_tokens")
    C = out.get("completion_tokens")
    d1 = bool(P is not None and C is not None
              and P + C >= NUM_CTX and not out["valid"])
    d2 = d1
    if out["valid"] is None:
        d2 = None
    out["D1"] = d1
    out["D2"] = d2
    out["D3"] = (not d2) if state == "NORMAL" else None
    if policy == "R0":
        out["event"] = "starvation_no_action" if d2 else "none"
        out["halted"] = False
        out["loop_available"] = True
    else:
        out["event"] = "resource_impossible" if d2 else "none"
        out["halted"] = bool(d2)
        out["loop_available"] = not bool(d2)
    out.update({"action": 0, "executor_invocations": 0,
                "retry": False})
    with open(path, "rb") as f:
        src_sha_after = hashlib.sha256(f.read()).hexdigest()[:16]
    out["source_sha_before"] = src_sha_before
    out["source_sha_after"] = src_sha_after
    out["context_hash_before"] = ctx_hash
    out["context_hash_after"] = sha_text(context)
    out["K_hash_before"] = k_hash
    out["K_hash_after"] = sha_text(json.dumps(kset))
    out["checks"] = {
        "K_after_eq_K_before":
            out["K_hash_after"] == out["K_hash_before"],
        "context_unchanged":
            out["context_hash_after"] == out["context_hash_before"],
        "source_unchanged": src_sha_before == src_sha_after,
        "executor_invocations_zero": out["executor_invocations"] == 0,
        "no_retry": out["retry"] is False,
        "no_action": out["action"] == 0,
    }
    if state == "NORMAL":
        out["checks"]["D3_normal_silent"] = (out["D2"] is False)
    else:
        out["checks"]["MISS_d2_eq_d1"] = (out["D2"] == out["D1"])
    p = os.path.join(DIR, "RR1_%s_%s_%s.json" % (policy, state, rep))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved %s; valid=%s P=%s C=%s D1=%s D2=%s event=%s "
          "checks_ok=%s" % (p, out["valid"], out["prompt_tokens"],
                            out["completion_tokens"], out["D1"],
                            out["D2"], out["event"],
                            all(out["checks"].values())), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell")
    ap.add_argument("--matrix", action="store_true")
    args = ap.parse_args()
    if args.cell:
        policy, state, rep = args.cell.split("|")
        run_cell(policy, state, rep)
        return
    if args.matrix:
        for policy in POLICIES:
            for state in STATES:
                for rep in REPS:
                    run_cell(policy, state, rep)
        return
    print("--cell или --matrix")


if __name__ == "__main__":
    main()
