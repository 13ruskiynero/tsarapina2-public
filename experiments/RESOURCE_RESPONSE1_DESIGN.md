# RESOURCE-RESPONSE-1: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора: архитектурная идея PASS;
внесены 4 поправки до FREEZE (MARGINAL операционально; R0/R1
формально разведены; detection D1/D2/D3; read-only hashes);
после них — FREEZE → PROTOCOL → preflight → 12 runs. База:
B5 REPLICATED, MAP-1 PASS→CLOSED (B_required ≈136; граница
(120,140)), RESOURCE STATE R0.

## 1. Research question (FROZEN)

> **Что является корректной реакцией агента на обнаруженное
> ресурсное ограничение, если выполнение обычного действия
> становится невозможно?**

Причина B5 уже охарактеризована (113 < 136) — этот эксперимент
НЕ исследует причину. Он устанавливает более простое:
**можно ли вообще различить разные ресурсные реакции, не смешивая
ресурсное состояние с изменением знания?**

## 2. Принцип честности (anti-thermometer)

```
R2/R4 НЕ реализуются как «давайте уменьшим prompt» — это внесло
бы гипотезу вместе с проверкой. Первый прогон: только
DETECTION + R0/R1 + инварианты. R2/R3/R4 — спецификации,
отдельные ветки по слову.
```

## 3. Терминология (поправка 1: операционально)

```
Ресурсные состояния (свойство промпта; B_available = 4096 − P):
  NORMAL:   B_available > 140
  MARGINAL: 120 < B_available < 140
  STARVED:  B_available <= 120

MARGINAL = resource state overlapping the empirically observed
contract-completion boundary. НЕ «probabilistic zone»: мы не
исследовали вероятность; мы специально помещаемся в область
неопределённости границы.

Выбор MARGINAL-контекста (PROTOCOL): существующая replay-запись
с B_available в (120,140), ближайшая к mid-point 130; точный
эпизод заморожен ДО прогона; если подходящей записи нет —
НЕ создавать её задним числом.

Detection — механический факт (см. §6 D1); не «мнение модели».
Response policy — правило поведения контура ПОСЛЕ detection.
```

## 4. Response-policy classes (поправка 2: R0/R1 формально)

```
R0 NO-ACTION (baseline):
  detect B5 → proposal invalid → NO ACTION → normal loop remains
  available (loop_available=True; halted=False).
  Запись события: starvation_no_action.

R1 HALT / RESOURCE-IMPOSSIBLE:
  detect B5 → RESOURCE-IMPOSSIBLE → HALT →
  no proposal retry → no executor → no Knowledge mutation →
  no automatic recovery (halted=True).
  Запись события: resource_impossible.
  R1 НЕ меняет Knowledge: иначе «у нас кончился бюджет» станет
  «память считает знание плохим» — прямо против I1.

R2 RESOURCE-AWARE REPRESENTATION (только спецификация):
  изменение ТОЛЬКО формы представления запроса при том же
  множестве знаний и тех же фактах; запрещено менять/выбирать/
  отбрасывать знания и менять контракт. Отдельная ветка.

R3 DEFER (только спецификация): без механизма отложенности
  вырождается в R0; не запускается.

R4 SELF-COMPRESSION (только спецификация): пересекает
  relevance-политику; отдельный дизайн и anti-cheat; не в
  прогоне 1.
```

## 5. Инварианты

```
I1  Ресурсное состояние ≠ состояние знания: detection не
    мутирует knowledge и не переклассифицирует его.
I2  proposal ≠ permission ≠ action.
I3  detection — механический (D1 §6), не интерпретация.
I4  Recovery не создаёт verified consequence сам по себе.
I5  Никакого implicit fallback: нет действия → нет действия.
I6  Append-only события ресурса.
I7  R2/R4 не меняют контракт и не отбрасывают знание.
```

## 6. Наблюдаемые (поправка 3: D1/D2/D3)

