# -*- coding: utf-8 -*-
"""LONG-1A analyzer: A-L1-1..6 + L-chain invariant + counters."""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
SERIES = ("r1", "r2")
EPS = (0, 1, 2, 3, 4, 5)
OUT = []
CHECKS = []


def w(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line, flush=True)


def ck(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    w("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def load(series, ep):
    p = os.path.join(DIR, "LONG1A_E%d_%s.json" % (ep, series))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    data = {s: {ep: load(s, ep) for ep in EPS} for s in SERIES}
    w("LONG-1A: АНАЛИЗ (12 runs; PROTOCOL FROZEN 11.09.2026)")
    w("")

    first_seen = {}
    cmd_map = {}
    for s in SERIES:
        fs = {}
        for ep in EPS:
            for a in data[s][ep]["knowledge_diff"]["added"]:
                if a["kid"] not in fs:
                    fs[a["kid"]] = ep
                    cmd_map[a["kid"]] = a.get("cmd")
        first_seen[s] = fs

    # --- counters ---
    counters = {}
    for s in SERIES:
        c = {}
        for kid, fse in first_seen[s].items():
            c[kid] = {"first_seen": fse, "last_used": None,
                      "retrieved": 0, "actioned": 0,
                      "vs": 0, "vf": 0, "cmd": cmd_map.get(kid)}
        for ep in EPS:
            r = data[s][ep]
            for kid in r["context_source"]:
                if kid not in c:
                    c[kid] = {"first_seen": None, "last_used": None,
                              "retrieved": 0, "actioned": 0,
                              "vs": 0, "vf": 0, "cmd": None}
                c[kid]["retrieved"] += 1
                c[kid]["last_used"] = ep
            if r["decision"] == "executed":
                act = (r["action"] or {}).get("command")
                out = r["evaluation"]
                for kid, cc in c.items():
                    # EF-14: actioned/vs/vf — только эпизоды ПОСЛЕ
                    # first_seen (знание существовало до действия)
                    fs = cc["first_seen"]
                    if (cc["cmd"] and cc["cmd"] == act
                            and fs is not None and fs < ep):
                        cc["actioned"] += 1
                        if out == "success":
                            cc["vs"] += 1
                        elif out in ("partial", "failure"):
                            cc["vf"] += 1
        counters[s] = c

    # --- A-L1-1: полная запись + audit ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            full = all([r["audit_before"] == r["audit_after"],
                        r["knowledge_state_before"] is not None,
                        r["knowledge_state_after"] is not None,
                        r["knowledge_diff"] is not None,
                        r["strategy_before"] is not None,
                        r["strategy_after"] is not None,
                        (r["context"] is not None
                         if r["mode"] == "llm" else True),
                        r["decision"] is not None])
            ck("A-L1-1/%s E%d полная запись + audit" % (s, ep), full)

    # --- A-L1-2 ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            if r["decision"] == "executed":
                added = [a["kid"] for a in r["knowledge_diff"]["added"]]
                ck("A-L1-2/%s E%d consequence -> diff" % (s, ep),
                   r["created_knowledge_id"] in added
                   and r["evaluation"] is not None)

    # --- A-L1-3: retrieved-связи восстановимы ---
    for s in SERIES:
        ok = True
        for ep in EPS:
            r = data[s][ep]
            for kid in r["context_source"]:
                if counters[s].get(kid, {}).get("retrieved", 0) < 1:
                    ok = False
        ck("A-L1-3/%s retrieved-связи восстановимы" % s, ok)

    # --- A-L1-4 / L-chain invariant ---
    for s in SERIES:
        ok = True
        for ep in EPS:
            if ep == 0:
                continue
            prev_kids = [k for k, f in first_seen[s].items()
                         if f is not None and f < ep]
            inter = set(prev_kids) & set(data[s][ep]["context_source"])
            ck("A-L1-4/%s E%d chain (prior verified knowledge "
               "retrieved)" % (s, ep), len(inter) > 0,
               "prior=%d" % len(inter))
            for kid in data[s][ep]["context_source"]:
                f = first_seen[s].get(kid)
                if f is None or f >= ep:
                    ok = False
        ck("L-chain/%s first_seen(K) < n для всех retrieved" % s, ok)

    # --- A-L1-5: деградации нет ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            ok = True
            if r["mode"] == "llm":
                if r["decision"] == "executed":
                    ok = (len(r["gates"]) == 4
                          and all(g["ok"] for g in r["gates"])
                          and r["result"] is not None
                          and r["result"].get("refused") is False)
                else:
                    ok = r["no_action_reason"] in ("G-a", "G-b",
                                                   "G-c", "G-d")
            for a in r["knowledge_diff"]["added"]:
                if r["experience_id"] not in (a["exp"] or []):
                    ok = False
            ck("A-L1-5/%s E%d нет деградации (ворота/chain)" % (s, ep),
               ok)
    eps_all = [data[s][ep]["episode_id"] for s in SERIES for ep in EPS]
    ck("A-L1-5 append-only: episode_id уникальны",
       len(eps_all) == len(set(eps_all)))

    # --- A-L1-6: r1≡r2 ---
    for ep in EPS:
        a, b = data["r1"][ep], data["r2"][ep]
        det = (a["mode"] == b["mode"] and a["world"] == b["world"]
               and a["decision"] == b["decision"]
               and a["strategy_before"]["strategy_id"] ==
               b["strategy_before"]["strategy_id"]
               and (len(a["knowledge_diff"]["added"]) ==
                    len(b["knowledge_diff"]["added"]))
               and (len(a["context_source"]) ==
                    len(b["context_source"])))
        ck("A-L1-6 E%d r1≡r2 (структурные)" % ep, det,
           "dec=%s/%s ctx=%d/%d" % (
               a["decision"], b["decision"],
               len(a["context_source"]), len(b["context_source"])))

    # --- сводка ---
    w("")
    w("=== ЭПИЗОДЫ ===")
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            act = ((r.get("llm") or {}).get("parsed") or {}).get("action")
            added = [(a["kid"][:10], a["cmd"], a["outcome"])
                     for a in r["knowledge_diff"]["added"]]
            w("  %s E%d %-4s world=%-4s%s dec=%-9s eval=%-8s "
              "act=%-30s added=%s ctx_src=%d" % (
                  s, ep, r["mode"], r["world"],
                  "+n" if r.get("noise") == "n" else "  ",
                  r["decision"], str(r["evaluation"]), str(act),
                  added, len(r["context_source"])))
    w("")
    w("=== COUNTERS (per knowledge) ===")
    for s in SERIES:
        w("  -- %s --" % s)
        for kid, c in sorted(counters[s].items(),
                             key=lambda kv: (kv[1]["first_seen"]
                                             if kv[1]["first_seen"]
                                             is not None else 99,
                                             kv[0])):
            w("    %s cmd=%-28s first=%-2s last=%-4s ret=%d act=%d "
              "vs=%d vf=%d" % (
                  kid[:12], str(c["cmd"]), c["first_seen"],
                  str(c["last_used"]), c["retrieved"], c["actioned"],
                  c["vs"], c["vf"]))
    w("")
    w("=== OBSERVATION: proposal_diff ===")
    for s in SERIES:
        for ep in EPS:
            if data[s][ep]["mode"] == "llm":
                pd = data[s][ep]["proposal_diff"] or {}
                w("  %s E%d changed=%s prev=%r cur=%r" % (
                    s, ep, pd.get("changed"), pd.get("prev"),
                    pd.get("cur")))

    fails = [c for c in CHECKS if not c[1]]
    w("")
    w("=== ИТОГ LONG-1A: %s (%d checks, FAIL=%d) ===" % (
        "PASS" if not fails else "FAIL", len(CHECKS), len(fails)))
    for c in fails:
        w("  FAIL:", c[0])
    with open(os.path.join(DIR, "LONG1A_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    w("saved LONG1A_ANALYSIS.txt")


if __name__ == "__main__":
    main()
