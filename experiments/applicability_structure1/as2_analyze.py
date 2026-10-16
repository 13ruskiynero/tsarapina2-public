# -*- coding: utf-8 -*-
"""AS-2 analyzer (FROZEN 06.09.2026): проекции C1 (E; V), C2 (E∧V),
C3 (вектор расхождения) на AS2_records.json. Сначала RAW-матрица,
потом метрики к GT, потом сравнение с предсказаниями, потом A/B/C.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.join(BASE, "experiments", "applicability_structure1")
OUT = os.path.join(DIR, "AS2_ANALYSIS.txt")
GT = {"w1": True, "w2": False, "wX": False, "wY": True, "noise": True}
rep_lines = []


def w(s=""):
    print(s, flush=True)
    rep_lines.append(s)


def main():
    data = json.load(open(os.path.join(DIR, "AS2_records.json"),
                          encoding="utf-8"))
    refs = data["refs"]
    recs = data["records"]
    w("=" * 72)
    w("APPLICABILITY-STRUCTURE-1 / AS-2: АНАЛИЗ (06.09.2026)")
    w("FROZEN; measurement-only; порядок: RAW → метрики → A/B/C")
    w("=" * 72)
    w("learn-эталоны: r1=%s r2=%s" % (refs["r1"], refs["r2"]))

    # RAW-матрица: сигналы и исходы по мирам и репликам
    w("")
    w("RAW (сигналы ДО действия; ok = fix-a реально вылечил):")
    w("  rep world  E       V  S  ok    GT-применим")
    for r in recs:
        s = r["signals"]
        w("  %-3s %-6s %-7s %-2s %-2s %-5s %s"
          % (r["rep"], r["world"], s["E"], s["V"], s["S"],
             "yes" if r["ok"] else "no", GT[r["world"]]))

    # метрики проекций
    w("")
    w("--- Проекции (стоп-решение = условие нарушено) ---")
    w("  классификация: VS=верный стоп, LS=ложный стоп, BL=слепота,"
      " VA=верное применение")
    rows_by = {}
    for r in recs:
        rows_by.setdefault(r["world"], []).append(r)

    def eval_cond(cond_fn):
        out = {}
        for world, rows in rows_by.items():
            for r in rows:
                stop = cond_fn(r)
                gt = GT[world]
                if not gt and stop:
                    label = "VS"
                elif gt and stop:
                    label = "LS"
                elif not gt and not stop:
                    label = "BL"
                else:
                    label = "VA"
                out.setdefault(world, []).append(label)
        return out

    c1e = eval_cond(lambda r: r["signals"]["E"] != refs[r["rep"]]["E"])
    c1v = eval_cond(lambda r: r["signals"]["V"] != refs[r["rep"]]["V"])
    c2 = eval_cond(lambda r: (r["signals"]["E"] != refs[r["rep"]]["E"])
                   or (r["signals"]["V"] != refs[r["rep"]]["V"]))
    for name, res in (("C1-E (одиночное E)", c1e),
                      ("C1-V (одиночное V)", c1v),
                      ("C2 (E ∧ V)", c2)):
        w("  %s:" % name)
        for world in ("w1", "w2", "wX", "wY", "noise"):
            labels = res.get(world, [])
            w("    %-6s %s" % (world, " ".join(labels)))

    # C3: вектор расхождения
    w("")
    w("--- C3: вектор расхождения (dE, dV) от learn-эталона ---")
    c3 = {}
    for r in recs:
        dE = 1 if r["signals"]["E"] != refs[r["rep"]]["E"] else 0
        dV = 1 if r["signals"]["V"] != refs[r["rep"]]["V"] else 0
        c3.setdefault(r["world"], []).append((dE, dV))
    for world in ("w1", "w2", "wX", "wY", "noise"):
        vecs = c3.get(world, [])
        uniq = sorted(set(vecs))
        w("  %-6s %s (уникальных: %d/%d)"
          % (world, vecs, len(uniq), len(vecs)))
    wXv = sorted(set(c3.get("wX", [])))
    wYv = sorted(set(c3.get("wY", [])))
    w("  расхождение стабильно: wX %s, wY %s" % (wXv, wYv))
    w("  wX и wY неразличимы по вектору: %s"
      % (wXv == wYv and len(wXv) == 1))

    # сравнение с предсказаниями дизайна
    w("")
    w("--- Сверка с предсказаниями (до прогона) ---")
    checks = []
    # C1-E
    checks.append(("C1-E: VS w2/wX, VA w1/wY",
                   all(x == "VS" for x in c1e["w2"]) and
                   all(x == "VS" for x in c1e["wX"]) and
                   all(x == "VA" for x in c1e["w1"]) and
                   all(x == "VA" for x in c1e["wY"])))
    # C1-V
    checks.append(("C1-V: VS w2, BL wX, LS wY",
                   all(x == "VS" for x in c1v["w2"]) and
                   all(x == "BL" for x in c1v["wX"]) and
                   all(x == "LS" for x in c1v["wY"])))
    # C2
    checks.append(("C2: VS w2/wX, LS wY (V испортил конъюнкцию)",
                   all(x == "VS" for x in c2["w2"]) and
                   all(x == "VS" for x in c2["wX"]) and
                   all(x == "LS" for x in c2["wY"])))
    # C3
    stable_wx = (len(wXv) == 1 and wXv[0] == (1, 0))
    stable_wy = (len(wYv) == 1 and wYv[0] == (0, 1))
    checks.append(("C3: расхождение стабильно (wX=(1,0) 6/6, "
                   "wY=(0,1) 6/6); направление различает миры, но "
                   "НЕ определяет GT (оба расхождения, GT "
                   "противоположны)",
                   stable_wx and stable_wy))
    for name, ok in checks:
        w("  %s %s" % ("PASS" if ok else "NOT-CONFIRMED", name))

    # A/B/C
    w("")
    w("--- Вердикт ---")
    if all(x == "VS" for x in c2["w2"]) and \
            all(x == "VS" for x in c2["wX"]) and \
            all(x == "LS" for x in c2["wY"]):
        w("C1/C2: списки условий работают как предсказано; C2 вносит "
          "ложный стоп wY (V-член) — конъюнкция пригодных сигналов "
          "наследует слепоту/ложь своих членов (A-подтверждение).")
    if stable_wx and stable_wy:
        w("C3: расхождение сигналов — УСТОЙЧИВЫЙ наблюдаемый класс "
          "(wX=(1,0) 6/6, wY=(0,1) 6/6 — B: отношение существует как "
          "отдельное наблюдаемое), но направление расхождения НЕ "
          "определяет GT: (1,0) → не применим, (0,1) → применим — "
          "одинаковый «тип» (расхождение), противоположные исходы. "
          "Кто из сигналов каузален — не выводится из пары (C-граница: "
          "нужен внешний источник или история).")
    else:
        w("C3: расхождение НЕ стабильно — проверить RAW.")
    w("")
    w("Вывод: «расхождение» не сводится к false-условию (wX и wY "
      "оба дают C2-false, а GT различаются); список условий не "
      "различает расхождение; вектор-отношение стабилен и различает "
      "направления, но решения не несёт — структура наблюдаема, "
      "каузальность сигнала из пары не выводится.")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep_lines) + "\n")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
