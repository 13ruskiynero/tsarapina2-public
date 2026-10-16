# RESOURCE-RESPONSE-1: ОТЧЁТ (11.09.2026)

**Статус: PASS → CLOSED (вердикт профессора, 11.09).**

Ключевой отрицательный результат (каноническая формулировка):

> **Explicit HALT does not produce an observable trajectory
> difference from natural NO-ACTION under the tested read-only
> conditions.**

## 1. Матрица (12 runs; read-only реплей)

```
NORMAL (P=3907, B_available=189):
  R0: valid=True (C=155/137);  R1: valid=True (C=155/171);
  D1/D2=False во всех — детектор молчит (D3 ✓); event=none.
MARGINAL (P=3967, B_available=129):
  R0: invalid ×2 (C=129 = упор в окно) → starvation_no_action;
  R1: invalid ×1 (129) + valid ×1 (129!) → resource_impossible
      / none.
STARVED (P=3983, B_available=113):
  все 4: invalid (C=113, упор); R0 → starvation_no_action
  (halted=False); R1 → resource_impossible (halted=True).
```

## 2. Detection (D1/D2/D3) — ПОДТВЕРЖДЕНА

```
D1 (B5-факт): там, где окно исчерпано и proposal invalid —
  True; в NORMAL — False.
D2 (детектор): D2 == D1 во всех клетках (MISS-контроль ✓).
D3 (молчание): NORMAL → детектор молчит во всех 4 клетках ✓.
Чувствительность и отсутствие ложных срабатываний — механически
подтверждены.
```

## 3. Инварианты (I1–I7; C1–C7) — ЧИСТО

```
S1: knowledge не менялось (K_hash before == after) — 12/12;
S2: implicit fallback отсутствует (action=0) — 12/12;
context_hash / source_sha: неизменны — 12/12;
executor_invocations=0; retry=False — 12/12;
«ресурсная проблема не превратилась в проблему знания».
```

## 4. R0 vs R1: ключевое наблюдение

```
На STARVED и MARGINAL (invalid-реплики) proposal-исход ОДИНАКОВ
(контракт не закрывается); политики различимы ТОЛЬКО на уровне
декларации: event (starvation_no_action vs resource_impossible)
и halted (False vs True).
На NORMAL обе политики не реагируют (event=none).
Итог: явная HALT-политика не проявляет ПОВЕДЕНЧЕСКОГО отличия от
естественного NO-ACTION на наблюдаемом уровне; отличие — в
фиксации намерения (event/halted), не в траектории.
Это ровно тот отрицательный результат, который допускался
заранее; расширение автоматически не делается.
```

## 5. Стохастика границы (наблюдение)

```
MARGINAL дал 1 валидное завершение из 4 при C=129 (R1-r2):
контракт может уложиться в 129 токенов при том же промпте.
NORMAL: completion варьируется 137..171 (содержательная
вариативность; temp=0 не гарантирует побитовый детерминизм
содержимого).
STARVED: строго 113/113 — упор в окно детерминирован.
Вывод: граница — ЗОНА, не точка; «минимально необходимое»
варьируется от прогона к прогону; на STARVED дефицит
арифметический (113 < 129..136), на MARGINAL — исходный.

Три режима (фиксируется вместо одного threshold; вердикт 11.09):

```
B <  B_min   → impossible            (STARVED: 113)
B ≈  B_min   → resource-contingent   (MARGINAL: 129;
                                     1 valid из 4)
B >> B_min   → sufficient            (NORMAL: 189; 137..171)
```

B_min НЕ объявляется константой: наблюдаем контрактную границу,
а не физическую константу.
```

## 6. Что установлено / что нет

```
Установлено:
  * ресурсную невозможность можно детектировать механически
    (D1/D2/D3), без смешения с состоянием знания;
  * инварианты I1–I7 исполнимы в реплее (K/context/source
    неизменны; нет action/executor/retry);
  * R0 и R1 корректно различимы на уровне события/останова.
Не установлено (не входило):
  * какая реакция «лучше» (R2/R4 не тестировались);
  * поведенческое различие R0/R1 — его нет в наблюдаемом слое;
  * влияние любой из политик на долгосрочную траекторию
    (реплей одномоментный).
```

## 7. Артефакты

```
resource_response1/PROTOCOL.md (FROZEN), rr1_driver.py,
rr1_analyze.py, RR1_*.json (12), RR1_ANALYSIS.txt, этот отчёт.
Слои/store/записи recon1 и long3 не изменялись (read-only;
source_sha неизменны во всех 12).
```
