# -*- coding: utf-8 -*-
"""brute_stable.py — повтор Ф4b GENERALIZATION-1 с УСТОЙЧИВЫМ
критерием успеха (state=active через 2с после действия; повторная
проверка). Причина повтора: в основном прогоне svc_state() сразу
после start/restart попадал в окно жизни демона (Type=simple: unit
active между fork и exit 1; на нагруженной системе окно расширялось)
— ложные success. Устойчивый критерий: сервис active И остаётся
active через 2 секунды.

Команды перебора (та же BIN): start, restart, fix-a, fix-b, fix-ab,
fix-c — до устойчивого success (макс 12). 7 эпизодов, env c.
"""
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

SVC = "tsasvc"
BIN = ["systemctl start tsasvc", "systemctl restart tsasvc",
       "fix-a", "fix-b", "fix-ab", "fix-c"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "F4b_stable_run.log")


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_c():
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    open("/run/tsasvc.lock.c", "w").close()
    _run(["systemctl", "reset-failed", SVC])


def stable_active():
    """active и остаётся active через 2с."""
    if _run(["systemctl", "is-active", SVC]).stdout.strip() != "active":
        return False
    time.sleep(2)
    return _run(["systemctl", "is-active", SVC]).stdout.strip() == "active"


def episode(n):
    env_c()
    for i, cmd in enumerate(BIN[:12]):
        p = _run(cmd.split())
        time.sleep(0.5)
        state_now = _run(["systemctl", "is-active", SVC]).stdout.strip()
        ok = stable_active() if state_now == "active" else False
        log({"ep": n, "n": i + 1, "command": cmd, "exit": p.returncode,
             "state_immediate": state_now, "stable_success": ok})
        if ok:
            return True, i + 1
    return False, len(BIN)


def main():
    open(OUT, "w", encoding="utf-8").close()
    res = []
    for n in range(1, 8):
        ok, steps = episode(n)
        res.append({"ep": n, "ok": ok, "steps": steps})
    log({"event": "summary", "data": res})
    print(json.dumps(res, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
