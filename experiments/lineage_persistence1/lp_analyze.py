# -*- coding: utf-8 -*-
"""LP-1 analyzer (FROZEN 07.09.2026).

Читает LP1_records_{F0,F1,F2}.json (RAW). Критерий DESIGN р.5:
  - reopened == 0: версия с V в applicable_when, созданная при prior
    С field-bearing членами, но pivot без поля (структура обойдена);
  - honest (Q1-норма): V-версия при prior БЕЗ field-bearing членов
    (пустой prior = honest_q1; только без-полевые члены = honest_equiv,
    путь кода reopen, результат ≡ honest; регистр mech_reopen);
  - latest-уровень (S0–S4): aw == {E:absent}, obs V[1,2] disagreement,
    V ∉ aw(latest); S5 — только фиксация состояния;
  - детерминизм r1 ≡ r2 (нормализованный отпечаток);
  - лемма 2.1: F1 ≡ F2 на всех прогонах.
Пишет LP1_ANALYSIS.txt и дублирует в stdout.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
BRANCHES = ["F0", "F1", "F2"]
SEQS = ["S0", "S1", "S2", "S3", "S4", "S5"]
EXPECTED_OUTCOMES = {"w1": "success", "wY": "success", "noise": "partial"}

out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(branch):
    with open(os.path.join(DIR, "LP1_records_%s.json" % branch),
              encoding="utf-8") as f:
        return json.load(f)


def row_of(step, kid):
    for r in step.get("snapshot") or []:
        if r["knowledge_id"] == kid:
            return r
    return None


def classify(step):
    """Метка success-шага по prior/pivot (без учёта V в aw)."""
    pi = step.get("prior_info") or {}
    if not pi:
        return None
    if pi.get("pivot_id") is None:
        return "honest_q1"
    if pi.get("pivot_has_aw"):
        return "normal_fb"
    return "honest_equiv" if not pi.get("fb_existed") else "reopened"


def aw_sorted(aw):
    return sorted((aw or {}).items())


def obs_norm(obs):
    out = []
    for o in obs or []:
        out.append({"signal": o.get("signal"),
                    "values_seen": o.get("values_seen"),
                    "relation": o.get("relation")})
    return sorted(out, key=lambda o: str(o))


def step_fp(step):
    """Отпечаток шага (без id/времён/episode_refs)."""
    kid = step.get("created_knowledge_id")
    r = row_of(step, kid) if kid else None
    return [step.get("world"), step.get("outcome"),
            classify(step),
            aw_sorted(r.get("applicable_when")) if r else None,
            obs_norm(r.get("applicability_observations")) if r else None]


def run_fp(run, final_map):
    """Нормализованный отпечаток прогона (для r1≡r2 и F1≡F2)."""
    steps = [step_fp(s) for s in run["steps"]]
    probes = []
    for p in run["probes"]:
        refs = []
        for kid in p.get("knowledge_refs") or []:
            r = final_map.get(kid)
            refs.append(aw_sorted(r.get("applicable_when")) if r else None)
        probes.append([p["world"], p["candidate_commands"], sorted(
            [str(x) for x in refs])])
    return json.dumps([steps, probes], ensure_ascii=False, sort_keys=True)


def latest_of(run):
    """latest-знание линии: созданное финальным success-шагом."""
    step = run["steps"][-1]
    return row_of(step, step["created_knowledge_id"]), step


def analyze_run(run):
    """Возвращает сводку по прогону."""
    steps = run["steps"]
    outcomes = [(s["world"], s["outcome"]) for s in steps]
    deviations = [o for o in outcomes
                  if EXPECTED_OUTCOMES.get(o[0]) != o[1]]
    counters = {"honest": 0, "reopened": 0, "mech": 0, "normal_fb": 0}
    labels = []
    for s in steps:
        lab = classify(s)
        labels.append(lab)
        if lab is None:
            continue
        kid = s.get("created_knowledge_id")
        r = row_of(s, kid) if kid else None
        has_v = r is not None and "V" in (r.get("applicable_when") or {})
        if lab == "reopened":
            counters["reopened"] += 1 if has_v else 0
        elif lab in ("honest_q1", "honest_equiv"):
            counters["honest"] += 1 if has_v else 0
            if lab == "honest_equiv":
                counters["mech"] += 1
        elif lab == "normal_fb":
            counters["normal_fb"] += 1
    last_r, last_s = latest_of(run)
    aw = last_r.get("applicable_when") or {}
    obs = last_r.get("applicability_observations") or []
    v_obs = [o for o in obs if o.get("signal") == "V"]
    aw_ok = aw == {"E": "absent"}
    obs_ok = bool(v_obs and v_obs[0].get("values_seen") == ["1", "2"]
                  and v_obs[0].get("relation") == "disagreement")
    latest_ok = aw_ok and obs_ok and "V" not in aw
    final_map = {r["knowledge_id"]: r for r in steps[-1]["snapshot"]}
    return {"outcomes": outcomes, "deviations": deviations,
            "labels": labels, "counters": counters,
            "latest": {"kid": last_r["knowledge_id"], "aw": aw, "obs": obs,
                       "latest_ok": latest_ok,
                       "applies": run["sequence"] in ("S0", "S1", "S2",
                                                      "S3", "S4")},
            "fp": run_fp(run, final_map),
            "probes": run["probes"], "final_map": final_map}


def fmt_aw(aw):
    if not aw:
        return "None"
    return "{" + ", ".join("%s: %s" % (k, json.dumps(v, ensure_ascii=False))
                           for k, v in sorted(aw.items())) + "}"


def fmt_refs(probe, final_map):
    parts = []
    for kid in probe.get("knowledge_refs") or []:
        r = final_map.get(kid)
        parts.append("%s(aw=%s)" % (kid[:14], fmt_aw(
            r.get("applicable_when") if r else None)))
    return parts


def main():
    data = {b: load(b) for b in BRANCHES}
    w("LP-1: АНАЛИЗ (FROZEN; критерий DESIGN р.5, PROTOCOL р.4)")
    for b in BRANCHES:
        d = data[b]
        same = (d["audit_before"] == d["audit_after"])
        w("audit %s layers unchanged: %s" % (b, same))
    w("")

    summ = {}
    fprints = {}
    for b in BRANCHES:
        summ[b] = {}
        fprints[b] = {}
        for run in data[b]["runs"]:
            s = run["sequence"]
            summ[b].setdefault(s, {})[run["rep"]] = analyze_run(run)
            fprints[b].setdefault(s, {})[run["rep"]] = summ[b][s][
                run["rep"]]["fp"]

    for b in BRANCHES:
        for run in data[b]["runs"]:
            s = run["sequence"]
            a = summ[b][s][run["rep"]]
            w("=== %s %s %s ===" % (b, s, run["rep"]))
            w("  шаги: %s" % a["outcomes"])
            if a["deviations"]:
                w("  !!! ОТКЛОНЕНИЕ outcome: %s" % a["deviations"])
            for i, lab in enumerate(a["labels"]):
                st = run["steps"][i]
                if lab is None:
                    continue
                kid = st.get("created_knowledge_id")
                r = row_of(st, kid) if kid else None
                w("  m%d %-5s %-11s aw=%-28s label=%s" % (
                    i + 1, st["world"], st["outcome"],
                    fmt_aw(r.get("applicable_when") if r else None), lab))
            L = a["latest"]
            crit = ("reopened=%d honest=%d mech=%d"
                    % (a["counters"]["reopened"], a["counters"]["honest"],
                       a["counters"]["mech"]))
            if L["applies"]:
                w("  latest: %s aw=%s obs=%s" % (L["kid"][:14],
                                                 fmt_aw(L["aw"]), L["obs"]))
                w("  критерий: %s; latest-уровень: %s"
                  % (crit, "PASS" if L["latest_ok"] else "FAIL"))
            else:
                w("  latest: %s aw=%s obs=%s (S5: состояние, критерий не "
                  "применяется)" % (L["kid"][:14], fmt_aw(L["aw"]),
                                    L["obs"]))
                w("  регистры: %s" % crit)
            for p in a["probes"]:
                w("  проба %-5s obs=%s -> %s refs=%s" % (
                    p["world"], p["obs"], p["candidate_commands"],
                    fmt_refs(p, a["final_map"])))
            w("")

    # детерминизм r1 vs r2
    w("=== ДЕТЕРМИНИЗМ (r1 ≡ r2, нормализованный отпечаток) ===")
    det_ok = True
    for b in BRANCHES:
        for s in SEQS:
            f1 = fprints[b][s].get("r1")
            f2 = fprints[b][s].get("r2")
            ok = f1 == f2
            det_ok = det_ok and ok
            w("  %s %s: %s" % (b, s, "r1≡r2" if ok else "РАСХОЖДЕНИЕ"))
    w("")

    # сводка
    w("=== СВОДКА (reopened | honest | latest) ===")
    for b in BRANCHES:
        row = []
        for s in SEQS:
            reps = summ[b][s]
            r = reps["r1"]
            L = r["latest"]
            lv = "PASS" if (L["applies"] and L["latest_ok"]) else (
                "FAIL" if L["applies"] else "state")
            row.append("%s:%d/%d/%d/%s" % (s, r["counters"]["reopened"],
                                           r["counters"]["honest"],
                                           r["counters"]["mech"], lv))
        w("  %s  %s" % (b, "  ".join(row)))
    w("")

    # лемма F1 ≡ F2
    w("=== ЛЕММА 2.1 (F1 ≡ F2) ===")
    eq = True
    for s in SEQS:
        for rep in ("r1", "r2"):
            same = fprints["F1"][s][rep] == fprints["F2"][s][rep]
            eq = eq and same
            w("  %s %s: %s" % (s, rep, "≡" if same else "РАЗЛИЧАЮТСЯ"))
    w("")

    # вердикт
    w("=== ВЕРДИКТ ===")
    f0_sum = {s: summ["F0"][s]["r1"] for s in SEQS}
    crit_ok = True
    for b in BRANCHES:
        for s in SEQS:
            if summ[b][s]["r1"]["counters"]["reopened"] != 0:
                crit_ok = False
    repro_ok = all(not f0_sum[s]["latest"]["latest_ok"]
                   for s in ("S1", "S3", "S4")) and f0_sum["S2"]["latest"][
                       "latest_ok"] and f0_sum["S0"]["latest"]["latest_ok"]
    lp_ok = all(summ[b][s]["r1"]["counters"]["reopened"] == 0
                for b in ("F1", "F2") for s in SEQS)
    latest_fix = all(summ[b][s]["r1"]["latest"]["latest_ok"]
                     for b in ("F1", "F2") for s in ("S0", "S1", "S2", "S3",
                                                     "S4"))
    w("F0 воспроизводит AB-1 (S1/S3/S4 latest FAIL, S0/S2 PASS): %s"
      % repro_ok)
    w("Главный критерий (reopened == 0 во всех ветках): %s" % crit_ok)
    w("F1/F2 reopened == 0 (S1–S5): %s" % lp_ok)
    w("F1/F2 latest-уровень PASS на S0–S4: %s" % latest_fix)
    w("Лемма F1 ≡ F2 подтверждена: %s" % eq)
    w("Детерминизм r1 ≡ r2: %s" % det_ok)
    w("Проверка honest-следа (V в Q1-срезах есть и на S0/F0): %s"
      % (summ["F0"]["S0"]["r1"]["counters"]["honest"] >= 1))
    w("v0.6 остаётся FROZEN; «победитель» F1/F2 не назначается — "
      "слово профессора.")

    with open(os.path.join(DIR, "LP1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved LP1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
