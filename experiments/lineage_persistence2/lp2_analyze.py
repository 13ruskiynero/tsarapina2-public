# -*- coding: utf-8 -*-
"""LP-2 analyzer (FROZEN 07.09.2026).

Читает LP2_records_{F0,F1,F2}.json (RAW; анализ только после полного
RAW — все 3 ветки). Критерии (DESIGN р.6, PROTOCOL р.5):
  - aw-чистота: V ∉ applicable_when(latest); регистры: reopened_aw
    (V в aw: pivot без поля при fb-структуре), reopened_locus (тот же
    локалитет независимо от V), honest, mech;
  - obs-состав: success-derived vs failure-derived (source="verified
    failure"; тип (a) signal=V / (b) без signal);
  - Q2: F0-S6a(=S1) vs F0-S6b — aw-чистота (формат/структура);
  - Q1: F1 vs F2 на S1/S3/S4/S6b — состав obs при одинаковом aw;
  - критерий успеха F1: failure-obs как evidence, aw не меняется
    (aw={E:absent,V:2} после S6b = провал F1);
  - детерминизм r1 ≡ r2; F1/F2-сравнение (ожидаемо различаются).
Пишет LP2_ANALYSIS.txt и дублирует в stdout.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
BRANCHES = ["F0", "F1", "F2"]
SEQS = ["S0", "S1", "S2", "S3", "S4", "S5", "S6b"]
EXPECTED_OUTCOMES = {"w1": "success", "wY": "success",
                     "noise": "partial", "noise2": "partial"}
CRIT_SEQS = ("S0", "S1", "S2", "S3", "S4", "S6b")  # latest-критерий
DISC_SEQS = ("S1", "S3", "S4", "S6b")              # Q1-дискриминатор

out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(branch):
    with open(os.path.join(DIR, "LP2_records_%s.json" % branch),
              encoding="utf-8") as f:
        return json.load(f)


def row_of(step, kid):
    for r in step.get("snapshot") or []:
        if r["knowledge_id"] == kid:
            return r
    return None


def classify(step):
    """Метка success-шага по prior/pivot."""
    pi = step.get("prior_info") or {}
    if not pi:
        return None
    if pi.get("pivot_id") is None:
        return "honest_q1"
    if pi.get("pivot_has_aw"):
        return "normal_fb"
    return "honest_equiv" if not pi.get("fb_existed") else "reopened"


def entry_kind(o):
    """'fail_a' | 'fail_b' | 'success'."""
    if o.get("source") == "verified failure":
        return "fail_a" if o.get("signal") else "fail_b"
    return "success"


def obs_norm(obs):
    out = []
    for o in obs or []:
        out.append({k: v for k, v in sorted(o.items())
                    if k != "episode_refs"})
    return sorted(out, key=str)


def step_fp(step):
    kid = step.get("created_knowledge_id")
    r = row_of(step, kid) if kid else None
    return [step.get("world"), step.get("outcome"), classify(step),
            sorted((r.get("applicable_when") or {}).items()) if r else None,
            obs_norm(r.get("applicability_observations")) if r else None]


def run_fp(run, final_map):
    steps = [step_fp(s) for s in run["steps"]]
    probes = []
    for p in run["probes"]:
        refs = []
        for kid in p.get("knowledge_refs") or []:
            r = final_map.get(kid)
            refs.append(sorted((r.get("applicable_when") or {}).items())
                        if r else None)
        probes.append([p["world"], p["candidate_commands"],
                       sorted([str(x) for x in refs])])
    return json.dumps([steps, probes], ensure_ascii=False, sort_keys=True)


def analyze_run(run):
    steps = run["steps"]
    outcomes = [(s["world"], s["outcome"]) for s in steps]
    deviations = [o for o in outcomes
                  if EXPECTED_OUTCOMES.get(o[0]) != o[1]]
    counters = {"honest": 0, "reopened_aw": 0, "reopened_locus": 0,
                "mech": 0}
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
            counters["reopened_locus"] += 1
            counters["reopened_aw"] += 1 if has_v else 0
        elif lab in ("honest_q1", "honest_equiv"):
            counters["honest"] += 1 if has_v else 0
            if lab == "honest_equiv":
                counters["mech"] += 1
    last_r = row_of(steps[-1], steps[-1].get("created_knowledge_id"))
    aw = last_r.get("applicable_when") or {}
    obs = last_r.get("applicability_observations") or []
    aw_clean = "V" not in aw
    v_obs = [o for o in obs if o.get("signal") == "V"]
    aw_ok = aw == {"E": "absent"}
    obs_ok = bool(v_obs and v_obs[0].get("values_seen") == ["1", "2"]
                  and v_obs[0].get("relation") == "disagreement")
    latest_ok = aw_ok and obs_ok and aw_clean
    kinds = [entry_kind(o) for o in obs]
    f_entries = sum(1 for k in kinds if k in ("fail_a", "fail_b"))
    s_entries = sum(1 for k in kinds if k == "success")
    final_map = {r["knowledge_id"]: r for r in steps[-1]["snapshot"]}
    return {"outcomes": outcomes, "deviations": deviations,
            "labels": labels, "counters": counters,
            "latest": {"kid": last_r["knowledge_id"], "aw": aw, "obs": obs,
                       "aw_clean": aw_clean, "latest_ok": latest_ok,
                       "kinds": kinds, "f_entries": f_entries,
                       "s_entries": s_entries,
                       "applies": run["sequence"] in CRIT_SEQS},
            "fp": run_fp(run, final_map),
            "probes": run["probes"], "final_map": final_map}


def fmt_aw(aw):
    if not aw:
        return "None"
    return "{" + ", ".join("%s: %s" % (k, json.dumps(v, ensure_ascii=False))
                           for k, v in sorted(aw.items())) + "}"


def fmt_obs_entry(o):
    e = {k: v for k, v in sorted(o.items()) if k != "episode_refs"}
    return json.dumps(e, ensure_ascii=False)


def fmt_refs(probe, final_map):
    parts = []
    for kid in probe.get("knowledge_refs") or []:
        r = final_map.get(kid)
        parts.append("%s(aw=%s)" % (kid[:14], fmt_aw(
            r.get("applicable_when") if r else None)))
    return parts


def main():
    data = {b: load(b) for b in BRANCHES}
    w("LP-2: АНАЛИЗ (FROZEN; критерии DESIGN р.6, PROTOCOL р.5)")
    for b in BRANCHES:
        d = data[b]
        w("audit %s layers unchanged: %s" % (
            b, d["audit_before"] == d["audit_after"]))
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
                if lab is None:
                    continue
                st = run["steps"][i]
                kid = st.get("created_knowledge_id")
                r = row_of(st, kid) if kid else None
                obs_kinds = [entry_kind(o) for o in
                             (r.get("applicability_observations") or [])]
                w("  m%d %-6s %-8s aw=%-26s obs=%s label=%s" % (
                    i + 1, st["world"], st["outcome"],
                    fmt_aw(r.get("applicable_when") if r else None),
                    obs_kinds, lab))
            L = a["latest"]
            c = a["counters"]
            crit = ("reopened_aw=%d reopened_locus=%d honest=%d mech=%d "
                    "| obs: fail=%d success=%d"
                    % (c["reopened_aw"], c["reopened_locus"], c["honest"],
                       c["mech"], L["f_entries"], L["s_entries"]))
            if L["applies"]:
                w("  latest: %s aw=%s aw_clean=%s" % (
                    L["kid"][:14], fmt_aw(L["aw"]), L["aw_clean"]))
                for o in L["obs"]:
                    w("    obs[%s] %s" % (entry_kind(o), fmt_obs_entry(o)))
                w("  критерий: %s; latest-уровень: %s"
                  % (crit, "PASS" if L["latest_ok"] else "FAIL"))
            else:
                w("  latest: %s aw=%s (S5: состояние)" % (L["kid"][:14],
                                                          fmt_aw(L["aw"])))
                w("  регистры: %s" % crit)
            for p in a["probes"]:
                w("  проба %-6s obs=%s -> %s refs=%s" % (
                    p["world"], p["obs"], p["candidate_commands"],
                    fmt_refs(p, a["final_map"])))
            w("")

    # детерминизм
    w("=== ДЕТЕРМИНИЗМ (r1 ≡ r2) ===")
    det_ok = True
    for b in BRANCHES:
        for s in SEQS:
            ok = fprints[b][s].get("r1") == fprints[b][s].get("r2")
            det_ok = det_ok and ok
            w("  %s %s: %s" % (b, s, "r1≡r2" if ok else "РАСХОЖДЕНИЕ"))
    w("")

    # сводка
    w("=== СВОДКА (r1): aw_clean | latest | reopened_aw/locus | honest "
      "| obs fail/success ===")
    for b in BRANCHES:
        row = []
        for s in SEQS:
            r = summ[b][s]["r1"]
            L = r["latest"]
            lv = ("PASS" if (L["applies"] and L["latest_ok"]) else
                  ("FAIL" if L["applies"] else "state"))
            row.append("%s:%s/%s/%d/%d/%d/%d/%d" % (
                s, L["aw_clean"], lv, r["counters"]["reopened_aw"],
                r["counters"]["reopened_locus"], r["counters"]["honest"],
                L["f_entries"], L["s_entries"]))
        w("  %s  %s" % (b, "  ".join(row)))
    w("")

    # F1 vs F2 сравнение
    w("=== F1 vs F2 (лемма LP-1 расширяется?) ===")
    eq_map = {}
    for s in SEQS:
        eq_map[s] = all(fprints["F1"][s][rep] == fprints["F2"][s][rep]
                        for rep in ("r1", "r2"))
        w("  %s: %s" % (s, "≡ (не различаются)" if eq_map[s]
                        else "РАЗЛИЧАЮТСЯ"))
    w("")

    # вердикт: Q2 и Q1 раздельно
    w("=== ВЕРДИКТ (раздельно Q2 и Q1) ===")
    f0 = {s: summ["F0"][s]["r1"] for s in SEQS}
    f1 = {s: summ["F1"][s]["r1"] for s in SEQS}
    f2 = {s: summ["F2"][s]["r1"] for s in SEQS}

    # Q2: формат/структура — F0-S6a(=S1) vs F0-S6b
    q2_s6a_fail = not f0["S1"]["latest"]["aw_clean"]   # V снова в aw
    q2_s6b_clean = f0["S6b"]["latest"]["aw_clean"]     # V остался в obs
    w("Q2 (F0): S6a(=S1) aw_clean=%s (ожидание: False — V возвращается "
      "в condition); S6b aw_clean=%s (ожидание: True — V уходит в obs)"
      % (f0["S1"]["latest"]["aw_clean"],
         f0["S6b"]["latest"]["aw_clean"]))
    w("Q2-вывод: %s" % (
        "ПОДТВЕРЖДЕНО: поведение F0 зависит от наличия attributable "
        "applicability signal в failure-записи — форматно-структурная "
        "граница механизма (не «failure пуст по природе»)" if
        (q2_s6a_fail and q2_s6b_clean) else
        "НЕ подтверждено в ожидаемой форме — см. RAW"))

    # Q1: F1 vs F2 — состав obs при одинаковом aw
    aw_same = all(f1[s]["latest"]["aw"] == f2[s]["latest"]["aw"]
                  for s in DISC_SEQS)
    f1_carries = all(f1[s]["latest"]["f_entries"] >= 1 for s in DISC_SEQS)
    f2_empty = all(f2[s]["latest"]["f_entries"] == 0 for s in DISC_SEQS)
    w("Q1: aw(F1)==aw(F2) на S1/S3/S4/S6b: %s; failure-derived в obs: "
      "F1 да на всех: %s; F2 нет ни на одной: %s"
      % (aw_same, f1_carries, f2_empty))
    w("Q1-вывод: %s" % (
        "ДИСКРИМИНАТОР УСТАНОВЛЕН: F1 и F2 различаются по составу "
        "observations (failure-derived сохраняются в F1 и недоступны "
        "в F2) при одинаковом applicable_when" if
        (aw_same and f1_carries and f2_empty and
         any(not eq_map[s] for s in DISC_SEQS)) else
        "НЕ различаются — лемма LP-1 расширяется на failure-obs"))

    # критерий успеха F1 (evidence-не-condition)
    f1_ok = f1["S6b"]["latest"]["aw_clean"] and \
        f1["S6b"]["latest"]["aw"] == {"E": "absent"} and \
        f1["S6b"]["latest"]["f_entries"] >= 1 and \
        f1["S6b"]["latest"]["s_entries"] >= 1
    w("Критерий успеха F1 (evidence, не condition: aw={E:absent}, obs "
      "V с обоими источниками после S6b): %s" % f1_ok)

    w("F0 регрессия (S1/S3/S4 aw FAIL как AB-1; S0/S2 aw чист): %s" % (
        all(not f0[s]["latest"]["aw_clean"] for s in ("S1", "S3", "S4"))
        and f0["S0"]["latest"]["aw_clean"]
        and f0["S2"]["latest"]["aw_clean"]))
    w("Детерминизм r1 ≡ r2: %s" % det_ok)
    w("«Победитель» F1/F2 НЕ назначается; v0.6 остаётся FROZEN; "
      "выбор семантики — слово профессора.")

    with open(os.path.join(DIR, "LP2_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved LP2_ANALYSIS.txt")


if __name__ == "__main__":
    main()
