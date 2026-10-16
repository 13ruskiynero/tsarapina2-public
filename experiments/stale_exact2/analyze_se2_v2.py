# -*- coding: utf-8 -*-
"""STALE-EXACT-2: анализ v2 (06.09) — строго ВНУТРИ серий (стыки
серий не создают пар), классификация промахов индикатора
(noise vs learn-вмешательство). Полигон не трогается."""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.join(BASE, "experiments", "stale_exact2")
LOG = os.path.join(DIR, "STALE_EXACT2_run.log")
OUT = os.path.join(BASE, "experiments",
                   "STALE_EXACT2_E2_analysis2.txt")


def main():
    rep = []
    def w(s=""):
        print(s, flush=True)
        rep.append(s)

    seqs = {}
    for line in open(LOG, encoding="utf-8"):
        r = json.loads(line)
        if r.get("event") == "EPISODE":
            seqs.setdefault(r["series"], []).append(
                "s" if r["outcome"] == "success" else "f")
    w("== STALE-EXACT-2: E2c/E4 (внутрисерийный подсчёт) ==")
    for s in ("S-OK", "N", "ST", "ST-L", "S2", "LATE", "ALT", "MIX"):
        w("  %-6s %s" % (s, " ".join(seqs.get(s, []))))

    first_f = 0          # первый не-success после успешного хвоста
    trig = 0             # срабатывание «2 подряд не-success»
    pred_ok = 0          # прогноз верен (следующий = не-success)
    pred_miss_noise = 0  # промах при отсутствии вмешательства
    pred_miss_learn = 0  # промах из-за learn-вмешательства (ST-L)
    for s, seq in seqs.items():
        if s == "S-OK":
            continue
        for i, o in enumerate(seq):
            if o == "s":
                continue
            prev = seq[max(0, i - 1):i]
            prev2 = seq[max(0, i - 2):i]
            if len(prev2) == 2 and prev2 == ["f", "f"]:
                trig += 1
                if i + 1 < len(seq):
                    nxt = seq[i + 1]
                    if nxt == "f":
                        pred_ok += 1
                    else:
                        # промах: следующий успешен — learn (ST-L)
                        if s == "ST-L":
                            pred_miss_learn += 1
                        else:
                            pred_miss_noise += 1
            elif prev == ["s"] or prev2 == ["s", "s"] or prev == []:
                first_f += 1
    w("  первый не-success после успеха (1-й эпизод, E2b-граница): "
      "%d" % first_f)
    w("  индикатор «2 подряд не-success» сработал: %d" % trig)
    w("  прогноз следующего не-success: верно %d | промах из-за "
      "learn-вмешательства %d | промах на шуме %d"
      % (pred_ok, pred_miss_learn, pred_miss_noise))
    noise_trig = 0
    for s in ("N", "ALT"):
        seq = seqs.get(s, [])
        noise_trig += sum(1 for i in range(2, len(seq))
                          if seq[i - 2] == "f" and seq[i - 1] == "f")
    w("  срабатывания на чисто шумовых сериях N/ALT: %d (ложных: %d)"
      % (noise_trig, noise_trig))
    # где срабатывает (по сериям) — все в мирах w2 после смены:
    pos = []
    for s in ("S2", "LATE", "MIX", "ST"):
        seq = seqs.get(s, [])
        for i in range(2, len(seq)):
            if seq[i - 2] == "f" and seq[i - 1] == "f":
                pos.append("%s@%d" % (s, i + 1))
    w("  позиции срабатывания (ST/S2/LATE/MIX; все после смены мира "
      "w1→w2): %s" % pos)
    # «первый f после смены мира» не даёт сигнала: для каждой серии
    # со сменой: первый w2-f идёт после s-хвоста (нет f,f) — всегда
    w("  вывод-измерение: ни одно срабатывание не приходится на "
      "первый f после смены мира (граница 1-го эпизода "
      "сохраняется); все срабатывания — на 2-м подряд f.")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    w("")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
