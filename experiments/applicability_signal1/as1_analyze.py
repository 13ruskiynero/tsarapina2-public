# -*- coding: utf-8 -*-
"""AS-1 analyzer (FROZEN-порядок: RAW → ground truth → FP/FN/
consistency → сравнение кандидатов → A/B/C)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIR = os.path.dirname(os.path.abspath(__file__))
GT = {"C1": [True] * 8, "C2": [True] * 3 + [False] * 5,
      "C3": [True] * 8, "C4": [True] * 8, "C5": [True] * 6}
CANDIDATES = ["E", "V", "N", "D", "S", "L"]
OUT = os.path.join(DIR, "AS1_ANALYSIS.txt")

data = json.load(open(os.path.join(DIR, "AS1_candidates.json"),
                      encoding="utf-8"))
rep_lines = []


def w(s=""):
    print(s, flush=True)
    rep_lines.append(s)


def cand_val(row, cand):
    """Значение кандидата в эпизоде (P — P1 для C5)."""
    c = row.get("cand", {})
    if cand == "P":
        return c.get("P1") if row["series"] == "C5" else c.get("P")
    return c.get(cand)


def delta(vals):
    """Дельта-траектория: изменение между соседними эпизодами."""
    out = [False]
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        if isinstance(a, str) and isinstance(b, str):
            out.append(a != b)
        else:
            out.append(a != b)
    return out


def stable(vals):
    """Свойство 5: стабильность внутри состояния (нет изменений
    при неизменном мире... для C5 pulse отдельно)."""
    # для бинарных: доля эпизодов, где значение == предыдущему
    # при том же gt (т.е. внутри стабильной фазы)
    d = delta(vals)
    same_gt = [True] + [GT[s][i] == GT[s][i - 1]
                        for s in ["C1"] for i in range(1, 8)]  # unused
    return d


def main():
    w("APPLICABILITY-SIGNAL-1: АНАЛИЗ (FROZEN-порядок)")
    w("=" * 72)
    # RAW: согласованность ground truth с мирами
    w("1. RAW → сверка ground truth:")
    gt_ok = True
    for row in data:
        world_gt = row["gt"]
        ok_world = (row["world"] == "w1" or row["world"] == "dbg"
                    or row["world"] == "noise") and world_gt or \
            (row["world"] == "w2" and not world_gt)
        # noise-мир: gt=True (адресно применим; C3-серия)
        if row["world"] == "noise":
            ok_world = world_gt and row["series"] in ("C3",)
        if row["world"] == "w2":
            ok_world = (not world_gt) and row["series"] == "C2"
        if not ok_world:
            gt_ok = False
            w("  ! GT mismatch: %s" % row)
    w("  ground truth согласована с мирами: %s" % ("OK" if gt_ok
                                                    else "ERROR"))

    # 2. FP/FN/consistency по кандидатам (на сериях × повторах)
    w("")
    w("2. FP / FN / consistency (по дельтам эпизодов; кандидат "
      "«пригоден»: FP=0, FN=0, consistency=1.0):")
    w("")
    hdr = "%-4s | " % "канд"
    for sname in ("C1", "C2", "C3", "C4", "C5"):
        hdr += "%s FP FN cs | " % sname
    hdr += "ИТОГ"
    w(hdr)
    w("-" * 88)
    verdicts = {}
    for cand in CANDIDATES:
        line = "%-4s | " % cand
        cand_ok = True
        for sname in ("C1", "C2", "C3", "C4", "C5"):
            fps = fns = cs_all = n = 0
            for rep in ("r1", "r2"):
                rows = [r for r in data if r["series"] == sname
                        and r["rep"] == rep]
                rows.sort(key=lambda r: r["ep"])
                vals = [cand_val(r, cand) for r in rows]
                d = delta(vals)
                gt = GT[sname]
                gd = delta(gt)
                for i in range(1, len(rows)):
                    n += 1
                    if d[i] and not gd[i]:
                        fps += 1
                    if gd[i] and not d[i]:
                        fns += 1
                    if d[i] == gd[i]:
                        cs_all += 1
            ok_s = (fps == 0 and fns == 0 and (cs_all / n == 1.0
                                               if n else True))
            cand_ok = cand_ok and ok_s
            line += "%s %s %s %.2f | " % (
                "0" if fps == 0 else str(fps),
                "0" if fns == 0 else str(fns),
                cs_all / n if n else 1.0,
                cs_all / n if n else 1.0)
        verdicts[cand] = cand_ok
        line += "ПРИГОДЕН" if cand_ok else "НЕ пригоден"
        w(line)
    # P: C5-стабильность
    w("")
    w("P (pulse, C5, два чтения в эпизоде):")
    p_stable = []
    for rep in ("r1", "r2"):
        rows = [r for r in data if r["series"] == "C5"
                and r["rep"] == rep]
        for r in rows:
            p1 = r["cand"].get("P1")
            p2 = r["cand"].get("P2")
            p_stable.append(p1 == p2)
    w("  внутриэпизодная стабильность pulse: %d/12"
      % sum(p_stable))
    w("  (ожидание: 0 — pulse флуктуирует внутри состояния; "
      "свойство 5 нарушено)")
    # L-заметка: непрерывный
    w("")
    w("L (load1) — непрерывный: изменения почти каждый эпизод "
      "(см. колонки); непрерывные значения → только RESEARCHABLE "
      "(порог запрещён дизайном).")
    # Сводная таблица пригодности с трактовкой
    w("")
    w("3. Сравнение кандидатов (ожидания дизайна):")
    expect = {"E": "пригоден", "V": "пригоден", "N": "НЕ (шум → FP)",
              "D": "НЕ (декор → FP)", "P": "НЕ (нестабилен)",
              "S": "НЕ (дубликат симптома: FN на C2)",
              "L": "RESEARCHABLE (непрерывный; порог запрещён)"}
    for cand in CANDIDATES:
        w("  %s: измерено %s | ожидание: %s | %s"
          % (cand,
             "ПРИГОДЕН" if verdicts[cand] else "НЕ пригоден",
             expect[cand],
             "совпадает" if (verdicts[cand] == (expect[cand]
                                                 == "пригоден"))
             else "РАСХОЖДЕНИЕ"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep_lines) + "\n")
    w("")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
