# TSARAPINA AGGREGATION-1: ОТЧЁТ (зона 2, 06.09.2026)

Протокол: AGGREGATION1_DESIGN.md (frozen). Механика: evidence
aggregation (уровень B): сигнатура группы (симптом, первая команда
действия, исход) — детерминированно из знания (context), его опыта
и action-записи; агрегат K_agg {experience_refs: все, evidence_count};
исходные knowledge superseded (retract — история цела); конфликты
переносятся на агрегаты (declare_conflict); детерминированный id
(sha1) — идемпотентность. R1 Strategy заморожена — ОДНА для baseline
и aggregation.

## Локальный тест механики (23/23 PASS)

G1 exact dup ×6: 6→1 активного; refs 6/6; decision fix-a;
идемпотентность; версии целы (≥13). G2: 3→1, refs 3/3. G3: same
symptom/diff actions — агрегации нет, активных 2 (вариативность
сохранена). G4: D-набор (2×s + 2×f + declare) → 2 агрегата +
конфликт перенесён + S3-защита сохранена. G5: сложный конфликт
(разные actions) — группы по 1, оба активны. G6: mixed — created
≥3, идемпотентность. G7: Experience/Result не изменены; агрегатор
не импортирует llm/update/strategy/executor.

Пойманный артефакт теста: read_knowledge_versions_all возвращает
ВСЕ версии (исторические v1 остаются active) — счёт активных обязан
идти по ПОСЛЕДНИМ версиям (агрегатор считал правильно; тест
исправлен).

## Сетка A–F (baseline vs aggregation через R1 Strategy)

```
набор  содержимое                     M1(до→после)  M2    M3   M4        M5
A      6× same success (fix-a)        6 → 1         1.00  ДА   —         ДА
B      3× same action, diff episodes  3 → 1         1.00  ДА   —         ДА
C      same symptom, diff actions     2 → 2 (нет    1.00  ДА   вар-сть   ДА
                                       повторов)           сохр.
D      success+failure same action    4 → 2         1.00  ДА   S3 сохр.  ДА
E      success/failure diff actions   4 → 2         1.00  ДА   S3 сохр.  ДА
F      mixed A+B+C+D                  9 → 4         1.00  ДА   —         ДА
```

M1: компрессия есть там, где повтор; C не сжимается (повторов нет —
правильно). M2: provenance coverage 1.00 во всех наборах (все
исходные Experience достижимы из агрегатов). M3: decision
equivalence — стратегия и команда совпадают во всех наборах
(включая D/E: S3→S3; F: fix-a→fix-a). M4: конфликты различимы,
S3-защита сохранена (D/E: conflicts_transferred=1). M5:
идемпотентность во всех наборах. M6 (swap): решения S2 не
используют LLM; агрегатор без LLM; swap-свойство контура проверено
в RELEVANCE-1/LONGITUDINAL-1 — агрегат ведёт себя как обычное
знание для R1.

Регрессия 9/9 слоёв ПРОЙДЕНА (observer/experience/knowledge/
strategy/llm_adapter/executor/evaluation/update/aggregation).

## Вердикт

**AGGREGATION-1: PASS** по критериям дизайна (все 7 условий):
(1) активное знание компактнее там, где повтор; (2) provenance
coverage = 100%; (3) конфликты различимы; (4) Strategy сохраняет
ожидаемые решения; (5) детерминизм/идемпотентность; (6) swap
сохраняется; (7) старые Experience/Result/Raw не изменены и не
удалены.

**Проверяемое утверждение зоны 2 (в рамках синтетической сетки):
избыточное операциональное знание можно представить компактнее без
потери свидетельственной структуры и поведения.** Semantic
correctness — UNKNOWN (по дизайну: decision equivalence ≠ semantic
correctness; обобщение не заявляется).

**Статус:** зона 2 закрыта положительно в рамках полигона.
Механика aggregation НЕ включена в контур (вызывается явно;
интеграция/порядок вызова в потоке Update — по слову профессора).
Следующие зоны Layer C: 3. Trust/conflict resolution; 4.
Generalization.

## Артефакты

aggregation/aggregation.py; tests/test_aggregation.py;
experiments/AGGREGATION1_DESIGN.md; experiments/aggregation1/
aggregation1_grid.py, AGGREGATION1_grid.log,
AGGREGATION1_grid_report.json.
