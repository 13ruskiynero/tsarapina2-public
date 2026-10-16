# -*- coding: utf-8 -*-
"""TEMP-F runner: failure-ветка verification slot (тонкий адаптер
поверх ep2b_driver; механика — та же, новые среды только добавляются).

Клетка: --cell "TempF|TEMP|R|r1".
"""
import argparse
import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import ep2b_driver as base  # noqa: E402

base.HISTORIES["TempF"] = (
    [("w1", "1"), ("w1", "2")],
    [("f", "1", "w1", "n"),      # 1: шум → триггер C5; exclusion(K2)
     ("s", "1", "w1", None),     # 2: K1 → success → SOL; slot(K2)
     ("f", "1", "w2", None),     # 3: attempt(K2) → w2 → FAILURE
     ("f", "1", "w2", None)])    # 4: обычный цикл (sibling K3)
base.TRIGGERS["TempF"] = "C5"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    a = ap.parse_args()
    cell = a.cell
    assert cell.startswith("TempF|"), "cell: TempF|TEMP|R|r1"
    rec = base.run_cell(cell)
    out = os.path.join(DIR, "TEMPF_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    evs = [(e["event"], e.get("step"), e.get("result"))
           for e in rec["events"]]
    print("saved %s; steps=%d; events=%s" % (out, len(rec["steps"]), evs))


if __name__ == "__main__":
    main()
