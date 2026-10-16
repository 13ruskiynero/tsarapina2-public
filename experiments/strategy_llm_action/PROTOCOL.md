# STRATEGY → LLM → ACTION: PROTOCOL (FROZEN 11.09.2026)

База: STRATEGY_LLM_ACTION_DESIGN.md (FROZEN 11.09; граница
полномочий LLM; fail closed; LLM failure ≠ Explore; A1 — mechanical
guard). Решение профессора: точка входа — **external trigger**
(вариант A); strategy.py не трогается; EF-12 («когда Strategy сама
инициирует LLM request») остаётся OPEN-долгом. Провайдер:
**только gemma3:4b** (ollama active; qwen — отдельная ветка).

Долговая классификация (профессор, 11.09): Blocker — LLM Bridge
(этот эксперимент); Integration debt — EF-11/D-6, EF-12;
Research debt — D-2/D-3/D-4/D-6/EF-12 (не закрываются перед MVP).

## 1. Точка входа (вариант A, external trigger)

```
driver/policy (external)
        ↓ LLMRequest
   LLM Bridge (отдельный модуль; strategy НЕ импортирует LLM)
        ↓
   adapter.propose(provider="gemma", temperature=0)
        ↓
   parsed proposal
        ↓ G-a/G-b/G-c (bridge-side guards)
   executor._check_permission (G-d) → executor.execute
        ↓
   result → (evaluation; knowledge update — только если исполнено)
```

`strategy_state` фиксируется как часть эпизода: драйвер вызывает
`strategy.suggest(store, task)` и сохраняет suggestion (S1/S2/S3,
refs); сам вызов моста — драйверный (policy external, как выдача
прав в Permission-линии). T7 сохраняется.

## 2. Контракт (уточнения при написании ⚠)

```
LLMRequest
    ├── context               (task, symptom, store-факты)
    ├── allowed_action_space  (механически: executor.ALLOWED_PREFIXES)
    └── request metadata      (episode_id, provider, ts)

LLMProposal
    ├── ok        (bool)
    ├── action    (command | null)
    └── arguments
```

Ворота (порядок фиксирован):
```
G-a  structural validity: ok=True; action непустой; arguments dict
     (иное → NO ACTION; N1)
G-b  action ∈ allowed_action_space (префикс-матч; иное → NO ACTION;
     N2)
G-c  command-match guard: command ∉ команд excluded-кандидатов
     (иное → NO ACTION; N4)
G-d  executor permission (permitted + allowlist + МЕTА) →
     executor.execute; отказ ворот = NO ACTION (N5)
```
⚠-1 (уточнение, внесено при написании): P1 — живой вызов
gemma3:4b; N1/N3 — контролируемые отказы уровня adapter
(injected raw / недоступный endpoint), т.к. проверяют обработку
сбоев; N2/N4/N5 — injected proposal валидной схемы, проверяют
ворота G-b/G-c/G-d (ворота не должны зависеть от модели). Если
требуется провести N2/N4 через живую модель — они станут
недетерминированными (провокация модели), что противоречит смыслу
воротных проверок. Везде, где вызывается модель, — только
gemma3:4b.

## 3. Клетки (6 × r1/r2 = 12 runs)

```
P1  live proposal: задача «tsasvc.service inactive symptom=a;
    предложи одну команду из allowed_action_space» → ожидание:
    ok=True, команда ∈ пространства → permitted=True → ровно одно
    исполнение → result; origin-цепочка полная.
N1  invalid model output (injected raw: не-JSON / schema
    violation) → ok=False → NO ACTION.
N2  unknown action: proposal (injected) с командой ∉
    allowed_action_space → NO ACTION (G-b).
N3  LLM error: реальный сетевой отказ/timeout (endpoint
    недоступен) → ok=False → NO ACTION; НЕ S3; НЕ Explore.
N4  excluded candidate: store с excluded K (команда X; механизм
    v0.6.x+A1, exclude по триггеру); proposal (injected) с
    command == X → NO ACTION (G-c); K остаётся excluded.
    ОГРАНИЧЕНИЕ (каноническое): «N4 establishes command-level
    exclusion protection, not semantic provenance of the
    proposal» — об эквивалентных действиях под другим именем
    эксперимент ничего не утверждает.
N5  not-permitted: proposal (injected) с командой ∈ пространстве,
    но action.permitted=False (право в контексте не выдано) →
    executor отклоняет → NO ACTION (G-d).
```

## 4. Assertions (общие для всех клеток)

```
A1  audit clean (слои не изменяются прогоном).
A2  append-only (записи только добавляются; дублей нет).
A3  no executor bypass (ни одно действие не исполнено вне
    executor.execute; для N-клеток — 0 исполнений).
A4  proposal origin recoverable (поля §5 восстанавливают цепочку).
A5  r1 ≡ r2: N1/N3 — строгое равенство (детерминированные пути);
    P1/N2/N4/N5 — эквивалентность permission-decision и
    executor-эффекта; raw proposal сохраняется в обоих прогонах;
    недетерминизм raw = observation, не FAIL. (⚠-2: конкретизация
    внесена при написании.)
```

## 5. Наблюдаемость (обязательная; решение профессора — с первого прогона)

```
episode_id; strategy_state (suggestion); llm_request (context,
allowed_action_space, metadata); model/provider; raw proposal
(текст + meta); parsed proposal (ok/action/arguments); permission
decision (gate, allowed/denied, reason); action (если исполнено —
запись actions.jsonl); executor result; evaluation; knowledge
update (если был). Всё — в append-only record LLM1_cell_*.json
+ строки лога.
```

## 6. Среды

```
Полигон tsasvc; свежий стор на клетку (data_llm1_<cell>).
P1/N2/N3/N5: стор с одним success-знанием K1 (fix-a; learn-эпизод
через update.apply) — минимальный контекст; allowed_action_space =
executor.ALLOWED_PREFIXES (механически).
N4: как выше + exclude(K1) через strategy.exclusion.GateModule
(mechanical); excluded-команда = fix-a.
N1/N3: adapter-уровень (endpoint/hook), store не обязателен.
Задача одна: «tsasvc.service inactive symptom=a».
```

## 7. Критерии PASS/FAIL

```
P1: ровно одно исполнение; result получен; полная origin-цепочка.
N1–N5: 0 исполнений; причина отказа соответствует клетке
(G-a/G-b/G-c/G-d); N3: нет S3/Explore-событий; N4: K remains
excluded.
Общие: A1–A5.
PASS = все 12 runs удовлетворяют своим assertions.
```

## 8. Процедура

```
FROZEN (этот файл) → orchestrator (bridge + driver; отдельный
модуль; strategy не трогается) → preflight (1 живой вызов
gemma3:4b + 1 воротный smoke) → RUN 12 → LLM1_ANALYSIS.txt →
STRATEGY_LLM_ACTION_REPORT.md → решение о полном цикле
(longitudinal) — отдельным словом.
```

## 9. Артефакты

strategy_llm_action/PROTOCOL.md (этот файл, FROZEN),
bridge.py + llm1_driver.py (после), LLM1_cell_*.json (12),
LLM1_ANALYSIS.txt, STRATEGY_LLM_ACTION_REPORT.md. Слои v0.6.x+A1
не изменяются; experimental-каталоги не трогаются.
