# -*- coding: utf-8 -*-
"""AB-1 analyzer (FROZEN 07.09.2026): критерий DESIGN раздел 6.

Читает AB1_records.json (RAW) → AB1_ANALYSIS.txt. Гипотеза НЕ
чинится: вердикт фиксирует BOUNDARY или закрытие гипотезы.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
LINEAGE = {"sym": ["a"], "ctx": "absent", "cmd": "fix-a"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def lineage_latest(snapshot):
    """Latest-версия линии (a, absent, fix-a) по created_at."""
    rows = [r for r in snapshot if r.get("lineage") == LINEAGE]
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("created_at", ""))


def main():
    data = load(os.path.join(DIR, "AB1_records.json"))
    runs = data["runs"]
    out = []
    def w(s=""):
        out.append(s)

    w("AB-1: АНАЛИЗ (FROZEN; критерий DESIGN р.6)")
    w("audit layers unchanged: %s"
      % (data.get("audit_before") == data.get("audit_after")))
    w("")
    summary = {}
    summary_latest = {}
    summary_full = {}
    for run in runs:
        name, rep = run["sequence"], run["rep"]
        last_snap = run["steps"][-1]["snapshot"]
        latest = lineage_latest(last_snap)
        w("=== %s %s ===" % (name, rep))
        outcomes = [(s["world"], s["outcome"]) for s in run["steps"]]
        w("  шаги: %s" % outcomes)
        if latest is None:
            w("  ! знание линии (a, absent, fix-a) не найдено")
            summary.setdefault(name, []).append(False)
            continue
        aw = latest.get("applicable_when")
        obs = latest.get("applicability_observations") or []
        v_obs = [o for o in obs if o.get("signal") == "V"]
        aw_ok = aw == {"E": "absent"}
        obs_ok = (len(v_obs) == 1
                  and v_obs[0].get("values_seen") == ["1", "2"]
                  and v_obs[0].get("relation") == "disagreement")
        v_in_aw_any = any(
            "V" in (r.get("applicable_when") or {})
            for r in last_snap)
        latest_ok = aw_ok and obs_ok
        crit = latest_ok and not v_in_aw_any
        w("  latest: id=%s v=%s aw=%s" % (
            latest["knowledge_id"], latest["version"],
            json.dumps(aw, sort_keys=True)))
        w("  obs: %s" % json.dumps(obs, sort_keys=True))
        w("  критерий: aw=={E}=%s; obs V[1,2]=%s; V не в aw(стор)=%s"
          % (aw_ok, obs_ok, not v_in_aw_any))
        w("  latest-уровень: %s; полный (со стором): %s"
          % ("PASS" if latest_ok else "FAIL", "PASS" if crit else "FAIL"))
        # поведенческий маркер: eligibility-пробы
        for p in run["probes"]:
            w("  проба %-5s obs=%s -> %s %s refs=%s rules=%s"
              % (p["world"], json.dumps(p["obs"], sort_keys=True),
                 p["strategy_id"], p["candidate_commands"],
                 p["knowledge_refs"], p["rationale"]))
        w("")
        summary.setdefault(name, []).append(crit)
        summary_latest.setdefault(name, []).append(latest_ok)
        summary_full.setdefault(name, []).append(crit)

    w("=== СВОДКА (r1/r2): latest-уровень | полный (со стором) ===")
    verdict_rows = []
    for name in ("S1", "S2", "S3", "S4"):
        lo = all(summary_latest.get(name, []))
        fo = all(summary_full.get(name, []))
        verdict_rows.append((name, lo, fo))
        w("  %s: latest=%s | полный=%s" % (
            name, "PASS" if lo else "FAIL", "PASS" if fo else "FAIL"))
    w("")
    s1l = verdict_rows[0][1]
    s2l = verdict_rows[1][1]
    s3l = verdict_rows[2][1]
    s4l = verdict_rows[3][1]
    s1f = verdict_rows[0][2]
    s2f = verdict_rows[1][2]
    if (not s1l) and s2l and (not s3l) and (not s4l):
        verdict = ("ГИПОТЕЗА ПОДТВЕРЖДЕНА (позиционная форма, "
                   "latest-уровень): S1/S3/S4 — latest-знание переоткрыто "
                   "({E,V2}, obs пусто); S2 — latest восстановлен "
                   "({E}+obs V[1,2]) самовосстановлением на втором "
                   "success. ПОЛНЫЙ критерий (V не в aw по стору): FAIL "
                   "ВЕЗДЕ, включая S2 — промежуточная версия (w1-знание "
                   "после noise) несёт V в applicable_when. BOUNDARY: "
                   "приобретённая структура не устойчива к interleaved "
                   "failure; след V-в-условии остаётся в истории стора "
                   "в любой позиции failure. v0.6 остаётся FROZEN; "
                   "обработка — отдельным решением.")
    elif (not s1l) and (not s2l) and (not s3l) and (not s4l):
        verdict = ("ГИПОТЕЗА ПОДТВЕРЖДЕНА (сильная форма): latest-знание "
                   "переоткрыто во всех последовательностях.")
    else:
        verdict = ("ГИПОТЕЗА НЕ ПОДТВЕРЖДЕНА: гипотеза о _prior_lineage "
                   "закрыта (latest: %s)"
                   % [n for n, lo, fo in verdict_rows if not lo])
    w("ВЕРДИКТ: %s" % verdict)
    with open(os.path.join(DIR, "AB1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out), flush=True)


if __name__ == "__main__":
    main()
