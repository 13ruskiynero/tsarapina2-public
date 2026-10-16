# -*- coding: utf-8 -*-
"""EP-1 driver (FROZEN 07.09.2026; measurement-only; v0.6.x НЕ меняется).

Дизайн: EVIDENCE_PERMISSION1_DESIGN.md (FROZEN); протокол:
evidence_permission1/PROTOCOL.md (FROZEN). Миры: w1 (lock.a; fix-a
лечит), w2 (lock.a+lock.q; q скрыт; fix-a мёртв, fix-aq лечит);
шум-вставка = lock.n на один эпизод (мир не меняется). envver
пишется драйвером (тип recorder-записи: @V1 -> D2/(b), @V2 -> V/(a)).
Линия L = (a, absent, fix-a). Эпизоды эксплуатационные (suggest-
driven; S3-бездействие при пустом eligible), learn-фаза
принудительная (фикс. команда). Вмешательства simulated:
R(K1) — исключение из prior_lineage-чтений и suggest-кандидатов;
S(K1) — только из suggest-кандидатов; X — следующий эпизод
исполняет fix-aq. Policy однократна, срабатывает при первом
возникновении события E1..E6.

Запуск: python3 ep1_driver.py --cell <POLICY>|<HIST>|<rep>
POLICY: B | E1X..E6X | E3R..E5R | E3S..E5S  (матрица участия DESIGN §8;
клетки «−» и derived/undefined не запускаются).
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

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
PROBLEM = "tsasvc.service inactive symptom=a"

# --- истории (FROZEN; шаг: (мир, шум?, envver, замысел)) ---------------
# мир: w1 (a) | w2 (a+q); noise: lock.n на эпизод; замысел f/s — исход
# fix-a в этом мире (фактический исход фиксируется по службе).
W1 = ("w1", None)
W2 = ("w2", None)
NOISE = ("w1", "n")

HISTORIES = {
    "N1D": [("f", NOISE, "1"), ("s", W1, "1"), ("s", W1, "1")],
    "N1V": [("f", NOISE, "2"), ("s", W1, "1"), ("s", W1, "1")],
    "NaD": [("f", NOISE, "1"), ("s", W1, "1"), ("f", NOISE, "1"),
            ("s", W1, "1"), ("f", NOISE, "1"), ("s", W1, "1")],
    "NpD": [("f", NOISE, "1"), ("f", NOISE, "1"), ("f", NOISE, "1"),
            ("s", W1, "1")],
    "NpV": [("f", NOISE, "2"), ("f", NOISE, "2"), ("f", NOISE, "2"),
            ("s", W1, "1")],
    "NpM": [("f", NOISE, "1"), ("f", NOISE, "2"), ("f", NOISE, "1"),
            ("s", W1, "1")],
    "SD": [("f", W2, "1"), ("f", W2, "1"), ("f", W2, "1")],
    "SV": [("f", W2, "2"), ("f", W2, "2"), ("f", W2, "2")],
    "SM": [("f", W2, "1"), ("f", W2, "2"), ("f", W2, "1")],
    "NSD": [("f", NOISE, "1"), ("s", W1, "1"), ("f", W2, "1"),
            ("f", W2, "1")],
    "E6N": [("f", NOISE, "1"), ("s", W1, "1"), ("s", W1, "1")],
    "E6S": [("f", W2, "1"), ("f", W2, "1"), ("f", W2, "1")],
}
E6_HISTS = ("E6N", "E6S")          # learn-фаза w1@V1 -> w1@V2

# --- политики: право по событию (B = baseline) --------------------------
POLICIES = {
    "B": (None, None),
    "E1X": ("E1", "X"), "E2X": ("E2", "X"), "E3X": ("E3", "X"),
    "E4X": ("E4", "X"), "E5X": ("E5", "X"), "E6X": ("E6", "X"),
    "E3R": ("E3", "R"), "E4R": ("E4", "R"), "E5R": ("E5", "R"),
    "E3S": ("E3", "S"), "E4S": ("E4", "S"), "E5S": ("E5", "S"),
}

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

_OUTCOME_RE = re.compile(r"outcome=(\w+)")
_ORIG_PRIOR_LINEAGE = update._prior_lineage


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def hash_layers():
    out = {}
    for rel in LAYER_FILES:
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()[:16]
    return out


def env_set(world, noise, envver):
    flags = ["a"]
    if world == "w2":
        flags.append("q")
    if noise == "n":
        flags.append("n")
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(envver)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(cell):
    d = os.path.join(DIR, "data_ep1_%s" % cell)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def outcome_of_row(r):
    m = _OUTCOME_RE.search(r.get("context") or "")
    return m.group(1) if m else None


def obs_kinds(r):
    kinds = []
    for o in r.get("applicability_observations") or []:
        if o.get("source") == "verified failure":
            kinds.append("a" if o.get("signal") else "b")
        else:
            kinds.append("s")
    return kinds


def addr_of(store, r):
    try:
        a = strategy._addr_cmd_of(store, r)
        if not a:
            return None
        return (sorted(a[0]) if hasattr(a[0], "__iter__") else [a[0]],
                a[1], a[2])
    except Exception:
        return None


def line_members(store, cmd="fix-a"):
    """Члены линии (symptom a, E=absent, cmd) по created_at, с
    outcome/aw/obs-типами. Возвращает список dict."""
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    members = []
    for v in latest.values():
        if v.get("status") not in ("active", "conflicted"):
            continue
        a = addr_of(store, v)
        if a and "a" in a[0] and a[1] == "absent" and a[2] == cmd:
            members.append({
                "kid": v["knowledge_id"], "created_at": v.get("created_at"),
                "outcome": outcome_of_row(v), "aw": v.get("applicable_when"),
                "kinds": obs_kinds(v), "gen": v.get("lineage_generation"),
                "version": v.get("version"),
            })
    members.sort(key=lambda m: (m["created_at"], m["kid"]))
    return members


def detect_events(members):
    """Все события E1..E5, возникшие на свежих членах L (после
    последнего success-члена). E3/E4 — гомогенные серии >=2; E5 —
    смешанная серия >=2; E1/E2 — (a)/(b) на последнем члене вне
    гомогенной серии. Возвращает set (может содержать несколько
    событий: напр. SM-шаг 2 -> {E5, E1})."""
    if not members:
        return set()
    last_succ = None
    for i in range(len(members) - 1, -1, -1):
        if members[i]["outcome"] == "success":
            last_succ = i
            break
    fresh = members[last_succ + 1:] if last_succ is not None \
        else list(members)
    if not fresh:
        return set()
    if fresh[-1]["outcome"] == "success":
        return set()  # серия оборвана
    ev = set()
    last_a = "a" in fresh[-1]["kinds"]
    last_b = "b" in fresh[-1]["kinds"]
    if len(fresh) >= 2:
        prev_a = "a" in fresh[-2]["kinds"]
        prev_b = "b" in fresh[-2]["kinds"]
        if last_a and prev_a and not last_b and not prev_b:
            return {"E3"}
        if last_b and prev_b and not last_a and not prev_a:
            return {"E4"}
        all_a = any("a" in m["kinds"] for m in fresh)
        all_b = any("b" in m["kinds"] for m in fresh)
        if all_a and all_b:
            ev.add("E5")
    if last_a and not last_b:
        ev.add("E1")
    if last_b and not last_a:
        ev.add("E2")
    return ev


def conflict_success_present(members):
    """E6: conflicting success в линии — success-член с success-derived
    V-дивергенцией в obs, ЛИБО два success-члена с разным V в aw
    (learn w1->wY: K1 {E,V1}, K2 {E}+obs V[1,2] -> kinds 's')."""
    for m in members:
        if m["outcome"] == "success" and "s" in m["kinds"]:
            return True
    vs = set()
    for m in members:
        if m["outcome"] == "success" and m.get("aw"):
            v = m["aw"].get("V")
            if v is not None:
                vs.add(str(v))
    return len(vs) >= 2


# --- эпизоды ------------------------------------------------------------
def learn_episode(store, world, envver, cmd, ep):
    """Принудительный learn (драйвер показывает лечение)."""
    env_set(world, None, envver)
    return _do_action(store, cmd, envver, ep, forced=True)


def check_episode(store, world, noise, envver, ep, state):
    """Эксплуатационный эпизод: suggest-driven / S3 / X-forced."""
    env_set(world, noise, envver)
    if state.get("x_pending"):
        state["x_pending"] = False
        return _do_action(store, "fix-aq", envver, ep, forced=True,
                          x=True, state=state)
    sug = strategy.suggest(store, {"problem": PROBLEM}, by="ep1",
                           ctx_now="absent",
                           obs_now={"E": "absent", "V": envver})
    sid = sug.get("strategy_id")
    refs = list(sug.get("knowledge_refs") or [])
    acts = [a for a in (sug.get("candidate_actions") or [])
            if a.get("type") == "command"]
    excl = state.get("exclude_kid")
    excluded = False
    if excl and refs and refs[0] == excl:
        excluded = True
    rec = {"step": ep, "world": world, "noise": noise, "envver": envver,
           "strategy_id": sid, "knowledge_refs": refs,
           "excluded": excluded}
    if excluded or sid == "S3" or not acts:
        # S3-бездействие (включая simulated exclusion)
        rec.update({"mode": "S3", "action": None, "outcome": None,
                    "excluded_kid": excl if excluded else None})
        return rec
    cmd = acts[0].get("command")
    rec["mode"] = "S2"
    res = _execute_cmd(cmd, envver, rec)
    return rec


def _do_action(store, cmd, envver, ep, forced=False, x=False, state=None):
    problem = PROBLEM
    facts = observer.collect(store)
    ctx = "absent"
    act = {"schema_version": "0.1",
           "action_id": "act_ep1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "EP-1%s" % ("-X" if x else "")}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=problem, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="ep1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"step": ep, "mode": "learn" if forced else "X",
            "action": cmd, "outcome": outcome, "ok": ok,
            "strategy_id": None,
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def _execute_cmd(cmd, envver, rec):
    problem = PROBLEM
    facts = observer.collect(store_g)
    act = {"schema_version": "0.1",
           "action_id": "act_ep1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "strategy",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "EP-1-S2"}
    store_g.append_action(act)
    res = executor.execute(store_g, act)
    ok = stable_active()
    ev = evaluation.evaluate(store_g, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=problem, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="ep1")
    experience.save(store_g, exp_full)
    k = update.apply(store_g, exp_full["experience_id"], outcome)
    rec.update({"action": cmd, "outcome": outcome, "ok": ok,
                "created_knowledge_id": k.get("knowledge_id")
                if k else None})
    return rec


store_g = None  # глобальный стор для _execute_cmd (упрощение)


def snapshot_all(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        rows.append({
            "knowledge_id": v["knowledge_id"], "version": v["version"],
            "status": v["status"], "created_at": v.get("created_at"),
            "schema_version": v.get("schema_version"),
            "context": v.get("context"),
            "lineage_generation": v.get("lineage_generation"),
            "applicable_when": v.get("applicable_when"),
            "applicability_observations": v.get(
                "applicability_observations"),
            "experience_refs": v.get("experience_refs"),
        })
    rows.sort(key=lambda r: r["knowledge_id"])
    return rows


def run_cell(cell):
    policy, hist, rep = cell.split("|")
    ev, right = POLICIES[policy]
    st = fresh_store(cell)
    global store_g
    store_g = st
    rec = {"cell": cell, "policy": policy, "event": ev, "right": right,
           "history": hist, "rep": rep, "learn": [], "steps": [],
           "trigger": None, "intervention": None, "checks": [],
           "audit_before": None, "audit_after": None,
           "final_snapshot": None, "line_trace": []}
    rec["audit_before"] = hash_layers()

    # learn-фаза
    if hist in E6_HISTS:
        learn_episode(st, "w1", "1", "fix-a", 0)
        rec["learn"].append({"cmd": "fix-a", "envver": "1"})
        learn_episode(st, "w1", "2", "fix-a", 0)
        rec["learn"].append({"cmd": "fix-a", "envver": "2"})
    else:
        learn_episode(st, "w1", "1", "fix-a", 0)
        rec["learn"].append({"cmd": "fix-a", "envver": "1"})

    state = {"x_pending": False, "exclude_kid": None,
             "intervened": False}
    trigger_step = None

    # E6: триггер на 1-м эпизоде проверки (момент 0), ДО failure
    if ev == "E6" and conflict_success_present(line_members(st)):
        trigger_step = 0
        rec["trigger"] = {"event": "E6", "step": 0, "at": "pre-step-1"}

    for i, (aim, (world, noise), envver) in enumerate(
            [tuple(s) for s in HISTORIES[hist]], start=1):
        if trigger_step is None and ev is not None and ev != "E6":
            ev_found = detect_events(line_members(st))
            if ev in ev_found:
                trigger_step = i - 1  # после шага i-1
                rec["trigger"] = {"event": ev, "step": i - 1,
                                  "at": "post-step-%d" % (i - 1)}
        if trigger_step is not None and not state["intervened"]:
            state["intervened"] = True
            if right == "X":
                state["x_pending"] = True
                rec["intervention"] = {"right": "X", "at": "before-step-%d"
                                       % i}
            elif right in ("R", "S"):
                mem = line_members(st)
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                state["exclude_kid"] = kid
                rec["intervention"] = {"right": right, "kid": kid,
                                       "at": "before-step-%d" % i}
                if right == "R" and kid:
                    _install_retract(kid)
        step = check_episode(st, world, noise, envver, i, state)
        rec["steps"].append(step)
        rec["line_trace"].append(line_members(st))
        # проверка механики после вмешательства (на шаге вмешательства)
        if (rec["intervention"] and rec["intervention"].get("at")
                == "before-step-%d" % i and right in ("R", "S")):
            sug = strategy.suggest(st, {"problem": PROBLEM}, by="ep1-chk",
                                   save=False, ctx_now="absent",
                                   obs_now={"E": "absent",
                                            "V": envver})
            refs0 = (sug.get("knowledge_refs") or [None])[0]
            rec["checks"].append({"step": i, "granted_excluded":
                                  (step.get("excluded") is True),
                                  "selected_ref": refs0,
                                  "exclude_kid":
                                  rec["intervention"].get("kid")})
    rec["final_snapshot"] = snapshot_all(st)
    rec["audit_after"] = hash_layers()
    if trigger_step is None and ev is not None and ev != "E6":
        ev_found = detect_events(line_members(st))
        if ev in ev_found:
            rec["trigger"] = {"event": ev, "step": len(rec["steps"]),
                              "at": "post-final-step", "terminal": True}
    return rec


def _install_retract(kid):
    """R: исключить kid из prior_lineage-чтений (simulated)."""
    orig = _ORIG_PRIOR_LINEAGE

    def wrapper(store, sym, e_val, cmd):
        return [r for r in orig(store, sym, e_val, cmd)
                if r.get("knowledge_id") != kid]
    update._prior_lineage = wrapper


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    cell = args.cell
    assert cell.count("|") == 2, "cell: POLICY|HIST|rep"
    rec = run_cell(cell)
    out = os.path.join(DIR, "EP1_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved %s; steps=%d; trigger=%s; intervention=%s; audit=%s"
          % (out, len(rec["steps"]), rec["trigger"],
             rec["intervention"],
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"


if __name__ == "__main__":
    main()
