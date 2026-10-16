# BOUNDARY RECON: ОТЧЁТ (r1→r2, 11.09.2026)

**Статус: PROVIDER OUTPUT-BUDGET BOUNDARY: OBSERVED (r1) →
REPLICATED (r2) — 11.09.**

```
Prompt truncation B2b:     NOT OBSERVED
Output starvation B5:      OBSERVED
Equilibrium:               OBSERVED
Retrieval:                 OPERATIONAL
Strategy:                  OPERATIONAL
Proposal:                  COLLAPSED
Execution:                 STOPPED
Knowledge growth:          STOPPED
```

## 1. Что произошло

При подходе к 97% утилизации num_ctx система столкнулась не с
усечением промпта, а с **конкурирующей границей того же окна**:
ollama делит `num_ctx=4096` между промптом и генерацией. При
`prompt=3983` выводу остаётся **113 токенов** — меньше минимума
для полного structured JSON (~119..136 по успешным эпизодам).
Следствие: raw обрывается на середине rationale → G-a →
no_action → no execution → no new Knowledge → промпт неизменен →
**самоподдерживающееся равновесие** (23/23 отказов, E491..E513).

## 2. Чистота границы

```
ни одного отказа при prompt+completion < 4096 (в signature);
ни одного исполнения при сумме = 4096;
E489 первый starvation (3971+125); E490 pass (3971+119=4090);
E491+: 3983+113=4096 — стабильно.
pre-boundary максимум сумм: E488 = 4082 (executed).
```

## 3. Классификация (вердикт 11.09)

```
I-5: proposal-channel collapse / output-budget starvation
     (не I-2: Knowledge из входного контекста НЕ терялась —
     retrieval/strategy/context construction операционны;
     отказ локализован в бюджете генерации);
B5: новый mechanical boundary (определение — RECON1_ANALYSIS §9;
строго после MAP-1: P + B_required > N_ctx, B_required ≈136,
граница (120,140), потребление варьируется 125–141);
B2b: NOT OBSERVED (не переписывать критерий);
N≈404: гипотетическая prompt-saturation boundary — не достигнута
     из-за более ранней output-boundary.
```

## 4. Архитектурный смысл

Ограничение, которое остановило систему, лежит НЕ там, где
ожидалось: память цела, доставка входа цела, слои живы — но
агент перестаёт действовать, потому что не может породить
достаточно длинный структурированный proposal. Цепочка
ограничений для живой памяти:

```
MEMORY INTEGRITY → CONTEXT DELIVERY → PROPOSAL CAPACITY →
ACTION CAPACITY
```

Ограничение одного слоя не обязано ломать предыдущие (продолжает
COMPETE-1: retrieval ≠ selection ≠ proposal; теперь: proposal
generation itself has a resource boundary).

## 5. Уровни S1/S2/S3 (E491..E513)

```
S1 OPERATIONAL (context_source=489 const; K_store−K_context=0);
S2 DELIVERED (counter=3983 const; output budget 113);
S3 COLLAPSED (structural failure 23/23; executions 0).
Equilibrium invariant: added=0, changed=0, prompt freeze
(E491→E492 одна транзиентная prev-строка, далее const).
```

## 6. Дальше — targeted r2 (обязательно)

```
Продолжение long3_r2 тем же драйвером (--series r2): prefill до
~0.94 num_ctx → LLM до первого B5 + 5 → сравнение: first
starvation ep; prompt/completion; truncation signature;
structural failure; execution count; Knowledge growth;
equilibrium persistence. Не чинить starvation до завершения r2.
```

## 7. Новый долг

```
D-context-2: coupled input/output budget (RESEARCH_DEBT.md):
«The current Ollama provider shares num_ctx between prompt and
completion. Longitudinal context growth therefore creates an
output-budget starvation boundary before prompt truncation. The
resulting failure can become self-maintaining because failed
proposal generation prevents execution and subsequent Knowledge
growth.»
```

## 8. Артефакты

```
recon1/PROTOCOL.md, RECON1_BASELINE.txt,
RECON1_EQUILIBRIUM_OBSERVATION.md (сырые факты),
RECON1_ANALYSIS.txt (13 секций), RECON1_E75..E513_r1.json,
RECON1_probe1..3.json, этот отчёт.
Слои не изменялись; STOP.txt не писался (r1 остановлен
инженером, не по формальному B2b).

## 9. r2 replication (REPLICATED)

```
targeted r2 (long3_r2; prefill 430 эпизодов до 95.0%; LLM
E505..E517): E511 первый starvation (3955+141=4096); E512 pass
(«перебежчик», 3955+117=4072); E513..E517 стабильно
(3967+129=4096, 5 подряд); STOP по протоколу (B5+5) @E517.
Invariant петли подтверждён: starvation-эпизоды added=0;
context_source const (511); counter const (3967); executions=0.
Механизм и форма воспроизведены; числа отличаются (completion-
«аппетит» выше → starvation на меньшем prompt). B2b: NOT
OBSERVED (обе реплики). Формулировка: replicated
self-maintaining proposal-channel starvation state.
```
