# -*- coding: utf-8 -*-
"""ACQ-1 кандидат-механизм acquisition (FROZEN 07.09.2026; DESIGN р.4-6,
8; PROTOCOL A0/A1/A2/A3).

Уровни:
- A0 — механизма нет (записи ведёт регистратор драйвера);
- A1 — структурный фильтр + recency-коммит: условие = конъюнкция
  прошедших фильтр фактов ПОСЛЕДНЕГО verified-success момента;
- A2 — A1 + межэпизодная структура: условие = инвариант значений по
  ВСЕМ verified-success моментам; факт с меняющимся значением → D1-
  наблюдение (relation=disagreement), в условие не входит.

Пробы (on_probe): вектор совпал с условием, вердикт != success → D2-
наблюдение {relation=outcome_disagreement}; условие НЕ меняется.
Победитель не назначается ни в D1, ни в D2.

Механизм НЕ получает имя мира и GT. Факт-кандидат:
  {name, value, source_type: "flag"|"enum"|"continuous",
   channel: "env"|"symptom"|"control"|"telemetry", stable: bool}
Фильтр: channel != "symptom"; source_type != "continuous"; stable.

N (lock.n) в кандидаты НЕ входит: HIDDEN n (политика CS-1), решение
профессора 07.09 (N = измерение). Регистратор ведёт n_obs отдельно.
"""
import json


class Mechanism:
    def __init__(self, level):
        assert level in ("A0", "A1", "A2")
        self.level = level
        self.records = []        # записи learn-моментов (acquisition)
        self.obs_d1 = []         # сигнальные расхождения
        self.obs_d2 = []         # исходные расхождения (пробы)
        self.condition = {}      # {name: value}
        self.seen = {}           # {name: set(values)} по успехам
        self.success_count = 0

    # --- фильтр (общий для A1/A2) ---
    @staticmethod
    def _passes(c):
        return (c["channel"] != "symptom"
                and c["source_type"] != "continuous"
                and c["stable"])

    @staticmethod
    def _reject_reason(c):
        if c["channel"] == "symptom":
            return "symptom_channel"
        if c["source_type"] == "continuous":
            return "continuous"
        if not c["stable"]:
            return "unstable"
        return None

    # --- learn-момент ---
    def on_learn(self, episode_id, candidates, verdict):
        rec = {"kind": "learn", "episode_id": episode_id,
               "verdict": verdict,
               "candidates": [{"name": c["name"], "value": c["value"],
                               "channel": c["channel"],
                               "source_type": c["source_type"],
                               "stable": c["stable"]} for c in candidates]}
        if self.level == "A0":
            self.records.append(rec)
            return rec
        passed = [c for c in candidates if self._passes(c)]
        rejected = [(c["name"], self._reject_reason(c))
                    for c in candidates if not self._passes(c)]
        rec["filtered"] = [{"name": c["name"], "value": c["value"]}
                           for c in passed]
        rec["rejected"] = [{"name": n, "reason": r} for n, r in rejected]
        if verdict == "success":
            self.success_count += 1
            if self.level == "A1":
                # recency-коммит: полная конъюнкция последнего успеха
                self.condition = {c["name"]: c["value"] for c in passed}
            else:  # A2
                for c in passed:
                    n, v = c["name"], c["value"]
                    self.seen.setdefault(n, set()).add(v)
                    if n in self.condition:
                        if self.condition[n] != v:
                            # инвариант нарушен → D1, из условия вон
                            del self.condition[n]
                            self.obs_d1.append({
                                "episode_id": episode_id, "fact": n,
                                "values_seen": sorted(self.seen[n]),
                                "relation": "disagreement"})
                    else:
                        # в условии, только если ещё не был в D1
                        if n not in [o["fact"] for o in self.obs_d1]:
                            self.condition[n] = v
        rec["condition_after"] = dict(self.condition)
        self.records.append(rec)
        return rec

    # --- проба (наблюдение, условие не обновляется) ---
    def on_probe(self, episode_id, candidates, verdict):
        if self.level in ("A0",):
            return None
        vec = {c["name"]: c["value"] for c in candidates}
        matched = (self.condition and
                   all(vec.get(n) == v for n, v in self.condition.items()))
        rec = {"kind": "probe", "episode_id": episode_id,
               "verdict": verdict, "matched": bool(matched),
               "condition": dict(self.condition)}
        if matched and verdict != "success":
            self.obs_d2.append({
                "episode_id": episode_id, "relation":
                "outcome_disagreement", "condition": dict(self.condition),
                "verdict": verdict})
            rec["d2"] = True
        self.records.append(rec)
        return rec

    def final(self):
        return {"level": self.level,
                "condition": dict(self.condition),
                "obs_d1": self.obs_d1,
                "obs_d2": self.obs_d2,
                "success_count": self.success_count}


def json_default(o):
    if isinstance(o, set):
        return sorted(o)
    raise TypeError
