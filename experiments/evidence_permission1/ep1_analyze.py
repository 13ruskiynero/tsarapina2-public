# -*- coding: utf-8 -*-
"""EP-1 analyzer (FROZEN 07.09.2026; анализ после полного RAW).

Читает все EP1_cell_<P>_<H>_<rep>.json (100). Per-cell статусы по
определениям PROTOCOL §6 (sufficient — ТОЛЬКО по records):
- X-клетка SUFFICIENT: на всех S-историях события (SD/SV/SM/NSD/
  E6S, где событие возникло НЕ терминально) достигнут success
  fix-aq (в шагах после смены мира); на всех N-историях события —
  восстановление (первый success) не позже baseline той же истории.
- R/S-клетка SUFFICIENT: на всех N-историях события восстановление
  не заблокировано (<= baseline); на всех S-историях события — 0
  повторений fix-a после триггера.
- Событие не возникло (trigger None/terminal) -> no-event (граница
  канала, EF-3/EF-4), НЕ INSUFFICIENT.
Вывод: EP1_ANALYSIS.txt.
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
S_HISTS = ("SD", "SV", "SM", "NSD", "E6S")   # после смены мира
N_HISTS = ("N1D", "N1V", "NaD", "NpD", "NpV", "NpM", "E6N")
# шаг, с которого мир = w2 (NSD: смена после шага 2, т.е. шаг >= 3)
SWITCH_STEP = {"SD": 1, "SV": 1, "SM": 1, "NSD": 3, "E6S": 1}
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load_cells():
    cells = {}
    for p in sorted(glob.glob(os.path.join(DIR, "EP1_cell_*.json"))):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        cells[(r["policy"], r["history"], r["rep"])] = r
    return cells


def traj(r):
    return [(s.get("mode"), s.get("action"), s.get("outcome"),
             s.get("strategy_id")) for s in r["steps"]]


def first_success_step(r, after=None):
    for s in r["steps"]:
        if s.get("outcome") == "success":
            if after is None or s["step"] >= after:
                return s["step"]
    return None


def first_success_after_switch(r):
    return first_success_step(r, after=SWITCH_STEP.get(r["history"], 1))


def retries_after_trigger(r):
    """Число исполненных эпизодов fix-a после шага триггера."""
    tr = r.get("trigger")
    if not tr or tr.get("terminal"):
        return None
    tstep = tr.get("step", 0)
    return sum(1 for s in r["steps"]
               if s["step"] > tstep and s.get("action") == "fix-a")


def trigger_histories(cells, policy, rep):
    out = []
    for h in S_HISTS + N_HISTS:
        r = cells.get((policy, h, rep))
        if r and r.get("trigger") and not r["trigger"].get("terminal"):
            out.append(h)
    return out


def l6_walk(r):
    bad = []
    for x in r["final_snapshot"]:
        if x.get("schema_version") != "0.3":
            bad.append("%s schema=%s" % (x["knowledge_id"],
                                         x["schema_version"]))
        for o in x.get("applicability_observations") or []:
            if o.get("source") not in ("verified success",
                                       "verified failure"):
                bad.append("%s source=%r" % (x["knowledge_id"],
                                             o.get("source")))
            if not o.get("episode_refs"):
                bad.append("%s refs пуст" % x["knowledge_id"])
    return bad


def main():
    cells = load_cells()
    w("EP-1: АНАЛИЗ (FROZEN; после полного RAW; 100 прогонов)")
    w("files: %d" % len(cells))
    w("")

    w("=== ДЕТЕРМИНИЗМ (r1 vs r2) ===")
    det_bad = []
    for pol in sorted(set(k[0] for k in cells)):
        for h in S_HISTS + N_HISTS:
            a = cells.get((pol, h, "r1"))
            b = cells.get((pol, h, "r2"))
            if a is None or b is None:
                continue
            if traj(a) != traj(b) or (a.get("trigger") or {}).get("step") \
                    != (b.get("trigger") or {}).get("step"):
                det_bad.append((pol, h))
    w("расхождений r1/r2: %d %s" % (len(det_bad), det_bad))
    w("")

    w("=== ТРАЕКТОРИИ (r1): B и клетки = (mode,action,outcome) ===")
    for h in S_HISTS + N_HISTS:
        b = cells.get(("B", h, "r1"))
        if b is None:
            continue
        w("%s B: %s" % (h, traj(b)))
        for pol in sorted(set(k[0] for k in cells if k[1] == h
                              and k[0] != "B" and k[2] == "r1")):
            r = cells[(pol, h, "r1")]
            tr = r.get("trigger")
            iv = r.get("intervention")
            tstr = ("tr=%s@%s" % (tr["event"], tr["step"])) if tr else "tr=-"
            if tr and tr.get("terminal"):
                tstr += "(term)"
            ivstr = ("iv=%s" % iv["right"]) if iv else ""
            w("  %-5s %-4s %s %s: %s" % (h, pol, tstr, ivstr, traj(r)))
        w("")

    w("=== BASELINE: первый success (шаг) ===")
    base_succ = {}
    for h in S_HISTS + N_HISTS:
        b = cells.get(("B", h, "r1"))
        fs = first_success_step(b)
        fss = first_success_after_switch(b)
        base_succ[h] = fs
        w("  %s: first_success=%s after_switch=%s" % (h, fs, fss))
    w("")

    w("=== PER-CELL (r1; G-full; sufficient по records) ===")
    verdicts = {}
    policies = sorted(set(k[0] for k in cells if k[0] != "B" and k[2] == "r1"))
    for pol in policies:
        right = pol[-1]
        trig_h = trigger_histories(cells, pol, "r1")
        s_trig = [h for h in trig_h if h in S_HISTS]
        n_trig = [h for h in trig_h if h in N_HISTS]
        reasons = []
        ok = True
        if right == "X":
            if not s_trig:
                ok = False
                reasons.append("нет S-историй события (no-event)")
            for h in s_trig:
                fs = first_success_after_switch(cells[(pol, h, "r1")])
                if fs is None:
                    ok = False
                    reasons.append("%s: success не достигнут после смены"
                                   % h)
            for h in n_trig:
                fs = first_success_step(cells[(pol, h, "r1")])
                bf = base_succ.get(h)
                if fs is None or (bf is not None and fs > bf):
                    ok = False
                    reasons.append("%s: восстановление %s vs baseline %s"
                                   % (h, fs, bf))
        else:  # R/S
            for h in n_trig:
                fs = first_success_step(cells[(pol, h, "r1")])
                bf = base_succ.get(h)
                if fs is None or (bf is not None and fs > bf):
                    ok = False
                    reasons.append("%s: восстановление заблокировано/позже "
                                   "baseline (%s vs %s)" % (h, fs, bf))
            for h in s_trig:
                rt = retries_after_trigger(cells[(pol, h, "r1")])
                if rt != 0:
                    ok = False
                    reasons.append("%s: повторений fix-a после триггера=%s"
                                   % (h, rt))
        status = "SUFFICIENT" if ok else "INSUFFICIENT"
        if not s_trig and not n_trig:
            status = "NO-EVENT"  # событие нигде не возникло (EF-3)
        elif right == "X" and not s_trig:
            status = "NO-EVENT"
        verdicts[pol] = (status, s_trig, n_trig, reasons)
        w("%s: %s | S-триггеры=%s N-триггеры=%s%s" % (
            pol, status, s_trig, n_trig,
            (" | " + "; ".join(reasons)) if reasons else ""))
    w("")

    w("=== PER-CELL на G-single (N1D,N1V,NaD + S; вложенный анализ) ===")
    for pol in policies:
        right = pol[-1]
        trig_h = trigger_histories(cells, pol, "r1")
        s_trig = [h for h in trig_h if h in S_HISTS]
        n_single = [h for h in trig_h if h in ("N1D", "N1V", "NaD")]
        reasons = []
        ok = True
        if right == "X":
            if not s_trig:
                ok = False
                reasons.append("нет S-историй события")
            for h in s_trig:
                fs = first_success_after_switch(cells[(pol, h, "r1")])
                if fs is None:
                    ok = False
                    reasons.append("%s: success не достигнут" % h)
            for h in n_single:
                fs = first_success_step(cells[(pol, h, "r1")])
                bf = base_succ.get(h)
                if fs is None or (bf is not None and fs > bf):
                    ok = False
                    reasons.append("%s: восстановление %s vs %s"
                                   % (h, fs, bf))
        else:
            for h in n_single:
                fs = first_success_step(cells[(pol, h, "r1")])
                bf = base_succ.get(h)
                if fs is None or (bf is not None and fs > bf):
                    ok = False
                    reasons.append("%s: восстановление %s vs %s"
                                   % (h, fs, bf))
            for h in s_trig:
                rt = retries_after_trigger(cells[(pol, h, "r1")])
                if rt != 0:
                    ok = False
                    reasons.append("%s: повторений после триггера=%s"
                                   % (h, rt))
        status = "SUFFICIENT" if ok else "INSUFFICIENT"
        if not s_trig and not n_single:
            status = "NO-EVENT"
        elif right == "X" and not s_trig:
            status = "NO-EVENT"
        w("%s: %s | S=%s N-single=%s%s" % (
            pol, status, s_trig, n_single,
            (" | " + "; ".join(reasons[:3])) if reasons else ""))
    w("")

    w("=== E6-КОНТРОЛЬ: вторичная цена explore ===")
    for h in ("E6N", "E6S"):
        b = cells[("B", h, "r1")]
        x = cells[("E6X", h, "r1")]
        nb = sum(1 for s in b["steps"] if s.get("action") == "fix-aq")
        nx = sum(1 for s in x["steps"] if s.get("action") == "fix-aq")
        w("  %s: baseline fix-aq-эпизодов=%d, E6X fix-aq-эпизодов=%d "
          "(право выдано БЕЗ failure-сигнала; цена — лишняя линия "
          "fix-aq в живом мире)" % (h, nb, nx))
    w("")

    w("=== L6-WALK и checks ===")
    l6_bad = 0
    chk_ok = 0
    chk_bad = []
    for key, r in cells.items():
        l6_bad += len(l6_walk(r))
        for c in r.get("checks", []):
            if c.get("granted_excluded"):
                chk_ok += 1
            else:
                chk_bad.append((key, c))
    w("L6-нарушений: %d" % l6_bad)
    w("checks granted->excluded: %d; прочих: %d %s" % (
        chk_ok, len(chk_bad),
        chk_bad[:4] if chk_bad else ""))
    w("")

    w("=== РЕГРЕССИОННЫЙ ЯКОРЬ (B N1D/N1V) ===")
    for h in ("N1D", "N1V"):
        for rep in ("r1", "r2"):
            r = cells[("B", h, rep)]
            k1 = r["line_trace"][0][0]
            ok = (k1["outcome"] == "success" and
                  (k1["aw"] or {}).get("V") == "1" and k1["gen"] == 1)
            w("  B %s %s: K1 aw=%s gen=%s -> %s" % (
                h, rep, k1["aw"], k1["gen"], "OK" if ok else "FAIL"))
    w("")

    aud = all(r["audit_before"] == r["audit_after"] for r in cells.values())
    w("audit слоёв: %s" % ("OK (100/100)" if aud else "НАРУШЕН"))

    with open(os.path.join(DIR, "EP1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved EP1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
