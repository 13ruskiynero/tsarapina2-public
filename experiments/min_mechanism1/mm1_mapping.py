# -*- coding: utf-8 -*-
"""MIN-MECHANISM-1: persistent action-result mapping (minimal candidate).

Замороженная роль (MIN_MECHANISM1_DESIGN.md, FREEZE 12.09.2026):
verified success → persistent (condition, action, result) → lookup →
repeat. Condition — только symptom (§6.2). Никаких обработок
failure / revision / applicability (§6.1). Persistence — файл JSONL
между эпизодами, без ротации носителя. Кандидат экспериментальный,
вне production-слоёв.
"""
import json
import time


class Mapping:
    """Минимальный persistent mapping: condition → (action, result)."""

    def __init__(self, path):
        self.path = path
        self.entries = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))
        except FileNotFoundError:
            pass

    def lookup(self, condition):
        """Последняя verified запись по condition; иначе None."""
        found = None
        for e in self.entries:
            if e.get("condition") == condition:
                found = e
        return found

    def record(self, condition, action, result):
        """Запись только после verified success (вызывает драйвер)."""
        e = {"condition": condition, "action": action, "result": result,
             "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.entries.append(e)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e