```
D1  B5 действительно присутствует (механический факт):
    window exhausted (P + completion >= 4096) AND proposal invalid.
D2  агент/драйвер обнаружил (детектор сработал по правилу D1).
D3  detection не возник без B5: NORMAL → детектор молчит.
«Detection must be both sensitive to the defined B5 condition
and absent in NORMAL». Статистика чувствительности не требуется.

1. detect (D1/D2/D3);
2. knowledge preserved: K_after = K_before (hash набора
   транспортированных knowledge (kid,version));
3. no unsanctioned knowledge modification (FORBIDDEN; не
   «ожидается 0»);
4. action: 0/1; ворота;
5. new context: сериализованный контекст не меняется
   (context_hash);
6. exit: без внешнего ресурса выхода нет (фиксируется);
7. fake-learning check: Δknowledge=0; нет новых verified
   consequences.
```

## 7. Матрица первого прогона (FROZEN)

```
{policies: R0, R1} × {states: NORMAL, MARGINAL, STARVED} ×
{r1, r2} = 12 runs.
Read-only реплей существующих записей; store/executor не
мутируются; точные контексты — в PROTOCOL.
НЕ расширять автоматически, если R0 ≡ R1: «явная политика HALT
не проявляет отличий от естественного NO-ACTION на наблюдаемом
уровне» — валидный отрицательный результат.
```

## 8. Отрицательные контроли (поправка 4: hashes)

```
C1  запрещено «успешное» закрытие контракта ценой изменения
    знания/контракта;
C2  запрещено отбрасывание/выбор знаний (relevance — вне scope);
C3  recovery не порождает новое знание/не меняет kid;
C4  fake-learning: knowledge_count и lineage неизменны, пока не
    исполнено реальное валидное действие по обычному пути;
C5  detection не зависит от содержимого знаний;
C6  ЗАПРЕЩЕНЫ в этом эксперименте: retry; prompt reduction;
    summarization; context pruning; изменение num_ctx;
    изменение max_tokens; альтернативный LLM; fallback-модель;
    automatic compression; новая Knowledge policy (это ответы
    на B5, не диагностика);
C7  read-only hashes: source-record sha до/после; context_hash
    до/после; transported-knowledge set hash до/после;
    executor_invocations = 0; Knowledge mutation = FORBIDDEN
    (проверка механическая: K_after = K_before).
```

## 9. Stop conditions

```
S1  изменение knowledge при detection/recovery → стоп, FAIL;
S2  implicit fallback (действие при невалидном proposal) →
    стоп, FAIL;
S3  R0 ≡ R1 → фиксируется; расширение не автоматическое;
S4  любое «улучшение» по ходу → стоп (как в RECON-1).
```

## 10. Вердикты OT (закрыты 11.09)

```
OT-1 🟡→ внесено: MARGINAL операционально (§3).
OT-2 🟢 PASS: матрица 12.
OT-3 🟢 PASS + hashes внесены (§8 C7).
OT-4 🟡→ внесено: D1/D2/D3 (§6).
OT-5 🟡→ внесено: R0/R1 формально разведены (§4).
OT-6 🟢 PASS: R2/R4 вне прогона.
OT-7 🟢 PASS: контроли/стоп + C6/C7.
```

## 11. Процедура

```
FROZEN (этот файл) → PROTOCOL (resource_response1/) → драйвер
(read-only реплей; без мутаций store) → preflight → 12 runs →
RR1_ANALYSIS.txt → RESOURCE_RESPONSE1_REPORT.md →
решение о R2/R4-ветках — отдельным словом.
```

## 12. Артефакты

```
RESOURCE_RESPONSE1_DESIGN.md (FROZEN), resource_response1/
PROTOCOL.md, драйвер RR1, 12 записей, RR1_ANALYSIS.txt,
RESOURCE_RESPONSE1_REPORT.md. Слои/store/long3-r1-r2 записи не
трогаются (read-only).
```
