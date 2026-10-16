# TSARAPINA INTEGRATION V0.6: ОТЧЁТ (07.09.2026)

Дизайн: INTEGRATION_V06_DESIGN.md (FROZEN 07.09). База: v0.5 FROZEN
(baseline strategy/strategy_v05_baseline.py — копия, не изменялась).
Инженерия: knowledge (schema 0.2 + applicable-поля), update
(acquisition A2), observer (envver-наблюдение), strategy (v0.6:
applicable_when-адресация). Гейт: experiments/gate_v06.py →
GATE_V06_run2.txt.

## Изменения (по дизайну, раздел 2)

- knowledge/knowledge.py: SCHEMA_VERSION "0.2"; create() принимает
  applicable_when {факт: значение} и applicability_observations
  [{signal, values_seen, relation, episode_refs}] (optional; версии
  копируют; retract/restore/conflict поля не теряют); provenance_walk
  включает оба поля; protocols/knowledge.schema.json: const 0.2 +
  новые свойства.
- update/update.py: acquisition-шаг (A2-механика ACQ-1) в apply() —
  ТОЛЬКО verified-success и ТОЛЬКО при ctx_extra (E) в args действия;
  линия = (symptom, E, command) — как адрес v0.5; V в идентичность
  линии не входит (решение Q1); пустое поле не пишется; failure/
  noise линию не меняют.
- observer/observer.py: envver-наблюдение в collect только при
  существующем /run/tsasvc.envver (реальный источник; без файла —
  молчание: CA-1/TE-миры не получают V-фактов).
- strategy/strategy.py → v0.6: knowledge с applicable_when
  проверяется по наблюдениям obs_now (E — ctx_now; расширяемо);
  legacy-знания без поля — ctx-путь v0.5 без изменений; S3-
  семантика сохранена; strategy_version "0.6".

## Гейт

### G1. Backward compatibility — PASS
- gate_v05 часть A (T1-T4e) на v0.6: 10/10 PASS; единственный FAIL —
  DET-литерал «strategy_version == 0.5» (проверка ярлыка версии,
  обязанная смениться); детерминизм подтверждён отдельно:
  DET-v0.6 — повторный suggest идентичен, version=0.6 — PASS;
- gate_v05 часть B (TE): 14/14 PASS;
- юнит-наборы 9/9 PASS (knowledge/update/observer/strategy +
  llm_adapter/executor/evaluation/experience/aggregation).
  Примечание (окружение): CA-1/TE-сценарии требуют полигона без
  envver-файла (learn-миры v0.6 пишут envver; TE-миры его не знают);
  гейт чистит /run/tsasvc.envver перед частями A/B и юнитами.

### G2. Behavioral equivalence — PASS
Знание линии с applicable_when={E:absent} + obs V[1,2]:
- задача A при E=absent, V=1: v0.6 == v0.5 → S2 fix-a, 1 действие;
- задача A при E=absent, V=2: v0.6 == v0.5 → S2 fix-a, 1 действие;
- AB → S2 fix-ab, 1 действие: v0.6 == v0.5;
- C-SEB-путь: G1 T4c (exploration → fix-c, 8 действ.) — не изменён.
applicable_when не меняет поведение там, где v0.5 работала.

### G3. Acquisition persistence — PASS
- applicable_when={E:absent} и observations V[1,2] (disagreement,
  episode_refs) переживают новый процесс (Store reopen, subprocess);
- retract/restore сохраняют поля; версии целы (v1..v3);
- provenance_walk: applicable_when в цепочке, raw до фактов непуст;
- v1 (w1-знание, {E:absent,V:1}) не мутирована появлением v2.

### G4. Applicability actually used — PASS
- G4a: latest applicable_when == {E:absent} (равенство); obs V
  values_seen [1,2]; E=absent при V=1 → S2 (1 действие fix-a); при
  V=2 → S2 — V не стал условием;
- G4b: E=present при V=1 (wX) и V=2 (w2) → S3, знание не применяется
  вслепую;
- G4c: (i) знание с applicable_when БЕЗ ctx_extra в args — S2 при
  E=absent, S3 при E=present (поле управляет, не артефакт args);
  (ii) legacy-знание без поля — ctx-путь v0.5; (iii) ни одно знание
  с V в observations не содержит V в applicable_when (assert).

## Вердикт

**GATE V0.6: PASS (24 PASS, 0 FAIL).** Интеграция приобретённой
структуры применимости в рабочий цикл выполнена: поле реально
используется адресацией (G4), старые свойства сохранены (G1/G2),
структура персистентна с полным provenance (G3). V зарегистрирован
как расхождение и НЕ стал условием; E гейтит применение; legacy-путь
v0.5 не тронут.

**Strategy v0.6 FROZEN (07.09.2026; слово профессора: «GATE v0.6:
PASS, 24/24. Замораживаем»).** v0.5 — FROZEN BASELINE
(strategy_v05_baseline.py). Следующий этап (по слову профессора): не
расширение системы, а поиск границы applicability-механизма
(boundary experiment).

## Артефакты

INTEGRATION_V06_DESIGN.md (FROZEN), strategy/strategy_v05_baseline.py
(v0.5), knowledge/knowledge.py (0.2), protocols/knowledge.schema.json
(0.2), update/update.py, observer/observer.py, strategy/strategy.py
(v0.6), experiments/gate_v06.py, GATE_V06_run.txt / run2.txt,
gate_v06_data/ (сторы G1-DET/G2/G3/G4), INTEGRATION_V06_REPORT.md
(этот файл).
