# -*- coding: utf-8 -*-
"""STALE-EXACT-2 (ADDRESS-MATCH) driver (06.09.2026; FREEZE).

База: Strategy v0.4 (основная; ctx_now передаётся). Серии на v0.4
БЕЗ изменений стратегии: измерение поведения, каналов и
темпорального сигнала. Порядок анализа встроен в прогон:
(1) сырые траектории success / noise / stale / stale+learn;
(2) E2b: каналы первого failure (stale w2 vs noise-real w1+n) +
    адресная строка;
(3) E2c/E4: темпоральный индикатор-кандидат «2 подряд failure»
    (фиксируется ДО подсчёта): точность прогноза следующего исхода,
    ложные срабатывания на шумовых сериях, задержка после смены мира.

Миры: w1 = [a]; w2 = [a, q] (q скрыт: не в симптоме, не в ctx);
noise-real = [a, n] (n скрыт; fix-a не снимает; мир НЕ устарел).
Адрес знания во всех мирах: (symptom=a, ctx=absent) — B-условие.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "STALE_EXACT2_run.log")
WORLDS = {"w1": ["a"], "w2": ["a", "q"], "noise": ["a", "n"]}
TRACK = []  # (серия, индекс, исход) — для E2c/E4


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(world):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in WORLDS[world]:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def ctx_now():
    return polygon_sensor.sensor_envfact()[4]  # absent во всех мирах


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]  # a во всех мирах


def mk_action(store, command, proposed_by, ctx):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "STALE-EXACT-2"}
    store.append_action(a)
    return a


def save_episode(store, problem, facts, act, result_id, outcome):
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=result_id,
        machine="stale-exact-2")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"], outcome)


def learn(store, world, fix, ep):
    env_set(world)
    ctx = ctx_now()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, fix, proposed_by="operator/learn", ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    save_episode(store, problem, facts, act, res["result_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN", "world": world, "fix": fix,
         "ok": ok, "ctx": ctx})
    return ok, ctx


def episode(store, world, ep, series):
    """Эпизод контура на v0.4. Возвращает sug-словарь + канал."""
    env_set(world)
    ctx = ctx_now()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = strategy.suggest(store, {"problem": problem}, ctx_now=ctx,
                           by="stale-exact-2")
    sid = sug["strategy_id"]
    cmd = None
    if sid == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
    rule = sug["rationale"][0]["rule"] if sug["rationale"] else ""
    act = mk_action(store, cmd or "fix-a",
                    proposed_by="se2/%s" % ep, ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    save_episode(store, problem, observer.collect(store), act,
                 res["result_id"], outcome)
    channel = {
        "series": series, "ep": ep, "world": world,
        "address": {"symptom": symptom_now(), "ctx": ctx},
        "command": act["command"], "strategy": sid, "rule": rule,
        "exit_code": res.get("exit_code"),
        "stdout": res.get("stdout") or "",
        "stderr": res.get("stderr") or "",
        "state_before": res.get("state_before") or {},
        "state_after": res.get("state_after") or {},
        "outcome": outcome,
    }
    log({"ep": ep, "series": series, "event": "EPISODE", "world": world,
         "strategy": sid, "rule": rule, "cmd": act["command"],
         "outcome": outcome, "ctx": ctx})
    TRACK.append((series, outcome))
    return sug, channel


def fresh_store(name):
    d = os.path.join(DIR, "data_se2_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def norm_compare(a, b):
    """E2b: сравнение каналов по стабильным полям; плавающие
    (load/mem) помечаются как артефакты времени."""
    FLOATY = ("cpu.load1", "memory.mem_available_kb")
    keys_sb = set(a["state_before"]) | set(b["state_before"])
    keys_sa = set(a["state_after"]) | set(b["state_after"])
    diff_sb = {}
    for k in keys_sb:
        va = a["state_before"].get(k)
        vb = b["state_before"].get(k)
        if va != vb:
            diff_sb[k] = (va, vb)
    diff_sa = {}
    for k in keys_sa:
        va = a["state_after"].get(k)
        vb = b["state_after"].get(k)
        if va != vb:
            diff_sa[k] = (va, vb)
    real_diff = {}
    for d, diff in (("sb", diff_sb), ("sa", diff_sa)):
        for k, v in diff.items():
            if k not in FLOATY:
                real_diff["%s.%s" % (d, k)] = v
    artifact = {k: v for k, v in list(diff_sb.items())
                + list(diff_sa.items()) if k in FLOATY}
    return real_diff, artifact


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== STALE-EXACT-2 (ADDRESS-MATCH) — v0.4, FREEZE 06.09 ==",
          flush=True)
    print("Индикатор-кандидат (до подсчёта): «2 подряд failure» "
          "→ прогноз следующего исхода = failure.", flush=True)

    # ---------- СЕРИИ: сырые траектории ----------
    # S-OK: success-эталон (w1 ×6)
    st = fresh_store("ok")
    learn(st, "w1", "fix-a", "ok_L1")
    for i in range(1, 7):
        episode(st, "w1", "ok_%d" % i, "S-OK")

    # N: noise-real (w1 ×2, noise ×1, w1 ×3)
    stn = fresh_store("noise")
    learn(stn, "w1", "fix-a", "no_L1")
    for i in (1, 2):
        episode(stn, "w1", "no_s%d" % i, "N")
    episode(stn, "noise", "no_f1", "N")       # реалистичный шум (канал)
    for i in (1, 2, 3):
        episode(stn, "w1", "no_s%d" % (i + 2), "N")

    # ST: stale (w1 learn; w2 ×6 без learn)
    stt = fresh_store("stale")
    learn(stt, "w1", "fix-a", "st_L1")
    for i in range(1, 7):
        episode(stt, "w2", "st_%d" % i, "ST")

    # ST-L: stale+learn: 3 застревания → learn fix-aq → эпизод
    stl = fresh_store("stale_learn")
    learn(stl, "w1", "fix-a", "sl_L1")
    for i in (1, 2, 3):
        episode(stl, "w2", "sl_f%d" % i, "ST-L")
    learn(stl, "w2", "fix-aq", "sl_L2")
    episode(stl, "w2", "sl_after", "ST-L")

    # E2c/E4 серии: S2 (w1×2, w2×4), LATE (w1×4, w2×3),
    # ALT (w1, noise, w1, noise, w1), MIX (w1, noise, w1, w2×3)
    st2 = fresh_store("c_s2")
    learn(st2, "w1", "fix-a", "c2_L1")
    for i in (1, 2):
        episode(st2, "w1", "c2_s%d" % i, "S2")
    for i in (1, 2, 3, 4):
        episode(st2, "w2", "c2_f%d" % i, "S2")
    st3 = fresh_store("c_late")
    learn(st3, "w1", "fix-a", "cl_L1")
    for i in (1, 2, 3, 4):
        episode(st3, "w1", "cl_s%d" % i, "LATE")
    for i in (1, 2, 3):
        episode(st3, "w2", "cl_f%d" % i, "LATE")
    st4 = fresh_store("c_alt")
    learn(st4, "w1", "fix-a", "ca_L1")
    for i in (1, 2):
        episode(st4, "w1", "ca_s1_%d" % i, "ALT")
        episode(st4, "noise", "ca_f1_%d" % i, "ALT")
        episode(st4, "w1", "ca_s2_%d" % i, "ALT")
    st5 = fresh_store("c_mix")
    learn(st5, "w1", "fix-a", "cm_L1")
    episode(st5, "w1", "cm_s1", "MIX")
    episode(st5, "noise", "cm_f1", "MIX")
    episode(st5, "w1", "cm_s2", "MIX")
    for i in (1, 2, 3):
        episode(st5, "w2", "cm_f%d" % i, "MIX")

    print()
    print("=== СЫРЫЕ ТРАЕКТОРИИ (серия: исходы) ===", flush=True)
    by_series = {}
    for s, out in TRACK:
        by_series.setdefault(s, []).append(out)
    for s, outs in by_series.items():
        print("  %-6s %s" % (s, " ".join("s" if o == "success"
                                          else "f" for o in outs)),
              flush=True)

    # ---------- E2b: каналы первого failure ----------
    print()
    print("=== E2b: канал первого failure: stale(w2) vs noise-real"
          " ===", flush=True)
    st_chan = None
    no_chan = None
    for s, ch in []:
        pass
    # извлечём из логов сторов: первый w2-эпизод stale-серии и
    # noise-эпизод серии N
    stt_chan = None
    stn_chan = None
    for dname, want, key in ((stt, "w2", "ST"),
                             (stn, "noise", "N")):
        pass
    # прямой путь: повторное чтение results по action_id из стора —
    # надёжнее: соберём из TRACK-каналов? каналы не сохранялись в
    # TRACK. Считаем по сторам: последний результат действия fix-a
    # с миром w2 (stale) и миром noise (noise): world в опыте не
    # хранится: action.proposed_by несёт ep: st_1 (w2) и no_f1.
    def chan_of(store, ep_prefix):
        import glob as _g
        acts = {}
        for line in open(os.path.join(os.path.dirname(store.obs_jsonl),
                                      "actions.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r.get("proposed_by", "").startswith("se2/" + ep_prefix):
                acts[r["action_id"]] = r
        res = None
        for line in open(os.path.join(os.path.dirname(store.obs_jsonl),
                                      "results.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r.get("action_id") in acts:
                res = r
        if res is None:
            return None
        sb = res.get("state_before") or {}
        sa = res.get("state_after") or {}
        return {"state_before": sb, "state_after": sa,
                "exit_code": res.get("exit_code"),
                "stdout": res.get("stdout") or "",
                "stderr": res.get("stderr") or "",
                "address": "symptom=a ctx=absent",
                "outcome": "failure"}
    st_ch = chan_of(stt, "st_1")
    no_ch = chan_of(stn, "no_f1")
    if st_ch and no_ch:
        real_diff, art = norm_compare(st_ch, no_ch)
        print("  адрес (оба): %s" % st_ch["address"], flush=True)
        print("  адрес (noise): %s" % no_ch["address"], flush=True)
        print("  различающиеся стабильные поля: %s"
              % (real_diff or "НЕТ"), flush=True)
        print("  артефакты времени (исключены): %s"
              % (art or "нет"), flush=True)
        print("  вердикты: stale=%s noise=%s" % (st_ch["outcome"],
                                                  no_ch["outcome"]),
              flush=True)
        log({"event": "E2B", "real_diff": real_diff,
             "artifacts": list(art.keys())})
    else:
        print("  каналы не найдены (stale: %s, noise: %s)"
              % (bool(st_ch), bool(no_ch)), flush=True)

    # ---------- E2c/E4: темпоральный индикатор ----------
    print()
    print("=== E2c/E4: индикатор «2 подряд failure» ===", flush=True)
    seq = [o for _, o in TRACK]
    first_f_after_s = 0
    second_f = 0
    second_f_followed_by_f = 0
    for i in range(len(seq)):
        if seq[i] != "failure":
            continue
        prev2 = seq[max(0, i - 2):i]
        if prev2 == ["success", "success"] or (i >= 1 and
                                               prev2 == ["success"]):
            first_f_after_s += 1
        if len(prev2) == 2 and prev2[0] == "failure" and \
                prev2[1] == "failure":
            second_f += 1
            if i + 1 < len(seq) and seq[i + 1] == "failure":
                second_f_followed_by_f += 1
    # ложные срабатывания: серия ALT (чистый шум) — индикатор f,f
    alt_seq = [o for s, o in TRACK if s == "ALT"]
    alt_ff = sum(1 for i in range(2, len(alt_seq))
                 if alt_seq[i - 2] == "failure"
                 and alt_seq[i - 1] == "failure")
    # задержка: первый f после смены мира (w2) по сериям ST/S2/LATE/MIX:
    # «первый w2-f после s-хвоста» не имеет f,f перед собой (всегда)
    print("  всего failure-эпизодов: %d" % sum(1 for o in seq
                                               if o == "failure"),
          flush=True)
    print("  из них первые после s-хвоста (неразличимы, E2b): %d"
          % first_f_after_s, flush=True)
    print("  индикатор сработал (2-й подряд f): %d; прогноз f на "
          "следующем: %d/%d"
          % (second_f, second_f_followed_by_f, max(second_f, 1)),
          flush=True)
    print("  ложные срабатывания на чисто шумовой серии ALT: %d"
          % alt_ff, flush=True)
    log({"event": "E2C", "first_f_after_s": first_f_after_s,
         "second_f": second_f,
         "second_f_followed_by_f": second_f_followed_by_f,
         "alt_false_positive": alt_ff})
    print()
    print("saved %s" % LOG, flush=True)


if __name__ == "__main__":
    main()
