# INTEGRATION — STRATEGY v0.3: ОТЧЁТ (06.09.2026)

**Strategy v0.3: contextual exploitation + insufficiency routing.**
SEB-1 M2 интегрирован в ОСНОВНУЮ Strategy (strategy/strategy.py).
Интегрирована именно маршрутизация; Knowledge/Update/Evaluation/
Executor/R1/conflict-S3 не изменены; trust и generalization не
появились.

## 1. Что изменилось в strategy.py (минимально)

1. **Insufficiency routing (M2/SEB-1)** в выборе S2:
   - задача несёт симптом И exact-знание о нём ЕСТЬ → S2-эксплуатация
     (recency в exact-пуле) — как v0.2+R1;
   - задача несёт симптом, exact-знания НЕТ → broad-знание НЕ
     эксплуатируется: ОДНА гипотеза (свежайшее non-failure broad-
     знание, флаг hypothesis=True, rationale rule=broad_hypothesis);
     при не-success гипотезы в эпизоде (banned_commands непуст при
     повторном suggest) → exploration=True (S1 + rationale
     insufficiency_exploration: контур выполняет систематический
     перебор; право искать, НЕ право знать, что искать);
   - конфликт релевантных знаний → S3 (приоритет сохранён);
   - задачи без симптома — broad-fallback как v0.2 (не менялся).
2. **Multi-action извлечение (fix скрытого дефекта v0.2):** кандидат
   знания = ПОСЛЕДНЕЕ действие опыта (то, чей исход зафиксирован
   update'ом), вместо всех действий опыта. Для одно-действенных
   опытов (все прежние сценарии) поведение идентично; для
   exploration-опытов (multi-action) кандидат корректен (не первое
   действие). Задокументирован как часть v0.3 (см. SEB-1, дефект 2).
3. Новые поля suggestion: hypothesis, exploration, strategy_version
   "0.3". Сигнатура suggest(..., banned_commands=None).

## 2. Integration gate (10 пунктов профессора) — ПРОЙДЕН 10/10

Прогон: experiments/gate_v03.py; лог GATE_V03_run.log (run2).
Юнит-регрессия 9/9 зелёная (strategy/observer/experience/knowledge/
llm_adapter/executor/evaluation/update/aggregation).

```
G1  регрессия 9/9                                PASS
G2  return-A 3/3 (S2 fix-a, 1 действие)          PASS
G3  AB 3/3 (S2 fix-ab)                           PASS
G4/5 UA → S3 (stale не «молча решён»; conflict)  PASS
G6  C1: гипотеза fix-ab (partial) → exploration  PASS
    → перебор → fix-c success (7 действий)
G7  C2–C7: S2 fix-c (1 действие)                 PASS
G8  swap (S2 fix-c после знания)                 PASS
G9  determinism: повтор C1 на свежем сторе —     PASS
    та же траектория (гипотеза → exploration →
    fix-c); повтор C2 → S2 fix-c
G10 multi-action regression: знание из опыта с   PASS
    3 действиями → кандидат fix-c (последнее),
    не fix-ab (первое)
```

## 3. Техническая заметка (learn-процедура)

Первый прогон gate (run1) дал G2 FAIL (fix-b вместо fix-a) — дефект
learn-процедуры ДРАЙВЕРА: problem-строка опыта строилась после
лечения → «symptom=none» → exact-пул пуст. Исправлено единообразно
с RELEVANCE-1/SEB-1: симптом фиксируется ДО лечения (сразу после
env_set). run2 — валидный. (В SEB-1 драйвер уже содержал фикс;
прогон SEB-1 остаётся валидным.) Паттерн зафиксирован как
требование к learn-процедурам экспериментов.

## 4. Формулировка (профессор)

> **Strategy v0.3: contextual exploitation + insufficiency routing.**
> Эксплуатация — при наличии точного (symptom-exact) знания;
> структурная недостаточность (симптом есть, exact-знания нет)
> маршрутизируется: одна broad-гипотеза → при не-success
> систематический поиск; знание нового класса — только из
> проверенного последствия (не из гипотезы, не переносом).

Границы сохранены: (а) exact-устаревание (знание есть, мир
изменился) — не маршрутизируется v0.3 (зона 3: новые последствия);
(б) перенос A/B→C отсутствует (зона 4); (в) trust-числа нет.

## Артефакты

strategy/strategy.py (v0.3, стратегия_версия в suggestion),
experiments/gate_v03.py, GATE_V03_run.log/.txt (run2 валидный;
run1 — INVALID learn-процедура, сохранён), INTEGRATION_V03_REPORT.md
(этот файл). Шапка-комментарий strategy.py обновлён.
