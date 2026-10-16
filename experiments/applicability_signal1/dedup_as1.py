# -*- coding: utf-8 -*-
"""Дедупликация AS1_candidates.json (повторные append-партии):
оставить последнее вхождение (series, rep, ep)."""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
path = os.path.join(BASE, "experiments", "applicability_signal1",
                    "AS1_candidates.json")
rows = json.load(open(path, encoding="utf-8"))
print("до дедупликации:", len(rows), flush=True)
seen = {}
for r in rows:
    seen[(r["series"], r["rep"], r["ep"])] = r
out = [seen[k] for k in sorted(seen)]
print("после:", len(out), flush=True)
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False,
          indent=1)
from collections import Counter
print("по сериям:", dict(Counter(r["series"] for r in out)), flush=True)
