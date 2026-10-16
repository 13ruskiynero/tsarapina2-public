# -*- coding: utf-8 -*-
"""mini-проверка hotfix v0.5: ctx_mismatch-путь (S3) не падает."""
import os
import shutil
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

DIR = os.path.join(BASE, "tests", "tmp_ctxmismatch")
if os.path.exists(DIR):
    shutil.rmtree(DIR)
os.makedirs(DIR)
st = Store(os.path.join(DIR, "t.db"), DIR)
GOAL = {"property": "service:tsasvc.state", "value": "active"}

# learn в мире absent (a)
sub = __import__("subprocess")


def env(extra):
    sub.run(["systemctl", "stop", "tsasvc"], capture_output=True,
            timeout=40)
    for p in __import__("glob").glob("/run/tsasvc.lock.*"):
        os.remove(p)
    open("/run/tsasvc.lock.a", "w").close()
    if extra:
        open("/run/tsasvc.lock.extra", "w").close()
    sub.run(["systemctl", "reset-failed", "tsasvc"], capture_output=True,
            timeout=40)


def stable():
    time.sleep(0.4)
    out = sub.run(["systemctl", "is-active", "tsasvc"],
                  capture_output=True, text=True).stdout.strip()
    return out == "active"


now = time.strftime("%Y-%m-%dT%H:%M:%S")
aid = st.append_action({
    "schema_version": "0.1", "action_id": "act_x_%s" % time.time(),
    "strategy_id": None, "proposed_by": "learn", "type": "command",
    "command": "fix-a", "args": {"goal": GOAL, "ctx_extra": "absent"},
    "permitted": True, "proposed_at": now, "rationale": "mini"})
env(False)
res = executor.execute(st, st.read_action(aid) or
                       {"action_id": aid, "type": "command",
                        "command": "fix-a", "permitted": True})
exp = experience.build(
    problem="tsasvc.service inactive symptom=a",
    observations=observer.collect(st), actions=[aid],
    result_ref=res["result_id"], machine="mini")
experience.save(st, exp)
update.apply(st, exp["experience_id"], "success")

# задача при ctx=present → S3 ctx_mismatch (без краха)
env(True)
ctx_now = polygon_sensor.sensor_envfact()[4]
print("ctx_now:", ctx_now, flush=True)
sug = strategy.suggest(st, {"problem": "tsasvc.service inactive "
                        "symptom=a"}, ctx_now=ctx_now, save=False)
print("strategy:", sug["strategy_id"], flush=True)
print("rule:", sug["rationale"][0]["rule"] if sug["rationale"] else "",
      flush=True)
print("actions:", len(sug["candidate_actions"]), flush=True)
assert sug["strategy_id"] == "S3", "ожидался S3 (ctx_mismatch)"
assert any(r.get("rule") == "context_mismatch" for r in sug["rationale"])
print("OK: ctx_mismatch → S3, без краха", flush=True)
