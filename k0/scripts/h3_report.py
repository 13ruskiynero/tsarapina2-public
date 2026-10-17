#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v37-A — механический анализ условия H3 (пригодная открытая цель).

Ред. 2 (2026-10-17, по замечаниям независимого ревью):
  1) различаются три состояния: проба в целевой клетке / проба в другой клетке /
     отсутствие исполненной пробы; последнее — unclassified (таблица критерия
     такого случая не предусматривает);
  2) успех проверяется по СВЯЗКЕ «принятое действие → исполненная проба» по
     контракту журнала §11: action_requested → probe_outcome → budget
     (action_ref = seq действия); проба должна быть раскрытой (revealed);
  3) окно W — строго по определению критерия: подряд идущие вызовы после K,
     каждый — фаза F2, цель видна в контексте (hypotheses); иных условий окно
     не добавляет (окно не является фильтром по результату и не закрывается
     при отсутствии действий).

Ред. 3 (2026-10-17, по замечанию ревью): O3 — число ПАР Q1/H1 по правилу
связывания (Q1+H1 в одном вызове, пары = min; одиночные — отдельный счётчик).
Ред. 4 (2026-10-17, по замечанию ревью): отказы читаются по ФАКТИЧЕСКОЙ схеме
derived/rejections.json — поле label (requested — запасной вариант); отказы
вердиктов (kind=verdict, label=None) не попадают ни в O3, ни в O4.

Вход: journal.jsonl, request-файлы, rejections.json. Только чтение.
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


def _rej_label(x):
    """Метка отказа: фактическая схема derived/rejections.json — label;
    requested принимается как запасной вариант (совместимость)."""
    return x.get("label") or x.get("requested")


def _pairs(rows):
    """Пары «действие → проба» по контракту §11.

    probe_outcome не несёт action_ref; связка позиционно-контрактная:
    action_requested(seq A) → [probe_outcome] → budget(action_ref=A).
    """
    budgets = {r.get("action_ref"): r for r in rows if r.get("type") == "budget"}
    probes = [r for r in rows if r.get("type") == "probe_outcome"]
    pairs = []
    for a in rows:
        if a.get("type") != "action_requested":
            continue
        b = budgets.get(a["seq"])
        po = None
        if b is not None:
            cand = [p for p in probes if a["seq"] < p["seq"] < b["seq"]]
            po = cand[-1] if cand else None
        pairs.append({"action": a, "probe": po, "completed": b is not None})
    return pairs


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

    acts = [r for r in rows if r.get("type") == "action_requested"]
    budgets = {r.get("action_ref"): r for r in rows if r.get("type") == "budget"}

    # окно W: подряд идущие вызовы после K, все условия определения
    window = []
    n = goal_call + 1
    while len(window) < 5:
        d = requests.get(n)
        if d is None or d.get("phase") != "F2":
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

    pairs = _pairs(rows)
    # O1 — только ЗАВЕРШЁННЫЕ действия по контракту §11 (есть budget)
    pairs_in = [p for p in pairs if p["completed"]
                and p["action"].get("call") in window]
    with_probe = [p for p in pairs_in if p["probe"] is not None]
    goal_revealed = [p for p in with_probe
                     if p["probe"].get("cell") == goal_cell
                     and p["probe"].get("revealed")]
    goal_masked = [p for p in with_probe
                   if p["probe"].get("cell") == goal_cell
                   and not p["probe"].get("revealed")]
    other_cell = [p for p in with_probe if p["probe"].get("cell") != goal_cell]

    qh = [x for x in rejections if x.get("kind") in ("question", "hypothesis")]
    o1 = bool(pairs_in)                    # принятое действие (блок исполнен)
    o2 = bool(goal_revealed)               # раскрытая проба ровно в клетке цели
    # O3 — число ПАР повторных попыток Q1/H1 (правило связывания, критерий §3):
    # в пределах одного вызова одна отклонённая QUESTION Q1 + одна отклонённая
    # HYPOTHESIS H1 = одна пара; пары = сумма min(Q,H) по вызовам; одиночные
    # записи (без пары) считаются отдельно и в O3 не входят.
    _qh = {}
    for _x in qh:
        _c = _call_num(_x)
        if _c in window and _rej_label(_x) in ("Q1", "H1"):
            _d = _qh.setdefault(_c, {"Q": 0, "H": 0})
            _d["Q" if _x.get("kind") == "question" else "H"] += 1
    o3 = sum(min(_d["Q"], _d["H"]) for _d in _qh.values())
    o3_singles = sum(abs(_d["Q"] - _d["H"]) for _d in _qh.values())
    o4 = 0
    for r in rows:
        if (r.get("type") in ("question", "hypothesis")
                and r.get("call") in window
                and r.get("origin") == "agent"):
            o4 += 1
    for x in qh:
        _l = _rej_label(x)
        if _call_num(x) in window and _l and _l not in ("Q1", "H1"):
            o4 += 1

    if o1 and o2 and o3 == 0:
        status = "supports_H3"
    elif not o1 and o3 > 0:
        status = "H3_not_supported"
    elif not o1 and o3 == 0 and o4 > 0:
        status = "uninformative_behavior"
    elif o1 and o3 == 0 and other_cell and not goal_revealed and not goal_masked:
        status = "H3_partial"
    else:
        # сюда попадают в т.ч.: действие без исполненной пробы; проба в клетке
        # цели без раскрытия; действие + дубли Q1/H1; прочие непокрытые случаи
        status = "unclassified"

    return {
        "status": status,
        "goal_call": goal_call,
        "goal_cell": goal_cell,
        "window": window,
        "window_size": len(window),
        "O1_valid_action": bool(o1),
        "O2_goal_cell_probe": bool(o2),
        "O3_q1h1_pairs": o3,
        "O3_q1h1_singles": o3_singles,
        "O4_new_goal_attempts": o4,
        "pairs_in_window": len(pairs_in),   # только завершённые (есть budget)
        "probes_in_window": len(with_probe),
        "goal_cell_probes": len(goal_revealed) + len(goal_masked),
        "goal_cell_probes_masked": len(goal_masked),
        "other_cell_probes": len(other_cell),
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
                  "O2_goal_cell_probe", "O3_q1h1_pairs", "O3_q1h1_singles",
                  "O4_new_goal_attempts", "probes_in_window",
                  "goal_cell_probes_masked", "reason"):
            if k in rep:
                print(f"  {k}: {rep[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
