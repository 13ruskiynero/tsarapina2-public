# REPRESENTATION PAUSE: архитектурная заметка (11.09.2026)

**Статус: зафиксировано.** Пауза между RESOURCE-RESPONSE-1
(CLOSED) и дизайном R2. Это НЕ эксперимент и НЕ дизайн; это
граница терминов, которую R2 не имеет права размыть.

Принят профессором как каноническая пауза (вердикт 11.09). Правило
после закрытия цикла: «Иногда лучшая научная операция — не
запускать ещё один прогон просто потому, что сервер всё ещё
включён.» R2 начинается **только с дизайн-документа** (иначе
пауза превращается в задним числом придуманный эксперимент).

## 1. Distinction (фиксируется до R2)

```
KNOWLEDGE
  ≠ KNOWLEDGE REPRESENTATION
  ≠ PROMPT SERIALIZATION
  ≠ MODEL COMPLETION

KNOWLEDGE — содержимое и идентичность знания (kid/lineage,
  applicable_when, applicability_observations, experience_refs,
  outcome). В R2 НЕ МЕНЯЕТСЯ — концептуально, не только по hash.
KNOWLEDGE REPRESENTATION — форма записи самого знания (как
  знание записано/структурировано само по себе).
PROMPT SERIALIZATION — как знание укладывается в запрос к LLM
  (строки контекста, порядок, формулировки).
MODEL COMPLETION — генерация; её бюджет зависит от
  serialization; восстановление способности действовать
  проявляется здесь.

R2 может менять (2) и/или (3). Не может — (1) и контракт.
```

## 2. Рамка R2 (кандидат в RQ; НЕ заморожена)

> **Может ли внешне сохранённое знание менять форму
> представления без изменения самого знания и тем самым
> восстанавливать способность системы действовать?**

Жёсткий внешний критерий: ресурсная граница B5
(P + B_required > N_ctx). Не «уменьшить prompt»; не context
compression benchmark.

Исследовательский вопрос линии ScratchAI: representation как
проверяемый механизм восстановления действия при неизменном
знании (продолжение линии FR-0, теперь с жёстким критерием).

## 3. Запреты (до дизайна R2)

```
* K_before == K_after концептуально (идентичность знания, не
  только хэш);
* никакого subsetting / отбрасывания / выбора знаний (это
  relevance-политика — вне scope);
* не менять контракт proposal; не менять num_ctx; не менять
  модель/провайдера;
* R4 self-compression — FROZEN (комбайн гипотез; не открывать).
```

## 4. Доска (после RR-1)

```
BOUNDARY  B5 output starvation        → REPLICATED
OUTPUT-BUDGET MAP-1                   → PASS / CLOSED
RESOURCE-RESPONSE-1                   → PASS / CLOSED
  R0 → baseline (absorbing equilibrium)
  R1 → no observable trajectory advantage
  I1 (resource ≠ knowledge)           → survived
  MARGINAL → resource-contingent (1 valid / 4 при 129)
B2b prompt truncation                 → NOT OBSERVED
NEXT: R2 RESOURCE-AWARE REPRESENTATION (DRAFT — по слову)
R4 self-compression                   → FROZEN
```

## 5. Артефакты

```
REPRESENTATION_PAUSE.md (этот файл); RESOURCE_RESPONSE1_REPORT.md
(CLOSED); RESEARCH_DEBT.md (доска). Слои/store не трогаются.
```
