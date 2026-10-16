# -*- coding: utf-8 -*-
"""Observer (Tsarapina, этап 1).

Собирает наблюдения детерминированными сенсорами (sensors.SENSORS),
сохраняет сырые выходы (raw, append-only) и факты (type=fact,
fact.schema + provenance) в Store. Никакой интерпретации: факт —
«что сервер сделал», не «что это значит».
"""
import os
import socket
import time

from observer import sensors
from storage.store import Store


def collect(store, machine=None):
    """Один проход по всем сенсорам → список фактов (уже сохранённых).

    v0.6 (integration gate): envver-наблюдение добавляется ТОЛЬКО если
    /run/tsasvc.envver существует (реальный внешний источник, CS-1).
    Без файла сенсор молчит: CA-1/TE-миры не получают V-фактов.
    Наблюдение без интерпретации (только environment_version = ...)."""
    machine = machine or socket.gethostname()
    facts = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    def append_one(name, fn):
        try:
            source, raw_text, subject, prop, value = fn()
        except Exception as exc:  # сенсор упал — факт-пустышка
            source, raw_text, subject, prop, value = (
                name, "", "sensor:%s" % name, "error", str(exc))
        raw_id = store.append_raw(source, raw_text)
        fact = {
            "type": "fact",
            "subject": subject,
            "property": prop,
            "value": str(value),
            "source": source,
            "timestamp": ts,
            "provenance": {
                "observed_at": ts,
                "recorded_at": ts,
                "machine": machine,
                "source": source,
                "observer": "observer/%s" % name,
                "raw_ref": raw_id,
                "context": "routine",
                # confidence для детерминированного сенсора: 1.0 при
                # успешном выполнении; механизм вычисления НЕ фиксируем
                # (RESEARCHABLE) — здесь просто «источник выполнен».
                "confidence": 1.0 if not value.startswith("sensor error")
                else 0.0,
                "history": [],
                "transformations": [],
            },
        }
        store.append_observation(fact)
        facts.append(fact)
        return fact

    for name, fn in sensors.SENSORS:
        append_one(name, fn)
    if os.path.exists("/run/tsasvc.envver"):
        from observer import polygon_sensor  # noqa: E402
        append_one("envver", polygon_sensor.sensor_envver)
    return facts
