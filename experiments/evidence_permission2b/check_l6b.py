# -*- coding: utf-8 -*-
"""EP-2B: краткий L6-чек по финальным снапшотам 48 клеток."""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
n = bad_aw = bad_src = bad_refs = 0
gens = 0
bad_cells = []
for p in sorted(glob.glob(os.path.join(DIR, "EP2B_cell_*.json"))):
    with open(p, encoding="utf-8") as f:
        r = json.load(f)
    cell_bad = 0
    for k in r["final_snapshot"]:
        n += 1
        ctx = k.get("context") or ""
        is_fail = "outcome=" in ctx and "outcome=success" not in ctx
        if is_fail and k.get("applicable_when") is not None:
            bad_aw += 1
            cell_bad += 1
        for o in (k.get("applicability_observations") or []):
            if o.get("source") not in ("verified success",
                                       "verified failure"):
                bad_src += 1
                cell_bad += 1
            if not o.get("episode_refs"):
                bad_refs += 1
                cell_bad += 1
        if k.get("lineage_generation") is not None:
            gens += 1
    if cell_bad:
        bad_cells.append(os.path.basename(p))
print("rows=%d gens=%d bad_aw=%d bad_src=%d bad_refs=%d"
      % (n, gens, bad_aw, bad_src, bad_refs))
print("bad_cells=%s" % (bad_cells or "нет"))
