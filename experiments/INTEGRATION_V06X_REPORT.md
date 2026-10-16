# TSARAPINA INTEGRATION GATE v0.6.x: ОТЧЁТ (07.09.2026)

Контракт: APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md (FROZEN;
L1–L6); gate: INTEGRATION_GATE_V06X_DESIGN.md (FROZEN; G1–G6).
Реализация в рабочих слоях (update.py, knowledge.py; v0.6 сохранён
как исполняемые baseline-копии update_v06_baseline.py /
knowledge_v06_baseline.py — откат восстановлением, без миграций
SQLite). Прогон: 9 сценариев (S0–S5, S6b, P1, P2) × r1/r2 = 18
прогонов на v0.6.x + 18 на v06-baseline (для G5) = 36 прогонов →
GATE_V06X_records_{v06x,v06}.json (RAW) → gate_v06x_analyze.py →
GATE_V06X_ANALYSIS.txt. Audit: слои не изменялись во время прогонов
(4/4). Детерминизм: r1 ≡ r2 (v06x, 9/9).

## 1. Реализовано (v0.6.x-контракт в коде)

- knowledge.create: параметр lineage_generation (None → поле не
  пишется; legacy/unknown); SCHEMA_VERSION 0.3 (аддитивно, legacy
  0.2 читается);
- update._acquire: L2 — pivot = последний field-bearing
  verified-success член линии; нет fb-структуры → честный срез
  (Q1/K1-норма); дивергенционные записи получают source=
  "verified success"; L3 — перенос failure-obs всех failure-членов
  линии в obs (никогда в aw), дедупликация слиянием episode_refs по
  сигнатуре;
- update.apply: non-success — нативный recorder (a)/(b) (source=
  "verified failure"; aw не создаётся и не меняется — L3-граница);
  lineage_generation = 1 + число предшествующих verified-success
  членов линии (learn-путь с E);
- strategy-слой не изменён.

## 2. Implementation findings (по правилу: дизайн не переписывается
молча; фиксируются findings)

- **IF-1 (анализатор, не реализация):** S4-K2 — повторный w1 с тем
  же honest-вектором {E:absent,V:1} ДО первого расхождения легитимно
  сохраняет V в aw (повтор honest-нормы, не reopened-дефект;
  реализация воспроизводит ровно цепочку LP-1-F1-S4: m2 {E,V1}
  normal_fb). Gate-критерий уточнён: aw-чистота применяется к latest
  и к поколениям ПОСЛЕ первого V-наблюдения (f-правило); V никогда
  не возвращается в aw после дивергенции. Дизайн gate (G2 «aw чист
  на latest») поддерживает это чтение.
- **IF-2 (косметика baseline-режима):** v06-прогоны пишут records с
  schema_version="0.3" (живой knowledge-модуль с расширенной
  сигнатурой; семантика — v0.6, recorder отсутствует, generation не
  пишется). На поведение и G5-сравнение не влияет.

## 3. Результаты (v0.6.x; r1 ≡ r2)

```
S0:   K1 gen1 {E,V:1}[] honest_q1 → K2 gen2 {E}[V 1,2 source=verified success]
S1:   K1 {E,V1}[] → K2 {E}[V-succ, D2 fail_b (condition {E,V1})]
S3:   K2 {E}[V-succ, fail_b refs=2]   (двойной (b) слит, без дубля)
S4:   K1 {E,V1}[] → K2 {E,V1}[] (IF-1, повтор до дивергенции) →
      K3 {E}[V-succ, fail_b]
S6b:  K2 {E}[V-succ, fail_a (V 1→2, source=verified failure)]
P1:   K3 {E}[V-succ, fail_a, fail_b]   (evidence через 2 цикла)
P2:   K4 gen4 {E}[V-succ refs=3, fail_b refs=2, fail_a refs=1]
      (evidence через 3 цикла; сигнатуры монотонны; дублей нет)
```

G6-L6-walk OK на всех 18 v06x-прогонах: source из enum; episode_refs
непустые и согласованы с outcome (failure-записи → failure-опыты,
success-записи → success-опыты); lineage_generation ∈ {1..n} по
цепочке; aw не содержит failure-derived.

## 4. Критерии (реальный код)

- **G1 PASS** — ACQ-1-регрессия: K1 {E:absent,V:1} gen1, K2
  {E:absent} + V[1,2] source="verified success" gen2.
- **G2 PASS** — AB-1-сценарии: reopened-локалитетов 0 на S1–S5;
  aw чист (latest / после первого V-наблюдения); K1-норма сохранена.
