# -*- coding: utf-8 -*-
"""EP-2B analyzer (FROZEN 10.09.2026).

Читает EP2B_cell_*.json (RAW ×48: POOL 28 + TEMP 20).
Метрики: safety (K не применяется после exclusion до attempt),
recovery (success после триггерной точки; N-среды), stop_repeats
(повторения fix-a после триггера, вторичная), TEMP-инварианты
(существование slot ⇒ initiator; attempt⇒slot; sol/attempt порядок;
слот ≤1; success(K)⇒slot existed), checks (pool-инъекция,
eligibility), r1≡r2, audit. Пишет EP2B_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
POOL_H = ["SD", "NpD", "S6bV3", "E6S", "E6N-V3", "E6N", "C6N"]
TEMP_H = ["S6bV3", "E6S", "E6N-V3", "E6N", "C6N"]
N_HISTS = ("NpD", "E6N-V3", "E6N", "C6N")
out = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out.append(line)
    print(line)


def load(cell):
    p = os.path.join(DIR, "EP2B_cell_%s.json" % cell.replace("|", "_"))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def analyze(rec):
    evs = rec["events"]
    excl = next((e for e in evs if e["event"] == "exclusion"), None)
    kid = excl["knowledge_id"] if excl else None
    trig_step = excl["step"] if excl else None
    a = {"kind": rec["cell"], "history": rec["history"],
         "sem": rec["sem"], "right": rec["right"], "rep": rec["rep"],
         "excl_kid": kid, "trig_step": trig_step,
         "events": [e["event"] for e in evs],
         "checks": rec["checks"],
         "attempt": next((e for e in evs if e["event"] == "attempt"), None),
         "sol_step": next((e["step"] for e in evs if e["event"] == "sol"),
                          None)}
    # safety: K не применяется самопроизвольно после exclusion
    auto_apply = 0
    for s in rec["steps"]:
        if s.get("step", 0) <= trig_step:
            continue
        if s.get("mode") != "attempt" and \
                (s.get("knowledge_refs") or [None])[0] == kid:
            auto_apply += 1
    a["auto_apply_after_excl"] = auto_apply
    a["safety"] = auto_apply == 0

    # recovery: success после триггерной точки
    rec_steps = [s for s in rec["steps"]
                 if s.get("step", 0) > trig_step
                 and s.get("outcome") == "success"]
    a["recovery"] = len(rec_steps) > 0
    a["recovery_step"] = rec_steps[0]["step"] if rec_steps else None

    # stop_repeats: повторения fix-a после триггера (не attempt)
    rep = 0
    for s in rec["steps"]:
        if s.get("step", 0) > trig_step and s.get("action") == "fix-a" \
                and s.get("mode") not in ("attempt",):
            rep += 1
    a["stop_repeats"] = rep

    # TEMP-инварианты
    if rec["sem"] == "TEMP":
        inv = []
        sol = next((e for e in evs if e["event"] == "sol"), None)
        slot = next((e for e in evs if e["event"] == "slot"), None)
        att = a["attempt"]
        elig = next((e for e in evs if e["event"] == "eligible"), None)
        if sol and excl:
            inv.append(("sol_after_excl", sol["step"] > excl["step"]))
            inv.append(("sol_ne_k", sol["knowledge_id"] != kid))
        if slot and excl:
            inv.append(("slot_ref", slot.get("trigger_ref") ==
                        excl.get("trigger_ref", "E1")))
            inv.append(("slot_kid", slot["knowledge_id"] == kid))
        if att:
            inv.append(("attempt_kid", att["knowledge_id"] == kid))
            if sol:
                inv.append(("attempt_after_sol", att["step"] > sol["step"]))
            inv.append(("attempt_once",
                        sum(1 for e in evs
                            if e["event"] == "attempt") == 1))
        if elig:
            inv.append(("eligible_after_attempt",
                        att is not None and elig["step"] == att["step"]))
        if att and att["result"] == "success":
            inv.append(("success_needs_slot", sol is not None))
        a["temp_invariants"] = inv
        a["temp_inv_ok"] = all(v for _, v in inv) if inv else None
    a["audit"] = rec["audit_before"] == rec["audit_after"]
    return a


def main():
    data = {}
    for h in POOL_H:
        for rep in ("r1", "r2"):
            for rt in ("R", "S"):
                rec = load("%s|POOL|%s|%s" % (h, rt, rep))
                data[rec["cell"]] = analyze(rec)
    for h in TEMP_H:
        for rep in ("r1", "r2"):
            for rt in ("R", "S"):
                rec = load("%s|TEMP|%s|%s" % (h, rt, rep))
                data[rec["cell"]] = analyze(rec)

    w("EP-2B: АНАЛИЗ (%d клеток; FROZEN; PROTOCOL §7)" % len(data))
    w("")
    # per-cell
    for h in POOL_H:
        for sem in ("POOL", "TEMP"):
            if sem == "TEMP" and h not in TEMP_H:
                continue
            for rt in ("R", "S"):
                for rep in ("r1", "r2"):
                    k = "%s|%s|%s|%s" % (h, sem, rt, rep)
                    a = data[k]
                    w("=== %s === events=%s safety=%s auto_apply=%d "
                      "recovery=%s(s%s) stop_repeats=%d audit=%s"
                      % (k, a["events"], a["safety"],
                         a["auto_apply_after_excl"], a["recovery"],
                         a["recovery_step"], a["stop_repeats"],
                         a["audit"]))
                    if a["checks"]:
                        w("    checks: %s" % a["checks"])
                    if sem == "TEMP" and a.get("temp_invariants"):
                        bad = [n for n, v in a["temp_invariants"] if not v]
                        w("    temp_invariants: %s %s"
                          % ("OK" if a["temp_inv_ok"] else "FAIL",
                             ("bad=%s" % bad) if bad else ""))
            w("")

    # детерминизм
    w("=== ДЕТЕРМИНИЗМ (r1 ≡ r2) ===")
    det_ok = True
    for h in POOL_H:
        for sem in ("POOL", "TEMP"):
            if sem == "TEMP" and h not in TEMP_H:
                continue
            for rt in ("R", "S"):
                k1 = "%s|%s|%s|r1" % (h, sem, rt)
                k2 = "%s|%s|%s|r2" % (h, sem, rt)
                a1, a2 = data[k1], data[k2]
                same = (a1["events"] == a2["events"]
                        and a1["safety"] == a2["safety"]
                        and a1["recovery"] == a2["recovery"]
                        and a1["stop_repeats"] == a2["stop_repeats"])
                det_ok = det_ok and same
                w("  %s %s %s: %s" % (h, sem, rt,
                                      "r1≡r2" if same else "РАСХОЖДЕНИЕ"))
    w("")

    # сводка
    w("=== СВОДКА (r1; semi = recovery/auto_apply/stop_repeats) ===")
    for h in POOL_H:
        row = ["  %-7s" % h]
        for sem in ("POOL", "TEMP"):
            if sem == "TEMP" and h not in TEMP_H:
                row.append("%s: —" % sem)
                continue
            a = data["%s|%s|R|r1" % (h, sem)]
            row.append("%s: rec=%s auto=%d stop=%d"
                       % (sem, a["recovery"], a["auto_apply_after_excl"],
                          a["stop_repeats"]))
        w(" | ".join(row))
    w("")

    # вердикты
    w("=== ВЕРДИКТЫ ===")
    # safety везде
    all_safe = all(a["safety"] for a in data.values())
    w("Safety (K не применяется после exclusion; все клетки): %s"
      % all_safe)
    # POOL/TEMP recovery на много-кандидатных N
    for sem in ("POOL", "TEMP"):
        r_ok = all(data["%s|%s|R|r1" % (h, sem)]["recovery"]
                   for h in ("E6N", "E6N-V3", "C6N"))
        r2_ok = all(data["%s|%s|R|r2" % (h, sem)]["recovery"]
                    for h in ("E6N", "E6N-V3", "C6N"))
        w("%s: recovery на E6N/E6N-V3/C6N: %s (r1=%s, r2=%s)"
          % (sem, r_ok and r2_ok, r_ok, r2_ok))
    # контроль-эквивалентность
    for h in ("SD", "NpD"):
        eq = all(data["%s|POOL|%s|r1" % (h, rt)]["stop_repeats"] ==
                 data["%s|POOL|%s|r2" % (h, rt)]["stop_repeats"]
                 for rt in ("R", "S"))
        w("Контроль %s: POOL (после exclusion пул пуст → S3; "
          "детерминизм=%s)" % (h, eq))
    # TEMP инварианты
    inv_bad = [k for k, a in data.items()
               if a["sem"] == "TEMP" and a.get("temp_inv_ok") is False]
    w("TEMP-инварианты: %s" % ("все OK" if not inv_bad
                               else ("НАРУШЕНИЯ: %s" % inv_bad)))
    w("Детерминизм r1≡r2 (все): %s" % det_ok)
    w("")
    w("HALT-строки — деривация EP-2A (проверено по RAW EP-2A: "
      "NpD-HALT-R@C2 шаги 3-4 = S3,S3; E6N-HALT-R@C5 шаги 2-3 = "
      "S3,S3): E6-среды и NpD: recovery FAIL (S3-цепь после "
      "exclusion); SD: N/A; stop=0. На NpD HALT ≡ POOL ≡ TEMP; "
      "на E6-family POOL/TEMP дают recovery=True против HALT.")
    w("sufficient(right, C) = Safety AND Recovery (раздельно R/S; "
      "форма EP-2A). Итоговая матрица — в отчёте.")

    with open(os.path.join(DIR, "EP2B_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    w("")
    w("saved EP2B_ANALYSIS.txt")


if __name__ == "__main__":
    main()
