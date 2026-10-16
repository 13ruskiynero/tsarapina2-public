# -*- coding: utf-8 -*-
"""LP-3 analyzer (FROZEN 07.09.2026).

Читает LP3_records_{F0,F1,F2}.json (RAW; анализ только после полного
RAW). Критерии (DESIGN р.5, PROTOCOL р.4):
  - F1: K2+ aw_clean (aw=={E:absent}, V ∉ aw), reopened_aw/locus=0;
    K1 — honest-норма;
  - монотонность раздельно: evidence_signature(K) (нормализованные
    obs без episode_refs): sig(K1)⊆sig(K2)⊆...; episode_refs(K) —
    provenance coverage: refs(K_g) ⊇ refs(K_{g-1}) для общих сигнатур;
  - (a) на K2+, (b) на K3+; source сохраняется;
  - F0-контраст: K2 чист, K3 V→aw; F2-контраст: fail-entries=0;
  - детерминизм r1≡r2; audit.
K-поколения = success-шаги по порядку. Пишет LP3_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
BRANCHES = ["F0", "F1", "F2"]
SEQS = ["P1", "P2"]
EXPECTED_OUTCOMES = {"w1": "success", "wY": "success",
                     "noise": "partial", "noise2": "partial"}
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(branch):
    with open(os.path.join(DIR, "LP3_records_%s.json" % branch),
              encoding="utf-8") as f:
        return json.load(f)


def row_of(step, kid):
    for r in step.get("snapshot") or []:
        if r["knowledge_id"] == kid:
            return r
    return None


def classify(step):
    pi = step.get("prior_info") or {}
    if not pi:
        return None
    if pi.get("pivot_id") is None:
        return "honest_q1"
    if pi.get("pivot_has_aw"):
        return "normal_fb"
    return "honest_equiv" if not pi.get("fb_existed") else "reopened"


def entry_kind(o):
    if o.get("source") == "verified failure":
        return "fail_a" if o.get("signal") else "fail_b"
    return "success"


def obs_norm(obs):
    out = []
    for o in obs or []:
        out.append({k: v for k, v in sorted(o.items())
                    if k != "episode_refs"})
    return sorted(out, key=str)


def gen_chain(run):
    """Поколения: success-шаги по порядку -> (label, row)."""
    chain = []
    for s in run["steps"]:
        if s["outcome"] != "success":
            continue
        kid = s.get("created_knowledge_id")
        r = row_of(s, kid) if kid else None
        if r is not None:
            chain.append((classify(s), r))
    return chain


def run_fp(run, final_map):
    """Нормализованный отпечаток прогона."""
    steps = []
    for s in run["steps"]:
        kid = s.get("created_knowledge_id")
        r = row_of(s, kid) if kid else None
        steps.append([s.get("world"), s.get("outcome"),
                      sorted((r.get("applicable_when") or {}).items())
                      if r else None,
                      obs_norm(r.get("applicability_observations"))
                      if r else None])
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
    chain = gen_chain(run)
    gens = []
    for g, (lab, r) in enumerate(chain, start=1):
        aw = r.get("applicable_when") or {}
        obs = r.get("applicability_observations") or []
        sig = set(json.dumps(e, ensure_ascii=False, sort_keys=True)
                  for e in obs_norm(obs))
        kinds = [entry_kind(o) for o in obs]
        refs = {}
        for o in obs:
            s = json.dumps({k: v for k, v in sorted(o.items())
                            if k != "episode_refs"},
                           ensure_ascii=False, sort_keys=True)
            refs[s] = set(o.get("episode_refs") or [])
        gens.append({"gen": g, "label": lab, "kid": r["knowledge_id"],
                     "aw": aw, "aw_clean": "V" not in aw,
                     "kinds": kinds, "sig": sig, "refs": refs,
                     "f_count": sum(1 for k in kinds
                                    if k in ("fail_a", "fail_b"))})
    final_map = {r["knowledge_id"]: r for r in steps[-1]["snapshot"]}
    return {"outcomes": outcomes, "deviations": deviations, "gens": gens,
            "fp": run_fp(run, final_map),
            "probes": run["probes"], "final_map": final_map}


def check_run(a, branch):
    """Возвращает (ok, причины) по критериям DESIGN р.5."""
    gens = a["gens"]
    reasons = []
    if len(gens) < 2:
        return False, ["нет поколений K2+"]
    k1 = gens[0]
    if branch == "F1" and k1["aw_clean"]:
        # K1 honest-норма: V в aw ожидается на F1/F2/F0 (Q1-срез)
        pass
    ok = True
    for g in gens[1:]:
        if not g["aw_clean"] or g["aw"] != {"E": "absent"}:
            ok = False
            reasons.append("K%d aw=%s" % (g["gen"], g["aw"]))
        if g["label"] in ("reopened", "honest_equiv"):
            reasons.append("K%d label=%s" % (g["gen"], g["label"]))
    # монотонность сигнатур
    prev = set()
    for g in gens:
        if not (prev <= g["sig"]):
            ok = False
            reasons.append("K%d sig убывает" % g["gen"])
        # provenance coverage для общих сигнатур
        for s in (prev & g["sig"]):
            prev_refs = None
            for g0 in gens:
                if g0["gen"] < g["gen"] and s in g0["refs"]:
                    prev_refs = g0["refs"][s]
            if prev_refs is not None and not (prev_refs <= g["refs"][s]):
                ok = False
                reasons.append("K%d refs убывают для %s" % (g["gen"], s))
        prev = g["sig"]
    # состав: (a) на K2+, (b) на K3+
    kinds_by_gen = {g["gen"]: g["kinds"] for g in gens}
    if len(gens) >= 2 and not any(k == "fail_a" for k in kinds_by_gen[2]):
        ok = False
        reasons.append("нет (a) на K2")
    if len(gens) >= 3 and not any(k == "fail_b" for k in kinds_by_gen[3]):
        ok = False
        reasons.append("нет (b) на K3")
    return ok, reasons


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
    w("LP-3: АНАЛИЗ (FROZEN; критерии DESIGN р.5, PROTOCOL р.4)")
    for b in BRANCHES:
        d = data[b]
        w("audit %s layers unchanged: %s" % (
            b, d["audit_before"] == d["audit_after"]))
    w("")

    summ = {}
    fprints = {}
    checks = {}
    for b in BRANCHES:
        summ[b] = {}
        fprints[b] = {}
        checks[b] = {}
        for run in data[b]["runs"]:
            s = run["sequence"]
            summ[b].setdefault(s, {})[run["rep"]] = analyze_run(run)
            fprints[b].setdefault(s, {})[run["rep"]] = summ[b][s][
                run["rep"]]["fp"]
            checks[b].setdefault(s, {})[run["rep"]] = check_run(
                summ[b][s][run["rep"]], b)

    for b in BRANCHES:
        for run in data[b]["runs"]:
            s = run["sequence"]
            a = summ[b][s][run["rep"]]
            w("=== %s %s %s ===" % (b, s, run["rep"]))
            w("  шаги: %s" % a["outcomes"])
            if a["deviations"]:
                w("  !!! ОТКЛОНЕНИЕ outcome: %s" % a["deviations"])
            for g in a["gens"]:
                sigs = sorted(g["sig"])
                w("  K%d: aw=%-24s aw_clean=%s kinds=%s sig=%d refs=%d "
                  "label=%s" % (g["gen"], fmt_aw(g["aw"]), g["aw_clean"],
                                g["kinds"], len(sigs),
                                sum(len(v) for v in g["refs"].values()),
                                g["label"]))
                for sig_s in sigs:
                    w("      sig: %s | refs=%d" % (
                        sig_s, len(g["refs"].get(sig_s, []))))
            for p in a["probes"]:
                w("  проба %-6s obs=%s -> %s refs=%s" % (
                    p["world"], p["obs"], p["candidate_commands"],
                    fmt_refs(p, a["final_map"])))
            ok, reasons = checks[b][s][run["rep"]]
            w("  критерии: %s%s" % ("OK" if ok else "НАРУШЕНЫ",
                                    ("; " + "; ".join(reasons))
                                    if reasons else ""))
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

    # сводка поколений (r1)
    w("=== СВОДКА K-цепочек (r1): поколение: aw | kinds ===")
    for b in BRANCHES:
        for s in SEQS:
            a = summ[b][s]["r1"]
            parts = ["K%d:%s[%s]" % (g["gen"], fmt_aw(g["aw"]),
                                     ",".join(g["kinds"]))
                     for g in a["gens"]]
            ok, _ = checks[b][s]["r1"]
            w("  %s %s: %s  -> %s" % (b, s, "  ".join(parts),
                                      "OK" if ok else "НАРУШЕНЫ"))
    w("")

    # вердикт
    w("=== ВЕРДИКТ ===")
    f1_ok = all(checks["F1"][s][rep][0]
                for s in SEQS for rep in ("r1", "r2"))
    f0_k2 = all(summ["F0"][s][rep]["gens"][1]["aw_clean"]
                for s in SEQS for rep in ("r1", "r2"))
    f0_k3_fail = all(not summ["F0"][s][rep]["gens"][2]["aw_clean"]
                     for s in SEQS for rep in ("r1", "r2"))
    f2_empty = all(g["f_count"] == 0
                   for s in SEQS for rep in ("r1", "r2")
                   for g in summ["F2"][s][rep]["gens"])
    f2_clean = all(g["aw_clean"] for s in SEQS for rep in ("r1", "r2")
                   for g in summ["F2"][s][rep]["gens"][1:])
    w("F1 (выбранная семантика): контроль persistence %s" % (
        "ПРОЙДЕН — evidence пережило 2–3 цикла acquisition, "
        "V ∉ aw на K2+" if f1_ok else
        "ПРОВАЛЕН — фиксируем boundary, пересматриваем merge-семантику "
        "(код не чинить)"))
    w("F0-контраст: K2 aw чист (recorder спасает локальную форму): %s; "
      "K3 V→aw (формат без семантики не персистентен): %s" % (
        f0_k2, f0_k3_fail))
    w("F2-контраст: aw чист на K2+, failure-derived отсутствуют: %s"
      % (f2_clean and f2_empty))
    w("Детерминизм r1 ≡ r2: %s" % det_ok)
    w("«Победитель» не пересматривается (F1); v0.6 остаётся FROZEN. "
      "После вердикта — APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md "
      "(L1–L5) + integration gate по слову профессора.")

    with open(os.path.join(DIR, "LP3_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved LP3_ANALYSIS.txt")


if __name__ == "__main__":
    main()
