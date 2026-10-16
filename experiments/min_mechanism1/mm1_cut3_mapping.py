# -*- coding: utf-8 -*-
"""MIN-MECHANISM-1 / CUT-3: persistent mapping + applicability + E2.

Experimental минимальный кандидат (FREEZE Cut-3, 12.09.2026):
- persistent (condition=symptom, action, result, applicable_when);
- fail-streak (в памяти прогона) — два последовательных non-success
  ПРИМЕНЕНИЯ → E2_detected (тем же сигналом exploration_authorized);
- записи не удаляются; lookup — последняя (PRESERVE + SELECT).
E2 не выбирает действие сам: exploration/action — общий BIN
(запускается драйвером). Без trust/selection/LLM/D-4.
"""
import json
import time


class MappingCut3:
    """Persistent mapping + applicable_when + E2-сигнал."""

    def __init__(self, path):
        self.path = path
        self.entries = []
        self.streak = {}
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

    def record(self, condition, action, result, obs, source):
        """Запись только после verified success (вызывает драйвер)."""
        e = {"condition": condition, "action": action, "result": result,
             "applicable_when": dict(obs), "source": source,
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

    def note_non_success(self, condition):
        self.streak[condition] = self.streak.get(condition, 0) + 1

    def note_success(self, condition):
        self.streak[condition] = 0

    def fail_streak(self, condition):
        return self.streak.get(condition, 0)

    def should_transition(self, condition):
        """E2: два последовательных non-success применения."""
        return self.fail_streak(condition) >= 2
