# TSARAPINA TEMP-F: VALIDATION (failure branch of TEMP) — 10.09.2026

**Статус: COMPLETED (10.09.2026; 4/4 клетки OK, все проверки
выдержаны).** Targeted validation существующей TEMP-семантики
(EP-2B, CLOSED): failure-ветка verification slot'а наблюдена
буквально. Прогон: TempF|TEMP|{R,S}|{r1,r2} = 4 (RAW:
TEMPF_cell_*.json; чек: TEMPF_CHECK.txt). Слои v0.6.x не изменялись.

## Вопрос

> Что происходит, когда система получила право проверить исключённый
> K (sign-of-life → slot), но проверка снова показала, что K плох?

## Конструкция (TempF; минимальная)

```
learn:  w1@V1 (K1), w1@V2 (K2)   — конфликт успехов (как E6)
phase:  1) f@V1(n) w1  → триггер C5; exclusion(K2)
        2) s@V1    w1  → K1 применён → success → SOL; slot(K2)
        3) attempt(K2) w2 → fix-a мёртв → FAILURE
        4) f@V1    w2  → обычный цикл продолжается (sibling K3)
```

Мир: w1 живой на шагах 1–2 (sign-of-life достижим), на шаге 3
деградировал до w2 (проверка проваливается). Смена мира — тот же
полигонный канал (lock.q), новых механизмов нет.

## Проверки (буквально)

1. attempt: ровно один; result=failure; события eligible НЕТ;
2. K остаётся excluded: K ∉ refs любых последующих применений;
3. самопроизвольный новый slot не возникает: sol=1, slot=1,
   attempt=1;
4. нет повторного применения K; следующий цикл — обычное
   применение (S2), не attempt;
5. append-only: K-запись не мутирована (стор, audit, provenance
   exclusion→sol→slot→attempt сохранена);
6. sibling'ы не получают побочного exclusion (K1/K3 активны,
   K3 выбирается на шаге 4);
7. next cycle не превращается в бесконечный recheck.

## Клетки

```
TempF|TEMP|R|r1, TempF|TEMP|R|r2, TempF|TEMP|S|r1, TempF|TEMP|S|r2
(4 прогона; HALT/POOL не требуются — ветка существует только у TEMP)
```

## Результат (4/4 OK)

```
exclusion(шаг1) → sol(шаг2) → slot(шаг2) → attempt(шаг3, partial/FAIL)
→ K remains excluded; шаг4 — обычный S2 (sibling K3)
```

Проверки §«Проверки (буквально)» — все True на всех 4 клетках:
attempt ровно один и non-success (в полигоне «failure» = non-success/
partial: fix-a мёртв в w2); события eligible НЕТ; K не применяется
повторно (шаг 4 применил sibling K3); sol=1, slot=1, attempt=1
(новый slot самопроизвольно не возникает); шаг 4 — S2, не attempt
(нет бесконечного recheck); causal chain slot.trigger_ref ==
exclusion сохранена; K-запись присутствует в финальном снапшоте
(append-only: exclusion не мутирует запись — состояние «excluded» —
свойство контура); sibling'ы K1/K3 активны, побочного exclusion
нет; audit=True. R ≡ S.

**Вывод.** Failure-ветка TEMP подтверждена эмпирически (не только
protocol semantics): неудачная проверка оставляет K исключённым,
слот потреблён, автоматических повторов нет. TEMP полностью
измерена в обеих ветках (success EP-2B / failure TEMP-F).

## Артефакты

TEMP_FAILURE_VALIDATION.md (этот файл), tempf_runner.py,
tempf_check.py, TEMPF_cell_*.json (RAW ×4), TEMPF_CHECK.txt.
Слои v0.6.x не изменяются; эпистемический статус: validation
existing semantics (EP-2B), не новое исследование.
