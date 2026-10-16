# STRATEGY → LLM → ACTION: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Решения профессора по всем восьми точкам §5
внесены (11.09). Первый эксперимент, где Gemma становится участником
настоящего контура; граница её полномочий зафиксирована ДО чисел
(арифметика — из конкретных proposal-cells, после PROTOCOL).

**Принцип (FREEZE):**

> **LLM is a proposal generator. The right to execute belongs to the
> architecture, not to the model's ability to produce valid JSON.**

## 1. Вопрос

> **Можно ли подключить LLM как генератор action proposals,
> сохранив архитектурное право системы решать, что действительно
> может быть выполнено?**

Это не вопрос «можно ли доверять Gemma» — это вопрос канала
`proposal → permission → action`.

## 2. Контекст фактов (проверено по коду)

```
F1  strategy.py: S5 = «запросить план у процессора (LLM)»;
    suggestion несёт флаг llm_request (strategy.py:463).
F2  llm/adapter.py: узкий контракт; JSON; провайдеры
    gemma3:4b/qwen3:4b/qwen2.5:3b; ошибки → ok=False; адаптер не
    импортирует knowledge/experience/storage/executor.
F3  executor.py: ворота допуска уже жёсткие — permitted +
    allowlist команд + запрет метасимволов (executor.py:79-87,121).
F4  strategy.py НЕ импортирует llm (тест T7; сохраняется — см. §5.1).
F5  A1/exclusion (v0.6.x+A1) управляет кандидатами-знаниями;
    стык «proposal ↔ A1» — mechanical guard, не reasoning layer.
```

## 3. Контракт (FROZEN; минимальный)

```
LLMRequest
    ├── context
    ├── allowed_action_space
    └── request metadata

LLMProposal
    ├── ok            (bool)
    ├── action        (command | null)
    └── arguments
```

**НЕ включать в обязательный контракт:** confidence, trust,
reasoning, ranking, self-evaluation. Исследуем канал, а не
«внутреннюю психологию» модели.

**Инварианты:**

```
I1  LLM никогда не вызывает executor и не пишет в store
    (адаптер соответствует; мост — тоже).
I2  Ни одно действие не исполняется в обход executor-ворот;
    LLM-путь не создаёт альтернативного пути исполнения.
I3  Proposal ≠ permission: это разные записи; отказ фиксируется
    (append-only) и не роняет систему.
I4  S5 — единственная точка входа LLM-предложений; при S2 знание
    выбирается штатно, модель не подменяет знание.
I5  FAIL CLOSED: LLM unavailable / timeout / invalid JSON /
    schema violation / adapter error / empty proposal /
    unsupported action → NO ACTION.
    LLM failure must degrade to non-execution, never to implicit
    fallback execution.
I6  LLM failure ≠ Explore: неуспех модели не превращается в
    S3 → Explore. Explore — право из candidate absence (EP-2C),
    не из сбоя LLM.
I7  An LLM proposal must not bypass A1 candidate addressing or
    exclusion eligibility; excluded knowledge не восстанавливает
    eligibility через proposal (mechanical guard; способ
    установления связи определяет PROTOCOL — без допущений вида
    «LLM использовал K1», если адаптер этого не предоставляет).
I8  Audit/append-only: proposal и permission — раздельные записи;
    origin предложения восстановим.
```

## 4. Что НЕ входит

```
N1  Свободный режим Gemma; мульти-модельные сравнения.
N2  ОБУЧЕНИЕ / FINE-TUNING Gemma (заменяемый генератор предложений).
N3  Trust/confidence-исследования; оценка «качества Gemma».
N4  Изменение permission-алгебры A1 (только mechanical guard).
N5  Долгие прогоны; правки executor-ворот/knowledge/update/
    evaluation; изменение T7 (сохраняется).
```

## 5. Решения по восьми точкам (FROZEN, 11.09)

```
1. Bridge location: A — отдельный orchestrator между Strategy и
   LLM/Action; strategy.py НЕ импортирует llm; T7 сохраняется.
2. Gemma role: proposal generator only. Модель возвращает
   proposal — даже идеально оформленный JSON не является
   разрешением.
3. A1: mechanical eligibility/exclusion guard
   («An LLM proposal must not bypass A1 candidate addressing or
   exclusion eligibility»); A1 НЕ становится reasoning layer для
   LLM; семантику связи proposal↔excluded определяет эксперимент.
4. Proposal contract: минимальный (LLMRequest/LLMProposal §3);
   без confidence/trust/reasoning/ranking/self-evaluation.
5. LLM failure: fail closed → NO ACTION; без implicit fallback;
   и НЕ → Explore.
6. Первый эксперимент: маленький. Одна короткая цепочка
   (Strategy → llm_request → Gemma → proposal → permission →
   Executor → Result) + обязательные негативные случаи: invalid
   proposal; unknown action; LLM error; excluded candidate;
   not-permitted action; + положительный: valid → permitted →
   executor → result.
7. Обучение/fine-tuning: НЕТ (заменяемый генератор).
8. Scope: без trust/confidence; числа — только после PROTOCOL.
```

## 6. Следующее

```
FROZEN (этот файл) → PROTOCOL (точные proposal-cells, среды,
механическое определение связи «proposal ↔ excluded», критерии
по каждому негативному кейсу; арифметика чисел — из клеток) →
FREEZE PROTOCOL → минимальный контракт-прогон →
STRATEGY_LLM_ACTION_REPORT.md → решение о фазе «живого цикла»
(результаты действий → Experience → Knowledge → Strategy →
следующий запрос к Gemma — отдельный шаг, не этот).
```

## 7. Артефакты

STRATEGY_LLM_ACTION_DESIGN.md (этот файл, FROZEN), PROTOCOL
(после), orchestrator/мост (после FREEZE PROTOCOL), отчёт.
Слои v0.6.x+A1 не изменяются до FREEZE PROTOCOL. D-6/D-2/D-3/D-4 —
вне этого шага.
