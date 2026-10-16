# -*- coding: utf-8 -*-
"""EVENT-SUFFICIENCY-1 / E0: чистое измерение на существующих логах
STALE-EXACT-1 (06.09.2026). НИКАКИХ изменений: ни Strategy, ни
повторного исполнения, ни восстановления данных, ни новых
конфликтов. Только вопрос: какие различия уже содержатся в
имеющемся журнале между не-success-последствиями STALE-класса
(fix-a в новом мире) и NOISE-класса (синтетический шум fix-a)?

Канал эпизода = полный result-вектор: command, exit_code, stdout,
stderr, state_before (снимок сенсоров), state_after, вердикт
evaluation.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIR = os.path.join(BASE, "experiments", "stale_exact1")
OUT = os.path.join(BASE, "experiments",
                   "EVENT_SUFFICIENCY1_E0_measure.txt")
MECHS = ["F0", "F1", "F2", "F3"]


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def by_id(recs, key="id"):
    d = {}
    for r in recs:
        d[r.get(key)] = r
    return d


def load_store(dirname):
    d = os.path.join(DIR, dirname)
    results = read_jsonl(os.path.join(d, "results.jsonl"))
    actions = by_id(read_jsonl(os.path.join(d, "actions.jsonl")),
                    "action_id")
    exps = read_jsonl(os.path.join(d, "experiences.jsonl"))
    evals = read_jsonl(os.path.join(d, "evaluations.jsonl"))
    ev_by_rid = {}
    for e in evals:
        ev_by_rid.setdefault(e.get("result_id"), []).append(e)
    return {"dir": d, "results": results, "actions": actions,
            "exps": exps, "evals": ev_by_rid}


def verdict_of(store, rid):
    evs = store["evals"].get(rid, [])
    return evs[-1].get("outcome") if evs else None


def episodes_fix(store):
    """Эпизоды (experience), чьё последнее действие — fix-a; вернуть
    (action, result, exp)."""
    out = []
    for exp in store["exps"]:
        if not exp.get("actions"):
            continue
        aid = exp["actions"][-1]
        act = store["actions"].get(aid)
        if act is None or act.get("command") != "fix-a":
            continue
        res = None
        for r in store["results"]:
            if r.get("action_id") == aid:
                res = r
                break
        out.append({"act": act, "res": res, "exp": exp})
    return out


def channel(res, act, verdict):
    if res is None:
        return None
    sb = res.get("state_before") or {}
    sa = res.get("state_after") or {}
    return {
        "command": act.get("command"),
        "exit_code": res.get("exit_code"),
        "stdout_head": (res.get("stdout") or "")[:60],
        "stderr_head": (res.get("stderr") or "")[:60],
        "sb": sb, "sa": sa, "verdict": verdict,
        "sb_state": sb.get("service:tsasvc.state"),
        "sa_state": sa.get("service:tsasvc.state"),
        "sb_symptom": sb.get("tsasvc.symptom"),
        "sa_symptom": sa.get("tsasvc.symptom"),
    }


def main():
    rep = []
    def w(s=""):
        print(s, flush=True)
        rep.append(s)

    w("=" * 78)
    w("EVENT-SUFFICIENCY-1 / E0: измерение на существующих логах")
    w("STALE-EXACT-1 (чисто измерительный; 06.09.2026)")
    w("=" * 78)

    per_mech = {}
    for mech in MECHS:
        stale_dir = "data_stale_%s" % mech
        noise_dir = "data_noise_%s" % mech
        if not os.path.exists(os.path.join(DIR, stale_dir)):
            w("[%s] нет data_stale_%s" % (mech, mech))
            continue
        st_stale = load_store(stale_dir)
        st_noise = load_store(noise_dir) if os.path.exists(
            os.path.join(DIR, noise_dir)) else None
        w("")
        w("--- %s ---" % mech)
        stale_ch = []
        for e in episodes_fix(st_stale):
            v = verdict_of(st_stale, (e["res"] or {}).get("result_id"))
            if v not in ("success", "unverified", None) and e["res"]:
                stale_ch.append(channel(e["res"], e["act"], v))
        noise_ch = []
        if st_noise:
            for e in episodes_fix(st_noise):
                act = e["act"]
                if act.get("proposed_by") != "world/noise":
                    continue
                v = verdict_of(st_noise,
                               (e["res"] or {}).get("result_id"))
                if e["res"]:
                    noise_ch.append(channel(e["res"], e["act"], v))
        per_mech[mech] = (stale_ch, noise_ch)
        w("stale fix-a не-success эпизодов: %d" % len(stale_ch))
        w("noise fix-a (synthetic) эпизодов:   %d" % len(noise_ch))
        for label, chs in (("STALE", stale_ch), ("NOISE", noise_ch)):
            if not chs:
                w("  %s: записей нет" % label)
                continue
            keys_sb = set()
            keys_sa = set()
            trans = set()
            sym_trans = set()
            for c in chs:
                keys_sb |= set(c["sb"].keys())
                keys_sa |= set(c["sa"].keys())
                trans.add("%s -> %s" % (c["sb_state"], c["sa_state"]))
                sym_trans.add("%s -> %s" % (c["sb_symptom"],
                                            c["sa_symptom"]))
            w("  %s: sb-полей=%d sa-полей=%d" %
              (label, len(keys_sb), len(keys_sa)))
            w("  %s: переходы state: %s" % (label, sorted(trans)))
            w("  %s: переходы symptom: %s" % (label, sorted(sym_trans)))

    w("")
    w("--- Сравнение каналов stale vs noise (общие поля) ---")
    for mech in MECHS:
        if mech not in per_mech:
            continue
        stale_ch, noise_ch = per_mech[mech]
        if not stale_ch or not noise_ch:
            w("[%s] нет пары для сравнения" % mech)
            continue
        c1 = stale_ch[0]
        c2 = noise_ch[0]
        common_sb = set(c1["sb"].keys()) & set(c2["sb"].keys())
        common_sa = set(c1["sa"].keys()) & set(c2["sa"].keys())
        diff_sb = {k: (c1["sb"].get(k), c2["sb"].get(k))
                   for k in common_sb if c1["sb"].get(k) != c2["sb"].get(k)}
        diff_sa = {k: (c1["sa"].get(k), c2["sa"].get(k))
                   for k in common_sa if c1["sa"].get(k) != c2["sa"].get(k)}
        w("[%s] общих sb-полей: %d, различаются: %s"
          % (mech, len(common_sb), diff_sb or "нет"))
        w("[%s] общих sa-полей: %d, различаются: %s"
          % (mech, len(common_sa), diff_sa or "нет"))
        w("[%s] поля только в stale-sb: %s" %
          (mech, sorted(set(c1["sb"]) - set(c2["sb"])) or "нет"))
        w("[%s] поля только в stale-sa: %s" %
          (mech, sorted(set(c1["sa"]) - set(c2["sa"])) or "нет"))
        w("[%s] поля только в noise-sb: %s" %
          (mech, sorted(set(c2["sb"]) - set(c1["sb"])) or "нет"))
        w("[%s] поля только в noise-sa: %s" %
          (mech, sorted(set(c2["sa"]) - set(c1["sa"])) or "нет"))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    w("")
    w("saved %s" % OUT)


if __name__ == "__main__":
    main()
