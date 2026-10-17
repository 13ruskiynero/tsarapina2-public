#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v36-A — механический анализ возвратов к клетке опровергнутой гипотезы (S3).

Ред. 2 (2026-10-17, по замечаниям ревью):
  (1) основания обоснованного возврата считаются НЕЗАВИСИМО: state_change и
      new_prediction — два отдельных флага; общий счётчик обоснованных —
      объединение (без задвоения);
  (2) отклонённые попытки классифицируются по состоянию НА МОМЕНТ попытки:
      журнал обходится строго по seq, «последняя исполненная проба» берётся
      из уже пройденного префикса (а не из итогового словаря будущих проб).

Читает raw/journal.jsonl прогона и считает:
  * исполненные пробы; возвраты к клетке H1 (исполненные);
  * обоснованные возвраты: (а) state_change объекта клетки случился между
    предыдущей пробой этой клетки и возвратом; (б) PREDICT возврата отличается
    от ранее наблюдённого исхода (новая гипотеза, а не повтор);
  * необоснованные возвраты (ни (а), ни (б));
  * отклонённые попытки возврата (action_rejected с descriptor «probe <клетка>»
    или «repeat», разрешённый в последнюю исполненную пробу НА ТОТ МОМЕНТ):
    они НЕ исполнялись и классифицируются отдельно.

Только чтение журнала; сеть и модель не используются. Детерминированный отчёт.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_cell(text: str):
    """'O3 T=2 H=0' -> ('O3',). Для state_change достаточно object_id."""
    if not text:
        return None
    parts = text.split()
    return parts[0] if parts else None


def analyze(rows):
    by_seq = {r["seq"]: r for r in rows}

    hyps = {r.get("label"): r for r in rows if r.get("type") == "hypothesis"}
    verdicts = [r for r in rows if r.get("type") == "verdict"]
    refuted = [v for v in verdicts if v.get("resolution") == "refuted"]
    h1_label, h1_cell = None, None
    if refuted:
        h1_label = refuted[0].get("h_label")
        h1_cell = (hyps.get(h1_label) or {}).get("cell")

    # state_change: seq-и по object_id
    sc = {}
    for r in rows:
        if r.get("type") == "state_change":
            for ch in r.get("changes", []):
                sc.setdefault(ch.get("object_id"), []).append(r["seq"])

    returns = []
    attempts = []
    probe_count = 0
    prev_seq, prev_out = {}, {}      # только префикс журнала (строго по seq)
    last_action = None
    last_cell = None

    for r in sorted(rows, key=lambda x: x["seq"]):
        t = r.get("type")

        if t == "action_requested":
            last_action = r

        elif t == "probe_outcome":
            probe_count += 1
            cell = r.get("cell")
            pred = None
            if last_action and last_action.get("prediction_ref"):
                pr = by_seq.get(last_action["prediction_ref"])
                if pr and pr.get("type") == "prediction_pre":
                    pred = pr.get("outcome")
            if cell and h1_cell and cell == h1_cell and cell in prev_seq:
                a, b = r["seq"], prev_seq[cell]
                obj = _parse_cell(cell)
                changed = any(b < s < a for s in sc.get(obj, []))
                pred_diff = pred is not None and pred != prev_out.get(cell)
                returns.append({"seq": a, "cell": cell, "pred": pred,
                                "prev_outcome": prev_out.get(cell),
                                "state_changed_since": changed,
                                "new_prediction": pred_diff,
                                "justified": bool(changed or pred_diff)})
            if cell:
                prev_seq[cell] = r["seq"]
                prev_out[cell] = r["outcome"]
                last_cell = cell

        elif t == "action_rejected":
            req = (r.get("requested") or "").strip()
            cell = None
            if req.lower().startswith("probe "):
                cell = req[len("probe "):].strip()
            elif req == "repeat":
                cell = last_cell
            if cell and h1_cell and cell == h1_cell:
                obj = _parse_cell(cell)
                b = prev_seq.get(cell)          # последняя проба ДО этой попытки
                changed = (b is not None and any(
                    b < s < r["seq"] for s in sc.get(obj, [])))
                attempts.append({"seq": r["seq"], "cell": cell,
                                 "reason": r.get("reason"),
                                 "state_changed_since": changed})

    justified_sc = sum(1 for x in returns if x["state_changed_since"])
    justified_np = sum(1 for x in returns if x["new_prediction"])
    justified_total = sum(1 for x in returns if x["justified"])
    unjustified = sum(1 for x in returns if not x["justified"])

    return {
        "h1_label": h1_label,
        "h1_cell": h1_cell,
        "probes": probe_count,
        "returns_executed": len(returns),
        "returns_justified_state_change": justified_sc,
        "returns_justified_new_prediction": justified_np,
        "returns_justified_total": justified_total,
        "returns_unjustified": unjustified,
        "returns_detail": returns,
        "attempts_rejected_total": len(attempts),
        "attempts_rejected_with_state_change": sum(
            1 for x in attempts if x["state_changed_since"]),
        "attempts_rejected_without_state_change": sum(
            1 for x in attempts if not x["state_changed_since"]),
        "attempts_detail": attempts,
        "verdicts": len(verdicts),
        "decisions": sum(1 for r in rows if r.get("type") == "decision"),
        "s3_unjustified_returns": unjustified,
        "s3_note": ("возвратов не было — критерий вакуумно"
                    if not returns else ""),
    }


def load_journal(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="K0 S3-анализ возвратов к клетке H1")
    ap.add_argument("journal", help="путь к raw/journal.jsonl")
    ap.add_argument("--json", action="store_true", help="вывод JSON")
    args = ap.parse_args(argv)
    rep = analyze(load_journal(args.journal))
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print("h1_cell:", rep["h1_cell"], "| probes:", rep["probes"])
        print("returns executed:", rep["returns_executed"],
              "| justified(state_change):", rep["returns_justified_state_change"],
              "| justified(new_prediction):", rep["returns_justified_new_prediction"],
              "| justified(total):", rep["returns_justified_total"],
              "| unjustified:", rep["returns_unjustified"])
        print("attempts rejected:", rep["attempts_rejected_total"],
              "| with state change:", rep["attempts_rejected_with_state_change"],
              "| without:", rep["attempts_rejected_without_state_change"])
        print("verdicts:", rep["verdicts"], "| decisions:", rep["decisions"])
        if rep["s3_note"]:
            print("S3:", rep["s3_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
