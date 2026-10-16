# -*- coding: utf-8 -*-
"""AA-1 analyzer (FROZEN 10.09.2026). Читает AA1_cell_*.json (RAW;
анализ — только после полного RAW).

Критерии (PROTOCOL §7–8; раздельные утверждения):
  AA-1 PASS (адресация): A1-B: ref_outcome == success везде;
    B-траектории A1 ≡ A0 (действия/исходы по историям); audit; L6
    (source enum, aw только success-путь, append-only); r1≡r2; якорь
    (сверка A0-B-N1D с EP-1 B-N1D, форма K-цепочки).
  R/S PASS (permission на правильно адресованном кандидате):
    A1-R/S@E4 (SD, E6S): повторений fix-a после триггера == 0 И
    checks granted→excluded; A0: повторения == 1 (контроль).
Границы (не FAIL AA-1): A1-R/S на NpD — S3-остановка, восстановление
потеряно (постоянный R/S; EP-2-материал); NSD-R/S@E4 — терминальный
триггер (EF-4), ожидание ≡ B.
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
HISTS = ["N1D", "NaD", "NpD", "N1V", "SV", "SD", "SM", "NSD", "E6S"]
RS_HISTS = ["NpD", "SD", "NSD", "E6S"]
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load_cells():
    cells = {}
    for p in sorted(glob.glob(os.path.join(DIR, "AA1_cell_*.json"))):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        cells[(r["branch"], r["mode"], r["history"], r["rep"])] = r
    return cells


def traj(rec):
    return [(s.get("world"), s.get("envver"), s.get("action"),
             s.get("outcome"), s.get("excluded"))
            for s in rec["steps"]]


def fp(rec):
    """Структурная подпись прогона БЕЗ kid'ов (uuid недетерминированы):
    траектория + ref-классы (len/outcome; outcome — только S2: на S3
    refs — диагностический список, порядок kid'ов недетерминирован)
    + триггер."""
    return json.dumps({"traj": traj(rec),
                       "ref_cls": [(len(s.get("knowledge_refs") or []),
                                    s.get("ref_outcome")
                                    if s.get("mode") == "S2" else None)
                                   for s in rec["steps"]],
                       "trig": rec.get("trigger")}, sort_keys=True,
                      ensure_ascii=False)


def repeats_after_trigger(rec):
    trig = rec.get("trigger")
    if not trig:
        return None
    t = trig["step"]
    return sum(1 for s in rec["steps"]
               if s["step"] > t and s.get("action") == "fix-a")


def l6_check(rec):
    """L6-базовый: source enum; aw только success-путь; refs непусты у
    obs failure."""
    problems = []
    for row in rec["final_snapshot"]:
        out = None
        ctx = row.get("context") or ""
        for tok in ctx.split():
            if tok.startswith("outcome="):
                out = tok.split("=", 1)[1]
        for o in row.get("applicability_observations") or []:
            src = o.get("source")
            if src not in ("verified success", "verified failure"):
                problems.append("source=%s у %s" % (src,
                                row["knowledge_id"][:10]))
            if src == "verified failure" and not o.get("episode_refs"):
                problems.append("failure-obs без refs: %s"
                                % row["knowledge_id"][:10])
        if out is not None and out != "success" \
                and row.get("applicable_when") is not None:
            problems.append("aw у failure-знания: %s"
                            % row["knowledge_id"][:10])
    return problems


def anchor_check(cells):
    """Сверка A0-B-N1D с EP-1 B-N1D (форма K-цепочки линии)."""
    a = cells.get(("A0", "B", "N1D", "r1"))
    ep1_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "evidence_permission1",
        "EP1_cell_B_N1D_r1.json")
    if a is None or not os.path.exists(ep1_path):
        return None, "нет данных для якоря"
    with open(ep1_path, encoding="utf-8") as f:
        ep1 = json.load(f)

    def line_form(rec, trace_key):
        tr = rec[trace_key][-1]
        form = []
        for m in tr:
            aw = m.get("aw")
            form.append((m.get("outcome"),
                         None if aw is None else tuple(sorted(aw.items())),
                         tuple(m.get("kinds") or [])))
        return [x for x in form if x[0] in ("success", "failure",
                                            "partial")]

    f1 = line_form(a, "line_trace")

    tr_e = ep1.get("line_trace") or []
    f2 = []
    if tr_e:
        for m in tr_e[-1]:
            aw = m.get("aw")
            f2.append((m.get("outcome"),
                       None if aw is None else tuple(sorted(aw.items())),
                       tuple(m.get("kinds") or [])))
    ok = f1 == f2
    return ok, "A0-B-N1D form=%s | EP1-B-N1D form=%s" % (f1, f2)


def main():
    cells = load_cells()
    w("AA-1: АНАЛИЗ (FROZEN 10.09.2026; критерии PROTOCOL §7–8)")
    w("клеток загружено: %d" % len(cells))
    w("")

    # --- per-cell ---
    b_traj = {}
    fails = []
    for key in sorted(cells):
        rec = cells[key]
        branch, mode, hist, rep = key
        row = ["=== %s|%s|%s|%s ===" % key]
        row.append("  траектория: %s" % [(s.get("action"),
                                          s.get("outcome"))
                                         for s in rec["steps"]])
        if branch == "A1" and mode == "B":
            ro = [s.get("ref_outcome") for s in rec["steps"]
                  if s.get("mode") == "S2"]
            bad = [x for x in ro if x != "success"]
            row.append("  ref_outcome(S2): %s%s"
                       % (ro, "  <-- FAILURE-REFS!" if bad else ""))
            if bad:
                fails.append(key)
        if mode in ("R@E4", "S@E4"):
            rep_n = repeats_after_trigger(rec)
            row.append("  триггер: %s; повторения после: %s; checks: %s"
                       % (rec.get("trigger"), rep_n, rec["checks"]))
        pr = l6_check(rec)
        row.append("  audit: %s; L6: %s"
                   % (rec["audit_before"] == rec["audit_after"],
                      "OK" if not pr else pr))
        w("\n".join(row))
        if mode == "B":
            b_traj.setdefault(hist, {})[branch] = traj(rec)
    w("")

    # --- B-траектории A1 ≡ A0 ---
    w("=== B-траектории A1 ≡ A0 (действия/исходы) ===")
    w("N-истории (вердикт AA-1): N1D, NaD, NpD; V2-контроль: N1V, SV; "
      "S-истории (различия — измеренный эффект, не FAIL): SD, SM, "
      "NSD, E6S")
    n_hists = ["N1D", "NaD", "NpD"]
    traj_ok = True
    for h in HISTS:
        t = b_traj.get(h)
        if not t or "A0" not in t or "A1" not in t:
            w("  %s: нет пары" % h)
            if h in n_hists:
                traj_ok = False
            continue
        ok = t["A0"] == t["A1"]
        if h in n_hists:
            traj_ok = traj_ok and ok
        tag = ("N" if h in n_hists
               else ("V2" if h in ("N1V", "SV") else "S"))
        w("  [%s] %s: %s" % (tag, h, "идентичны" if ok else
                             ("РАСХОЖДЕНИЕ: A0=%s A1=%s"
                              if h not in n_hists else
                              "РАСХОЖДЕНИЕ (FAIL): A0=%s A1=%s")
                             % (t["A0"], t["A1"])))
    w("")

    # --- R/S-механика ---
    w("=== R/S-механика (повторения после триггера) ===")
    rs_rows = {}
    for h in RS_HISTS:
        for branch in ("A0", "A1"):
            for mode in ("R@E4", "S@E4"):
                rec = cells.get((branch, mode, h, "r1"))
                if rec is None:
                    continue
                rep_n = repeats_after_trigger(rec)
                ch = rec["checks"][0] if rec["checks"] else {}
                rs_rows[(branch, mode, h)] = (rep_n, ch)
                succ = any(s.get("outcome") == "success"
                           for s in rec["steps"])
                w("  %s %s %s: повторения=%s; granted_excluded=%s; "
                  "success в горизонте: %s"
                  % (branch, mode, h, rep_n,
                     ch.get("granted_excluded"), succ))
    w("")

    # --- r1 ≡ r2 ---
    w("=== ДЕТЕРМИНИЗМ r1 ≡ r2 ===")
    det_ok = True
    for key in sorted(cells):
        if key[3] != "r1":
            continue
        k2 = (key[0], key[1], key[2], "r2")
        if k2 in cells:
            ok = fp(cells[key]) == fp(cells[k2])
            if not ok:
                w("  РАСХОЖДЕНИЕ: %s|%s|%s" % key[:3])
                det_ok = False
    w("  r1≡r2: %s" % ("OK" if det_ok else "ЕСТЬ РАСХОЖДЕНИЯ"))
    w("")

    # --- якорь ---
    w("=== РЕГРЕССИОННЫЙ ЯКОРЬ (A0-B-N1D vs EP-1 B-N1D) ===")
    ank_ok, ank_msg = anchor_check(cells)
    w("  %s: %s" % ("OK" if ank_ok else ("FAIL" if ank_ok is False
                                         else "n/a"), ank_msg))
    w("")

    # --- вердикты ---
    w("=== ВЕРДИКТЫ (раздельные) ===")
    aa1_pass = (not fails) and traj_ok and det_ok and (
        ank_ok is not False)
    w("AA-1 PASS (адресация): %s (failure-refs=%d, B-траектории=%s, "
      "детерминизм=%s, якорь=%s)"
      % ("ДА" if aa1_pass else "НЕТ", len(fails), traj_ok, det_ok,
         ank_ok))
    rs_ok = all(
        rs_rows.get(("A1", m, h), (None, {}))[0] == 0 and
        rs_rows.get(("A1", m, h), (None, {}))[1].get(
            "granted_excluded") for h in ("SD", "E6S")
        for m in ("R@E4", "S@E4"))
    a0_rep = [rs_rows.get(("A0", m, h), (None,))[0] for h in ("SD", "E6S")
              for m in ("R@E4", "S@E4")]
    a0_ok = all(x == 1 for x in a0_rep)
    w("R/S PASS (permission на правильно адресованном кандидате): %s "
      "(A1 SD/E6S: повторения 0 + excluded; A0-контроль повторения "
      "==1: %s → %s)"
      % ("ДА" if (rs_ok and a0_ok) else "НЕТ", a0_rep, a0_ok))
    w("Границы (не FAIL AA-1):")
    for h in ("NpD",):
        for m in ("R@E4", "S@E4"):
            r = rs_rows.get(("A1", m, h))
            if r:
                w("  A1 %s %s: повторения=%s, success в горизонте=%s "
                  "(постоянный R/S; EP-2)" % (m, h, r[0],
                                              any(s.get("outcome")
                                                  == "success"
                                                  for s in
                                                  cells[("A1", m, h,
                                                         "r1")]["steps"])))
    w("  NSD-R/S@E4: терминальный триггер (EF-4) — ожидание ≡ B")

    with open(os.path.join(DIR, "AA1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved AA1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
