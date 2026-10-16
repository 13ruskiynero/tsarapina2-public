# -*- coding: utf-8 -*-
"""Executor (Tsarapina, этап 6).

Правила (FIXED):
- принимает ТОЛЬКО структурированный Action (action_id/type/
  permitted/...);
- проверяет разрешение: observe — по имени сенсора; command — флаг
  permitted + allowlist + запрет метасимволов (| ; & > < ` $ ( ));
- фиксирует state_before; выполняет РОВНО указанную команду;
  сохраняет stdout/stderr/exit/state_after; возвращает Result;
- НЕ думает: плохую команду НЕ чинит (refused, команда не
  модифицируется), ничего не объясняет и не «улучшает»;
- отказ — тоже запись (refused=true, exit_code=null, stderr с
  причиной): аудит невыполнения;
- result.outcome = unverified (оценку ставит ТОЛЬКО Evaluation).

RESEARCHABLE: выбор команды, планирование, автономные изменения
шире точечного allowlist.
"""
import os
import re
import shlex
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observer import sensors  # noqa: E402

# Разрешённые команды (диагностика) — префикс-матчинг по lstrip-команде.
# Изменяющее действие — ТОЛЬКО точечный рестарт ssh (исправление среза).
ALLOWED_PREFIXES = (
    "systemctl status", "systemctl is-active", "systemctl show",
    "systemctl restart ssh", "systemctl start ssh", "systemctl stop ssh",
    # полигон VERTICAL-1: имитатор tsasvc (см. VERTICAL1_PROTOCOL.md)
    "systemctl restart tsasvc", "systemctl start tsasvc",
    "systemctl stop tsasvc",
    # полигон VERTICAL-1 v2: лечение tsafix (невыводимое из задачи)
    "tsafix",
    # полигон LONGITUDINAL-1: лечения болезней (политика; LLM их не знает)
    "fix-a", "fix-b", "fix-c", "fix-ab", "fix-a2",
    # полигон STALE-EXACT-2: лечение w2 (скрытый q; политика 06.09)
    "fix-aq",
    "ss ", "ps ", "df ", "free", "journalctl", "uptime",
    "cat /etc/ssh/", "ls -la /etc/ssh/",
)
META = re.compile(r"[|;&><`$()]")
TIMEOUT = 15


def snapshot():
    """Ключевое состояние: факты сенсоров (только значения, без
    интерпретации)."""
    st = {}
    for name, fn in sensors.SENSORS:
        try:
            source, raw, subject, prop, value = fn()
            st["%s.%s" % (subject, prop)] = value
        except Exception:
            st[name] = ""
    return st


def _check_permission(action):
    """Вернуть (разрешено, причина-отказа)."""
    atype = action.get("type")
    if atype == "observe":
        sensor = (action.get("args") or {}).get("sensor") or \
            action.get("sensor")
        names = [n for n, _ in sensors.SENSORS]
        if sensor in names or any(sensor == n.split(":")[-1]
                                  for n in names):
            return True, ""
        return False, "observe: неизвестный сенсор %r" % sensor
    if atype != "command":
        return False, "type=%s не разрешён Executor'ом" % atype
    if not action.get("permitted"):
        return False, "action.permitted=False"
    cmd = (action.get("command") or "").strip()
    if not cmd:
        return False, "command пуст"
    if META.search(cmd):
        return False, "метасимволы запрещены: %r" % cmd
    if not cmd.startswith(tuple(ALLOWED_PREFIXES)):
        return False, "команда вне allowlist: %r" % cmd
    return True, ""


def _run_observe(action):
    sensor = (action.get("args") or {}).get("sensor") or \
        action.get("sensor") or ""
    for name, fn in sensors.SENSORS:
        if name == sensor or name.split(":")[-1] == sensor:
            try:
                source, raw, subject, prop, value = fn()
                return 0, "subject=%s property=%s value=%s\n%s" % (
                    subject, prop, value, raw), ""
            except Exception as exc:
                return 1, "", "observe error: %s" % exc
    return 1, "", "сенсор не найден: %s" % sensor


def _run_command(action):
    cmd = (action.get("command") or "").strip()
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return None, "", "не могу разобрать команду: %s" % exc
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=TIMEOUT)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return None, "", "команда не найдена: %s" % argv[0]
    except subprocess.TimeoutExpired:
        return None, "", "timeout %ds: %s" % (TIMEOUT, cmd)


def execute(store, action):
    """Выполнить действие. Вернуть result-запись (сохранённую)."""
    aid = action.get("action_id") or ("act_%s" % uuid.uuid4().hex[:8])
    state_before = snapshot()
    allowed, reason = _check_permission(action)
    refused = not allowed
    exit_code = None
    stdout = ""
    stderr = ""
    if allowed:
        if action.get("type") == "observe":
            exit_code, stdout, stderr = _run_observe(action)
        else:
            exit_code, stdout, stderr = _run_command(action)
    else:
        stderr = "REFUSED: %s" % reason
    state_after = snapshot()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    res = {
        "schema_version": "0.1",
        "result_id": "res_%s_%s" % (time.strftime("%Y%m%dT%H%M%S"),
                                    uuid.uuid4().hex[:8]),
        "action_id": aid,
        "executed_at": now,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "state_before": state_before,
        "state_after": state_after,
        "outcome": "unverified",
        "refused": refused,
    }
    store.append_result(res)
    return res
