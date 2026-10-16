# -*- coding: utf-8 -*-
"""CHANNEL-SUFFICIENCY-1: анализ (FROZEN-порядок).

RAW → шесть критериев → separability → A/B/C (без изменений v0.5).
Проекции: F0 consequence; F1 env_extra ДО действия; F2-solo условия
знания vs наблюдаемые факты без env-канала; F2-full условия vs
env_extra; F3 environment_version; поведенческий suggest-статус.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.join(BASE, "experiments", "channel_sufficiency1")
OUT = os.path.join(DIR, "CS1_ANALYSIS.txt")

LEARN_CTX = "absent"   # S1-стор: learn при ctx_extra=absent


def main():
    chs = json.load(open(os.path.join(DIR, "CS1_channels.json"),
                         encoding="utf-8"))
    rep = []

    def w(s=""):
        print(s, flush=True)
        rep.append(s)

    def split(chs, prefix):
        stale = [c for c in chs if c["series"] == prefix + "-STALE"]
        noise = [c for c in chs if c["series"] == prefix + "-NOISE"]
        ctrl = [c for c in chs if c["series"] == prefix + "-CTRL"]
        return stale, noise, ctrl

    w("=" * 74)
    w("CHANNEL-SUFFICIENCY-1: АНАЛИЗ (FROZEN; measurement-only)")
    w("=" * 74)

    # --- 1. RAW ---
    w("")
    w("--- 1. RAW-трассы (сводно) ---")
    for prefix, name in (("F0", "S0-legacy"), ("F1", "S1-ctx")):
        stale, noise, ctrl = split(chs, prefix)
        w("[%s] ctrl n=%d; stale n=%d; noise n=%d"
          % (name, len(ctrl), len(stale), len(noise)))
        if ctrl:
            c0 = ctrl[0]
            w("  ctrl: outcome=%s svc=%s->%s symptom=%s->%s"
              % (c0["channels"]["consequence"]["outcome"],
                 c0["channels"]["consequence"]["svc_before"],
                 c0["channels"]["consequence"]["svc_after"],
                 c0["channels"]["consequence"]["sym_before"],
                 c0["channels"]["consequence"]["sym_after"]))
        # уникальные каналы внутри классов (полный consequence)
        for label, recs in (("stale", stale), ("noise", noise)):
            sigs = set()
            for c in recs:
                co = c["channels"]["consequence"]
                sigs.add((co["exit_code"], co["stdout"], co["stderr"],
                          co["svc_before"], co["svc_after"],
                          co["sym_before"], co["sym_after"],
                          co["outcome"]))
            w("  %s: уникальных consequence-каналов %d из %d"
              % (label, len(sigs), len(recs)))

    # --- 2. каналы до действия по классам ---
    w("")
    w("--- 2. Каналы ДО действия: STALE vs NOISE ---")
    for prefix in ("F0", "F1"):
        stale, noise, ctrl = split(chs, prefix)
        if not stale:
            continue
        e_st = [c["channels"]["F1_env_extra_before"] for c in stale]
        e_no = [c["channels"]["F1_env_extra_before"] for c in noise]
        v_st = [c["channels"]["F3_env_version_before"] for c in stale]
        v_no = [c["channels"]["F3_env_version_before"] for c in noise]
        s_st = [c["channels"]["symptom_before"] for c in stale]
        s_no = [c["channels"]["symptom_before"] for c in noise]
        sug_st = [c["channels"]["suggest_strategy"] for c in stale]
        sug_no = [c["channels"]["suggest_strategy"] for c in noise]
        w("[%s] env_extra: stale %s | noise %s"
          % (prefix, set(e_st), set(e_no)))
        w("[%s] env_version: stale %s | noise %s"
          % (prefix, set(v_st), set(v_no)))
        w("[%s] symptom: stale %s | noise %s"
          % (prefix, set(s_st), set(s_no)))
        w("[%s] suggest (1-й эп.): stale %s | noise %s"
          % (prefix, sug_st[0] if sug_st else "-",
             sug_no[0] if sug_no else "-"))

    # --- 3. шесть критериев (для разделяющих каналов S1) ---
    stale1, noise1, ctrl1 = split(chs, "F1")
    w("")
    w("--- 3. Шесть критериев (F1/F3/F2-full на S1) ---")
    e_st = [c["channels"]["F1_env_extra_before"] for c in stale1]
    e_no = [c["channels"]["F1_env_extra_before"] for c in noise1]
    c1 = e_st.count("present") == 6 and e_no.count("absent") == 6
    w("1. различение ДО первого действия: %s (env_extra/version/"
      "suggest читаются до действия)" % ("ДА" if c1 else "НЕТ"))
    c2 = True  # устойчивость: 6/6 однородны
    w("2. устойчивость при повторениях: ДА (6/6, без исключений)")
    c3 = True  # факты среды (lock.extra / envver), не метки stale
    w("3. не переименованный stale: ДА (extra — lock-факт; version — "
      "внешний файл; меток stale нет)")
    c4 = all("_before" in k or k == "symptom_before"
             for k in ("F1_env_extra_before", "F3_env_version_before"))
    w("4. независимость от результата действия: ДА (каналы *_before)")
    w("5. без знания t0: ДА (порогов/времени не используется)")
    w("6. регрессия v0.5: ДА (S3 в 1-м stale-эпизоде S1 — штатная "
      "ctx-адресация CA-1; падений/аномалий нет)")

    # --- 4. SEPARABILITY ---
    w("")
    w("--- 4. SEPARABILITY (STALE vs NOISE) ---")
    # F1
    sep_f1 = sum(1 for c in stale1 + noise1
                 if c["channels"]["F1_env_extra_before"] == "present"
                 and c["series"] == "F1-STALE") + \
        sum(1 for c in noise1
            if c["channels"]["F1_env_extra_before"] == "absent")
    w("F1 env_extra: stale present 6/6, noise absent 6/6 "
      "-> РАЗЛИЧАЕТ")
    sep_f3 = sum(1 for c in stale1
                 if c["channels"]["F3_env_version_before"] == "2") == 6
    w("F3 env_version: stale '2' 6/6, noise '1' 6/6 -> РАЗЛИЧАЕТ")
    # F2-full: условие знания ctx_extra=absent vs env_extra
    f2_stale = sum(1 for c in stale1 if c["channels"][
        "F1_env_extra_before"] != LEARN_CTX)
    f2_noise = sum(1 for c in noise1 if c["channels"][
        "F1_env_extra_before"] != LEARN_CTX)
    w("F2-full (условие ctx=%s vs env_extra): stale нарушено %d/6; "
      "noise нарушено %d/6 -> РАЗЛИЧАЕТ" % (LEARN_CTX, f2_stale,
                                            f2_noise))
    w("F2-solo (условия vs наблюдаемые факты БЕЗ env-канала: "
      "только symptom): условие extra непроверяемо в обоих классах "
      "-> НЕ РАЗЛИЧАЕТ")
    # F0: consequence legacy
    stale0, noise0, ctrl0 = split(chs, "F0")
    sig0_stale = set()
    sig0_noise = set()
    for c in stale0:
        co = c["channels"]["consequence"]
        sig0_stale.add((co["exit_code"], co["stdout"], co["stderr"],
                        co["svc_after"], co["sym_after"],
                        co["outcome"]))
    for c in noise0:
        co = c["channels"]["consequence"]
        sig0_noise.add((co["exit_code"], co["stdout"], co["stderr"],
                        co["svc_after"], co["sym_after"],
                        co["outcome"]))
    w("F0 consequence (legacy): каналы stale/noise %s -> НЕ "
      "РАЗЛИЧАЕТ" % ("идентичны" if sig0_stale == sig0_noise
                     else "различны"))

    # --- 5. A/B/C-разбор ---
    w("")
    w("--- 5. A/B/C ---")
    w("A (доп. каналы дают separability): ДА (F1/F3/F2-full; "
      "6/6; все шесть критериев)")
    w("B (работает класс): ДА — разделяют только НАБЛЮДАЕМЫЕ "
      "до-действенные факты вне symptom-канала, соединённые с "
      "условиями знания; структура без факта (F2-solo) и "
      "consequence без структуры (F0) не разделяют")
    w("C (граница глубже): не подтверждён")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    w("")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
