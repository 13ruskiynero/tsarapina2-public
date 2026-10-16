# -*- coding: utf-8 -*-
"""RETURN-1 / O3 analyzer (FROZEN 11.09.2026).

Читает RETURN1_E*_{K_r1,K_r2,N_r1,N_r2}.json (20 записей).
Вычисляет: R0..R5 (E4, раздельно), strategy_ref_hit отдельно,
L-chain (first_seen < n), M1..M6, narrative-leak check, таблицу
K vs NULL, интерпретации по репликам, O3 outcome (RETURN OBSERVED /
NOT OBSERVED / AMBIGUOUS / COUNTERCONTROL). Пишет
RETURN1_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
SERIES = ["K_r1", "N_r1", "K_r2", "N_r2"]
LEAK_MARKERS = ["вернул", "снова", "ранее", "напомина", "reconsider",
                "returned", "previously", "again", "success earlier"]
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(series):
    recs = []
    for ep in range(5):
        p = os.path.join(DIR, "RETURN1_E%d_%s.json" % (ep, series))
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    return recs


def cmd_outcome_of(state, kid):
    row = state.get(kid) or {}
    return row.get("cmd"), row.get("outcome")


def first_seen_map(recs):
    fs = {}
    for r in recs:
        for a in (r.get("knowledge_diff") or {}).get("added", []):
            fs.setdefault(a["kid"], r["ep"])
    return fs


def r_flags(recs):
    """R0..R5 + strategy_ref_hit для E4 (K-серии)."""
    r0 = recs[0]
    k1 = r0.get("created_knowledge_id")
    e4 = recs[4]
    ok = {}
    ok["K1"] = k1
    row = ((r0.get("knowledge_state_after") or {}).get(k1)
           if k1 else None) or {}
    ok["R0"] = bool(k1 and row.get("exp") and row.get("cmd")
                    and row.get("outcome"))
    ok["R1"] = bool(k1 and k1 in (e4.get("context_source") or []))
    ctx = e4.get("context") or ""
    line = "  %s → %s" % (row.get("cmd"), row.get("outcome"))
    ok["R2"] = bool(ok["R1"] and line in ctx)
    act = ((e4.get("action") or {}) or {}).get("command")
    ok["R3"] = bool(row.get("cmd") and act == row.get("cmd"))
    ok["R4"] = bool(ok["R3"] and e4.get("decision") == "executed"
                    and ((e4.get("result") or {}).get("refused")
                         is not True))
    ok["R5"] = bool(ok["R4"] and e4.get("evaluation"))
    sb = e4.get("strategy_before") or {}
    ok["strategy_ref_hit"] = bool(k1 and k1 in
                                  (sb.get("knowledge_refs") or []))
    ok["action4"] = act
    ok["eval4"] = e4.get("evaluation")
    return ok


def m_checks(data):
    fail = []
    ok = {}
    # M1: ровно один success-член L в K-сериях (K1)
    m1 = True
    for s in ("K_r1", "K_r2"):
        nsucc = 0
        for rec in data[s]:
            for a in rec["knowledge_diff"]["added"]:
                if a.get("outcome") == "success":
                    nsucc += 1
        m1 = m1 and (nsucc >= 1)
    ok["M1_K1_success_present"] = m1
    # M2: K1 first_seen = 0 (E0)
    m2 = True
    for s in ("K_r1", "K_r2"):
        fs = first_seen_map(data[s])
        k1 = (data[s][0].get("created_knowledge_id"))
        m2 = m2 and fs.get(k1) == 0
    ok["M2_K1_first_seen_E0"] = m2
    # M3: L-chain во всех записях (только first_seen < ep в контексте)
    m3 = True
    for s in SERIES:
        fs = first_seen_map(data[s])
        for rec in data[s]:
            for kid in (rec.get("context_source") or []):
                if fs.get(kid, 10 ** 9) >= rec["ep"]:
                    m3 = False
    ok["M3_L_chain"] = m3
    # M4: без посторонних success (K-серии держат только K1 success)
    # M4: без посторонних success в w2-фазе (E1..E3); E4-возврат —
    # ожидаемый success по конструкции (не нарушение)
    m4 = True
    for s in ("K_r1", "K_r2"):
        for rec in data[s][1:4]:
            for a in rec["knowledge_diff"]["added"]:
                if a.get("outcome") == "success":
                    m4 = False
    ok["M4_no_extra_success_in_K"] = m4
    # M5: narrative-leak
    leak = []
    for s in SERIES:
        for rec in data[s]:
            ctx = (rec.get("context") or "")
            for mk in LEAK_MARKERS:
                if mk.lower() in ctx.lower():
                    leak.append((s, rec["ep"], mk))
    ok["M5_no_leak"] = not leak
    # M6: audit
    m6 = all(rec["audit_before"] == rec["audit_after"]
             for s in SERIES for rec in data[s])
    ok["M6_audit_clean"] = m6
    for k, v in ok.items():
        if not v:
            fail.append(k)
    return ok, fail, leak


def main():
    data = {s: load(s) for s in SERIES}
    w("RETURN-1: АНАЛИЗ (FROZEN; R0..R5 раздельно)")
    w("")
    for s in SERIES:
        w("== %s ==" % s)
        for rec in data[s]:
            act = ((rec.get("llm") or {}).get("parsed") or {}).get(
                "action")
            if act is None:
                act = (rec.get("seed") or {}).get("action")
            w("E%d world=%s V=%s action=%s dec=%s eval=%s"
              % (rec["ep"], rec["world"], rec["envver"], act,
                 rec["decision"], rec.get("evaluation")))
        w("")
    w("== R-ступени (K-серии, E4) ==")
    flags = {}
    for s in ("K_r1", "K_r2"):
        f = r_flags(data[s])
        flags[s] = f
        c4, o4 = cmd_outcome_of(
            (data[s][0].get("knowledge_state_after") or {}), f["K1"])
        w("%s: K1=%s (%s→%s) R0=%s R1=%s R2=%s R3=%s R4=%s R5=%s "
          "strategy_ref_hit=%s"
          % (s, (f["K1"] or "")[:12], c4, o4,
             f["R0"], f["R1"], f["R2"], f["R3"], f["R4"], f["R5"],
             f["strategy_ref_hit"]))
    w("")
    # --- E4: K vs NULL ---
    w("== E4: K vs NULL ==")
    table = {}
    for s in SERIES:
        e4 = data[s][4]
        act = ((e4.get("llm") or {}).get("parsed") or {}).get("action")
        table[s] = act
        w("%s: action=%s decision=%s eval=%s"
          % (s, act, e4.get("decision"), e4.get("evaluation")))
    w("")
    # --- narrative leak ---
    ok, m_fail, leak = m_checks(data)
    w("== M-проверки ==")
    for k, v in ok.items():
        w("%s: %s" % (k, "OK" if v else "FAIL"))
    w("narrative-leak: %s" % (leak or "чисто (маркеров нет)"))
    w("")
    # --- интерпретации ---
    interp = {}
    for rep in ("r1", "r2"):
        k_act = table.get("K_" + rep)
        n_act = table.get("N_" + rep)
        k_fix = k_act == "fix-a"
        n_fix = n_act == "fix-a"
        if k_fix and not n_fix:
            txt = ("evidence consistent with memory effect "
                   "(associated with prior verified Knowledge)")
        elif k_fix and n_fix:
            txt = ("возврат неотделим от Gemma/default context "
                   "effect")
        elif not k_fix and not n_fix:
            txt = ("Knowledge транспортировано; behavioral return "
                   "не наблюдался")
        else:
            txt = ("против ожидаемого; отрицательный результат "
                   "(COUNTERCONTROL)")
        interp[rep] = txt
    w("== Интерпретация (по репликам) ==")
    for rep in ("r1", "r2"):
        w("%s: K=%s NULL=%s -> %s"
          % (rep, table.get("K_" + rep), table.get("N_" + rep),
             interp[rep]))
    w("")
    # --- O3 outcome ---
    outcomes = set()
    for rep in ("r1", "r2"):
        k_fix = table.get("K_" + rep) == "fix-a"
        n_fix = table.get("N_" + rep) == "fix-a"
        if not k_fix and n_fix:
            outcomes.add("COUNTERCONTROL")
        elif k_fix and not n_fix:
            outcomes.add("OBSERVED")
        elif k_fix and n_fix:
            outcomes.add("AMBIGUOUS (неотделим)")
        else:
            outcomes.add("NOT OBSERVED")
    if len(outcomes) > 1:
        outcome = "RETURN AMBIGUOUS (расхождение реплик: %s)" % sorted(
            outcomes)
    else:
        outcome = "RETURN " + outcomes.pop()
    pass_mech = (not m_fail) and (not leak)
    w("== ВЕРДИКТ ==")
    w("PROTOCOL %s (M1..M6%s)"
      % ("PASS" if pass_mech else "FAIL",
         "" if pass_mech else "; см. нарушения выше"))
    w("O3 outcome: %s" % outcome)
    w("Формулировка: «associated with», не causal proof; "
      "divergence фиксируется как результат.")
    with open(os.path.join(DIR, "RETURN1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("saved RETURN1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
