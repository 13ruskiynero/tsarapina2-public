# -*- coding: utf-8 -*-
"""EP-2C analyzer (FROZEN 10.09.2026).

Читает EP2C_cell_*.json (RAW ×40: 32 core-роли + 8 negative).
Проверки: explore_activated по unit; causality s3→explore;
K-невозврат (checks + refs); TEMP: slot не создан Explore;
exclusion counts (U5b=2, 1 stress); NEG: неактивация; r1≡r2;
R≡S; audit. Пишет EP2C_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
UNITS = ["U1", "U2", "U3", "U4", "U5a", "U5b", "U6a", "U6b"]
NEG = ["NEG-E6N-V3", "NEG-E6S"]
TEMP_UNITS = ("U6a", "U6b")
EXPECT_EXPLORE = {"U1": True, "U2": True, "U3": True, "U4": True,
                  "U5a": False, "U5b": True, "U6a": True, "U6b": True,
                  "NEG-E6N-V3": False, "NEG-E6S": False}
out = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out.append(line)
    print(line)


def load(cell):
    p = os.path.join(DIR, "EP2C_cell_%s.json" % cell.replace("|", "_"))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def analyze(rec):
    evs = rec["events"]
    excl = [e for e in evs if e["event"] == "exclusion"]
    s3 = [e for e in evs if e["event"] == "s3_detected"]
    exp = [e for e in evs if e["event"] == "explore"]
    sols = [e for e in evs if e["event"] == "sol"]
    slots = [e for e in evs if e["event"] == "slot"]
    atts = [e for e in evs if e["event"] == "attempt"]
    kid = excl[0]["knowledge_id"] if excl else None
    trig = excl[0]["step"] if excl else None
    k_auto = [s for s in rec["steps"]
              if s.get("step", 0) > trig and s.get("mode") == "S2"
              and (s.get("knowledge_refs") or [None])[0] == kid]
    chk_k = [c for c in rec["checks"]
             if c.get("type") == "post_explore_k_not_returned"]
    a = {
        "cell": rec["cell"], "unit": rec["unit"], "sem": rec["sem"],
        "right": rec["right"], "rep": rec["rep"], "role": rec["role"],
        "excl_count": len(excl),
        "stress_flags": [e.get("stress") for e in excl],
        "s3_count": len(s3), "explore_count": len(exp),
        "explore_activated": len(exp) > 0,
        "causality": (len(s3) == len(exp)) and all(
            exp[i]["step"] == s3[i]["step"] + 1 for i in range(len(exp))),
        "sol_count": len(sols), "slot_count": len(slots),
        "attempt_count": len(atts),
        "k_auto_applied": len(k_auto),
        "k_not_returned": all(c.get("k_absent") for c in chk_k)
        if chk_k else None,
        "new_candidate": exp[0].get("new_candidate") if exp else None,
        "new_candidate_ne_k": (exp[0].get("new_candidate") != kid)
        if exp else None,
        "audit": rec["audit_before"] == rec["audit_after"],
    }
    a["ok"] = (a["audit"] and a["k_auto_applied"] == 0
               and a["explore_activated"] == EXPECT_EXPLORE[rec["unit"]]
               and (a["causality"] if exp else True)
               and (a["k_not_returned"] in (True, None)))
    if rec["unit"] in TEMP_UNITS:
        a["slot_created_by_explore"] = (len(slots) == 0
                                        and len(sols) == 0
                                        and len(atts) == 0)
        a["ok"] = a["ok"] and a["slot_created_by_explore"]
    return a


def main():
    data = {}
    for u in UNITS + NEG:
        sem = "TEMP" if u in TEMP_UNITS else "POOL"
        for rt in ("R", "S"):
            for rep in ("r1", "r2"):
                rec = load("%s|%s|%s|%s" % (u, sem, rt, rep))
                data[rec["cell"]] = analyze(rec)
    w("EP-2C: АНАЛИЗ (%d уникальных клеток; PROTOCOL §5)" % len(data))
    w("")
    bad = []
    for u in UNITS + NEG:
        sem = "TEMP" if u in TEMP_UNITS else "POOL"
        for rt in ("R", "S"):
            for rep in ("r1", "r2"):
                a = data["%s|%s|%s|%s" % (u, sem, rt, rep)]
                if not a["ok"]:
                    bad.append(a["cell"])
                w("=== %s === explore=%s s3=%d excl=%d%s caus=%s "
                  "k_auto=%d k_not_ret=%s slot_by_explore=%s audit=%s"
                  % (a["cell"], a["explore_activated"], a["s3_count"],
                     a["excl_count"],
                     "(stress)" if a["stress_flags"] and
                     any(a["stress_flags"]) else "",
                     a["causality"], a["k_auto_applied"],
                     a["k_not_returned"],
                     a.get("slot_created_by_explore", "-"),
                     a["audit"]))
    w("")
    w("=== СВОДКА (explore_activated; ожидание) ===")
    for u in UNITS + NEG:
        sem = "TEMP" if u in TEMP_UNITS else "POOL"
        acts = [data["%s|%s|%s|%s" % (u, sem, rt, rep)][
            "explore_activated"] for rt in ("R", "S") for rep in
            ("r1", "r2")]
        w("  %-11s role=%-15s explore=%s (expect %s) %s"
          % (u, data["%s|%s|R|r1" % (u, sem)]["role"],
             set(acts) == {True} and "АКТИВЕН" or
             (set(acts) == {False} and "не активирован" or acts),
             EXPECT_EXPLORE[u],
             "OK" if set(acts) == {EXPECT_EXPLORE[u]} else "FAIL"))
    w("")
    w("=== ДЕТЕРМИНИЗМ / R≡S ===")
    det_ok = True
    rs_ok = True
    for u in UNITS + NEG:
        sem = "TEMP" if u in TEMP_UNITS else "POOL"
        for rt in ("R", "S"):
            a1 = data["%s|%s|%s|r1" % (u, sem, rt)]
            a2 = data["%s|%s|%s|r2" % (u, sem, rt)]
            same = [a1[k] for k in ("explore_activated", "s3_count",
                                    "explore_count", "excl_count")] == \
                [a2[k] for k in ("explore_activated", "s3_count",
                                 "explore_count", "excl_count")]
            det_ok = det_ok and same
        ar = data["%s|%s|R|r1" % (u, sem)]
        as_ = data["%s|%s|S|r1" % (u, sem)]
        rs = [ar[k] for k in ("explore_activated", "s3_count",
                              "explore_count", "excl_count")] == \
            [as_[k] for k in ("explore_activated", "s3_count",
                              "explore_count", "excl_count")]
        rs_ok = rs_ok and rs
    w("  r1≡r2 (все): %s; R≡S (все): %s" % (det_ok, rs_ok))
    w("")
    w("=== ВЕРДИКТЫ ===")
    w("S3→Explore causality: все explore-события на шаг после "
      "s3_detected; K-невозврат: %s" %
      all(data[k]["k_not_returned"] in (True, None) for k in data))
    w("Нерефлекс: U5a/NEG (pool не пуст) — explore не активирован: %s"
      % all(not data["%s|POOL|%s|%s" % (u, rt, rep)][
          "explore_activated"] for u in ("U5a", "NEG-E6N-V3",
                                         "NEG-E6S")
          for rt in ("R", "S") for rep in ("r1", "r2")))
    w("TEMP-разделение прав (Explore не создаёт slot; U6a/U6b): %s"
      % all(data[k].get("slot_created_by_explore") for k in data
            if data[k]["sem"] == "TEMP"))
    w("U5b boundary (2 exclusion, 1 stress): %s"
      % all(data["U5b|POOL|%s|%s" % (rt, rep)]["excl_count"] == 2 and
            any(data["U5b|POOL|%s|%s" % (rt, rep)]["stress_flags"])
            for rt in ("R", "S") for rep in ("r1", "r2")))
    w("Нарушений: %d %s" % (len(bad), bad if bad else ""))
    w("")
    w("Интеграл (алгебра прав): evidence → R/S → {POOL|TEMP} → "
      "candidate absence → S3 → Explore; Explore — не TEMP slot; "
      "новый candidate — fix-aq-линия; NEG — «не рефлекс».")
    w("Слои v0.6.x не изменялись (audit 40/40=%s)." %
      all(a["audit"] for a in data.values()))
    with open(os.path.join(DIR, "EP2C_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    w("")
    w("saved EP2C_ANALYSIS.txt")


if __name__ == "__main__":
    main()
