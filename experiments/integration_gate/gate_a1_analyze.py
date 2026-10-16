# -*- coding: utf-8 -*-
"""INTEGRATION GATE A1 analyzer (FROZEN 10.09.2026).

Читает GATE_A1_cell_*.json (+ R0-записи). Проверки:
  G1 (c1): failure-derived не выбирается (refs[0] — success-знание;
      legacy-failure в конфигурации отсутствует после A1);
  G2/G3/G8 (c2): excluded K не в refs; sibling продолжает работать;
  G4 (c3): exclusion → sol → slot → attempt(success) → eligible;
  G5 (c4): attempt-failure → remains excluded; без второго slot;
  G6 (c5): empty pool → S3 → Explore (EP-1-стиль);
  G7 (c6): Explore не создаёт slot; excluded K не восстанавливается;
  R1 (c7/c8): SD4-серия и S6bV3 на модуле;
  L6/append-only: source enum; refs непусты; версии знаний = 1;
  guards; audit; детерминизм r1≡r2.
R0: сверка с GATE_V06X_records_v06x.json (anchor; при наличии).
Пишет INTEGRATION_GATE_ANALYSIS.txt.
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.dirname(DIR)
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load_cell(name):
    p = os.path.join(DIR, "GATE_A1_cell_%s.json" % name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def snap_map(rec):
    return {r["knowledge_id"]: r for r in rec.get("final_snapshot") or []}


def outcome_of_ctx(ctx):
    import re
    m = re.search(r"outcome=(\w+)", ctx or "")
    return m.group(1) if m else None


def fp_cell(rec):
    steps = [[s.get("mode"), s.get("action"), s.get("outcome")]
             for s in rec.get("steps") or []]
    events = [[e.get("event"), e.get("result")] for e in rec.get("events") or []]
    ss = rec.get("slot_state") or {}
    ss_norm = {}
    for k, v in ss.items():
        kk = "<kid>" if isinstance(k, str) and k.startswith("K_") else k
        vv = ("<kid>" if isinstance(v, str) and v.startswith("K_")
              else v)
        ss_norm[kk] = vv
    return json.dumps([steps, events, ss_norm], ensure_ascii=False,
                      sort_keys=True)


def main():
    w("INTEGRATION GATE A1: АНАЛИЗ (FROZEN 10.09.2026)")
    fails = []

    cells = {}
    for c in ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"):
        rights = ("NA",) if c == "c1" else ("R", "S")
        for sem in ("POOL", "TEMP"):
            for right in rights:
                for rep in ("r1", "r2"):
                    rec = load_cell("%s_%s_%s_%s" % (c, sem, right, rep))
                    if rec:
                        cells["%s|%s|%s|%s" % (c, sem, right, rep)] = rec

    w("клеток загружено: %d" % len(cells))

    # audit + guards
    bad_audit = [k for k, r in cells.items()
                 if r.get("audit_before") != r.get("audit_after")]
    bad_guards = [k for k, r in cells.items()
                  if not all(g["ok"] for g in r.get("guards") or [])]
    w("audit чистый: %d/%d; guards ok: %d/%d"
      % (len(cells) - len(bad_audit), len(cells),
         len(cells) - len(bad_guards), len(cells)))
    if bad_audit:
        fails.append("audit")
        w("  audit: %s" % bad_audit)
    if bad_guards:
        fails.append("guards")
        w("  guards: %s" % bad_guards)

    # детерминизм
    det_bad = []
    for base in ("c1_POOL", "c2_POOL", "c3_TEMP", "c4_TEMP", "c5_POOL",
                 "c6_TEMP", "c7_POOL", "c8_POOL"):
        for right in ("R", "S"):
            a = load_cell("%s_%s_r1" % (base, right))
            b = load_cell("%s_%s_r2" % (base, right))
            if a and b and fp_cell(a) != fp_cell(b):
                det_bad.append("%s_%s" % (base, right))
    w("детерминизм r1≡r2: %s" % ("OK" if not det_bad else det_bad))
    if det_bad:
        fails.append("determinism")

    # G1 (c1)
    w("")
    w("=== G1 (c1: addressing; без прав) ===")
    g1_ok = True
    for rep in ("r1", "r2"):
        rec = cells.get("c1|POOL|NA|%s" % rep)
        if not rec:
            continue
        sm = snap_map(rec)
        for s in rec["steps"]:
            if s.get("mode") == "S2" and s.get("refs"):
                ref0 = s["refs"][0]
                oc = outcome_of_ctx(sm.get(ref0, {}).get("context"))
                if oc != "success":
                    g1_ok = False
                    w("  !!! шаг %s ref_outcome=%s" % (s["step"], oc))
        w("  c1-%s шаги: %s" % (rep, [(s["step"], s["mode"],
                                       s.get("outcome")) for s in
                                      rec["steps"]]))
    w("  G1: %s" % ("PASS" if g1_ok else "FAIL"))
    if not g1_ok:
        fails.append("G1")

    # G2/G3/G4/G5/G6/G7
    def ev_names(rec):
        return [e["event"] for e in rec.get("events") or []]

    w("")
    w("=== G2/G3/G8 (c2: POOL; sibling) ===")
    g2_ok = True
    for right in ("R", "S"):
        for rep in ("r1", "r2"):
            rec = cells.get("c2|POOL|%s|%s" % (right, rep))
            if not rec:
                continue
            excl = rec.get("exclusions_final") or []
            excl_kid = (rec.get("trigger") or {}).get("kid")
            tr_step = (rec.get("trigger") or {}).get("step", 0)
            s2 = [s for s in rec["steps"] if s.get("mode") == "S2"]
            s2_after = [s for s in s2 if s["step"] > tr_step]
            ok = len(s2_after) >= 2 and bool(excl) and bool(excl_kid)
            if ok:
                for s in s2_after:
                    if excl_kid in (s.get("refs") or []):
                        ok = False
                        w("  !!! excluded K виден в refs шага %s" % s["step"])
            g2_ok = g2_ok and ok
            w("  c2-%s-%s: excl_final=%s excluded=%s modes=%s" % (
                right, rep, excl, excl_kid[:12] if excl_kid else None,
                [(s["step"], s["mode"]) for s in rec["steps"]]))
    w("  G2/G3/G8: %s" % ("PASS" if g2_ok else "FAIL"))
    if not g2_ok:
        fails.append("G2")

    w("")
    w("=== G4 (c3: TEMP success-цикл) ===")
    g4_ok = True
    for right in ("R", "S"):
        rec = cells.get("c3|TEMP|%s|r1" % right)
        if not rec:
            continue
        ev = ev_names(rec)
        st = rec.get("slot_state") or {}
        modes = [s.get("mode") for s in rec["steps"]]
        ok = ("exclusion" in ev and "sol" in ev and "slot" in ev
              and "eligible" in ev and "attempt" in modes
              and not rec.get("exclusions_final"))
        g4_ok = g4_ok and ok
        w("  c3-%s: events=%s attempt=%s excl_final=%s" % (
            right, ev, "attempt" in modes, rec.get("exclusions_final")))
    w("  G4: %s" % ("PASS" if g4_ok else "FAIL"))
    if not g4_ok:
        fails.append("G4")

    w("")
    w("=== G5 (c4: TEMP failure-ветка) ===")
    g5_ok = True
    for right in ("R", "S"):
        for rep in ("r1", "r2"):
            rec = cells.get("c4|TEMP|%s|%s" % (right, rep))
            if not rec:
                continue
            ev = ev_names(rec)
            att = [e for e in rec["events"] if e["event"] == "attempt"]
            slots = [e for e in rec["events"] if e["event"] == "slot"]
            ok = (len(att) == 1 and att[0].get("result") != "success"
                  and len(slots) == 1 and "eligible" not in ev
                  and rec.get("exclusions_final"))
            g5_ok = g5_ok and ok
            w("  c4-%s-%s: attempt=%s eligible=%s excl_final=%s" % (
                right, rep, att[0].get("result") if att else None,
                "eligible" in ev, rec.get("exclusions_final")))
    w("  G5: %s" % ("PASS" if g5_ok else "FAIL"))
    if not g5_ok:
        fails.append("G5")

    w("")
    w("=== G6 (c5: empty pool → S3 → Explore) ===")
    g6_ok = True
    for right in ("R", "S"):
        for rep in ("r1", "r2"):
            rec = cells.get("c5|POOL|%s|%s" % (right, rep))
            if not rec:
                continue
            ev = ev_names(rec)
            modes = [s.get("mode") for s in rec["steps"]]
            expl = [s for s in rec["steps"] if s.get("mode") == "explore"]
            ok = ("s3_detected" in ev and "explore" in ev
                  and "S3" in modes and expl and
                  expl[0].get("outcome") == "success")
            g6_ok = g6_ok and ok
            w("  c5-%s-%s: modes=%s events=%s" % (
                right, rep, modes, ev))
    w("  G6: %s" % ("PASS" if g6_ok else "FAIL"))
    if not g6_ok:
        fails.append("G6")

    w("")
    w("=== G7 (c6: TEMP + explore; slot НЕ создаётся) ===")
    g7_ok = True
    for right in ("R", "S"):
        for rep in ("r1", "r2"):
            rec = cells.get("c6|TEMP|%s|%s" % (right, rep))
            if not rec:
                continue
            ev = ev_names(rec)
            expl = [s for s in rec["steps"] if s.get("mode") == "explore"]
            ok = ("explore" in ev and "slot" not in ev and "sol" not in ev
                  and "eligible" not in ev and expl
                  and expl[0].get("outcome") == "success"
                  and rec.get("exclusions_final"))
            # K-невозврат: после eligible исключение осталось
            g7_ok = g7_ok and ok
            w("  c6-%s-%s: events=%s excl_final=%s" % (
                right, rep, ev, rec.get("exclusions_final")))
    w("  G7: %s" % ("PASS" if g7_ok else "FAIL"))
    if not g7_ok:
        fails.append("G7")

    w("")
    w("=== R1 (c7: SD4; c8: S6bV3) ===")
    r1_ok = True
    for cname in ("c7", "c8"):
        for right in ("R", "S"):
            for rep in ("r1", "r2"):
                rec = cells.get("%s|POOL|%s|%s" % (cname, right, rep))
                if not rec:
                    continue
                ev = ev_names(rec)
                expl = [s for s in rec["steps"] if s.get("mode") == "explore"]
                ok = ("explore" in ev and expl
                      and expl[0].get("outcome") == "success")
                r1_ok = r1_ok and ok
                w("  %s-%s-%s: events=%s" % (cname, right, rep, ev))
    w("  R1: %s" % ("PASS" if r1_ok else "FAIL"))
    if not r1_ok:
        fails.append("R1")

    # L6 / append-only (по всем клеткам)
    w("")
    w("=== L6 / append-only ===")
    l6_bad = []
    pool_info_any = False
    for k, rec in cells.items():
        for r in rec.get("final_snapshot") or []:
            if r.get("version") != 1:
                l6_bad.append((k, r["knowledge_id"], "version"))
            for o in r.get("applicability_observations") or []:
                src = o.get("source")
                refs = o.get("episode_refs") or []
                if src not in ("verified success", "verified failure") \
                        or not refs:
                    l6_bad.append((k, r["knowledge_id"], "obs"))
    w("  нарушений: %d" % len(l6_bad))
    if l6_bad:
        fails.append("L6")
        for b in l6_bad[:8]:
            w("    %s" % (b,))

    # R0 anchor
    w("")
    w("=== R0 (v0.6.x anchor на модуле) ===")
    old_path = os.path.join(EXP_DIR, "GATE_V06X_records_v06x.json")
    r0_ok = True
    authorized = []
    if not os.path.exists(old_path):
        w("  anchor-файл отсутствует — сверка пропущена")
    else:
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f)
        old_runs = {}
        for run in old.get("runs") or []:
            old_runs[(run.get("sequence"), run.get("rep"))] = run
        n_cmp = 0
        for s in ("S0", "S1", "S2", "S3", "S4", "S5", "S6b", "P1", "P2"):
            for rep in ("r1", "r2"):
                rec = load_cell("R0_%s_NA_%s" % (s, rep))
                if not rec:
                    continue
                ore = old_runs.get((s, rep))
                if not ore:
                    w("  %s %s: нет старой записи" % (s, rep))
                    continue
                n_cmp += 1
                st_old = [x.get("outcome") for x in ore["steps"]]
                st_new = [x.get("outcome") for x in rec["steps"]]
                if st_old != st_new:
                    r0_ok = False
                    w("  %s %s: steps MISMATCH old=%s new=%s" % (
                        s, rep, st_old, st_new))
                old_snap = {}
                for x in ore["steps"]:
                    for row in x.get("snapshot") or []:
                        old_snap[row["knowledge_id"]] = row
                for p_old, p_new in zip(ore.get("probes") or [],
                                        rec.get("probes") or []):
                    same = (p_old.get("strategy_id") == p_new.get(
                        "strategy_id")
                        and p_old.get("candidate_commands")
                        == p_new.get("candidate_commands"))
                    if same:
                        continue
                    # допустимое отличие: old выбирал failure-derived
                    # (legacy, aw=None, outcome!=success) — цель A1
                    refs = p_old.get("knowledge_refs") or []
                    refs_fail = []
                    for k in refs:
                        row = old_snap.get(k)
                        if row is not None and row.get(
                                "applicable_when") is None \
                                and outcome_of_ctx(row.get("context")) \
                                != "success":
                            refs_fail.append(k)
                    if refs and len(refs_fail) == len(refs):
                        authorized.append((s, rep, p_old.get("world"),
                                           [k[:12] for k in refs],
                                           p_old.get("strategy_id"),
                                           p_new.get("strategy_id")))
                    else:
                        r0_ok = False
                        w("  %s %s проба %s: MISMATCH old=%s/%s new=%s/%s"
                          % (s, rep, p_old.get("world"),
                             p_old.get("strategy_id"),
                             p_old.get("candidate_commands"),
                             p_new.get("strategy_id"),
                             p_new.get("candidate_commands")))
        w("  сверено прогонов: %d" % n_cmp)
        w("  A1-authorized отличия (old выбирал failure-derived; A1 "
          "устраняет): %d" % len(authorized))
        for a in authorized:
            w("    %s" % (a,))
        w("  R0: %s" % ("PASS" if r0_ok else "FAIL"))
    if not r0_ok:
        fails.append("R0")

    w("")
    w("=== ВЕРДИКТ ===")
    gate = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "R1", "R0"]
    status = "PASS" if not fails else "FAIL"
    w("INTEGRATION GATE A1: %s%s" % (
        status, ("  (%s)" % ", ".join(fails)) if fails else ""))
    w("Критерии: G1..G7, R1, R0, guards, audit, L6, детерминизм — "
      "конъюнкция (strict).")
    w("Слои v0.6.x не изменялись; модуль — experiments/"
      "integration_gate (ветка).")

    with open(os.path.join(DIR, "INTEGRATION_GATE_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved INTEGRATION_GATE_ANALYSIS.txt")


if __name__ == "__main__":
    main()
