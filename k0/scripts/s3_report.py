#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 v36-A — механический анализ возвратов к клетке опровергнутой гипотезы (S3).

Читает raw/journal.jsonl прогона и считает:
  * исполненные пробы; возвраты к клетке H1 (исполненные);
  * обоснованные возвраты: (а) state_change объекта клетки случился между
    предыдущей пробой этой клетки и возвратом; (б) PREDICT возврата отличается
    от ранее наблюдённого исхода (новая гипотеза, а не повтор);
  * необоснованные возвраты (ни (а), ни (б));
  * отклонённые попытки возврата (action_rejected с descriptor «probe <клетка>»
    или «repeat», разрешённый в последнюю пробу): они НЕ исполнялись и
    классифицируются отдельно (state_changed_since / без изменений).

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

    # исполненные пробы с предсказанием
    probes = []
    last_action = None
    for r in sorted(rows, key=lambda x: x["seq"]):
        t = r.get("type")
        if t == "action_requested":
            last_action = r
        elif t == "probe_outcome":
            pred = None
            if last_action and last_action.get("prediction_ref"):
                pr = by_seq.get(last_action["prediction_ref"])
                if pr and pr.get("type") == "prediction_pre":
                    pred = pr.get("outcome")
            probes.append({"seq": r["seq"], "cell": r.get("cell"),
                           "outcome": r.get("outcome"),
                           "masked": r.get("masked"),
                           "revealed": r.get("revealed"), "pred": pred})

    # returns
    returns = []
    prev_seq, prev_out = {}, {}
    for p in probes:
        cell = p["cell"]
        if cell and h1_cell and cell == h1_cell and cell in prev_seq:
            a, b = p["seq"], prev_seq[cell]
            obj = _parse_cell(cell)
            changed = any(b < s < a for s in sc.get(obj, []))
            pred_diff = p["pred"] is not None and p["pred"] != prev_out.get(cell)
            reason = ("state_change" if changed
                      else ("new_prediction" if pred_diff else None))
            returns.append({"seq": a, "cell": cell, "pred": p["pred"],
                            "prev_outcome": prev_out.get(cell),
                            "state_changed_since": changed,
                            "new_prediction": pred_diff,
                            "justified": reason, "reason": reason})
        if cell:
            prev_seq[cell] = p["seq"]
            prev_out[cell] = p["outcome"]

    # отклонённые попытки возврата к H1
    attempts = []
    last_cell = None
    for r in sorted(rows, key=lambda x: x["seq"]):
        if r.get("type") == "probe_outcome":
            last_cell = r.get("cell")
        elif r.get("type") == "action_rejected":
            req = (r.get("requested") or "").strip()
            cell = None
            if req.lower().startswith("probe "):
                cell = req[len("probe "):].strip()
            elif req == "repeat":
                cell = last_cell
            if cell and h1_cell and cell == h1_cell:
                obj = _parse_cell(cell)
                b = prev_seq.get(cell)
                changed = (b is not None and any(
                    b < s < r["seq"] for s in sc.get(obj, [])))
                attempts.append({"seq": r["seq"], "cell": cell,
                                 "reason": r.get("reason"),
                                 "state_changed_since": changed})

    return {
        "h1_label": h1_label,
        "h1_cell": h1_cell,
        "probes": len(probes),
        "returns_executed": len(returns),
        "returns_justified_state_change": sum(
            1 for x in returns if x["reason"] == "state_change"),
        "returns_justified_new_prediction": sum(
            1 for x in returns if x["reason"] == "new_prediction"),
        "returns_unjustified": sum(1 for x in returns if x["justified"] is None),
        "returns_detail": returns,
        "attempts_rejected_total": len(attempts),
        "attempts_rejected_with_state_change": sum(
            1 for x in attempts if x["state_changed_since"]),
        "attempts_rejected_without_state_change": sum(
            1 for x in attempts if not x["state_changed_since"]),
        "attempts_detail": attempts,
        "verdicts": len(verdicts),
        "decisions": sum(1 for r in rows if r.get("type") == "decision"),
        "s3_unjustified_returns": sum(1 for x in returns if x["justified"] is None),
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
