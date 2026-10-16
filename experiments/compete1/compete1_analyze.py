# -*- coding: utf-8 -*-
"""COMPETE-1 analyzer (FROZEN 11.09.2026).

Читает COMPETE1_E*_{C1_r1,C1_r2,C2_r1,C2_r2}.json (20 записей).
Уровни E4: retrieval/context/strategy/proposal/permission/
execution/consequence. Паттерн-таблица: recency-like / dominance
K_F / dominance K_G / non-recency / unstable / outside.
M1..M6 + narrative-leak. Пишет COMPETE1_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
SERIES = ["C1_r1", "C2_r1", "C1_r2", "C2_r2"]
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
        p = os.path.join(DIR, "COMPETE1_E%d_%s.json" % (ep, series))
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    return recs


def first_seen_map(recs):
    fs = {}
    for r in recs:
        for a in (r.get("knowledge_diff") or {}).get("added", []):
            fs.setdefault(a["kid"], r["ep"])
    return fs


def line_family(recs):
    """K_F/K_G: (kid, acq_ep) по командам acquisition-эпизодов."""
    kf = kg = None
    epf = epg = None
    for r in recs:
        acq = r.get("acq") or {}
        if acq.get("action") == "fix-a":
            kf, epf = r.get("created_knowledge_id"), r["ep"]
        elif acq.get("action") == "fix-aq":
            kg, epg = r.get("created_knowledge_id"), r["ep"]
    return kf, epf, kg, epg


def e4_levels(recs):
    e4 = recs[4]
    kf, epf, kg, epg = line_family(recs)
    ctx = e4.get("context") or ""
    src = e4.get("context_source") or []
    refs = ((e4.get("strategy_before") or {}).get("knowledge_refs")
            or [])
    act = ((e4.get("llm") or {}).get("parsed") or {}).get("action")
    return {
        "K_F": kf, "K_G": kg,
        "retrieval_F": bool(kf and kf in src),
        "retrieval_G": bool(kg and kg in src),
        "line_F_in_ctx": "  fix-a → success" in ctx,
        "line_G_in_ctx": "  fix-aq → success" in ctx,
        "strategy_ref_hit_F": bool(kf and kf in refs),
        "strategy_ref_hit_G": bool(kg and kg in refs),
        "proposal": act,
        "permission": e4.get("decision"),
        "execution": (e4.get("result") or {}).get("exit_code"),
        "consequence": e4.get("evaluation"),
    }


def category(a_c1, a_c2):
    f_ok = a_c1 == "fix-a"
    g_ok = a_c2 == "fix-aq"
    outside = any(a not in ("fix-a", "fix-aq")
                  for a in (a_c1, a_c2))
    if outside:
        return "outside/mixed"
    if f_ok and g_ok:
        return "recency-like"
    if a_c1 == "fix-a" and a_c2 == "fix-a":
        return "dominance K_F"
    if a_c1 == "fix-aq" and a_c2 == "fix-aq":
        return "dominance K_G"
    return "non-recency"


def main():
    data = {s: load(s) for s in SERIES}
    w("COMPETE-1: АНАЛИЗ (FROZEN)")
    w("")
    m_fail = []
    # M1/M5
    for s in SERIES:
        for r in data[s]:
            if (r.get("audit_before") is not None and
                    r["audit_before"] != r.get("audit_after")):
                m_fail.append("M1 audit %s E%d" % (s, r["ep"]))
            if (r.get("knowledge_diff") or {}).get("removed"):
                m_fail.append("M5 removed %s E%d" % (s, r["ep"]))
    # M2/M3
    fam = {}
    for s in SERIES:
        kf, epf, kg, epg = line_family(data[s])
        fam[s] = (kf, epf, kg, epg)
        for r in data[s]:
            if r.get("mode") == "acq" and r.get("evaluation") != \
                    "success":
                m_fail.append("M2 %s E%d acq != success (%s)"
                              % (s, r["ep"], r.get("evaluation")))
        if not (kf and kg and kf != kg):
            m_fail.append("M2 %s K_F/K_G не различны" % s)
        fs = first_seen_map(data[s])
        if fs.get(kf) != epf or fs.get(kg) != epg:
            m_fail.append("M3 %s first_seen mismatch" % s)
        for el, ep in ((kf, epf), (kg, epg)):
            row = ((data[s][ep].get("knowledge_state_after")
                    or {}).get(el) or {})
            if not row.get("exp"):
                m_fail.append("M3 %s kid %s: нет exp" % (s, el[:8]))
    # M4 + уровни
    w("== E4: уровни ==")
    e4s = {}
    for s in SERIES:
        e4s[s] = e4_levels(data[s])
        lv = e4s[s]
        w("%s: retr F/G=%s/%s | ctx lines F/G=%s/%s | "
          "strategy_ref F/G=%s/%s" % (
              s, lv["retrieval_F"], lv["retrieval_G"],
              lv["line_F_in_ctx"], lv["line_G_in_ctx"],
              lv["strategy_ref_hit_F"], lv["strategy_ref_hit_G"]))
        w("     proposal=%s | permission=%s | exec=%s | cons=%s"
          % (lv["proposal"], lv["permission"], lv["execution"],
             lv["consequence"]))
        if not (lv["retrieval_F"] and lv["retrieval_G"]):
            m_fail.append("M4 %s: не обе retrieved" % s)
        if not (lv["line_F_in_ctx"] and lv["line_G_in_ctx"]):
            m_fail.append("M4 %s: не обе строки в prompt" % s)
        if lv["proposal"] is None:
            m_fail.append("M4 %s: proposal None" % s)
    w("")
    # L-chain
    bad = []
    for s in SERIES:
        fs = first_seen_map(data[s])
        for r in data[s]:
            for k in r.get("context_source") or []:
                if fs.get(k, 10 ** 9) >= r["ep"]:
                    bad.append((s, r["ep"], k[:10]))
    # narrative leak
    leak = []
    for s in SERIES:
        ctx = (data[s][4].get("context") or "").lower()
        for mk in LEAK_MARKERS:
            if mk.lower() in ctx:
                leak.append((s, mk))
    w("== M-проверки ==")
    w("нарушения: %s" % (m_fail or "нет"))
    w("L-chain нарушения: %s" % (bad or "нет"))
    w("narrative-leak: %s" % (leak or "чисто"))
    w("")
    # Паттерн
    w("== Паттерн ==")
    acts = {s: e4s[s]["proposal"] for s in SERIES}
    cat_r1 = category(acts["C1_r1"], acts["C2_r1"])
    cat_r2 = category(acts["C1_r2"], acts["C2_r2"])
    w("C1_r1=%s C2_r1=%s -> %s" % (acts["C1_r1"], acts["C2_r1"],
                                   cat_r1))
    w("C1_r2=%s C2_r2=%s -> %s" % (acts["C1_r2"], acts["C2_r2"],
                                   cat_r2))
    if cat_r1 == cat_r2:
        pattern = cat_r1
    else:
        pattern = "unstable (r1: %s; r2: %s)" % (cat_r1, cat_r2)
    w("ИТОГ: %s" % pattern)
    if pattern == "recency-like":
        w("Формулировка: selection is consistent with "
          "acquisition-order / recency-like behavior.")
    w("strategy_ref_hit — отдельное механическое наблюдение "
      "(не доказательство).")
    w("")
    w("== ВЕРДИКТ ==")
    mech = (not m_fail) and (not bad) and (not leak)
    w("PROTOCOL %s (M1..M6%s)"
      % ("PASS" if mech else "FAIL",
         "" if mech else "; см. нарушения выше"))
    w("PATTERN: %s" % pattern)
    with open(os.path.join(DIR, "COMPETE1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("saved COMPETE1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
