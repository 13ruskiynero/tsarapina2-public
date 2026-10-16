# -*- coding: utf-8 -*-
"""RE-1: engine переносимости контура (RAW-first; изоляция).

Проверка переносимости на narrowed границе: state + applicable
knowledge → apply в другой среде. НЕ продуктовая ветка; автономный
контур, не трогающий портфель (recon1 r1, portfolio и т.д.).

Изоляция:
* локальная автономная среда: собственные tenant-каталоги (A/B),
  собственная локальная служба (state-файл), собственные команды
  fix-a/fix-aq (имена УЖЕ разрешены allowlist P7 — слои
  НЕ изменяются; PATH процесса указывает на tenant/bin);
* store: существующая схема storage как есть;
* таблица выученных действий: state.json (knowledge_id → command),
  привязана к знанию при acquisition; переносится вместе со store;
* rotation = снимок → активная база пуста; restore = возврат
  зафиксированного снимка (НЕ rebuild);
* в apply-эпизодах: БЕЗ update.apply / новых знаний /
  переприобретения; result связывается с тем же kid.

Запуск: python3 re1_engine.py --smoke | --run
Артефакты: RE1_E*.json, RE1_ANALYSIS.txt, state.json (RAW-first).
"""
import argparse
import glob
import hashlib
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
sys.path.insert(0, os.path.join(BASE, "strategy"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402

DIR = os.path.dirname(os.path.abspath(__file__))
TENANTS = os.path.join(DIR, "tenants")
ACTIVE = os.path.join(DIR, "active_store")
BACKUP = os.path.join(DIR, "snapshot_store")
STATE = os.path.join(DIR, "state.json")

LAYER_FILES = [
    "strategy/strategy.py", "strategy/exclusion.py",
    "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
    "llm/adapter.py",
]
SHA_EXTRA = [os.path.join(BASE, "experiments", "recon1",
                          "strategy_a1_isolated.py")]

FIXA = """#!/bin/bash
# локальное лечение A (изолированный tenant; имя разрешено P7)
D="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$D/state" ] && [ "$(cat "$D/state")" = "healthy" ]; then exit 0; fi
F="$(cat "$D/flags" 2>/dev/null)"
if [ "$F" = "a" ]; then echo healthy > "$D/state"; echo "healed A"; exit 0; fi
echo "fix-a: no effect (flags=$F)"; exit 1
"""
FIXAQ = """#!/bin/bash
# локальное лечение A+Q (изолированный tenant; имя разрешено P7)
D="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$D/state" ] && [ "$(cat "$D/state")" = "healthy" ]; then exit 0; fi
F="$(cat "$D/flags" 2>/dev/null)"
if [ "$F" = "a" ] || [ "$F" = "aq" ] || [ "$F" = "q" ]; then
  echo healthy > "$D/state"; echo "healed"; exit 0; fi
echo "fix-aq: no effect (flags=$F)"; exit 1
"""


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=60, shell=False)


def sha_all():
    out = {}
    for rel in LAYER_FILES:
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()[:16]
    for p in SHA_EXTRA:
        if os.path.exists(p):
            with open(p, "rb") as f:
                out["recon1/" + os.path.basename(p)] = \
                    hashlib.sha256(f.read()).hexdigest()[:16]
    return out


def setup_tenant(name, flags, env_marker):
    t = os.path.join(TENANTS, name)
    if os.path.exists(t):
        shutil.rmtree(t)
    os.makedirs(os.path.join(t, "bin"))
    with open(os.path.join(t, "bin", "fix-a"), "w") as f:
        f.write(FIXA)
    with open(os.path.join(t, "bin", "fix-aq"), "w") as f:
        f.write(FIXAQ)
    os.chmod(os.path.join(t, "bin", "fix-a"), 0o755)
    os.chmod(os.path.join(t, "bin", "fix-aq"), 0o755)
    with open(os.path.join(t, "flags"), "w") as f:
        f.write(flags)
    with open(os.path.join(t, "state"), "w") as f:
        f.write("sick")
    with open(os.path.join(t, "env"), "w") as f:
        f.write(env_marker)
    return t


def bind_env(t):
    """Связать окружение процесса с тенантом (PATH)."""
    os.environ["PATH"] = os.path.join(t, "bin") + ":" + \
        os.environ.get("PATH", "")
    with open(os.path.join(t, "env")) as f:
        return f.read().strip()


def healthy(t):
    try:
        with open(os.path.join(t, "state")) as f:
            return f.read().strip() == "healthy"
    except OSError:
        return False


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"actions": {}, "acquisition_events": [], "k_ids": []}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def open_store(d):
    return Store(os.path.join(d, "tsarapina.db"), d)