- **G3 PASS** — S6b: V-записи с ОБОИМИ источниками при aw={E:absent};
  S1: D2-запись + V-succ; запрещённого состояния (aw чист при
  failure-only V-evidence) нет ни на одном прогоне.
- **G4 PASS** — P1/P2: evidence_signature монотонна; episode_refs
  растут; поколения ровно 1,2,3,(4); повторный (b) не дублируется
  (слияние refs); failure не создаёт поколение.
- **G5 PASS** — поведенческая эквивалентность: команды и strategy_id
  проб идентичны v06-baseline на всех 9 сценариях × 4 мира × 2
  реплики (S2 fix-a всюду). Структурные критерии при этом выполнены
  независимо от legacy-спасения поведения.
- **G6 PASS** — audit 4/4; L6-механический walk OK; legacy-чтение
  (v06-записи без source/generation) без изменений, backfill
  отсутствует.

Контраст v06-baseline (информационно): S1/S6b/P1/P2 — K2 {E:absent,
V:2} reopened (дефект AB-1); P2 — K2..K4 {E,V2} reopened (дефект
самоподдерживается); поведение при этом идентично v0.6.x (G5).
Различие behavioral-absent / structural-strong воспроизведено на
реальном коде.

## 5. Вердикт

**GATE v0.6.x: PASS.** Реализация воспроизводит доказанную семантику
F1 (L1–L6) на реальном коде: failure остаётся членом lineage и
передаёт evidence (recorder (a)/(b), source-схема), pivot — последнее
field-bearing verified-success знание, aw никогда не принимает
failure-derived наблюдения, evidence персистентно через поколения,
поколения и provenance механически восстановимы (L6).

v0.6 остаётся baseline (update_v06_baseline.py, knowledge_v06_
baseline.py — исполняемый откат). Статус v0.6.x (присвоение имени,
дальнейшие шаги) — слово профессора.

## 6. Статус и фиксация версии (слово профессора, 07.09.2026)

**Tsarapina v0.6.x: INTEGRATION GATE PASS.**

- **v0.6** остаётся исполняемым frozen baseline (update_v06_baseline.
  py, knowledge_v06_baseline.py — откат восстановлением, без
  миграций).
- **v0.6.x** = рабочие слои (update.py, knowledge.py schema 0.3):
  узкий релиз с именем **applicability lineage persistence, F1
  semantics, structural provenance**. Это НЕ v0.7 и не новая
  архитектура: завершение исследовательского долга
  AB-1 → LP-1 → LP-2 → LP-3 → integration L1–L6 → real-code gate
  G1–G6 → v0.6.x PASS.
- **IF-1 принят**: S4-K2 (повтор honest-вектора до первой
  дивергенции) — нормальная история приобретения, не дефект; V ∈ aw
  до первого disagreement, V ∈ observations после — уточнение
  анализатора оставлено в силе.
- **IF-2 принят**: schema-tag косметика baseline-режима, не
  исследовательская проблема.
- **Ключевой результат интеграции**: G5 PASS при сильном структурном
  различии — экспериментально подтверждённый пример того, что
  поведение системы НЕДОСТАТОЧНО для проверки корректности внутренней
  структуры знания (F0-дефект воспроизводится на production path при
  поведенческой эквивалентности). Структурные инварианты (L6-walk) —
  необходимый слой проверки. Оформлено отдельным документом:
  RESEARCH_FINDING_APPLICABILITY_LINEAGE.md.
- Открытые долги лаборатории — RESEARCH_DEBT.md (реестр).

Цепочка закрытия долга:

```text
AB-1  →  дефект latest-record lineage (boundary)
LP-1  →  F1/F2 различены (12/12 эквивалентны в пустом failure)
LP-2  →  provenance становится самостоятельной осью (дискриминатор)
LP-3  →  F0: self-reinforcing failure | F1: persistence PASS
      →  F1 frozen
integration design L1–L6 → real-code gate G1–G6 → v0.6.x PASS
```

## 7. Артефакты

APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md (FROZEN),
INTEGRATION_GATE_V06X_DESIGN.md (FROZEN), update/update.py (v0.6.x),
update/update_v06_baseline.py, knowledge/knowledge.py (0.3),
knowledge/knowledge_v06_baseline.py, experiments/gate_v06x.py,
experiments/gate_v06x_analyze.py, GATE_V06X_records_{v06x,v06}.json
(RAW), GATE_V06X_audit_{v06x,v06}.txt, GATE_V06X_ANALYSIS.txt,
INTEGRATION_V06X_REPORT.md (этот файл).
