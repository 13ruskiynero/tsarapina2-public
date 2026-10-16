# -*- coding: utf-8 -*-
"""RECON-1 analyzer (FROZEN 11.09.2026).

Читает long3 E0..E74 + RECON1_E*_r1.json + RECON1_probe*.json.
Секции: baseline (заморожен), PREFILL-фаза (отдельно), LLM-фаза
(S1/S2/S3 раздельно), окно у границы, классы I-0..I-4.
«Выпавшие строки» НЕ реконструируются; формулировка максимум —
«consistent with loss of some context information».
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
LONG3 = os.path.join(DIR, "..", "long3")
NUM_CTX = 4096
BASELINE_ACTIONS = ("fix-a", "systemctl restart tsasvc.service",
                    "systemctl start tsasvc.service", "fix-aq")
out_lines = []


def w(*a):
    line = " ".join(str(x) for x in a)
    out_lines.append(line)
    print(line)


def load_records():
    recs = []
    for ep in range(75):
        p = os.path.join(LONG3, "LONG3_E%d_r1.json" % ep)
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        r["_phase"] = "LONG3"
        recs.append(r)
    k = 75
    while True:
        p = os.path.join(DIR, "RECON1_E%d_r1.json" % k)
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        r["_phase"] = r.get("mode", "?")
        recs.append(r)
        k += 1
    return recs


def load_probes():
    probes = []
    for p in sorted(glob.glob(os.path.join(DIR, "RECON1_probe*.json")),
                    key=lambda x: int("".join(
                        c for c in os.path.basename(x)[12:-5]
                        if c.isdigit()) or 0)):
        with open(p, encoding="utf-8") as f:
            probes.append(json.load(f))
    return probes


def top_ref(rec):
    sb = rec.get("strategy_before") or {}
    refs = sb.get("knowledge_refs") or []
    if not refs:
        return None, sb.get("strategy_id")
    st = rec.get("knowledge_state_before") or {}
    top = (st.get(refs[0]) or {}).get("cmd")
    if top is None and rec.get("mode") == "LLM":
        top = (st.get(refs[0]) or {}).get("cmd")
    return top, sb.get("strategy_id")


def main():
    recs = load_records()
    probes = load_probes()
    stop = None
    sp = os.path.join(DIR, "RECON1_STOP.txt")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            stop = json.load(f)
    w("RECON-1: АНАЛИЗ (FROZEN)")
    w("")
    w("== RECON-BASELINE (заморожен; не пересчитывается) ==")
    w("proposal==top-ref: 35/75 (47%); блоки 5/7/8/7/8; "
      "aggregate sha long3: 7fadefd1…")
    w("")
    w("== Фаза PREFILL (отдельно от LLM trajectory) ==")
    pre = [r for r in recs if r.get("mode") == "PREFILL_OPERATOR"]
    w("эпизодов PREFILL: %d (E%s..E%s)" % (
        len(pre), pre[0]["ep"] if pre else "-",
        pre[-1]["ep"] if pre else "-"))
    w("probe-точки (counter/util/chars):")
    for pr in probes:
        w("  n_eps=%s counter=%s util=%s chars=%s err=%s" % (
            pr.get("n_episodes_total"), pr.get("counter"),
            pr.get("utilization"), pr.get("context_chars"),
            pr.get("error")))
    w("")
    llm = [r for r in recs if r.get("mode") == "LLM" and
           r.get("ep", 0) >= 75]
    w("== Фаза LLM: S1/S2/S3 ==")
    if not llm:
        w("LLM-эпизодов пока нет (prefill не завершён)")
    for r in llm:
        top, sid = top_ref(r)
        act = ((r.get("llm") or {}).get("parsed") or {}).get("action")
        eq = bool(top and act == top)
        w("E%d: S1 src_n=%s sid=%s top=%s | S2 counter=%s util=%s "
          "B2b=%s | S3 action=%s eq=%s dec=%s eval=%s"
          % (r["ep"], r.get("context_source") and
             len(r["context_source"]), sid, top, r.get("counter"),
             r.get("utilization"), r.get("plateau_B2b"), act, eq,
             r.get("decision"), r.get("evaluation")))
    w("")
    w("== Окно у границы ==")
    b2b_ep = next((r["ep"] for r in llm if r.get("plateau_B2b")),
                  None)
    if b2b_ep is None:
        w("B2b не наступил (или LLM-фаза не начата); стоп: %s"
          % (stop or "нет"))
    else:
        w("B2b зафиксирован на E%d" % b2b_ep)
        win = [r for r in llm if b2b_ep - 6 <= r["ep"] <= b2b_ep + 3]
        acts = []
        for r in win:
            top, sid = top_ref(r)
            act = ((r.get("llm") or {}).get("parsed") or {}).get(
                "action")
            acts.append((r["ep"], act, act == top,
                         r.get("plateau_B2b")))
            w("  E%d act=%s eq_top=%s B2b=%s"
              % (r["ep"], act, act == top, r.get("plateau_B2b")))
        w("")
        w("== Классы (окно n=%d; наблюдения, не статистика) =="
          % len(win))
        outside = [a for (e, a, eq, b) in acts
                   if a and a not in BASELINE_ACTIONS]
        eq_after = [eq for (e, a, eq, b) in acts
                    if b2b_ep <= e <= b2b_ep + 3]
        eq_before = [eq for (e, a, eq, b) in acts
                     if b2b_ep - 6 <= e < b2b_ep]
        w("I-0/I-1: B2b=%s; S3 в baseline-наборе=%s"
          % (True, not outside))
        if not outside:
            w("  → delivery boundary без proposal-эффекта в окне "
              "(S3≈baseline); behavioral consequence не наблюдалась")
        if outside:
            w("I-2 КАНДИДАТ: действия вне baseline-набора: %s"
              % sorted(set(outside)))
        if eq_before and eq_after and any(eq_after) and not any(
                eq_before):
            w("I-4 КАНДИДАТ: recovery (==top появляется после B2b)")
        w("(I-3: retrieval/strategy refs остаются непустыми на всех "
          "эпизодах окна: %s)" % all(
            (r.get("context_source") or []) and
            ((r.get("strategy_before") or {}).get("knowledge_refs"))
            for r in win if r.get("mode") == "LLM"))
        w("Напоминание: «какие строки выпали» НЕ наблюдаемо; "
          "максимум — 'consistent with loss of some context "
          "information'.")
    w("")
    w("== Стоп ==")
    w(json.dumps(stop, ensure_ascii=False) if stop else "нет")
    with open(os.path.join(DIR, "RECON1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    w("")
    w("saved RECON1_ANALYSIS.txt")


if __name__ == "__main__":
    main()
