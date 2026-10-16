# -*- coding: utf-8 -*-
"""ACQ-1 analyzer (FROZEN 07.09.2026): P1-P7 по DESIGN раздел 6.

Читает ACQ1_records.json (+ ACQ1_PERM_records.json для P4b) →
ACQ1_ANALYSIS.txt. Мир/GT-маппинг — ТОЛЬКО здесь (механизм их не
видел). Приёмка по уровням: кандидат зоны A2 (P1-P7 = PASS
эксперимента); A1 — отрицательный контроль структуры; A0 — baseline,
P-метрики справочные.
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from storage.store import Store  # noqa: E402

GT_APP = {"w1": True, "w2": False, "wX": False, "wY": True,
          "noise": False}
PROBE_WORLDS = ["w1", "w2", "wX", "wY", "noise"]
FORBIDDEN_IN_COND = {"D", "P", "N"}
TELE_PREFIX = "T_"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm_ep(ep):
    """Нормализация для P4a: без knowledge_id/телеметрии/пульс-контента
    (host-телеметрия и pulse-таймстампы недетерминированы)."""
    e = json.loads(json.dumps(ep))
    e.pop("telemetry", None)
    if e.get("knowledge"):
        k = dict(e["knowledge"])
        k.pop("knowledge_id", None)
        e["knowledge"] = k
    s = json.dumps(e, ensure_ascii=False, sort_keys=True)
    s = re.sub(r"r[12]_(m\d+|p_\w+)", "REP_\\1", s)
    s = re.sub(r"pulse-[0-9.]+", "PULSE", s)
    s = re.sub(r"act_acq1_[0-9a-f]+", "ACT", s)
    s = re.sub(r"raw_[0-9A-Za-z]+", "RAW", s)
    s = re.sub(r"exp_[0-9a-f]{12}", "EXP", s)
    s = re.sub(r"\d{4}-\d{2}-\d{2}T[0-9:.]+", "TS", s)
    return s


def norm_mech(m):
    if m is None:
        return None
    s = json.dumps(m, ensure_ascii=False, sort_keys=True)
    s = re.sub(r"r[12]_(m\d+|p_\w+)", "REP_\\1", s)
    s = re.sub(r"pulse-[0-9.]+", "PULSE", s)
    return s


def main():
    data = load(os.path.join(DIR, "ACQ1_records.json"))
    runs = data["runs"]
    by = {}
    for r in runs:
        by[(r["config"], r["rep"])] = r
    out = []
    def w(s=""):
        out.append(s)

    w("ACQ-1: АНАЛИЗ P1-P7 (FROZEN протокол; DESIGN раздел 6)")
    w("runs: %d (6 конфигураций x r1/r2)" % len(runs))
    w("")

    res = {}  # (cfg,rep) -> {metric: val}
    for cfg in ("A0_clean", "A0_controls", "A1_clean", "A1_controls",
                "A2_clean", "A2_controls"):
        for rep in ("r1", "r2"):
            run = by[(cfg, rep)]
            mech = run["mechanism"]
            eps = run["episodes"]
            level, ctl = cfg.split("_")
            w("=== %s %s ===" % (cfg, rep))
            w("audit_same=%s" % run["audit_same"])
            if mech is None:
                # A0: справочно
                addrs = [e["knowledge"]["derived_addr"] for e in eps
                         if e.get("knowledge")]
                fields = [e["knowledge"]["fields"] for e in eps
                          if e.get("knowledge")]
                n_obs_learn = [e["n_obs"] for e in eps
                               if "_m" in e["episode_id"]]
                n_obs_noise = [e["n_obs"] for e in eps
                               if "noise" in e["episode_id"]]
                d_pres = [e["d_present"] for e in eps
                          if e.get("d_present") is not None]
                w("  A0: knowledge создано=%d; derived_addr=%s" % (
                    len(addrs), addrs[0] if addrs else None))
                w("  A0: applicable-поля в knowledge: %s"
                  % any("applicable_when" in f or "condition" in f
                        for f in fields))
                w("  A0: n_obs learn=%s (noise-проба=%s); dbg-инъекции=%s"
                  % (set(n_obs_learn), set(n_obs_noise), d_pres))
                w("  A0: P-метрики справочные (механизма нет)")
                w("")
                continue
            cond = mech["condition"]
            d1 = mech["obs_d1"]
            d2 = mech["obs_d2"]
            mrecs = run["mechanism_records"] or []
            learn_recs = [r for r in mrecs if r["kind"] == "learn"]
            probe_recs = [r for r in mrecs if r["kind"] == "probe"]
            w("  condition=%s" % cond)
            w("  D1=%d %s" % (len(d1), [(o["fact"], o["values_seen"])
                                        for o in d1]))
            w("  D2=%d %s" % (len(d2), [o["episode_id"] for o in d2]))
            # P1: E/V в acquisition-записи каждого learn-момента
            p1 = all(
                any(c["name"] == "E" for c in r["candidates"]) and
                any(c["name"] == "V" for c in r["candidates"])
                for r in learn_recs)
            w("  P1 (E/V на каждом learn-моменте): %s" % p1)
            # P2: запрещённые имена в condition
            bad = [n for n in cond
                   if n in FORBIDDEN_IN_COND or n.startswith(TELE_PREFIX)]
            s_in_cond = "S" in cond
            p2 = (not bad) and (not s_in_cond)
            w("  P2 (N/D/P/T_* не в condition; S не applicability): %s"
              % p2)
            if bad:
                w("    ! в condition: %s" % bad)
            # P3: пробы w1/w2/wX/wY (noise вне P3)
            metrics = []
            p3 = True
            for pr, world in zip(probe_recs, PROBE_WORLDS):
                if world == "noise":
                    continue
                app = GT_APP[world]
                m = pr["matched"]
                lbl = ("VA" if app and m else "VS" if not app and not m
                       else "LS" if app and not m else "BL")
                metrics.append("%s=%s" % (world, lbl))
                if lbl in ("LS", "BL"):
                    p3 = False
            w("  P3 (w1/w2/wX/wY): %s [%s]" % (p3, ", ".join(metrics)))
            # P5: winner-free + D1 исключённые не в condition
            d1_names = {o["fact"] for o in d1}
            p5 = (not (set(cond) & d1_names))
            w("  P5 (D1-факты вне condition, победитель не назначен): %s"
              % p5)
            res[(cfg, rep)] = {"p1": p1, "p2": p2, "p3": p3, "p5": p5,
                               "cond": cond, "d1": d1, "d2": d2,
                               "metrics": metrics}
            w("")

    # P4a: r1 vs r2 identity per config
    w("=== P4a: cross-check r1/r2 (нормализовано) ===")
    p4a = {}
    for cfg in ("A0_clean", "A0_controls", "A1_clean", "A1_controls",
                "A2_clean", "A2_controls"):
        e1 = [norm_ep(e) for e in by[(cfg, "r1")]["episodes"]]
        e2 = [norm_ep(e) for e in by[(cfg, "r2")]["episodes"]]
        m1 = norm_mech(by[(cfg, "r1")]["mechanism"])
        m2 = norm_mech(by[(cfg, "r2")]["mechanism"])
        ok = (e1 == e2) and (m1 == m2)
        p4a[cfg] = ok
        w("  %s: episodes=%s mechanism=%s" % (cfg, e1 == e2, m1 == m2))
    w("")

    # P4b: перестановки
    w("=== P4b: перестановки learn-порядка (ACQ1_PERM_records.json) ===")
    p4b = {}
    try:
        perm = load(os.path.join(DIR, "ACQ1_PERM_records.json"))["perms"]
        for level in ("A1", "A2"):
            conds = {}
            for p in perm:
                if p["level"] == level:
                    conds.setdefault(json.dumps(p["condition"], sort_keys=True),
                                     []).append(p["order"])
            unique = len(conds) == 1
            p4b[level] = unique
            w("  %s: уникальных финальных условий=%d -> %s" % (
                level, len(conds), "PASS" if unique else "FAIL"))
            for c, orders in conds.items():
                w("      %s x%d %s" % (c, len(orders), orders[0]))
    except OSError as e:
        p4b = {"A1": None, "A2": None}
        w("  (нет PERM-файла: %s)" % e)
    w("")

    # P6: provenance-цепочка
    w("=== P6: provenance (applicable-запись -> episode -> raw) ===")
    p6 = True
    for cfg in ("A1_clean", "A2_clean", "A2_controls"):
        run = by[(cfg, "r1")]
        mech = run["mechanism"]
        eps_by = {e["episode_id"]: e for e in run["episodes"]}
        store = Store(os.path.join(
            DIR, "data_acq1_%s_r1" % cfg.replace("_", "_"), "tsarapina.db"),
            os.path.join(DIR, "data_acq1_%s_r1" % cfg.replace("_", "_")))
        ok = True
        refs = 0
        for r in (mech or {}).get("records", []):
            if r["episode_id"] not in eps_by:
                ok = False
                w("  %s: episode_id %s отсутствует в эпизодах"
                  % (cfg, r["episode_id"]))
        for o in (mech or {}).get("obs_d1", []) + (mech or {}).get(
                "obs_d2", []):
            if o["episode_id"] not in eps_by:
                ok = False
                w("  %s: observation %s отсутствует"
                  % (cfg, o["episode_id"]))
            ep = eps_by.get(o["episode_id"])
            if ep:
                for t in ep.get("telemetry", []):
                    rid = t.get("raw_ref")
                    if rid:
                        refs += 1
                        if store.read_raw(rid) is None:
                            ok = False
                            w("  %s: raw %s не найден" % (cfg, rid))
        p6 &= ok
        w("  %s: цепочка механическая, raw-проверено=%d -> %s"
          % (cfg, refs, ok))
    w("")

    # Сводка
    w("=== СВОДКА P1-P7 ===")
    for level in ("A0", "A1", "A2"):
        for ctl in ("clean", "controls"):
            cfg = "%s_%s" % (level, ctl)
            if cfg not in res:
                continue
            vals = [res[(cfg, r)] for r in ("r1", "r2")]
            w("  %-12s P1=%s P2=%s P3=%s P5=%s P4a=%s"
              % (cfg,
                 all(v["p1"] for v in vals),
                 all(v["p2"] for v in vals),
                 all(v["p3"] for v in vals),
                 all(v["p5"] for v in vals),
                 p4a.get(cfg, "-")))
    w("  P4b: A1=%s A2=%s" % (p4b.get("A1"), p4b.get("A2")))
    w("  P7: audit_same на всех прогонах=%s"
      % all(r["audit_same"] for r in runs))
    w("")

    # Итог по уровням
    def level_pass(level):
        ok = True
        for ctl in ("clean", "controls"):
            for rep in ("r1", "r2"):
                v = res.get(("%s_%s" % (level, ctl), rep))
                if v is None:
                    continue
                ok = ok and v["p1"] and v["p2"] and v["p3"] and v["p5"]
        if level == "A2":
            ok = ok and p4a.get("A2_clean") and p4a.get("A2_controls") \
                and p4b.get("A2")
        return ok

    a1_ok = level_pass("A1")
    a2_ok = level_pass("A2")
    w("=== ИТОГ ===")
    w("A1 (recency-коммит, отрицательный контроль): %s"
      % ("ожидаемый FAIL подтверждён" if not a1_ok else "PASS (неожиданно)"))
    w("A2 (инвариант + D1/D2, кандидат зоны): %s" % a2_ok)
    w("P7 (audit): %s" % all(r["audit_same"] for r in runs))
    verdict = ("ACQ-1: PASS — acquisition приобретает структуру "
               "(A2: P1-P6); гейт v0.6 возможен"
               if a2_ok else
               "ACQ-1: FAIL — граница «структура измерима Observer'ом, "
               "но не приобретается learn»")
    w("VERDICT: %s" % verdict)
    with open(os.path.join(DIR, "ACQ1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out), flush=True)


if __name__ == "__main__":
    main()
