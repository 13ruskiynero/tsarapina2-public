#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v37-A — механический анализ условия H3 (пригодная открытая цель).

Читает артефакты прогона (journal.jsonl, request-файлы, rejections.json) и
считает O1–O4 в окне W по предрегистрированному критерию (K0_M3_H3_CRITERION
_DRAFT.md, ред. 2):

  O1 — валидный блок действия в окне (journal action_requested);
  O2 — исполненная проба в клетке пригодной цели (journal probe_outcome);
  O3 — повторные попытки регистрации Q1/H1 в окне (rejections);
  O4 — попытки новых целей агентом в окне (journal + rejections).

Классификация строго по таблице критерия; исходы вне таблицы — unclassified
(без переклассификации). Только чтение; сеть/модель не используются.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _call_num(entry):
    """'0012_F2_a1' -> 12; None, если не распознано."""
    c = entry.get("call") if isinstance(entry, dict) else None
    if not c:
        return None
    try:
        return int(str(c).split("_")[0])
    except ValueError:
        return None


def analyze(rows, requests, rejections):
    goal = next((r for r in rows if r.get("type") == "goal"), None)
    if goal is None:
        return {"status": "uninformative_no_goal",
                "reason": "в журнале нет записи goal"}
    if not goal.get("eligible"):
        return {"status": "uninformative_goal",
                "reason": goal.get("reason", ""), "goal": goal}

    goal_cell = goal.get("cell")
    goal_call = goal.get("call")
    if not isinstance(goal_call, int) or goal_call <= 0:
        return {"status": "uninformative_no_call",
                "reason": "у записи goal нет номера вызова", "goal": goal}

    # окно W: первые до 5 подряд вызовов после внедрения цели, в контексте
    # которых цель видна (список гипотез содержит клетку цели)
    window = []
    n = goal_call + 1
    while len(window) < 5:
        d = requests.get(n)
        if d is None:
            break
        hyps = d.get("hypotheses") or []
        if not any(h.get("cell") == goal_cell for h in hyps):
            break
        window.append(n)
        n += 1

    if len(window) < 3:
        return {"status": "uninformative_data", "window": window,
                "goal_call": goal_call, "goal_cell": goal_cell,
                "reason": "менее 3 вызовов с видимой пригодной целью"}

    qh = [x for x in rejections if x.get("kind") in ("question", "hypothesis")]
    o1 = any(r.get("type") == "action_requested" and r.get("call") in window
             for r in rows)
    o2 = any(r.get("type") == "probe_outcome" and r.get("call") in window
             and r.get("cell") == goal_cell for r in rows)
    o3 = sum(1 for x in qh if _call_num(x) in window
             and x.get("requested") in ("Q1", "H1"))
    o4 = 0
    for r in rows:
        if (r.get("type") in ("question", "hypothesis")
                and r.get("call") in window
                and r.get("origin") == "agent"):
            o4 += 1
    for x in qh:
        if _call_num(x) in window and x.get("requested") not in ("Q1", "H1"):
            o4 += 1

    if o1 and o2 and o3 == 0:
        status = "supports_H3"
    elif o1 and not o2 and o3 == 0:
        status = "H3_partial"
    elif not o1 and o3 > 0:
        status = "H3_not_supported"
    elif not o1 and o3 == 0 and o4 > 0:
        status = "uninformative_behavior"
    else:
        status = "unclassified"

    return {
        "status": status,
        "goal_call": goal_call,
        "goal_cell": goal_cell,
        "window": window,
        "window_size": len(window),
        "O1_valid_action": bool(o1),
        "O2_goal_cell_probe": bool(o2),
        "O3_q1h1_duplicates": o3,
        "O4_new_goal_attempts": o4,
    }


def load_run(run_dir):
    run_dir = Path(run_dir)
    rows = []
    jp = run_dir / "raw" / "journal.jsonl"
    for line in jp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    requests = {}
    calls_dir = run_dir / "raw" / "calls"
    for p in sorted(calls_dir.glob("*.request.txt")):
        n = int(p.name.split("_")[0])
        requests[n] = json.loads(p.read_text(encoding="utf-8"))
    rj_path = run_dir / "derived" / "rejections.json"
    rejections = (json.loads(rj_path.read_text(encoding="utf-8"))
                  if rj_path.exists() else [])
    return rows, requests, rejections


def main(argv=None):
    ap = argparse.ArgumentParser(description="K0 H3-анализ (пригодная цель)")
    ap.add_argument("run_dir", help="путь к каталогу прогона")
    ap.add_argument("--json", action="store_true", help="вывод JSON")
    args = ap.parse_args(argv)
    rep = analyze(*load_run(args.run_dir))
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("status:", rep["status"])
        for k in ("goal_call", "goal_cell", "window", "O1_valid_action",
                  "O2_goal_cell_probe", "O3_q1h1_duplicates",
                  "O4_new_goal_attempts", "reason"):
            if k in rep:
                print(f"  {k}: {rep[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
