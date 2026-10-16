# -*- coding: utf-8 -*-
"""A1 PRODUCTION TRANSFER: сравнение experimental ↔ production.

Спецификация: A1_PRODUCTION_TRANSFER_DESIGN.md §4.7 (FROZEN).
Читает GATE_A1_cell_<cell>.json (exp) и GATE_A1_PROD_cell_<cell>.json
(prod); нормализует kid'ы (<kid>) и сравнивает структурные
fingerprints: steps / events / slot_state / exclusions / guards /
audit. R0 (prod) сравнивается с v0.6.x anchor (authorized-отличия —
те же 4, что в exp). Пишет INTEGRATION_GATE_A1_PROD_COMPARE.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.dirname(DIR)
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def norm(obj):
    if isinstance(obj, dict):
        return {("<kid>" if isinstance(k, str) and k.startswith("K_")
                 else k): norm(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [norm(x) for x in obj]
    if isinstance(obj, str) and obj.startswith("K_"):
        return "<kid>"
    return obj


def load(name, prod=False):
    p = os.path.join(DIR, ("GATE_A1_PROD_cell_%s.json" if prod
                           else "GATE_A1_cell_%s.json") % name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fp(rec):
    return norm({
        "steps": rec.get("steps"),
        "events": rec.get("events"),
        "slot_state": rec.get("slot_state"),
        "exclusions": rec.get("exclusions_final"),
        "guards": rec.get("guards"),
        "audit_clean": rec.get("audit_before") == rec.get("audit_after"),
    })


def outcomes(rec):
    return [(s.get("world"), s.get("outcome")) for s in rec.get("steps")]


def main():
    w("A1 PRODUCTION TRANSFER: сравнение experimental ↔ production")
    cells = []
    for c in ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"):
        rights = ("NA",) if c == "c1" else ("R", "S")
        for sem in ("POOL", "TEMP"):
            for right in rights:
                for rep in ("r1", "r2"):
                    cells.append("%s_%s_%s_%s" % (c, sem, right, rep))
    n_ok = n_missing = 0
    diffs = []
    for cell in cells:
        e = load(cell, prod=False)
        p = load(cell, prod=True)
        if e is None or p is None:
            n_missing += 1
            w("  MISSING: %s (exp=%s prod=%s)" % (cell, e is not None,
                                                  p is not None))
            continue
        same = fp(e) == fp(p)
        if same:
            n_ok += 1
        else:
            diffs.append(cell)
            w("  DIFF: %s" % cell)
            if outcomes(e) != outcomes(p):
                w("    steps: exp=%s prod=%s" % (outcomes(e), outcomes(p)))
            for key in ("steps", "events", "slot_state", "exclusions",
                        "guards"):
                fe = norm({key: e.get(key) if key != "exclusions"
                           else e.get("exclusions_final")})
                fp_ = norm({key: p.get(key) if key != "exclusions"
                            else p.get("exclusions_final")})
                if fe != fp_:
                    w("    field %s differs" % key)
    w("")
    w("Механические клетки: совпало %d, расхождений %d, нет записей %d"
      % (n_ok, len(diffs), n_missing))

    # R0: prod vs v0.6.x anchor
    w("")
    w("=== R0 (prod) vs v0.6.x anchor ===")
    old_path = os.path.join(EXP_DIR, "GATE_V06X_records_v06x.json")
    r0_ok = True
    authorized = []
    if not os.path.exists(old_path):
        w("  anchor-файл отсутствует — сверка пропущена")
    else:
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f)
        old_runs = {(r.get("sequence"), r.get("rep")): r
                    for r in old.get("runs") or []}
        n_cmp = 0
        for s in ("S0", "S1", "S2", "S3", "S4", "S5", "S6b", "P1", "P2"):
            for rep in ("r1", "r2"):
                rec = load("R0_%s_NA_%s" % (s, rep), prod=True)
                ore = old_runs.get((s, rep))
                if not rec or not ore:
                    continue
                n_cmp += 1
                st_old = [x.get("outcome") for x in ore["steps"]]
                st_new = [x.get("outcome") for x in rec["steps"]]
                if st_old != st_new:
                    r0_ok = False
                    w("  %s %s: steps MISMATCH prod=%s old=%s"
                      % (s, rep, st_new, st_old))
                old_snap = {}
                for x in ore["steps"]:
                    for row in x.get("snapshot") or []:
                        old_snap[row["knowledge_id"]] = row
                for p_old, p_new in zip(ore.get("probes") or [],
                                        rec.get("probes") or []):
                    same = (p_old.get("strategy_id")
                            == p_new.get("strategy_id")
                            and p_old.get("candidate_commands")
                            == p_new.get("candidate_commands"))
                    if same:
                        continue
                    refs = p_old.get("knowledge_refs") or []
                    import re as _re

                    def _oc(ctx):
                        m = _re.search(r"outcome=(\w+)", ctx or "")
                        return m.group(1) if m else None
                    fail_refs = [k for k in refs
                                 if (old_snap.get(k) or {}).get(
                                     "applicable_when") is None
                                 and _oc((old_snap.get(k) or {}).get(
                                     "context")) != "success"]
                    if refs and len(fail_refs) == len(refs):
                        authorized.append((s, rep, p_old.get("world"),
                                           p_old.get("strategy_id"),
                                           p_new.get("strategy_id")))
                    else:
                        r0_ok = False
                        w("  %s %s проба %s: MISMATCH old=%s new=%s"
                          % (s, rep, p_old.get("world"),
                             (p_old.get("strategy_id"),
                              p_old.get("candidate_commands")),
                             (p_new.get("strategy_id"),
                              p_new.get("candidate_commands"))))
        w("  сверено прогонов: %d" % n_cmp)
        w("  A1-authorized отличий: %d" % len(authorized))
        for a in authorized:
            w("    %s" % (a,))
        w("  R0: %s" % ("PASS" if r0_ok else "FAIL"))

    w("")
    verdict = (n_ok == 30 and not diffs and r0_ok)
    w("=== ВЕРДИКТ (exp ↔ prod) ===")
    w("ЭКВИВАЛЕНТНОСТЬ: %s" % ("PASS" if verdict else "FAIL"))
    with open(os.path.join(DIR, "INTEGRATION_GATE_A1_PROD_COMPARE.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("saved INTEGRATION_GATE_A1_PROD_COMPARE.txt")


if __name__ == "__main__":
    main()
