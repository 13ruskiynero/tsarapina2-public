# -*- coding: utf-8 -*-
"""STALE-EXACT-2: анализ (06.09) поверх лога/сторов прогона.
Пересчёт E2c с не-success (partial/failure) + E2b внутриклассовый
контроль разброса (артефакты окружения не должны читаться как
класс-сигнал). Порядок: траектории уже зафиксированы; здесь только
измерения, полигон не трогается.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.join(BASE, "experiments", "stale_exact2")
LOG = os.path.join(DIR, "STALE_EXACT2_run.log")
OUT = os.path.join(BASE, "experiments",
                   "STALE_EXACT2_E2_analysis.txt")
FLOATY = ("cpu.load1", "memory.mem_available_kb")
FLOATY2 = ("process:sshd.count", "disk.free_kb", "log:ssh.tail_count")


def read_episodes():
    eps = []
    for line in open(LOG, encoding="utf-8"):
        r = json.loads(line)
        if r.get("event") == "EPISODE":
            eps.append(r)
    return eps


def series_seq(eps):
    by = {}
    for e in eps:
        by.setdefault(e["series"], []).append(e["outcome"])
    return by


def chan_of(store_dir, ep_prefix):
    acts = {}
    for line in open(os.path.join(store_dir, "actions.jsonl"),
                     encoding="utf-8"):
        r = json.loads(line)
        if r.get("proposed_by", "").startswith("se2/" + ep_prefix):
            acts[r["action_id"]] = r
    res = None
    for line in open(os.path.join(store_dir, "results.jsonl"),
                     encoding="utf-8"):
        r = json.loads(line)
        if r.get("action_id") in acts:
            res = r
    if res is None:
        return None
    return {"state_before": res.get("state_before") or {},
            "state_after": res.get("state_after") or {},
            "exit_code": res.get("exit_code"),
            "stdout": res.get("stdout") or "",
            "stderr": res.get("stderr") or ""}


def diff_fields(a, b):
    out = {}
    for phase in ("state_before", "state_after"):
        keys = set(a[phase]) | set(b[phase])
        for k in keys:
            if a[phase].get(k) != b[phase].get(k):
                out["%s.%s" % (phase.replace("state_", "s"),
                               k)] = (a[phase].get(k), b[phase].get(k))
    return out


def main():
    rep = []
    def w(s=""):
        print(s, flush=True)
        rep.append(s)

    eps = read_episodes()
    seqs = series_seq(eps)
    w("== STALE-EXACT-2: E2c/E4 пересчёт (не-success = partial) ==")
    for s in ("S-OK", "N", "ST", "ST-L", "S2", "LATE", "ALT", "MIX"):
        seq = seqs.get(s, [])
        w("  %-6s %s" % (s, " ".join("s" if o == "success" else "f"
                                      for o in seq)))
    # индикатор «2 подряд не-success»
    all_outs = []
    for s in ("N", "ST", "ST-L", "S2", "LATE", "ALT", "MIX"):
        all_outs += seqs.get(s, [])
    first_f = 0
    second_f = 0
    pred_ok = 0
    for i, o in enumerate(all_outs):
        if o == "success":
            continue
        prev2 = all_outs[max(0, i - 2):i]
        if len(prev2) == 2 and prev2[0] != "success" \
                and prev2[1] != "success":
            second_f += 1
            if i + 1 < len(all_outs) and all_outs[i + 1] != "success":
                pred_ok += 1
        elif not prev2 or (len(prev2) == 1):
            first_f += 1
    w("  не-success всего: %d" % sum(1 for o in all_outs
                                     if o != "success"))
    w("  из них первые после успеха (неразличимы на 1-м эпизоде): %d"
      % first_f)
    w("  индикатор «2 подряд не-success» сработал: %d; прогноз "
      "не-success на следующем: %d/%d" % (second_f, pred_ok,
                                           max(second_f, 1)))
    alt = seqs.get("ALT", [])
    alt_ff = sum(1 for i in range(2, len(alt))
                 if alt[i - 2] != "success" and alt[i - 1] != "success")
    w("  ложные срабатывания на чисто шумовой ALT: %d" % alt_ff)
    # перекрёстная проверка: S2 и LATE — отложенные (не участвовали
    # в фиксации индикатора): в них f,f встречается только после
    # смены мира; проверим: все «2-е подряд f» в S2/LATE — в w2
    late_ff_pos = []
    for s in ("S2", "LATE", "MIX"):
        seq = seqs.get(s, [])
        for i in range(2, len(seq)):
            if seq[i - 2] != "success" and seq[i - 1] != "success":
                late_ff_pos.append((s, i))
    w("  позиции срабатывания в S2/LATE/MIX (индексы): %s"
      % late_ff_pos)

    w("")
    w("== E2b: внутриклассовый контроль разброса ==")
    # межклассовое: st_1 (w2) vs no_f1 (noise)
    st_1 = chan_of(os.path.join(DIR, "data_se2_stale"), "st_1")
    no_1 = chan_of(os.path.join(DIR, "data_se2_noise"), "no_f1")
    if st_1 and no_1:
        d = diff_fields(st_1, no_1)
        w("  МЕЖкласс st_1 vs no_f1: различий %d: %s"
          % (len(d), {k: v for k, v in d.items()
                      if k.split(".")[-1] not in FLOATY + FLOATY2}
             or "только плавающие/окружение"))
        w("    все поля-различия: %s" % d)
    # внутриклассовые: st_1 vs st_2; no_f1 vs ca_f1_1 (ALT-noise)
    st_2 = chan_of(os.path.join(DIR, "data_se2_stale"), "st_2")
    alt_1 = chan_of(os.path.join(DIR, "data_se2_c_alt"), "ca_f1_1")
    if st_1 and st_2:
        d = diff_fields(st_1, st_2)
        w("  ВНУТРИ stale (st_1 vs st_2): различий %d: %s"
          % (len(d), d))
    if no_1 and alt_1:
        d = diff_fields(no_1, alt_1)
        w("  ВНУТРИ noise (no_f1 vs ca_f1_1): различий %d: %s"
          % (len(d), d))
    w("  Плавающие/окружение (исключаются из сигнала): %s"
      % (FLOATY + FLOATY2,))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    w("")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
