# -*- coding: utf-8 -*-
"""view_te_log.py — трассы DOUBLE/MIX из GATE_V05_te.log."""
import json
import os

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "gate_v05_data")
path = os.path.join(DIR, "GATE_V05_te.log")
rows = []
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except ValueError:
        pass
for r in rows:
    if r.get("series") in ("DOUBLE", "MIX") and r.get("event") in (
            "EPISODE", "EXPLORE", "SUGGEST", "RESULT"):
        print(r.get("series"), r.get("event"),
              r.get("ep") or r.get("i") or "",
              r.get("strategy", ""), r.get("cmd", ""),
              r.get("outcome", ""), "tr:", r.get("transition"),
              flush=True)
