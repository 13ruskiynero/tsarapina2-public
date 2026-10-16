# -*- coding: utf-8 -*-
"""TEMP-F checker: буквальные проверки TEMP_FAILURE_VALIDATION §Проверки."""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
out = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out.append(line)
    print(line)


all_ok = True
for p in sorted(glob.glob(os.path.join(DIR, "TEMPF_cell_*.json"))):
    with open(p, encoding="utf-8") as f:
        rec = json.load(f)
    evs = rec["events"]
    excl = next(e for e in evs if e["event"] == "exclusion")
    kid = excl["knowledge_id"]
    trig = excl["step"]
    sols = [e for e in evs if e["event"] == "sol"]
    slots = [e for e in evs if e["event"] == "slot"]
    atts = [e for e in evs if e["event"] == "attempt"]
    eligs = [e for e in evs if e["event"] == "eligible"]
    steps = rec["steps"]
    k_app = [s for s in steps
             if s.get("step", 0) > trig and s.get("mode") != "attempt"
             and (s.get("knowledge_refs") or [None])[0] == kid]
    snap = {r["knowledge_id"]: r for r in rec["final_snapshot"]}
    chk = {
        "attempt_once": len(atts) == 1,
        "attempt_failure": bool(atts) and atts[0]["result"] != "success",
        "no_eligible_event": len(eligs) == 0,
        "K_not_reapplied": len(k_app) == 0,
        "sol_once": len(sols) == 1,
        "slot_once": len(slots) == 1,
        "slot_ref": bool(slots) and
        slots[0].get("trigger_ref") == excl.get("trigger_ref"),
        "attempt_after_sol": bool(atts) and bool(sols) and
        atts[0]["step"] > sols[0]["step"],
        "next_cycle_S2": steps[-1].get("mode") == "S2",
        "K_present_append_only": kid in snap,
        "audit": rec["audit_before"] == rec["audit_after"],
    }
    ok = all(chk.values())
    all_ok = all_ok and ok
    w("=== %s === %s" % (rec["cell"], "OK" if ok else "FAIL"))
    bad = [k for k, v in chk.items() if not v]
    if bad:
        w("    FAIL: %s" % bad)
    w("    events=%s" % [(e["event"], e.get("step"),
                          e.get("result")) for e in evs])
    w("    steps: %s" % [(s.get("step"), s.get("mode"), s.get("action"),
                          s.get("outcome"),
                          (s.get("knowledge_refs") or [None])[0][:10]
                          if (s.get("knowledge_refs") or [None])[0]
                          else None) for s in steps])
    w("")

w("TEMP-F ALL_OK=%s (клеток: %d)" % (
    all_ok, len(glob.glob(os.path.join(DIR, "TEMPF_cell_*.json")))))
with open(os.path.join(DIR, "TEMPF_CHECK.txt"), "w",
          encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
w("saved TEMPF_CHECK.txt")
