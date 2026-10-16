# -*- coding: utf-8 -*-
"""LONG-2 analyzer: A-G-1..5 + growth-таблица + diagnostic split."""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
SERIES = ("r1", "r2")
EPS = tuple(range(12))
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
    p = os.path.join(DIR, "LONG2_E%d_%s.json" % (ep, series))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    data = {s: {ep: load(s, ep) for ep in EPS} for s in SERIES}
    w("LONG-2 / CONTEXT-GROWTH-1: АНАЛИЗ (24 runs; PROTOCOL FROZEN "
      "11.09.2026)")
    w("")

    first_seen = {}
    for s in SERIES:
        fs = {}
        for ep in EPS:
            for a in data[s][ep]["knowledge_diff"]["added"]:
                if a["kid"] not in fs:
                    fs[a["kid"]] = ep
        first_seen[s] = fs

    # --- A-G-1 ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            full = all([r["audit_before"] == r["audit_after"],
                        r["knowledge_state_before"] is not None,
                        r["knowledge_state_after"] is not None,
                        r["knowledge_diff"] is not None,
                        r["strategy_before"] is not None,
                        r["strategy_after"] is not None,
                        r["decision"] is not None])
            ck("A-G-1/%s E%d полная запись + audit" % (s, ep), full)

    # --- A-G-2 ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            d = r["knowledge_diff"]
            ok = (d["removed"] == []
                  and all(c["fields"] for c in d["changed"]))
            if r["decision"] == "executed":
                ok = ok and (r["created_knowledge_id"] in
                             [a["kid"] for a in d["added"]])
            ck("A-G-2/%s E%d append-only/структурно валиден" % (s, ep),
               ok)

    # --- A-G-3 ---
    for s in SERIES:
        seq = [data[s][ep]["growth"]["context_source_n"]
               for ep in EPS if data[s][ep]["growth"]]
        ok = all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
        ck("A-G-3/%s context_source_n неубывающий" % s, ok,
           "seq=%s" % seq)

    # --- A-G-4 ---
    for s in SERIES:
        ok = True
        for ep in EPS:
            r = data[s][ep]
            if not r["growth"]:
                continue
            for kid in r["growth"]["context_source_ids"]:
                f = first_seen[s].get(kid)
                if f is None or f >= ep:
                    ok = False
        ck("A-G-4/%s L-chain (first_seen < n) для всех"
           " транспортированных" % s, ok)

    # --- A-G-5 ---
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
            ck("A-G-5/%s E%d ворота/chain" % (s, ep), ok)
    eps_all = [data[s][ep]["episode_id"] for s in SERIES for ep in EPS]
    ck("A-G-5 append-only: episode_id уникальны",
       len(eps_all) == len(set(eps_all)))
    for ep in EPS:
        a, b = data["r1"][ep], data["r2"][ep]
        det = (a["mode"] == b["mode"] and a["world"] == b["world"]
               and a["decision"] == b["decision"]
               and a["strategy_before"]["strategy_id"] ==
               b["strategy_before"]["strategy_id"])
        if a["growth"] and b["growth"]:
            det = det and (a["growth"]["context_source_n"] ==
                           b["growth"]["context_source_n"])
        ck("A-G-5 E%d r1≡r2 (структурные)" % ep, det)

    # --- growth-таблица (observation) ---
    w("")
    w("=== GROWTH (observation; единый источник — driver) ===")
    w("  ep | kc | csn | chars | line | uniq | dup | store | trans |"
      " K- | dChars | dCsn")
    for s in SERIES:
        w("  -- %s --" % s)
        prev_c = prev_n = None
        for ep in EPS:
            r = data[s][ep]
            g = r["growth"]
            kc = len(r["knowledge_state_after"])
            if g is None:
                w("  E%-2d | %-3d| (seed; контекст не строился)" % (
                    ep, kc))
                continue
            dc = (g["context_chars"] - prev_c
                  if prev_c is not None else "-")
            dn = (g["context_source_n"] - prev_n
                  if prev_n is not None else "-")
            w("  E%-2d | %-3d| %-4d| %-6d| %-5d| %-5d| %-4d| %-6d|"
              " %-6d| %-3d| %s | %s" % (
                  ep, kc, g["context_source_n"], g["context_chars"],
                  g["context_lines"], g["unique_commands"],
                  g["dup_lines"], g["stored_knowledge_n"],
                  g["transported_knowledge_n"],
                  g["K_store_minus_K_context"], dc, dn))
            prev_c, prev_n = g["context_chars"], g["context_source_n"]

    # --- observations ---
    w("")
    w("=== OBSERVATION: proposal/action траектория ===")
    for s in SERIES:
        row = []
        for ep in EPS:
            r = data[s][ep]
            act = ((r.get("llm") or {}).get("parsed") or {}).get(
                "action") or ("fix-a(seed)" if r["mode"] == "seed"
                              else None)
            row.append("E%d:%s→%s" % (ep, act, r["evaluation"]))
        w("  %s: %s" % (s, " | ".join(row)))

    fails = [c for c in CHECKS if not c[1]]
    w("")
    w("=== ИТОГ LONG-2: %s (%d checks, FAIL=%d) ===" % (
        "PASS" if not fails else "FAIL", len(CHECKS), len(fails)))
    for c in fails:
        w("  FAIL:", c[0])
    with open(os.path.join(DIR, "LONG2_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    w("saved LONG2_ANALYSIS.txt")


if __name__ == "__main__":
    main()
