# LOOP-0: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Решения по OT-1..OT-5 внесены (слово
профессора, 11.09); сформулированы frozen question, fixed-список,
PASS requires (10) и PASS does not require. Числа: 4 эпизода ×
2 реплики = 8 runs (по записи на эпизод). База: LLM1 PASS; A1/
Exclusion в production; граница полномочий LLM (FROZEN).

## 0. Frozen question

> **Can a single verified interaction propagate through Result →
> Evaluation → Experience → Knowledge → Strategy → LLM proposal
> and affect the next action without bypassing permission?**

Secondary engineering question:

> **Is the causal chain episode N → verified consequence →
> Knowledge diff → N+1 context/proposal mechanically recoverable?**

## 1. Fixed (FROZEN)

```
F1   seed first episode (детерминированный; НЕ через Gemma;
     НЕ создаёт Knowledge напрямую — только обычный production
     path Result → Evaluation → Experience → Knowledge);
F2   r1/r2 — независимые stores (репликация-контроль, не ось);
     режима seed/no-seed НЕТ (seed — инструмент контроля);
F3   driver-generated N+1 context (не модель и не strategy.py;
     EF-12 остаётся OPEN);
F4   minimal frozen context (см. §3);
F5   Gemma = proposal generator (без изменений LLM1);
F6   permission остаётся external/mechanical (G-a..G-d);
F7   no fine-tuning; no LoRA; no hidden state; no new policy;
     no D-2/D-3/D-4;
F8   proposal change = OBSERVATION (оба proposal + raw хранятся;
     proposal_diff {changed, fields_changed}; вердикт не зависит);
F9   complete raw provenance; Knowledge diff между каждым
     эпизодом (added / changed / retracted / restored /
     conflicted / applicability / provenance);
F10  causal chain — mechanical invariant (см. §4).
```

## 2. Структура серии (FROZEN)

```
E0  seed interaction:
    seed action → Executor → known verified consequence →
    Evaluation → Experience → Knowledge ADD (production path).
E1  first LLM request:
    Knowledge from E0 → driver context → Gemma → proposal →
    permission → action → Result → Evaluation → Experience →
    Knowledge.
E2  second propagation:
    Knowledge from E1 → context → Gemma → proposal → permission →
    action → … → Knowledge.
E3  final propagation / persistence check:
    Knowledge from E2 → context → Gemma → proposal → permission →
    action → … → Knowledge.
Смысл четырёх эпизодов: однократная передача → повторное
использование → сохранение состояния (store живёт, не «случайная
передача объекта A→B»).
```

## 3. Minimal frozen context (OT-2)

```
СТРОГО:
  task (одна известная задача);
  previous episode: command → outcome;
  knowledge for lineage L with outcome.

НЕ передавать Gemma:
  episode_id; provenance IDs; внутренние Knowledge IDs;
  strategy internals; полный store; reasoning/history dump.

Фиксация драйвера (для доказательства транспорта):
  context_source = список kid, включённых в context (в записи
  эпизода; Gemma их не видит) — без него нельзя доказать, что
  Knowledge дошёл до N+1.
```

## 4. Mechanical invariant (FROZEN)

Для каждого Knowledge change механически проходимо:

```
forward:  Knowledge → Experience ref → Evaluation / verified
          outcome → Result → Episode;
backward: Episode N → Knowledge diff → N+1 context (context_source)
          → LLM request → proposal.
Ответ LOOP-0: не «следующий запрос содержит что-то похожее», а
«показано, какой именно verified consequence из N породил
конкретный Knowledge change, который затем был включён driver'ом
в context N+1».
```

## 5. PASS requires (FROZEN; 10)

```
P1   E0 produces verified consequence through normal production
     path;
P2   that consequence becomes traceable Knowledge;
P3   Strategy sees the resulting Knowledge state;
P4   driver incorporates it into N+1 context;
P5   Gemma receives that context;
P6   proposal produced or fails closed;
P7   permission gate remains authoritative;
P8   if proposal executable, execution occurs only after
     permission;
P9   full causal chain reconstructable;
P10  r1/r2 reproduce the structural behavior.
```

## 6. PASS does NOT require (FROZEN)

```
Gemma to change its proposal; Gemma to infer anything
sophisticated; generalization; long-term learning; trust;
stale-knowledge detection; autonomous policy formation.
LOOP-0 не должен доказывать интеллект — только замыкание контура.
```

## 7. Запреты

```
без изменения strategy.py и слоёв v0.6.x+A1; без новых policy
decisions; без TTL/trust; без обучения модели; числа — только
8 runs из FROZEN-структуры (E0..E3 × r1/r2).
```

## 8. Процедура

```
FROZEN (этот файл) → PROTOCOL (loop0/) → loop0_driver.py →
preflight → 8 runs → LOOP0_ANALYSIS.txt → LOOP0_REPORT.md →
решение о longitudinal — отдельным словом.
```

## 9. Артефакты

LOOP0_DESIGN.md (этот файл, FROZEN), loop0/PROTOCOL.md,
loop0/loop0_driver.py, loop0/loop0_analyze.py,
loop0/LOOP0_E*_r*.json (8), LOOP0_ANALYSIS.txt, LOOP0_REPORT.md.
Экспериментальные каталоги не трогаются.
