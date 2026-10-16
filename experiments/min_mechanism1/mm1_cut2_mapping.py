# -*- coding: utf-8 -*-
"""MIN-MECHANISM-1 / CUT-2: persistent mapping + applicability.

Experimental минимальный кандидат (FREEZE Cut-2, 12.09.2026):
persistent `(condition=symptom, action, result, applicable_when)`
→ lookup → applicable? → apply / reject. Один добавленный слой к
Cut-1: `applicable_when` (из текущего наблюдения E при записи).
Без recovery, без Explore, без failure-trigger. Condition остаётся
symptom-only. Persistence — JSONL между эпизодами.
"""
import json
import time


class MappingCut2:
    """Persistent mapping + applicable_when (минимальный кандидат)."""

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

    def record(self, condition, action, result, obs):
        """Запись только после verified success (вызывает драйвер).

        obs: текущие наблюдения, напр. {"E": "absent"} — становятся
        applicable_when (устойчивое условие применимости)."""
        e = {"condition": condition, "action": action, "result": result,
             "applicable_when": dict(obs),
             "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.entries.append(e)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e

    def applicable(self, entry, obs):
        """True — запись применима к текущим наблюдениям."""
        aw = entry.get("applicable_when")
        if not aw:
            return True
        return all(obs.get(k) == v for k, v in aw.items())
