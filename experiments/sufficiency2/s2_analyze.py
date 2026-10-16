# -*- coding: utf-8 -*-
"""SUFFICIENCY-2: офлайн-анализ (правила протокола FROZEN).

Для каждой серии: outcomes[1..60]. Пороги K=1..6:
- N_noise(K): первый K-run (K подряд non-success) в 1..60;
- N_stale(K): первый K-run в 31..60 (после t0);
- N_first(K): первый K-run во ВСЕЙ истории (критерий без знания t0);
hold-out: для noise — N(K) на 1..30 vs 31..60 (стационарность).
Классификация (дизайн): (A) не разделяются при фиксированном фоне;
(B) разделяются устойчиво; (C) режим фона с неразличимостью.
Печать: сырые строки → N(K)-таблица → hold-out → интерпретация.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
CELLS = ["noise_low", "noise_high", "noise_var",
         "stale_low", "stale_high", "stale_var"]


def load(cell, rep):
    p = os.path.join(DIR, "S2_series_%s_%s.json" % (cell, rep))
    d = json.load(open(p, encoding="utf-8"))
    return d["outcomes"]


def f_at(out, i):
    return out[i] != "success"


def first_krun(out, a, b, k):
    """Первый K-run в позициях [a..b] (1-based, включительно). None."""
    run = 0
    for i in range(a - 1, b):
        if f_at(out, i):
            run += 1
            if run >= k:
                return i + 1  # конец руна (1-based)
        else:
            run = 0
    return None


def fmt(v):
    return "None" if v is None else str(v)


def main():
    out = {}
    for cell in CELLS:
        out[cell] = {"r1": load(cell, "r1"), "r2": load(cell, "r2")}
    print("== SUFFICIENCY-2: СЫРЫЕ СЕРИИ ==", flush=True)
    for cell in CELLS:
        for rep in ("r1", "r2"):
            s = "".join("s" if o == "success" else "f"
                        for o in out[cell][rep])
            print("  %-12s %s  %s" % (cell, rep, s), flush=True)

    print()
    print("== N(K): первые K-run'ы ==", flush=True)
    for cell in CELLS:
        is_stale = cell.startswith("stale")
        for rep in ("r1", "r2"):
            o = out[cell][rep]
            n_first = []
            n_post = []
            for k in range(1, 7):
                n_first.append(first_krun(o, 1, 60, k))
                if is_stale:
                    n_post.append(first_krun(o, 31, 60, k))
            row = "K1=%s K2=%s K3=%s K4=%s K5=%s K6=%s" % tuple(
                fmt(v) for v in n_first)
            extra = ""
            if is_stale:
                extra = " | после t0: " + " ".join(
                    fmt(v) for v in n_post)
            print("  %-12s %s  %s%s" % (cell, rep, row, extra),
                  flush=True)
    print()
    print("== Hold-out (noise): N(K) на 1..30 vs 31..60 ==", flush=True)
    for cell in ("noise_low", "noise_high", "noise_var"):
        for rep in ("r1", "r2"):
            o = out[cell][rep]
            h1 = [first_krun(o, 1, 30, k) for k in range(1, 7)]
            h2 = [first_krun(o, 31, 60, k) for k in range(1, 7)]
            print("  %-12s %s  1-30: %s  31-60: %s"
                  % (cell, rep, " ".join(fmt(v) for v in h1),
                     " ".join(fmt(v) for v in h2)), flush=True)

    print()
    print("== Разделение noise vs stale при одинаковом фоне ==",
          flush=True)
    for bg in ("low", "high", "var"):
        nc = "noise_%s" % bg
        sc = "stale_%s" % bg
        for k in (1, 2, 3, 6):
            nv = [first_krun(out[nc][r], 1, 60, k) for r in ("r1", "r2")]
            sv = [first_krun(out[sc][r], 1, 60, k) for r in ("r1", "r2")]
            inter = set(nv) & set(sv)
            print("  фон=%s K=%d: noise=%s stale=%s пересечение=%s"
                  % (bg, k, [fmt(v) for v in nv], [fmt(v) for v in sv],
                     {fmt(v) for v in inter} if inter else "EMPTY"),
                  flush=True)


if __name__ == "__main__":
    main()
