# -*- coding: utf-8 -*-
"""RESOURCE-RESPONSE-1 analyzer (FROZEN 11.09.2026).

Читает RR1_*.json (12), строит RR1_ANALYSIS.txt:
таблица клеток (valid, P/C, D1/D2/D3, event, halted, checks),
детерминизм r1/r2, R0/R1-сравнение, стоп-условия, итог.
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = []
FAILS = []


def w(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(DIR, "RR1_*.json"))):
        with open(f, encoding="utf-8") as fh:
            rows.append(json.load(fh))
    return rows


def main():
    rows = load()
    w("RESOURCE-RESPONSE-1: ANALYSIS (%d клеток)" % len(rows))
    w("")
    w("=== КЛЕТКИ (policy/state/rep) ===")
    for r in rows:
        chk = r["checks"]
        ok = all(v for k, v in chk.items() if v is not None)
        if not ok:
            FAILS.append(r["cell"])
        w("%-4s %-8s %-2s | valid=%-5s P=%-4s C=%-3s sum=%-4s "
          "D1=%s D2=%s D3=%s | event=%-20s halted=%-5s | checks_ok=%s"
          % (r["policy"], r["state"], r["rep"], r["valid"],
             r["prompt_tokens"], r["completion_tokens"],
             (r["prompt_tokens"] or 0) + (r["completion_tokens"] or 0),
             r["D1"], r["D2"], r["D3"], r["event"], r["halted"], ok))
    w("")
    w("=== ДЕТЕРМИНИЗМ (r1 ≡ r2) ===")
    for policy in ("R0", "R1"):
        for state in ("NORMAL", "MARGINAL", "STARVED"):
            a = [r for r in rows if r["policy"] == policy
                 and r["state"] == state and r["rep"] == "r1"]
            b = [r for r in rows if r["policy"] == policy
                 and r["state"] == state and r["rep"] == "r2"]
            if not a or not b:
                continue
            a, b = a[0], b[0]
            same = (a["valid"] == b["valid"]
                    and a["prompt_tokens"] == b["prompt_tokens"]
                    and a["completion_tokens"]
                    == b["completion_tokens"]
                    and a["event"] == b["event"])
            w("  %s %-8s: %s (valid %s/%s; C %s/%s)"
              % (policy, state, "r1≡r2" if same else "РАСХОЖДЕНИЕ",
                 a["valid"], b["valid"], a["completion_tokens"],
                 b["completion_tokens"]))
    w("")
    w("=== R0 vs R1 ===")
    for state in ("NORMAL", "MARGINAL", "STARVED"):
        a = [r for r in rows if r["policy"] == "R0"
             and r["state"] == state][0]
        b = [r for r in rows if r["policy"] == "R1"
             and r["state"] == state][0]
        w("  %-8s: proposal(P/C/valid) %s/%s/%s vs %s/%s/%s; "
          "event %s vs %s; halted %s vs %s"
          % (state, a["prompt_tokens"], a["completion_tokens"],
             a["valid"], b["prompt_tokens"], b["completion_tokens"],
             b["valid"], a["event"], b["event"], a["halted"],
             b["halted"]))
    w("")
    w("=== СТОП-УСЛОВИЯ ===")
    s1 = all(r["checks"]["K_after_eq_K_before"] for r in rows)
    s2 = all(r["action"] == 0 for r in rows)
    w("  S1 (knowledge не менялось): %s" % s1)
    w("  S2 (нет implicit fallback): %s" % s2)
    det_ok = True
    for policy in ("R0", "R1"):
        for state in ("NORMAL", "MARGINAL", "STARVED"):
            a = [r for r in rows if r["policy"] == policy
                 and r["state"] == state and r["rep"] == "r1"][0]
            b = [r for r in rows if r["policy"] == policy
                 and r["state"] == state and r["rep"] == "r2"][0]
            det_ok = det_ok and (a["valid"] == b["valid"]
                                 and a["completion_tokens"]
                                 == b["completion_tokens"])
    w("  детерминизм: %s" % det_ok)
    st = [r for r in rows if r["state"] == "STARVED"]
    r0s = [r for r in st if r["policy"] == "R0"][0]
    r1s = [r for r in st if r["policy"] == "R1"][0]
    w("  S3: R0 vs R1 на STARVED: event %s (halted=%s) vs %s "
      "(halted=%s) — %s"
      % (r0s["event"], r0s["halted"], r1s["event"], r1s["halted"],
         "различимы на уровне события/останова (proposal-исход "
         "одинаков)" if r0s["valid"] == r1s["valid"] == False
         else "proposal-исходы различаются"))
    w("")
    w("=== ИТОГ ===")
    stdy = [r for r in rows if r["state"] == "STARVED"]
    marg = [r for r in rows if r["state"] == "MARGINAL"]
    norm = [r for r in rows if r["state"] == "NORMAL"]
    w("  NORMAL:   valid=%s (D3 молчит: %s)"
      % (sorted(set(r["valid"] for r in norm)),
         all(r["checks"].get("D3_normal_silent") in (True, None)
             for r in norm)))
    w("  MARGINAL: valid=%s; events=%s"
      % (sorted(set(r["valid"] for r in marg)),
         sorted(set(r["event"] for r in marg))))
    w("  STARVED:  valid=%s; events=%s"
      % (sorted(set(r["valid"] for r in stdy)),
         sorted(set(r["event"] for r in stdy))))
    w("  FAIL-клетки: %s" % (FAILS or "нет"))
    w("  Detection: чувствительность (STARVED/MARGINAL → D2=D1) и "
      "молчание в NORMAL — см. checks.")
    with open(os.path.join(DIR, "RR1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    print("saved RR1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
