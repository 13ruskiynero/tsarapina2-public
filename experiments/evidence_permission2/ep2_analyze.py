# -*- coding: utf-8 -*-
"""EP-2A analyzer (FROZEN 10.09.2026; ред. 1).

Читает EP2_cell_A1_*.json (54 клетки + якорь) и AA1-деривацию
(A1-B: SD, N1D, NpD, E6S). Критерии (PROTOCOL §8, раздельно R/S):
  stop_on_S: повторений fix-a после триггера == 0 и granted→excluded;
  recovery_on_N: success fix-a достижим и не позже baseline;
  Sufficient(right, C) = stop_on_S AND recovery_on_N.
Плюс: детерминизм r1≡r2; ref_outcome==success (адресация A1);
class_actual триггеров (C5a/C5b; boundary); L6-walk; audit.
Пишет EP2_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
AA1 = os.path.join(DIR, "..", "applicability_addressing1")
OUT = os.path.join(DIR, "EP2_ANALYSIS.txt")
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_cell(mode, hist, rep):
    p = os.path.join(DIR, "EP2_cell_A1_%s_%s_%s.json" % (mode, hist, rep))
    if os.path.exists(p):
        return load(p)
    p2 = os.path.join(AA1, "AA1_cell_A1_%s_%s_%s.json"
                      % (mode, hist, rep))
    if os.path.exists(p2):
        return load(p2)
    return None


def repeats_after_trigger(rec):
    if not rec.get("trigger") or not rec.get("intervention"):
        return None
    t = rec["intervention"]["at"]
    step0 = int(t.split("-")[-1])
    n = 0
    for s in rec["steps"]:
        if s["step"] >= step0 and s.get("action") == "fix-a":
            n += 1
    return n


def recovery_step(rec, after=0):
    """Первый эпизод с outcome success ПОСЛЕ шага `after` (0 = любой)."""
    for s in rec["steps"]:
        if s["step"] > after and s.get("outcome") == "success":
            return s["step"]
    return None


def ref_outcomes(rec):
    return [(s.get("step"), s.get("ref_outcome"))
            for s in rec["steps"] if s.get("mode") == "S2"]


def fp(rec):
    line = rec["line_trace"][-1] if rec.get("line_trace") else None
    if line:
        line = [(m.get("outcome"), m.get("aw"), m.get("kinds"))
                for m in line]
    checks = [(c.get("step"), c.get("granted_excluded"),
               c.get("selected_ref") is not None)
              for c in (rec.get("checks") or [])]
    trg = rec.get("trigger")
    if trg:
        trg = {"conf": trg.get("conf"), "step": trg.get("step"),
               "class_actual": trg.get("class_actual"),
               "conflict": trg.get("conflict"),
               "last_kinds": trg.get("last_kinds")}
    return json.dumps({
        "steps": [(s.get("world"), s.get("envver"), s.get("mode"),
                   s.get("action"), s.get("outcome"), s.get("ref_outcome"),
                   s.get("excluded")) for s in rec["steps"]],
        "line": line,
        "trigger": trg,
        "intervention": (rec.get("intervention") or {}).get("right"),
        "checks": checks,
    }, ensure_ascii=False, sort_keys=True)


CELLS = []
for conf, hists in (("C1", ("SD", "N1D")), ("C2", ("SD", "NpD")),
                    ("C3", ("SD4", "NpD")),
                    ("C5", ("S6bV3", "E6N-V3", "E6S", "E6N")),
                    ("C6", ("C6N",))):
    for h in hists:
        for right in ("R", "S"):
            for rep in ("r1", "r2"):
                CELLS.append(("%s@%s" % (right, conf), h, rep))
fails = []
for m, h in (("B", "SD"), ("B", "N1D"), ("B", "NpD"), ("B", "E6S"),
             ("B", "SD4"), ("B", "S6bV3"), ("B", "E6N-V3"), ("B", "E6N"),
             ("B", "C6N")):
    for rep in ("r1", "r2"):
        CELLS.append((m, h, rep))

data = {}
missing = []
for m, h, rep in CELLS:
    r = load_cell(m, h, rep)
    if r is None:
        missing.append((m, h, rep))
    else:
        data[(m, h, rep)] = r

w("EP-2A: АНАЛИЗ (FROZEN; PROTOCOL §8; раздельно R/S)")
w("клеток загружено: %d; отсутствуют: %s" % (len(data), missing))
if missing:
    w("!!! НЕПОЛНЫЙ RAW — анализ предварителен, стоп-условие.")
w("")
w("=== АУДИТ/ДЕТЕРМИНИЗМ ===")
audit_bad = [k for k, r in data.items()
             if r.get("audit_before") != r.get("audit_after")]
w("audit LAYERS_UNCHANGED: %s" % ("OK" if not audit_bad else audit_bad))
det_bad = []
for (m, h) in [(m, h) for m, h, _ in CELLS]:
    a = data.get((m, h, "r1"))
    b = data.get((m, h, "r2"))
    if a and b and fp(a) != fp(b):
        det_bad.append((m, h))
w("детерминизм r1≡r2: %s" % ("OK" if not det_bad else det_bad))
ro_bad = []
for k, r in data.items():
    for st, ro in ref_outcomes(r):
        if ro != "success":
            ro_bad.append((k, st, ro))
w("ref_outcome==success (адресация A1): %s" % ("OK" if not ro_bad else ro_bad))
w("")

w("=== КЛАССЫ ТРИГГЕРОВ (факт) ===")
for hist in ("S6bV3", "E6N-V3", "E6S", "E6N"):
    r = None
    for m in ("R@C5", "S@C5"):
        r = data.get((m, hist, "r1"))
        if r:
            break
    if r and r.get("trigger"):
        w("  %-8s: %s (kind=%s)" % (hist, r["trigger"]["class_actual"],
                                    r["trigger"]["last_kinds"]))
w("")

w("=== ПО КОНФИГУРАЦИЯМ: S-сторона (повторения после триггера) / "
  "N-сторона (восстановление) ===")
verdict = {}
for conf, sh, nh in (("C1", "SD", "N1D"), ("C2", "SD", "NpD"),
                     ("C3", "SD4", "NpD"),
                     ("C5", None, None), ("C6", None, "C6N")):
    if conf == "C5":
        pairs = [("S6bV3", "E6N-V3"), ("E6S", "E6N")]
    elif conf == "C6":
        pairs = [(None, "C6N")]
    else:
        pairs = [(sh, nh)]
    for (s_hist, n_hist) in pairs:
        w("--- %s: S=%s / N=%s ---" % (conf, s_hist, n_hist))
        aft = {"C1": 1, "C2": 2, "C3": 3, "C5": 1, "C6": 3}[conf]
        b_s = data.get(("B", s_hist, "r1")) if s_hist else None
        b_n = data.get(("B", n_hist, "r1")) if n_hist else None
        rb_s = repeats_after_trigger(b_s) if b_s and s_hist else None
        rb_n = recovery_step(b_n, aft) if b_n and n_hist else None
        w("  B: S-повторения=%s; N-восстановление шаг=%s" % (rb_s, rb_n))
        for right in ("R", "S"):
            r_s = data.get(("%s@%s" % (right, conf), s_hist, "r1")) if s_hist else None
            r_n = data.get(("%s@%s" % (right, conf), n_hist, "r1")) if n_hist else None
            rs = repeats_after_trigger(r_s) if r_s else None
            rec_n = recovery_step(r_n, aft) if r_n else None
            chk = None
            if r_s and r_s.get("checks"):
                chk = r_s["checks"][-1].get("granted_excluded")
            stop_ok = (rs == 0) if rs is not None else None
            rec_ok = None
            if rec_n is not None and rb_n is not None:
                rec_ok = rec_n <= rb_n
            elif n_hist is None:
                rec_ok = None
            elif rec_n is None:
                rec_ok = False
            suff = None
            if stop_ok is not None and rec_ok is not None:
                suff = bool(stop_ok and rec_ok)
            verdict[(right, conf, s_hist, n_hist)] = (stop_ok, rec_ok, suff)
            w("  %s: S-повторения=%s (granted->excluded=%s); "
              "N-восстановление шаг=%s; stop=%s recovery=%s "
              "SUFFICIENT=%s" % (right, rs, chk, rec_n, stop_ok, rec_ok,
                                 suff))
        w("")

w("=== СВОДКА SUFFICIENT (раздельно R и S) ===")
for key, (stop_ok, rec_ok, suff) in sorted(verdict.items(),
                                           key=str):
    right, conf, s_hist, n_hist = key
    w("  %s@%s [S=%s N=%s]: stop=%s recovery=%s sufficient=%s"
      % (right, conf, s_hist, n_hist, stop_ok, rec_ok, suff))
w("")

w("=== L6-WALK (по final_snapshot всех клеток) ===")
l6_bad = []
for k, r in data.items():
    for row in r.get("final_snapshot") or []:
        c = row.get("context") or ""
        is_fail = "outcome=" in c and "outcome=success" not in c
        if is_fail and row.get("applicable_when"):
            l6_bad.append((k, row["knowledge_id"][:12], "failure-with-aw"))
        for o in row.get("applicability_observations") or []:
            if o.get("source") not in ("verified success",
                                       "verified failure"):
                l6_bad.append((k, row["knowledge_id"][:12], "bad-source"))
            if not o.get("episode_refs"):
                l6_bad.append((k, row["knowledge_id"][:12], "no-refs"))
w("L6 нарушений: %s" % ("нет" if not l6_bad else l6_bad[:10]))
w("")

w("=== ПРЕДВАРИТЕЛЬНЫЙ ВЕРДИКТ (формулировка DESIGN §5, узкая) ===")
any_suff = [k for k, v in verdict.items() if v[2]]
w("sufficient-клеток: %d" % len(any_suff))
w("Кандидаты: %s" % (any_suff,))
w("Если ни одна клетка не sufficient по (б): результат EP-2A — "
  "при permanent R/S ни одна из исследованных evidence-конфигураций "
  "не удовлетворила совместному критерию остановки и восстановления; "
  "основание открыть EP-2B (временная semantics).")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
w("")
w("saved EP2_ANALYSIS.txt")
