# -*- coding: utf-8 -*-
"""LOOP-0 analyzer: A1–A9 (PROTOCOL loop0/PROTOCOL.md §5)."""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
SERIES = ("r1", "r2")
EPS = (0, 1, 2, 3)
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
    p = os.path.join(DIR, "LOOP0_E%d_%s.json" % (ep, series))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    data = {s: {ep: load(s, ep) for ep in EPS} for s in SERIES}
    w("LOOP-0: АНАЛИЗ (8 runs; PROTOCOL FROZEN 11.09.2026)")
    w("")

    # --- A1: E0 seed & chain ---
    for s in SERIES:
        e0 = data[s][0]
        ck("A1/%s E0 seed executed, success" % s,
           e0["mode"] == "seed" and e0["evaluation"] == "success"
           and e0["decision"] == "executed")
        added = e0["knowledge_diff"]["added"]
        ck("A1/%s E0 added>=1 и created_knowledge_id в added" % s,
           len(added) >= 1
           and e0["created_knowledge_id"] in [a["kid"] for a in added])
        ok_chain = True
        for a in added:
            if e0["experience_id"] not in (a["exp"] or []):
                ok_chain = False
        ck("A1/%s E0: kid -> experience_refs -> experience (chain)" % s,
           ok_chain and e0["experience_id"])
        w("   %s E0: added=%s" % (
            s, [(a["kid"][:10], a["outcome"]) for a in added]))

    # --- A2: транспорт ---
    for s in SERIES:
        kids_upto = set()
        for ep in EPS:
            r = data[s][ep]
            if ep > 0:
                src = set(r["context_source"])
                ck("A2/%s E%d context_source непуст и пересекает "
                   "состояние после E%d" % (s, ep, ep - 1),
                   len(src) > 0 and len(src & kids_upto) > 0)
            for a in r["knowledge_diff"]["added"]:
                kids_upto.add(a["kid"])
        k1 = data[s][0]["created_knowledge_id"]
        ck("A2/%s E1 context_source содержит K1 (added в E0)" % s,
           k1 in data[s][1]["context_source"])

    # --- A3: strategy state ---
    for s in SERIES:
        k1 = data[s][0]["created_knowledge_id"]
        for ep in (1, 2, 3):
            refs = (data[s][ep]["strategy_before"].get(
                "knowledge_refs") or [])
            ck("A3/%s E%d strategy_before refs ∋ K1" % (s, ep),
               k1 in refs)

    # --- A4: context не содержит kid/provenance ---
    for s in SERIES:
        for ep in (1, 2, 3):
            r = data[s][ep]
            ctx = r["context"] or ""
            leak = [k for k in r["context_source"] if k in ctx]
            ck("A4/%s E%d context: без kid; prev-строка есть" % (
                s, ep), not leak and "Предыдущий эпизод:" in ctx)

    # --- A5: mechanical invariant (обе стороны) ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            ok = True
            for a in r["knowledge_diff"]["added"]:
                if r["experience_id"] not in (a["exp"] or []):
                    ok = False
            ck("A5/%s E%d added kids -> experience -> episode" % (
                s, ep), ok)

    # --- A6: ворота / no bypass ---
    for s in SERIES:
        for ep in (1, 2, 3):
            r = data[s][ep]
            if r["decision"] == "executed":
                ok = (len(r["gates"]) == 4
                      and all(g["ok"] for g in r["gates"])
                      and r["result"] is not None
                      and r["result"].get("refused") is False)
            else:
                ok = (r["no_action_reason"] in
                      ("G-a", "G-b", "G-c", "G-d"))
            ck("A6/%s E%d permission/executor без обходов" % (s, ep),
               ok)

    # --- A7: audit/append-only ---
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            ck("A7/%s E%d audit clean" % (s, ep),
               r["audit_before"] == r["audit_after"])
    eps_all = [data[s][ep]["episode_id"] for s in SERIES for ep in EPS]
    ck("A7 append-only: episode_id уникальны",
       len(eps_all) == len(set(eps_all)))

    # --- A8: r1≡r2 структурно ---
    for ep in EPS:
        a, b = data["r1"][ep], data["r2"][ep]
        det = (a["mode"] == b["mode"] and a["world"] == b["world"]
               and a["decision"] == b["decision"])
        if ep == 0:
            det = det and a["evaluation"] == b["evaluation"]
            det = det and (len(a["knowledge_diff"]["added"]) ==
                           len(b["knowledge_diff"]["added"]))
        ck("A8 E%d r1≡r2 (структурные поля)" % ep, det,
           "decisions=%s/%s" % (a["decision"], b["decision"]))

    # --- A9: proposal_diff зафиксирован ---
    for s in SERIES:
        for ep in (1, 2, 3):
            ck("A9/%s E%d proposal_diff зафиксирован" % (s, ep),
               data[s][ep]["proposal_diff"] is not None)

    # --- сводка / наблюдения ---
    w("")
    w("=== СВОДКА (наблюдения) ===")
    for s in SERIES:
        for ep in EPS:
            r = data[s][ep]
            act = ((r.get("llm") or {}).get("parsed") or {}).get("action")
            added = [(a["kid"][:10], a["cmd"], a["outcome"])
                     for a in r["knowledge_diff"]["added"]]
            w("  %s E%d %-4s world=%s%s decision=%-9s eval=%-8s "
              "action=%-26s added=%s" % (
                  s, ep, r["mode"], r["world"],
                  "+n" if r.get("noise") == "n" else "  ",
                  r["decision"], str(r["evaluation"]), str(act),
                  added))
            if ep > 0:
                w("      ctx_src=%d prev=%r diff=%s" % (
                    len(r["context_source"]),
                    (r["proposal_diff"] or {}).get("changed"),
                    [a["kid"][:10] for a in
                     r["knowledge_diff"]["added"]]))

    fails = [c for c in CHECKS if not c[1]]
    w("")
    w("=== ИТОГ LOOP-0: %s (%d checks, FAIL=%d) ===" % (
        "PASS" if not fails else "FAIL", len(CHECKS), len(fails)))
    for c in fails:
        w("  FAIL:", c[0])
    with open(os.path.join(DIR, "LOOP0_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    w("saved LOOP0_ANALYSIS.txt")


if __name__ == "__main__":
    main()
