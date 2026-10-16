# -*- coding: utf-8 -*-
"""Политика полигона (см. LONGITUDINAL1_PROTOCOL.md, STALE_EXACT1_DESIGN.md,
EVENT_SUFFICIENCY1_DESIGN.md). Сенсор симптома видит флаги наблюдаемых
болезней a/b/c (symptom-строка; 'none' если пусто).

Политики экспериментальных веток (задокументированы в дизайнах):
- STALE-EXACT-1 (06.09): 'extra' — скрытое условие мира (устаревание):
  невидимо по признакам, видно только по последствиям;
- EVENT-SUFFICIENCY-1 / E0-target (06.09): 'n' — скрытый шумовой фактор:
  НЕ снимается fix-a, НЕ виден Observer, симптом не меняет. Оба флага
  (extra, n) скрыты от симптом-сенсора: symptom 'a' одинаков в классах;
- E1 (после E0, маршрут A): sensor_envfact() делает 'extra' наблюдаемым
  КАК ОТДЕЛЬНЫЙ ФАКТ СРЕДЫ (не симптом); 'n' остаётся скрытым;
- STALE-EXACT-2 (06.09): 'q' — скрытый фактор второго поколения (вне
  адреса v0.4: не в симптоме, не в envfact-контексте).
"""
HIDDEN_FLAGS = ("extra", "n", "q")


def sensor_symptom():
    import glob
    import os
    try:
        names = []
        for p in sorted(glob.glob("/run/tsasvc.lock.*")):
            base = os.path.basename(p)
            flag = base.replace("tsasvc.lock.", "")
            if flag in HIDDEN_FLAGS:
                continue  # скрытое условие (политика ветки)
            names.append(flag)
        value = " ".join(names) if names else "none"
        return ("ls", "\n".join(glob.glob("/run/tsasvc.lock.*")),
                "tsasvc", "symptom", value)
    except Exception as exc:
        return ("ls", "", "tsasvc", "symptom", "error:%s" % exc)


def sensor_envfact():
    """E1: наблюдаемый факт среды (не симптом): 'extra' present/absent.
    'n' остаётся скрытым (шум — не устаревание)."""
    import os
    try:
        present = os.path.exists("/run/tsasvc.lock.extra")
        value = "present" if present else "absent"
        return ("ls", "/run/tsasvc.lock.extra", "tsasvc", "extra", value)
    except Exception as exc:
        return ("ls", "", "tsasvc", "extra", "error:%s" % exc)


def sensor_envver():
    """F3 (CHANNEL-SUFFICIENCY-1): независимый внешний источник —
    файл версии среды /run/tsasvc.envver ('1'|'2'). Категорически не
    связан с lock-флагами (демон его не читает; Observer — читает)."""
    import os
    try:
        if os.path.exists("/run/tsasvc.envver"):
            with open("/run/tsasvc.envver", encoding="utf-8") as f:
                return ("envver", "/run/tsasvc.envver", "tsasvc",
                        "environment_version", f.read().strip())
        return ("envver", "", "tsasvc", "environment_version", "1")
    except Exception as exc:
        return ("envver", "", "tsasvc", "environment_version",
                "error:%s" % exc)
