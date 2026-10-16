# -*- coding: utf-8 -*-
"""LONG-3 analyzer (FROZEN 11.09.2026).

Режимы:
  --checkpoint12  LONG-2 compatibility checkpoint (gate):
                  сравнение LONG-3 @E0..E11 с LONG-2 @E0..E11;
                  пишет LONG3_CHECKPOINT12_<series>.json.
  (default)       полный анализ: A-T-1..6, B-таблица, L-chain,
                  чекпоинты, границы r1/r2; пишет LONG3_ANALYSIS.txt.
"""
import argparse
import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
LONG2 = os.path.join(os.path.dirname(DIR), "long2")
BRANCHES = ["r1", "r2"]
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load_series(series, upto=400):
    recs = []
    for ep in range(upto):
        p = os.path.join(DIR, "LONG3_E%d_%s.json" % (ep, series))
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    return recs


def load_long2(series):
    recs = []
    for ep in range(400):
        p = os.path.join(LONG2, "LONG2_E%d_%s.json" % (ep, series))
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    return recs


def boundary_of(series):
    p = os.path.join(DIR, "LONG3_BOUNDARY_%s.json" % series)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def growth_of(rec):
    g = rec.get("growth") or {}
    return {"knowledge_count": len(rec.get("knowledge_state_after")
                                   or {}),
            "context_source_n": g.get("context_source_n"),
            "context_chars": g.get("context_chars"),
            "context_lines": g.get("context_lines"),
            "unique_commands": g.get("unique_commands"),
            "dup_lines": g.get("dup_lines"),
            "K_store_minus_K_context": g.get("K_store_minus_K_context")}


def checkpoint12(series):
    r3 = load_series(series, 12)
    r2 = load_long2(series)
    if len(r3) < 12 or len(r2) < 12:
        w("CHECKPOINT12 %s: НЕ ДОСТАТОЧНО записей (long3=%d, "
          "long2=%d)" % (series, len(r3), len(r2)))
        return
    diffs = []
    for ep in range(12):
        g3 = growth_of(r3[ep])
        g2 = growth_of(r2[ep]) if ep < len(r2) else {}
        for key in ("knowledge_count", "context_source_n",
                    "context_chars", "context_lines",
                    "unique_commands", "dup_lines"):
            if g3.get(key) != g2.get(key):
                diffs.append((ep, key, g2.get(key), g3.get(key)))
        act3 = ((r3[ep].get("llm") or {}).get("parsed") or {}).get(
            "action") if r3[ep]["mode"] == "llm" else "seed:fix-a"
        act2 = ((r2[ep].get("llm") or {}).get("parsed") or {}).get(
            "action") if r2[ep]["mode"] == "llm" else "seed:fix-a"
        if act3 != act2:
            diffs.append((ep, "action", act2, act3))
    status = "PASS" if not diffs else "DIFF"
    out = {"series": series, "status": status, "diffs": diffs[:50],
           "n_diffs": len(diffs)}
    p = os.path.join(DIR, "LONG3_CHECKPOINT12_%s.json" % series)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    w("CHECKPOINT12 %s: %s (расхождений: %d) -> %s"
      % (series, status, len(diffs), p))
    for d in diffs[:20]:
        w("   E%d %s: long2=%s long3=%s" % d)


def full_analysis():
    w("LONG-3: АНАЛИЗ (FROZEN; A-T-1..6)")
    all_recs = {}
    bounds = {}
    for series in BRANCHES:
        recs = load_series(series)
        all_recs[series] = recs
        bounds[series] = boundary_of(series)
        w("")
        w("== серия %s: эпизодов %d; boundary: %s =="
          % (series, len(recs),
             ("%s @ E%d" % (bounds[series]["type"],
                            bounds[series]["ep"]))
             if bounds[series] else "не наблюдался"))
        # L-chain
        first_seen = {}
        for r in recs:
            for a in (r.get("knowledge_diff") or {}).get("added", []):
                first_seen.setdefault(a["kid"], r["ep"])
        lchain_bad = []
        for r in recs:
            if r["ep"] == 0:
                continue
            for k in r.get("context_source") or []:
                if first_seen.get(k, 10 ** 9) >= r["ep"]:
                    lchain_bad.append((r["ep"], k))
        # A-T-1/A-T-4: audit + полнота
        audit_bad = [r["ep"] for r in recs
                     if r.get("audit_before") is not None
                     and r.get("audit_after") is not None
                     and r["audit_before"] != r["audit_after"]
                     and not (r.get("b_checks") or {}).get("B4")]
        incomplete = [r["ep"] for r in recs
                      if r["mode"] == "llm"
                      and (r.get("llm") is None
                           or r.get("knowledge_diff") is None)]
        w("  A-T-1 audit нарушений: %s" % (audit_bad or "нет"))
        w("  A-T-4 неполных записей: %s" % (incomplete or "нет"))
        w("  L-chain нарушений: %s" % (lchain_bad or "нет"))
        # B-таблица
        w("  B-таблица: ep | csn | chars | counter | B-флаги")
        prev_counter = None
        for r in recs:
            g = r.get("growth") or {}
            bc = {k: v for k, v in (r.get("b_checks") or {}).items()
                  if v}
            w("    E%-3d csn=%-3s chars=%-4s counter=%-6s B=%s"
              % (r["ep"], g.get("context_source_n"),
                 g.get("context_chars"), r.get("context_counter"),
                 bc or "—"))
        # чекпоинты
        for cp in (12, 20, 30, 50, 75):
            if len(recs) >= cp:
                g = growth_of(recs[cp - 1])
                w("  чекпоинт N=%d: kc=%s csn=%s chars=%s K-=%s"
                  % (cp, g["knowledge_count"],
                     g["context_source_n"], g["context_chars"],
                     g["K_store_minus_K_context"]))
        # A-T-3
        if bounds[series]:
            mx = max(r["ep"] for r in recs)
            w("  A-T-3: последняя запись E%d; boundary E%d — %s"
              % (mx, bounds[series]["ep"],
                 "OK (остановка)" if mx == bounds[series]["ep"]
                 else "НАРУШЕНИЕ (серия шла после boundary)"))
    # A-T-5 сравнение границ
    w("")
    b1, b2 = bounds.get("r1"), bounds.get("r2")
    w("A-T-5: границы реплик: r1=%s; r2=%s"
      % (("%s@E%d" % (b1["type"], b1["ep"])) if b1
         else "нет до конца серии",
         ("%s@E%d" % (b2["type"], b2["ep"])) if b2
         else "нет до конца серии"))
    # A-T-6
    cp_ok = all(os.path.exists(os.path.join(
        DIR, "LONG3_CHECKPOINT12_%s.json" % s)) for s in BRANCHES)
    w("A-T-6: checkpoint12 %s" % ("выполнен" if cp_ok
                                  else "НЕ выполнен"))
    w("")
    w("Вердикт: A-T-2 = %s"
      % ("boundary зафиксирован: "
         + "; ".join("%s:%s@E%d" % (s, bounds[s]["type"],
                                    bounds[s]["ep"])
                     for s in BRANCHES if bounds[s])
         if any(bounds.values()) else
         "boundary not observed up to N=%d"
         % max(len(all_recs[s]) for s in BRANCHES)))
    with open(os.path.join(DIR, "LONG3_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("saved LONG3_ANALYSIS.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint12", action="store_true")
    ap.add_argument("--series", choices=["r1", "r2"])
    args = ap.parse_args()
    if args.checkpoint12:
        series = args.series or "r1"
        checkpoint12(series)
    else:
        full_analysis()


if __name__ == "__main__":
    main()
