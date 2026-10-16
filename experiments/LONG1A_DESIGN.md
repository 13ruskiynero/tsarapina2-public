# LONG-1A: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора по OT-1..5 внесён:
OT-1 — контекст расширяется до всех известных результатов задачи
(не весь store; kid/provenance в текст не попадают);
OT-2 — среды подтверждены; OT-3 — все шесть критериев остаются
(A-L1-4 центральный; строгая формулировка dynamic effect ниже);
OT-4 — proposal change = observation; OT-5 — 12 runs, не длинная
серия. Дополнительно: **L-chain invariant** (см. §4). Strategy не
трогается (EF-12 не закрывается задним числом).

## 1. Вопрос

> **Can repeated verified interactions cause externally stored
> Knowledge to alter subsequent Strategy/LLM proposals or action
> outcomes over a longitudinal episode sequence?**

Строгая формулировка dynamic effect (вердикт):

> **Dynamic effect means an observable change in subsequent system
> state/context/proposal/action attributable through the recorded
> chain to prior verified Knowledge.**

## 2. Что доказывается / что НЕ доказывается

```
ДОКАЗЫВАЕТСЯ:
  L1-1  накопление: repeated verified interactions → растущее
        persistent Knowledge (каждый consequence → diff);
  L1-2  повторное использование: знания retrieved в context/state
        последующих эпизодов (механически);
  L1-3  динамика: для каждого N→N+1 цепочка §4 проходит
        механически;
  L1-4  отсутствие структурной деградации;
  L1-5  r1 ≡ r2 (структурные поля).

НЕ ДОКАЗЫВАЕТСЯ: «ум»/обучение Gemma; generalization; trust;
staleness; устойчивость к шуму (шум — условие траектории, не
гипотеза); emergence; D-2/D-3/D-4; длинная серия (>6 эпизодов) —
после чистого L1-A, отдельным словом.
```

## 3. Структура серии (подтверждена)

```
L1-A: 6 эпизодов × 2 реплики = 12 runs:
  E0 seed w1 | E1 LLM w1 | E2 LLM шум | E3 LLM шум |
  E4 LLM w1 | E5 LLM w1.
Смысл участков: acquisition → reuse → repeated consequence →
accumulation / persistence (E4/E5 — после шумового участка).
```

Базис LOOP-0: seed первым (production path); r1/r2 независимые
stores; driver-built context; Gemma — proposal generator;
permission external; никаких новых policy.

## 4. L-chain invariant (механический; добавление вердикта)

```
Для любого знания K, считающегося использованным на эпизоде E_n,
существует восстановимая цепочка:

  verified consequence E_k → Knowledge K → K retrieved at E_n →
  context_source E_n → LLM request E_n → proposal / action,
  где k < n.

Запрещено засчитывать как «longitudinal influence»:
  * знание, созданное в ТОМ ЖЕ эпизоде после proposal;
  * знание, просто существующее в store, но не retrieved.
Механически: K ∈ context_source(E_n) ⟹ first_seen(K) < n.
```

## 5. Обязательная наблюдаемость (каждый эпизод)

```
knowledge_state_before; knowledge_diff; knowledge_state_after;
strategy_state_before; strategy_state_after;
context; context_source;
proposal (raw + parsed); permission (gates/decision);
action; result; evaluation.

Per-knowledge counters (observability; считает анализатор):
  first_seen_episode; last_used_episode; times_retrieved;
  times_actioned; times_verified_success; times_verified_failure.
Механика: retrieved = K ∈ context_source(E_n);
actioned = K.cmd == action cmd эпизода с исполнением;
verified_success/failure = по outcome того же эпизода
(success → success; partial/failure → failure).
```

## 6. Критерии (все шесть; подтверждены)

```
A-L1-1  каждый эпизод: полная запись + audit чистый;
A-L1-2  каждый verified consequence → knowledge_diff (буквально);
A-L1-3  retrieved-связи: для каждого K с times_retrieved>0
        восстановимо, в каком context/эпизоде он участвовал;
A-L1-4  динамика: для каждого N→N+1 (где proposal produced)
        цепочка §4 проходит механически;
A-L1-5  структурная деградация отсутствует: ворота/append-only/
        chain/kid→exp→episode на всех 12 runs;
A-L1-6  r1 ≡ r2 (структурные поля).
PASS = A-L1-1..6.
Observation (не критерий): proposal/action change (changed==true
не PASS; false не FAIL); accumulation-форма (какие линии растут).
```

## 7. Запреты

```
без новых policy; без fine-tuning/LoRA/hidden state; без
изменения strategy.py и слоёв; без длинной серии (отдельным
словом после L1-A); D-2/D-3/D-4 не открываются; «устойчивость к
шуму» не заявляется; kid/experience_refs/служебные ID — не в
текст prompt.
```

## 8. Процедура

```
FROZEN (этот файл) → PROTOCOL (long1a/) → long1a_driver.py →
long1a_analyze.py → preflight → RUN 12 → LONG1A_ANALYSIS.txt →
LONG1A_REPORT.md → решение о длинной серии — отдельным словом.
```

## 9. Артефакты

LONG1A_DESIGN.md (FROZEN), long1a/PROTOCOL.md, long1a_driver.py,
long1a_analyze.py, LONG1A_E*_r*.json (12), LONG1A_ANALYSIS.txt,
LONG1A_REPORT.md. Слои и experimental-каталоги не трогаются.