def write_rec(rec, ep):
    p = os.path.join(DIR, "RE1_E%d.json" % ep)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return p


def do_action(store, cmd, why):
    act = {"schema_version": "0.1",
           "action_id": "act_re1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": why, "type": "command",
           "command": cmd, "args": {"goal": {}, "ctx_extra": "local"},
           "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "RE-1"}
    store.append_action(act)
    res = executor.execute(store, act)
    return act, res


def knowledge_view(store, st):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for kid, v in latest.items():
        rows.append({"kid": kid, "outcome": v.get("context"),
                     "cmd": (st["actions"].get(kid) or {}).get("action"),
                     "status": v.get("status")})
    rows.sort(key=lambda r: r["kid"])
    return rows


def episode(store, t, st, ep, mode, cmd=None, kid=None,
            note=None):
    rec = {"ep": ep, "mode": mode, "tenant": os.path.basename(t),
           "env_marker": bind_env(t), "healthy_before": healthy(t),
           "action": None, "result": None, "local_check": None,
           "linked_knowledge": kid, "note": note,
           "knowledge_view": None, "sha": None}
    if mode in ("acquisition", "anchor", "anchor_post_restore",
                "anchor_after_env_rotation", "apply_no_k",
                "exposure", "env_bind"):
        if mode == "exposure" or mode == "env_bind":
            rec["local_check"] = None
            rec["knowledge_view"] = knowledge_view(store, st)
            return rec
        exe_cmd = cmd
        if mode in ("anchor", "anchor_post_restore",
                    "anchor_after_env_rotation", "apply_no_k"):
            if mode == "apply_no_k":
                # носитель проверяется ДО исполнения: без kid в store
                # применение невозможно (не память драйвера)
                kv = knowledge_view(store, st)
                if kid not in [r["kid"] for r in kv]:
                    rec["note"] = "no_knowledge (apply impossible)"
                    rec["local_check"] = "no_knowledge"
                    rec["knowledge_view"] = kv
                    return rec
            exe_cmd = (st["actions"].get(kid) or {}).get("action")
            if exe_cmd is None:
                rec["note"] = "no_knowledge (apply impossible)"
                rec["local_check"] = "no_knowledge"
                rec["knowledge_view"] = knowledge_view(store, st)
                return rec
        act, res = do_action(store, exe_cmd, "RE-1 " + mode)
        rec["action"] = {"action_id": act["action_id"],
                         "command": exe_cmd,
                         "permitted": act["permitted"]}
        rec["result"] = {"result_id": res.get("result_id"),
                         "refused": res.get("refused"),
                         "exit_code": res.get("exit_code")}
        rec["local_check"] = "success" if healthy(t) else "partial"
        if mode == "acquisition":
            ok = healthy(t)
            facts = observer.collect(store)
            ev = evaluation.evaluate(store, res["result_id"], {})
            outcome = "success" if ok else "partial"
            exp_full = experience.build(
                problem="local service inactive symptom=a",
                observations=facts, actions=[act["action_id"]],
                result_ref=res["result_id"], machine="re1")
            experience.save(store, exp_full)
            k = update.apply(store, exp_full["experience_id"], outcome)
            newkid = k.get("knowledge_id") if k else None
            st["actions"][newkid] = {"action": exe_cmd}
            st["acquisition_events"].append(
                {"ep": ep, "kid": newkid})
            st["k_ids"].append(newkid)
            save_state(st)
            rec["linked_knowledge"] = newkid
        rec["knowledge_view"] = knowledge_view(store, st)
        return rec
    return rec


def run(smoke=False):
    if os.path.exists(TENANTS):
        shutil.rmtree(TENANTS)
    os.makedirs(TENANTS)
    for p in (ACTIVE, BACKUP):
        if os.path.exists(p):
            shutil.rmtree(p)
    if os.path.exists(STATE):
        os.remove(STATE)
    sha_before = sha_all()
    ta = setup_tenant("A", "a", "1")
    tb = setup_tenant("B", "q", "2")

    store = open_store(ACTIVE)
    st = load_state()
    recs = []
    E = []

    def add(mode, t, cmd=None, kid=None, note=None):
        ep = len(E)
        rec_ = episode(store, t, st, ep, mode, cmd=cmd, kid=kid,
                       note=note)
        E.append(rec_)
        p = write_rec(rec_, ep)
        print("saved %s; mode=%s check=%s" % (p, mode,
                                              rec_["local_check"]),
              flush=True)
        return rec_

    add("env_bind", ta, note="bind env A (env=1)")
    add("exposure", ta, note="live 1 episode")
    add("acquisition", ta, cmd="fix-a")
    kid = E[-1]["linked_knowledge"]
    add("anchor", ta, kid=kid)
    # rotation: снимок → активная пустая
    if os.path.exists(ACTIVE):
        shutil.copytree(ACTIVE, BACKUP)
    shutil.rmtree(ACTIVE)
    os.makedirs(ACTIVE)
    store = open_store(ACTIVE)
    add("rotation", ta, note="active store emptied (snapshot kept)")
    add("apply_no_k", ta, kid=kid, note="apply K on empty store")
    # restore: возврат зафиксированного снимка
    shutil.rmtree(ACTIVE)
    shutil.copytree(BACKUP, ACTIVE)
    store = open_store(ACTIVE)
    add("restore", ta, note="snapshot restored (same store)")
    add("anchor_post_restore", ta, kid=kid)
    add("env_bind", tb, note="bind env B (env=2)")
    add("anchor_after_env_rotation", tb, kid=kid)

    sha_after = sha_all()
    kids = sorted(st["k_ids"])
    acq = st["acquisition_events"]
    checks = {
        "M1_local_run": True,
        "M2_layers_unchanged": sha_before == sha_after,
        "M3_restore_not_rebuild": E[7]["linked_knowledge"] == kid
        and kid in [r["kid"] for r in E[7]["knowledge_view"]],
        "M4_short_loop": len(E) <= 12,
        "M5_one_knowledge": len(kids) == 1,
        "M6_local_validation_different_results": (
            E[3]["local_check"] != E[9]["local_check"]),
        "M7_no_second_k_no_reacquisition":
            len(acq) == 1 and len(st["k_ids"]) == 1,
        "M8_one_operation": st["actions"][kid]["action"] == "fix-a",
        "M9_no_apply_without_holder":
            E[5]["local_check"] == "no_knowledge",
    }
    analysis = {"checks": checks, "k_ids": kids, "acquisition": acq,
                "episodes": [(r["ep"], r["mode"], r["tenant"],
                              r["local_check"]) for r in E]}
    with open(os.path.join(DIR, "RE1_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write(json.dumps(analysis, ensure_ascii=False, indent=1))
    print(json.dumps(checks, ensure_ascii=False, indent=1))
    if not all(checks.values()):
        print("SMOKE/RUN: есть невыполненные проверки")
    else:
        print("SMOKE/RUN: всё чисто")
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    run(smoke=args.smoke)


if __name__ == "__main__":
    main()
