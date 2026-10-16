# -*- coding: utf-8 -*-
"""Инспектор якорного прогона EP-1 (временный)."""
import json
import sys

r = json.load(open(sys.argv[1]))
print("cell:", r["cell"])
print("learn:", r["learn"])
for s in r["steps"]:
    print("step", s["step"], s.get("mode"), s.get("action"),
          s.get("outcome"), "sid", s.get("strategy_id"))
print("trigger:", r["trigger"], "intervention:", r["intervention"])
print("final members (a,absent,fix-a):")
for m in r["line_trace"][-1]:
    print(" ", m["kid"][:12], m["outcome"], m["aw"], m["kinds"],
          "gen", m["gen"])
print("snapshot rows:", len(r["final_snapshot"]))
for x in r["final_snapshot"]:
    print(" ", x["knowledge_id"][:12], x.get("lineage_generation"),
          (x.get("applicable_when") or {}), x.get("schema_version"))
