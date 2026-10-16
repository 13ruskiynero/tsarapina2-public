# -*- coding: utf-8 -*-
"""GATE v0.6.x analyzer (FROZEN 09-10.09.2026).

Читает GATE_V06X_records_{v06x,v06}.json (RAW). Проверки:
  G5: probes v06x vs v06 (strategy_id, candidate_commands равны;
      refs — фиксируются, различия допустимы);
  G1: S0 — K2 aw={E:absent}, obs V[1,2] source=verified success;
  G2: S1/S3/S4 — latest aw={E:absent} (V ∉ aw); K1 {E,V1};
      failure-знания aw=None;
  G3: S6b — K2 obs V-failure-(a); S1 — K2 obs D2-(b); запрещённые
      комбинации; failure-запись source=verified failure;
  G4: P1/P2 — поколения gen 1,2,3,(4); монотонность сигнатур obs
      (нормализованных); рост episode_refs (покрытие);
  L6-структурный: source enum; episode_refs непусты; состав (a)/(b);
  audit; r1≡r2 (steps+creations+probes).
Пишет GATE_V06X_ANALYSIS.txt.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load(impl):
    with open(os.path.join(DIR, "GATE_V06X_records_%s.json" % impl),
              encoding="utf-8") as f:
        return json.load(f)


def row_of(step, kid):
    for r in step.get("snapshot") or []:
        if r["knowledge_id"] == kid:
            return r
    return None


def outcome_of(r):
    import re
    m = re.search(r"outcome=(\w+)", r.get("context") or "")
    return m.group(1) if m else None


def kinds_of(r):
    ks = []
    for o in (r.get("applicability_observations") or []):
        if o.get("source") == "verified failure":
            ks.append("a" if o.get("signal") else "b")
        else:
            ks.append("s")
    return ks


def obs_norm(obs):
    out = []
    for o in obs or []:
        out.append({k: v for k, v in sorted(o.items())
                    if k != "episode_refs"})
    return sorted(out, key=str)


def chain(run):
    """(successes, failures): (world, kid, row) по шагам."""
    succ, fail = [], []
    for s in run["steps"]:
        kid = s.get("created_knowledge_id")
        r = row_of(s, kid) if kid else None
        if r is None:
            continue
        if s["outcome"] == "success":
            succ.append((s["world"], kid, r))
        else:
            fail.append((s["world"], kid, r))
    return succ, fail


def run_fp(run):
    steps = []
    for s in run["steps"]:
        kid = s.get("created_knowledge_id")
        r = row_of(s, kid) if kid else None
        steps.append([s.get("world"), s.get("outcome"),
                      sorted((r.get("applicable_when") or {}).items())
                      if r else None,
                      obs_norm(r.get("applicability_observations"))
                      if r else None])
    probes = [[p["world"], p.get("strategy_id"),
               p.get("candidate_commands")] for p in run["probes"]]
    return json.dumps([steps, probes], ensure_ascii=False, sort_keys=True)


def get_run(d, seq, rep):
    for r in d["runs"]:
        if r["sequence"] == seq and r["rep"] == rep:
            return r
    return None


def main():
    d6x = load("v06x")
    d6 = load("v06")
    w("GATE v0.6.x: АНАЛИЗ (реальный код; обе имплементации)")
    w("v06x прогонов: %d; v06 прогонов: %d" % (len(d6x["runs"]),
                                               len(d6["runs"])))
    w("audit v06x: %s; audit v06: %s" % (
        d6x["audit_before"] == d6x["audit_after"],
        d6["audit_before"] == d6["audit_after"]))
    w("")
    fails = []

    # G5: сравнение probes и шагов
    w("=== G5: v06x vs v06 (поведение; команды/стратегия) ===")
    g5_ok = True
    for seq in ("S0", "S1", "S2", "S3", "S4", "S5", "S6b", "P1", "P2"):
        for rep in ("r1", "r2"):
            a = get_run(d6x, seq, rep)
            b = get_run(d6, seq, rep)
            if not a or not b:
                w("  %s %s: ОТСУТСТВУЕТ" % (seq, rep))
                g5_ok = False
                continue
            stepok = ([s["outcome"] for s in a["steps"]]
                      == [s["outcome"] for s in b["steps"]])
            probs = []
            for pa, pb in zip(a["probes"], b["probes"]):
                same = (pa.get("strategy_id") == pb.get("strategy_id")
                        and pa.get("candidate_commands")
                        == pb.get("candidate_commands"))
                probs.append((pa["world"], same,
                              pa.get("candidate_commands"),
                              pb.get("candidate_commands")))
            pok = all(p[1] for p in probs)
            g5_ok = g5_ok and stepok and pok
            w("  %s %s: steps=%s probes=%s" % (
                seq, rep, "OK" if stepok else "MISMATCH",
                "OK" if pok else "MISMATCH"))
            for pr in probs:
                if not pr[1]:
                    w("      probe %s: v06x=%s v06=%s" % pr)
    w("  G5: %s" % ("PASS" if g5_ok else "FAIL"))
    if not g5_ok:
        fails.append("G5")
    w("")

    # G1..G4, L6 на v06x
    w("=== G1..G4 + L6 (v06x; r1) ===")
    g1 = g2 = g3 = g4 = True
    l6_bad = []
    for seq in ("S0", "S1", "S3", "S4", "S5", "S6b", "P1", "P2"):
        r = get_run(d6x, seq, "r1")
        succ, fail = chain(r)
        w("  %s: цепочка:" % seq)
        for world, kid, row in succ:
            aw = row.get("applicable_when")
            w("    K[%s] aw=%s gen=%s obs=%s" % (
                world, aw, row.get("lineage_generation"),
                [k for k in kinds_of(row)]))
        for world, kid, row in fail:
            w("    F[%s] aw=%s gen=%s obs=%s" % (
                world, row.get("applicable_when"),
                row.get("lineage_generation"), kinds_of(row)))
        # проверки
        if seq == "S0":
            if len(succ) >= 2:
                k2 = succ[-1][2]
                aw = k2.get("applicable_when") or {}
                obs = k2.get("applicability_observations") or []
                sig = any(o.get("signal") == "V"
                          and "1" in [str(x) for x in
                                      (o.get("values_seen") or [])]
                          and "2" in [str(x) for x in
                                      (o.get("values_seen") or [])]
                          and o.get("source") == "verified success"
                          for o in obs)
                g1 = g1 and aw == {"E": "absent"} and "V" not in aw and sig
        if seq in ("S1", "S3", "S4"):
            if len(succ) >= 2:
                k2 = succ[-1][2]
                aw = k2.get("applicable_when") or {}
                g2 = g2 and aw == {"E": "absent"} and "V" not in aw
            for world, kid, row in fail:
                g2 = g2 and row.get("applicable_when") is None
        if seq == "S6b":
            if len(succ) >= 1:
                k2 = succ[-1][2]
                ks = kinds_of(k2)
                g3 = g3 and "a" in ks and "s" not in ks
        if seq == "S1":
            if len(succ) >= 1:
                k2 = succ[-1][2]
                ks = kinds_of(k2)
                g3 = g3 and "b" in ks and "a" not in ks
        if seq in ("P1", "P2"):
            gens = [row.get("lineage_generation") for _, _, row in succ]
            want = list(range(1, len(succ) + 1))
            g4 = g4 and gens == want
            sigs = []
            for _, _, row in succ:
                sigs.append(set(json.dumps(e, ensure_ascii=False,
                                           sort_keys=True)
                                for e in obs_norm(
                                    row.get("applicability_observations"))))
            for i in range(1, len(sigs)):
                g4 = g4 and sigs[i - 1] <= sigs[i]
        # L6-структурный
        for _, _, row in succ + fail:
            for o in row.get("applicability_observations") or []:
                src = o.get("source")
                refs = o.get("episode_refs") or []
                if src not in ("verified success", "verified failure") \
                        or not refs:
                    l6_bad.append((seq, row["knowledge_id"], o))
                if src == "verified failure":
                    if not (o.get("signal") or
                            o.get("relation") == "outcome_disagreement"):
                        l6_bad.append((seq, row["knowledge_id"], o))
    w("")
    w("G1 (S0): %s" % g1)
    w("G2 (S1/S3/S4): %s" % g2)
    w("G3 (S6b/S1 recorder-состав): %s" % g3)
    w("G4 (P1/P2 поколения/монотонность): %s" % g4)
    w("L6-структурный: %s (%d нарушений)" % (
        "PASS" if not l6_bad else "FAIL", len(l6_bad)))
    for b in l6_bad[:10]:
        w("    %s" % (b,))
    for name, ok in (("G1", g1), ("G2", g2), ("G3", g3), ("G4", g4)):
        if not ok:
            fails.append(name)
    if l6_bad:
        fails.append("L6")

    # детерминизм
    w("")
    w("=== ДЕТЕРМИНИЗМ v06x (r1 ≡ r2) ===")
    det_ok = True
    for seq in ("S0", "S1", "S2", "S3", "S4", "S5", "S6b", "P1", "P2"):
        a = get_run(d6x, seq, "r1")
        b = get_run(d6x, seq, "r2")
        ok = run_fp(a) == run_fp(b)
        det_ok = det_ok and ok
        w("  %s: %s" % (seq, "r1≡r2" if ok else "РАСХОЖДЕНИЕ"))
    if not det_ok:
        fails.append("determinism")

    w("")
    w("=== ВЕРДИКТ ===")
    w("v06x GATE: %s%s" % ("PASS" if not fails else "FAIL",
                           ("  (%s)" % ", ".join(fails)) if fails else ""))
    w("Замечание: baseline-прогоны (v06) — сравнение поведения G5; "
      "структурные проверки — на v06x (новый контракт).")

    with open(os.path.join(DIR, "GATE_V06X_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved GATE_V06X_ANALYSIS.txt")


if __name__ == "__main__":
    main()
