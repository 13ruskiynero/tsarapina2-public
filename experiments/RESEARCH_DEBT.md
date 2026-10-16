# TSARAPINA RESEARCH_DEBT — реестр исследовательских долгов

**Выпуск 2: 08.09.2026.** Выпуск 1 — 07.09.2026 (после v0.6.x GATE
PASS). Правило: долг закрывается дизайном → экспериментом →
интеграцией → словом профессора; пункт не закрывается «по ходу»
других работ.

**Контекст выпуска 2:** EP-1 CLOSED (strong finding;
EVIDENCE_PERMISSION1_REPORT.md). Установлено: (1) единого evidence
threshold нет — explore = permitted verification (граница в
allowlist, не в evidence); (2) R/S-INSUFFICIENT вызван upstream
selection (failure-знания в recency-гонке), проблема ДО permission
layer; (3) V/D2-канал структурно несимметричен (D2 — первое
evidence); (4) persistent noise ≡ stale на общем префиксе —
repetition count не является основанием для trust/permission.

---

## D-1. APPLICABILITY ADDRESSING — OPEN, **приоритет ↑↑ (следующая
граница; AA-1)**

- **Суть (переформулировано после EP-1).** Strategy-слой выбирает
  S2-кандидата recency-гонкой среди exact/legacy-пула, ВКЛЮЧАЯ
  failure-знания (aw=None → legacy-матчинг): после первого failure
  контур эксплуатирует «НЕ перевело»-записи как known_fix.
  Следствие: simulated R/S(verified-success знание) не влияет на
  выбор (EP-1 checks: granted→excluded 0/20) — дорогие права
  нереализуемы, пока выбор не инвариантен к failure-знаниям.
  Проблема локализована ДО permission layer: candidate selection →
  applicable lineage/address → permission → exclusion.
- **Вопрос (формулировка профессора):** can candidate selection be
  made invariant to failure-derived knowledge, so that retract/
  suppress permissions act on the same applicability lineage that
  produced the candidate?
- **Где зафиксировано.** EVIDENCE_PERMISSION1_REPORT.md §3.2/§5
  (пересечение R/S с D-1); APPLICABILITY_LINEAGE_INTEGRATION_DESIGN
  .md §3/§6 (вне scope v0.6.x); TRUST1-T2 (no-failure-action —
  механизм-прецедент); APPLICABILITY_BOUNDARY1_REPORT.md §3/§4
  (корригенда).
- **AA-1: PASS (10.09.2026).** APPLICABILITY_ADDRESSING1_REPORT.md:
  failure-refs == 0 на всех A1-B-прогонах; N-траектории A1 ≡ A0;
  якорь/L6/audit/r1≡r2 чисты; R/S-механика разблокирована
  (A1-SD/E6S: granted→excluded True, повторения 0; A0-контроль 1–2);
  найдено измеренное различие A0/A1 на SM (A0 эксплуатирует
  нерелевантное failure-знание на V2-шаге, A1 останавливается).
  strategy_aa.py — кандидат на интеграцию в strategy-слой (отдельный
  gate по слову профессора). Границы: постоянный R/S на NpD
  останавливает контур с потерей восстановления; NSD — терминальный
  триггер (EF-4).
- **Статус: CLOSED (10.09.2026; слово профессора).** AA-1 PASS
  (оба раздельных утверждения); D-1 experimentally confirmed.
  strategy_aa.py НЕ интегрируется в working layers: экспериментальная
  реализация доказанного механизма; integration gate — отдельно,
  ПОСЛЕ EP-2, по слову профессора.
- **Что осталось.** EP-2 (umbrella, порядок A→B→C; следующий шаг —
  EP-2A): граница R/S при корректной адресации, семантика permanent/
  temporary retract, S3→explore; интеграция A1 — отдельным gate
  ПОСЛЕ EP-2.

## D-2. SEMANTIC TRUST — OPEN (формулировка изменена после EP-1)

- **Суть.** НЕ «найти trust score». Категориальная permission-
  алгебра: Explore = разрешение проверить гипотезу действием
  (EP-1); R/S = разрешение изменить доступность существующего
  candidate (AA-1 разблокировал механику). Вопрос: какое право на
  изменение поведения следует из конкретной СТРУКТУРЫ evidence.
  Разные формы разрешения не сводятся к одной шкале доверия.
- **EP-2: OPEN (umbrella; порядок A→B→C; НЕ смешивать):**
  - **A — Evidence → R/S: ЗАКРЫТ (10.09; слово профессора).**
    No-sufficient при permanent R/S; HALT — измеренная semantics;
    EF-5 — CLOSED execution finding (POOL — предсказанная
    альтернатива, finding'ом не считается). См.
    EVIDENCE_PERMISSION2A_REPORT.md;
  - **B — exclusion semantics: CLOSED (10.09; слово профессора;
    EVIDENCE_PERMISSION2B_REPORT.md).** 48 RAW (POOL 28 + TEMP 20;
    HALT — деривация); audit 48/48, r1≡r2, L6 212/0. Фиксация:
    POOL и TEMP обе sufficient на C5/C6 (без победителя;
    не взаимозаменяемы: POOL — continuation через sibling; TEMP —
    восстановление САМОГО K через verification slot); HALT
    insufficient; C1/C2 insufficient (≡ EP-2A); R/S совпали;
    safety 48/48; S6bV3 — ограничение (нет sign-of-life → нет
    восстановления). EF-5 валиден (смена semantics меняет
    место/характер recovery failure). TEMP failure branch —
    отдельный targeted validation (TEMP-F); интеграция A1 —
    после EP-2C;
  - **C — candidate absence → Explore: CLOSED (10.09; слово
    профессора; EVIDENCE_PERMISSION2C_REPORT.md — Finding).**
    40 уникальных клеток (32 core + 8 negative; U5a≡NEG-E6N —
    общий носитель); 0 нарушений; audit 40/40; r1≡r2; R≡S.
    Результат: S3 → Explore активируется только при пустом
    eligible pool после exclusion (28/28); нерефлекс подтверждён
    (12/12); excluded K не восстанавливается Explore; Explore не
    создаёт TEMP slot; новый candidate — fix-aq-линия; U5b —
    boundary (double exclusion). Канонический Finding EP-2C — в
    отчёте; далее — D-5. TEMP-F — VALIDATED (10.09; 4/4 OK;
    TEMP_FAILURE_VALIDATION.md).
  Детали: EVIDENCE_PERMISSION2_DESIGN.md (FROZEN EP-2A-часть);
  отчёт A: EVIDENCE_PERMISSION2A_REPORT.md.
- **Где зафиксировано.** EVIDENCE_PERMISSION1_REPORT.md;
  APPLICABILITY_ADDRESSING1_REPORT.md; TRUST1_DESIGN.md.
- **Критерий закрытия.** EP-2A+B+C с границами per-уровень;
  trust-число не строится.

## D-3. GENERALIZATION A/B→C — OPEN (не трогать; отдельная ветка)

- **Суть.** Перенос знания A/B→C отсутствует (SEB1): приобретение
  через прямое последствие, не обобщение. EP-1 не разрешил и не
  должен был разрешать; permission ≠ generalization сохранено
  (explore нашёл fix-aq по allowlist-подсказке, не обобщил).
- **Критерий закрытия.** Дизайн + эксперимент переноса A/B→C с
  контролем безопасности; отдельным маршрутом.

## D-4. STALE-KNOWLEDGE / applicability signals — OPEN (граница
уточнена после EP-1)

- **Суть.** Чистая граница: текущий evidence channel НЕ отличает
  persistent noise от stale knowledge на общем префиксе (Np ≡ S до
  восстановления; repetition count не достаточен). Решение должно
  прийти либо через НОВЫЙ наблюдаемый сигнал, либо через изменение
  структуры адресации/применимости (D-1), НЕ через увеличение k.
  При D-1-адресации stale-петля останавливается S3/R/S; explore =
  permitted verification (EP-1) — но «что разрешает системе
  действовать» остаётся вопросом EP-2.
- **Где зафиксировано.** EVIDENCE_PERMISSION1_REPORT.md §3.4;
  STALE_EXACT1_REPORT.md (BOUNDARY одного последствия);
  STALE_EXACT2 (address-match consequence-mismatch).
- **Критерий закрытия.** Новый сигнал/структура с дизайном и
  шумовым контролем, различающие Np и S на общем префиксе; либо
  явное решение о закрытии направления.

## D-5. INTEGRATION GATE (A1 → strategy layer) — PASS (10.09.2026)

- **Суть.** Первый момент, когда исследованная цепочка (EP-1 →
  AA-1 → EP-2A/B/TEMP-F → EP-2C) входит в реальные слои. Принцип:
  *Integration must implement the experimentally established
  permission algebra, not introduce a new policy.*
- **Проверки (минимум G1–G10):** G1 addressing (failure-derived
  не становится кандидатом через legacy aw=None); G2 R/S на том же
  K из applicability lineage; G3 POOL (K удалён из eligible pool,
  остальные eligible работают); G4 TEMP (sign-of-life → slot →
  attempt — только для конкретного excluded K); G5 TEMP failure
  (attempt non-success → K remains excluded; без второго slot);
  G6 empty pool → S3 → Explore; G7 Explore isolation (не
  восстанавливает K; не создаёт slot; новый candidate — новая
  applicability lineage); G8 non-empty pool → normal selection
  (без S3/Explore); G9 append-only/provenance (исторический
  K-record не изменяется); G10 regression (v0.6.x behavioral
  anchor эквивалентен baseline там, где новая политика не должна
  менять поведение).
- **НЕ делать:** выбор production semantics (POOL vs TEMP) —
  отдельный decision experiment (стоимость, recovery latency,
  collateral effects); «улучшения» Strategy сверх алгебры.
- **Слои v0.6.x до этого момента не изменялись** — правильный
  момент для интеграции (слова профессора).
- **Результат (INTEGRATION_GATE_REPORT.md, 10.09).** 48 прогонов
  (30 механических + 18 R0-anchor); G1–G10 PASS (конъюнкция
  strict); guards 30/30; audit 48/48 (слои не изменялись); L6 0;
  детерминизм OK; R≡S. R0: 4 A1-authorized отличия (S5: old
  выбирал failure-derived K через legacy aw=None; модуль — S3):
  ровно цель A1; иных отличий нет. Execution findings EF-6..EF-10
  (технические фиксы драйвера/анализатора; перезапуски
  зафиксированы; семантика не менялась).
- **Номенклатура/следующее.** «A1 experimental integration» (ветка
  experiments/integration_gate) → перенос выполнен (ниже);
  финальный ярлык «v0.6.x+A1» — после решения EF-11. POOL/TEMP —
  обе валидные конфигурации; HALT не интегрируется.
- **Перенос (11.09; INTEGRATION_GATE_A1_PROD_REPORT.md).**
  Выполнен по FROZEN-спецификации (A1_PRODUCTION_TRANSFER_DESIGN.md):
  strategy.py (3 ханка) + strategy/exclusion.py (механизм 1:1;
  fail-closed ValueError); backup strategy_v06x_baseline.py
  (sha 2040d495…); test_exclusion 24/24; production gate 48
  прогонов (30 мех. + 18 R0); сравнение exp↔prod — 30/30
  идентично, R0: те же 4 authorized; ЭКВИВАЛЕНТНОСТЬ PASS.
  Update/knowledge/storage/executor/evaluation/observer —
  не менялись.
- **EF-11 (ОТКРЫТ; слово профессора).** Знания без outcome-метки
  в context (production-путь update.apply всегда ставит метку;
  без метки создаются только вручную/в тестах) исключаются
  A1-фильтром (faithful-буква эксперимента); существующий
  test_strategy t1 падает (IndexError). Варианты: (a) сохранить
  букву (unknown ⇒ не-кандидат; t1-сценарий нереалистичен;
  правка теста — отдельным решением); (b) новое правило
  (unknown ⇒ legacy-допустим) — новый research question.
  Рекомендация инженера — (a) + отдельный пункт D-6.
  Решение профессора (11.09): (a) принято — «Knowledge without a
  verified outcome is not an A1 candidate»; A1 не откатывается;
  test t1 — known expected mismatch; вопрос вынесен в D-6.

## D-6. KNOWLEDGE WITHOUT VERIFIED OUTCOME — OPEN

```
Question:  What is the status of knowledge created without
           verified-outcome provenance?
Known:     A1 rejects it as a candidate (faithful semantics).
Unknown:   whether such knowledge should be migrated,
           reclassified, made eligible under a separate legacy
           policy, or prohibited at creation.
Constraint: must not be resolved inside A1.
```

## D-context-1. SILENT TRUNCATION — OPEN (инфраструктура)

> Current provider configuration (`ollama 0.30.10`, `gemma3:4b`,
> effective `num_ctx=4096`) silently truncates oversized prompts.
> `prompt_eval_count` plateau is therefore the primary observable
> boundary signal; transport success alone is insufficient to
> establish faithful context delivery.

Статус: свойство инфраструктуры; влияет на любые будущие
эксперименты с длинным контекстом. Источник: LONG-3A
(LONG3A_PROVIDER_SCALE.md). Не «баг» и не задача A1-линии —
отдельный пункт долга.

## D-selection-1. RETRIEVAL ≠ SELECTION ≠ PROPOSAL — OPEN

> Retrieval, mechanical candidate selection and LLM proposal are
> empirically distinct in the current prototype. The mechanical
> exact-pool exhibits acquisition-order/recency-like behavior,
> while the LLM proposal may ignore the selected candidate and
> produce an action outside the retrieved Knowledge lines. The
> mechanism and intended contract between Strategy selection and
> LLM proposal remain unresolved.

Появился из COMPETE-1 (11.09). Возможные причины (проверять
различающими экспериментами, не чинить): ожидаемое свойство
дизайна / prompt-context representation / особенность Gemma /
strategy reference недостаточно явен / LLM не обязана следовать
выбранному кандидату / отдельный феномен.

**Запрет (до закрытия): Do not modify Strategy→LLM semantics to
force proposal adherence** — сначала OBSERVE, затем EXPLAIN,
и только потом MODIFY. COMPETE-2 — в долге (не открывать до
понимания разрыва).

## D-context-2. COUPLED INPUT/OUTPUT BUDGET — OPEN

> The current Ollama provider shares `num_ctx` between prompt and
> completion. Longitudinal context growth therefore creates an
> output-budget starvation boundary before prompt truncation. The
> resulting failure can become self-maintaining because failed
> proposal generation prevents execution and subsequent Knowledge
> growth.

Появился из RECON-1 r1 (11.09; OUTPUT-BOUNDARY OBSERVED; I-5/B5;
equilibrium: proposal failure → no execution → no Knowledge →
prompt freeze → starvation). Связан с D-selection-1 (у границы
ломается proposal-канал, не retrieval/strategy) и с D-context-1
(LONG-3A). Не чинить до завершения targeted r2.
**MAP-1 (11.09, read-only): PASS → CLOSED.** Under Ollama
num_ctx=4096, prompt and completion share a single window.
The current structured proposal contract requires approximately
136 completion tokens, with the tested validity boundary in
(120,140); observed consumption varies ≈125–141. At starvation
contexts with only 113 tokens available, increasing requested
max_tokens cannot restore validity (provider window exhausted:
min(200,113)=113<136). Self-maintaining: invalid proposal → no
action → no Knowledge growth → unchanged context.
RESOURCE STATE R0 (baseline): prompt≈3983; available=113;
required≈136; proposal invalid; action none; growth 0.
B2b remains NOT OBSERVED (prompt truncation не доказана
невозможной — лишь не достигнута на этой траектории).
**RESOURCE-RESPONSE-1 — следующий шаг (по слову); архитектуру
не менять.**
**RESOURCE-RESPONSE-1 (11.09): DRAFT дизайн открыт** (RQ;
response-policy classes R0–R4; инварианты I1–I7; отрицательные
контроли; стоп-условия; матрица 2×3×2, read-only реплей;
RESOURCE_RESPONSE1_DESIGN.md). На ревью OT-1..7; ветка не
открыта до FREEZE; код не пишется.
**RESOURCE-RESPONSE-1: выполнен (11.09) — PASS по протоколу
(12/12; все checks True).** Детекция D1/D2/D3 подтверждена
(чувствительна; молчит на NORMAL); инварианты I1–I7 чисты
(K/context/source неизменны; executor=0; retry=False). Ключевое:
R0 vs R1 различимы только декларативно (event/halted), при
одинаковом proposal-исходе — поведенческого отличия нет
(отрицательный результат, допускался заранее). Граница — зона:
MARGINAL дал 1 валидное завершение из 4 при C=129; STARVED —
строго 113/113. RESOURCE_RESPONSE1_REPORT.md.
**CLOSED (вердикт 11.09):** explicit HALT не даёт наблюдаемого
траекторного отличия от natural NO-ACTION (read-only условия);
I1 выдержал; три режима (impossible / resource-contingent /
sufficient; B_min не константа). NEXT: **R2 resource-aware
representation** (рамка и distinction зафиксированы:
REPRESENTATION_PAUSE.md); R4 self-compression — FROZEN.

---

## Сводка на 10.09.2026

- Закрыто: v0.6.x (lineage persistence; 07.09); EP-1 (08.09);
  AA-1 (D-1: адресация — PASS); EP-2A (HALT; EF-5 CLOSED);
  EP-2B (POOL/TEMP sufficient — без победителя);
  TEMP-F (COMPLETED / incorporated into EP-2B);
  **EP-2C (CLOSED; Finding: exclusion removes last eligible
  candidate → S3 → Explore; права разделены;
  EVIDENCE_PERMISSION2C_REPORT.md)**.
- Открыто: **D-6 (статус knowledge без verified-outcome provenance;
  EF-11 выделен из переноса A1)**; D-2 (trust; выбор semantics при
  необходимости — отдельный decision experiment); D-3; D-4.
- D-5/перенос A1: **PASS с маркировкой** (semantic equivalence PASS;
  production gate PASS; A1 regression PASS; existing suite
  8/9 baseline-compatible; EF-11 → D-6). Следующий шаг:
  **Strategy → LLM → Action** — DESIGN FROZEN 11.09 (граница
  полномочий LLM: proposal generator only; мост — отдельный
  orchestrator; fail closed; LLM failure ≠ Explore; A1 —
  mechanical guard); далее PROTOCOL (proposal-cells).
  **LLM1 (STRATEGY → LLM → ACTION): PASS (11.09; 12 runs;
  71 checks; audit 12/12; r1≡r2) — канал proposal → permission →
  action работает; LLM предлагает, право остаётся у системы;
  fail closed подтверждён буквально; EF-13 (регистрация драйвера)
  исправлен. Следующее (по слову): полный цикл (Result →
  Evaluation → Experience → Knowledge → Strategy → следующий
  запрос к Gemma; longitudinal episodes).**
  **LOOP-0 (замыкание петли): PASS (11.09; 8 runs; 59 checks;
  audit 8/8; r1≡r2).** Verified consequence E0 → K1 → context E1 →
  Gemma → permission → executor → … → Knowledge; causal chain
  механически восстановима; ворота без обходов. Наблюдения:
  Gemma не меняла предложение (observation); контекст — линия
  fix-a (F4); состав контекста — первый кандидат на дизайн-решение
  перед longitudinal. Следующее (по слову): longitudinal-фаза.
  **LONG-1A: PASS → CLOSED (вердикт 11.09; 12 runs; 57 checks;
  audit 12/12; r1≡r2).** Establishes: persistent external
  Knowledge + longitudinal retrieval + context transport +
  observed proposal/action dynamics. НЕ establishes: learning law;
  stable policy adaptation; monotonic improvement; forgetting;
  generalization; long-term competence. EF-14 — execution finding
  (исправлен). **LONG-2: дизайн FROZEN; результат — ниже.**
  **LONG-2 / CONTEXT-GROWTH-1: PASS → CLOSED (вердикт 11.09;
  24 runs; 89 checks; audit 24/24; r1≡r2).** csn растёт линейно
  (+1/эпизод); chars 143→506 (serializer-proxy; не token metric);
  duplicate-строки 0→8; unique_commands плато 3; **K_store−K_context
  = 0 на всех эпизодах** (при N=12 транспорт не отстаёт от памяти).
  Whiteboard: establishes — faithful transport at N=12; linear
  record accumulation; sub-linear unique-content growth;
  increasing duplicate burden; does NOT establish — context
  scalability; transport capacity limit; optimal context
  construction; compression/relevance policy; model degradation.
  **LONG-3 / CONTEXT-THRESHOLD-1: DRAFT — следующий** (поиск
  границы faithful transport; ступени N=20/30/50/75; stop по
  первому mechanical boundary; пороги — до запуска).
  O3 — **PROTOCOL PASS / RETURN OBSERVED → CLOSED (слово 11.09;
  RETURN1_REPORT.md)**. 20 runs; M1–M6 чисто; narrative-leak
  чисто; r1≡r2 полностью; R0..R5 полная цепочка в обеих
  K-репликах; counterfactual: K=fix-a→success / NULL=restart→
  partial (обе пары) — return behavior associated with prior
  verified Knowledge (не causal proof).
  **COMPETE-1: PASS / STRUCTURAL RESULT → CLOSED (вердикт 11.09;
  20 runs; M1–M6; r1≡r2).** Канон: retrieval, mechanical candidate
  selection и LLM proposal — эмпирически различимые стадии; обе
  линии retrieved/transported; exact-pool — acquisition-order/
  recency-like (C1→K_G, C2→K_F); LLM proposal не следует выбору
  и не совпадает ни с одной линией (C1 restart / C2 start);
  consequence partial. См. COMPETE1_REPORT.md; долг D-selection-1.
  Следующий шаг: **targeted boundary reconnaissance** (поведение
  слоёв Retrieval → Strategy → Proposal при приближении к silent
  truncation; НЕ полный N≈404 — только после обнаружения
  интересной деградации); cross-series — заморожен; COMPETE-2 —
  в долге.
  **LONG-3 / CONTEXT-THRESHOLD-1: PASS → CLOSED (вердикт 11.09;
  150 записей; оба checkpoint@12 PASS; ноль B-срабатываний;
  counter 167→878 монотонно; K_store−K_context=0 на всех 148
  LLM-эпизодах; L-chain/audit чисты).** Adapter observability
  patch (sha 143f3609…; test_llm_adapter пройден).
  **LONG-3A / PROVIDER-SCALE: COMPLETE (11.09; observation-only;
  LONG3A_PROVIDER_SCALE.md).** ollama 0.30.10; gemma3:4b;
  фактический num_ctx=4096 (дефолт); переполнение = silent
  truncation (промпт ~8–16k ток. молча обсечён до 4095, без
  ошибки); utilization N=75 = 21.44%; экстраполяция достижения
  капа ≈ N≈404 (темп 9.74 tok/эпизод). Метрика provider-границ —
  counter; chars — serializer observation. Развилка: (a) far → O3;
  (b) targeted прогон до ~N≈400 (≈2.5 ч/реплика) — по слову.
  **EF-12 (pre-experiment finding, 11.09):** в strategy.py S5 нигде
  не выдаётся (присвоения strategy_id ∈ {S1,S2,S3}; llm_request =
  (strategy_id == S5) → всегда False; S5 зарезервирован «LLM —
  позже»). У моста нет штатной точки входа от strategy; требуется
  решение (external trigger / S5-выдача в strategy / иное);
  PROTOCOL и 12-run ждут слова.
- Цепочка: EP-1 → AA-1 → EP-2A → EP-2B → TEMP-F → EP-2C →
  **Integration Gate (PASS)** → A1 → strategy layer (**перенос
  выполнен 11.09; v0.6.x+A1 — условно**) → **Strategy → LLM →
  Action: LLM1 PASS (11.09)** → **LOOP-0 / LONG-1A / LONG-2 /
  LONG-3 / LONG-3A** → **RETURN-1 (PROTOCOL PASS /
  RETURN OBSERVED; 20 runs; M1–M6; r1≡r2; полная цепь R0–R5;
  NULL-контроль чист)** →
  **COMPETE-1 (STRUCTURAL RESULT) → D-selection-1** →
  **boundary recon: OUTPUT-BOUNDARY OBSERVED (r1) → REPLICATED
  (r2, STOP @E517; I-5/B5; equilibrium invariant; B2b NOT
  OBSERVED) → D-context-2**; N≈404 — гипотетическая (не
  достигнута); пауза в boundary-ветке (по слову).
- **RE-1 (переносимость контура): PASS → CLOSED (вердикт 11.09;
  10/10 checks; локальная изоляция; слои sha-неизменны; портфель
  не тронут)** — канон: verified Knowledge переживает ротацию
  носителя и восстанавливается без переприобретения; то же знание
  участвует в применении (restore ≠ reconstruction; apply зависит
  от носителя, не от residual driver state; persistence ≠
  applicability; A→B partial — не generalization-результат).
  С output-boundary веткой не смешивается.
- **OBM-1 (OUTPUT-BUDGET MAP): COMPLETE (11.09).** Fixed-prompt,
  сетка max_tokens: STARVED (113) — контракт не закрывается;
  MARGINAL (129) — resource-contingent (в серии 1 valid из 4);
  NORMAL (189) — sufficient. B_min — не константа: существует
  зона (карта — вход для ресурсных вопросов).
- **RESOURCE-RESPONSE-1 (RR-1): PASS → CLOSED (вердикт 11.09;
  12 runs; read-only; I1 выдержан; детектор чувствителен и
  молчит на NORMAL).** Канон: «Explicit HALT does not produce an
  observable trajectory difference from natural NO-ACTION under
  the tested read-only conditions» (отрицательный результат —
  валидный и наблюдаемый). Три режима: impossible /
  resource-contingent / sufficient.
- **REPRESENTATION_PAUSE: принят канонически (11.09)** —
  KNOWLEDGE ≠ KNOWLEDGE REPRESENTATION ≠ PROMPT SERIALIZATION
  ≠ MODEL COMPLETION; R2 — NOT STARTED (только с
  дизайн-документа); R4 FROZEN. Правило на доске: «Иногда лучшая
  научная операция — не запускать ещё один прогон просто потому,
  что сервер всё ещё включён».
- Слои v0.6.x: первое изменение выполнено (11.09, A1 production
  transfer; baseline-копия на месте); дальнейшие изменения — по
  слову. D-6/D-2/D-3/D-4 не блокируют шаг №2.
- Диск-ревизия (11.09): принята как фактический baseline; все
  линии сверены по файлам; RETURN1_REPORT восстановлен из diff
  (RAW/прогоны не тронуты; документный риск закрыт, нового долга
  нет). NEXT: **R2 (NOT STARTED — дизайна не существует)**;
  R4 FROZEN; N≈404 FROZEN; boundary-ветка не продолжается; новых
  прогонов нет.

---

## S-G4 / EE-1: DECISION MAP (12.09.2026)

> **Decision map of Tsarapina v0.6.x+A1 demonstrates a complete
> observed KNOW → EXPLOIT → EXPLORE → KNOW → EXPLOIT cycle. On the
> held-out C sequence, the first successful exploration cost
> 9 actions, followed by six one-action exploit episodes. Plain
> Gemma4 solved 0/40 matched scenes. The result supports an
> external-memory efficiency effect on the tested operational
> domain, but does not establish a general learning law or
> superiority outside this domain.**
>
> **Historical GENERALIZATION-1 failure mode (knowledge blocks
> search) did not reproduce on v0.6.x+A1. Candidate explanation:
> insufficiency routing + applicability addressing. Causal
> attribution remains unresolved.**
>
> **D-4 remains open: E2 transition does not distinguish stale
> knowledge from persistent/double noise.**

RAW: explore_exploit1/ (EE1_trace.jsonl, EE1_run.log,
EE1_ANALYSIS.txt, EXPLORE_EXPLOIT1_REPORT.md); дизайн:
EXPLORE_EXPLOIT1_DESIGN.md (FREEZE). No code changes before run.

---

## S-G4 / EE-2: MULTI-CLASS SELF-ACQUISITION AND AMORTIZATION (12.09.2026)

> На актуальном контуре Tsarapina v0.6.x+A1 + Gemma4 в EE-2
> продемонстрировано самоприобретение трёх различных классов без
> операторских learn-slots при driver-policy P2. Классы A, B и C
> были самостоятельно приобретены через exploration и затем
> повторно эксплуатировались с одной операцией: A = 3→1→1,
> B = 5→1, C = 9→1. Amortization coverage = 3/3. В отдельной
> revision-сцене A′ старое решение A после двух последовательных
> non-success вызвало E2 → exploration → новое решение fix-aq за
> 7 действий → последующее применение за 1 действие; Knowledge A
> и B при этом сохранили эксплуатационную пригодность.
>
> Operator dependence = 0/N **как свойство driver-policy P2**, а не
> как самостоятельное свойство Царапины.
>
> Acquisition cost определяется позицией решения в фиксированном
> BIN-переборе и поэтому не интерпретируется как мера сложности
> класса.
>
> LLM-fallback в EE-2 не использовался.
>
> Результат поддерживает наблюдаемый механизм: **self-acquisition
> → persistent Knowledge → amortized exploitation → revision →
> renewed exploitation** на трёх классах в данном полигоне. Не
> устанавливает универсальную масштабируемость, независимость от
> порядка BIN, generalization за пределы операционного домена или
> закон обучения.
>
> D-4 остаётся открытым. D-selection-1 не исследовался.

RAW: explore_exploit2/ (EE2_trace.jsonl, EE2_run.log,
EE2_ANALYSIS.txt, EXPLORE_EXPLOIT2_REPORT.md); дизайн:
EXPLORE_EXPLOIT2_DESIGN.md (FREEZE). No code changes before run.

---

## S-G4 / MIN-MECHANISM-1: CUT-1 — AMORTIZATION ≠ DEVELOPMENT (12.09.2026)

**Статус: PASS (Cut-1; по Run-2).** Run-1 — INVALIDATED PARTIAL RUN
(instrument defect: `ctx_extra` не передавался → `applicable_when`
не создавался → клетка R3-FULL не измеряла замороженный фактор;
сохранён, как отрицательный результат не используется).

Замысел разреза: SAME ACQUISITION → verified SUCCESS → {FULL,
MAPPING} → R1–R9. Acquisition у обеих сторон — общий BIN-перебор;
различие — только механизм использования приобретённого после
первого verified success. MAPPING — экспериментальный driver-level
кандидат (persistent (condition, action, result) → lookup), без
recovery policy. Preflight Run-2 подтвердил прибор до серии
(`ctx_extra` → `applicable_when={"E":"absent"}` → S3/cm при
mismatch).

**Cut-1 (строгая формулировка).**
Persistent action-result mapping **достаточно** для:

- acquisition;
- повторного применения (cheap repeat, 3→1);
- наблюдаемой амортизации стоимости.

Persistent action-result mapping **недостаточно** для:

- applicability-aware mismatch rejection;
- реакции на повторяющийся failure;
- exploration/revision;
- приобретения нового решения после изменения мира.

FULL path обеспечивает эти дополнительные свойства на данном
полигоне.

**Causal boundary:**

```text
persistent action-result mapping
        ├──→ cheap repeat       ✓   (3→1; обе стороны)
        └──→ mismatch/revision  ✗   (слепое применение; 4 fail без реакции)

FULL architecture
        ├──→ cheap repeat       ✓   (3→1)
        ├──→ mismatch           ✓   (S3 context_mismatch; K не применяется)
        └──→ revision           ✓   (2 fail → E2 → explore → fix-aq → 1)
```

Итог: **амортизация и развитие экспериментально разделены** —
амортизация дешёвая; управление изменением опыта, по-видимому,
требует большей части контура. R9-наблюдение: после revision
старое знание не удаляется — FULL сохраняет историю и выбирает
текущее предпочтительное знание (PRESERVE HISTORY → ACQUIRE NEW →
SELECT PREFERRED), не DELETE→WRITE.

Границы притязаний: один полигон (tsasvc, gemma4, драйверные
политики P2/EE-2); MAPPING — минимальный кандидат, не «Царапина
минус слои»; вывод не масштабируется автоматически.

**NEXT (резерв; отдельным словом; не объединять):**
1) MAPPING + applicability → mismatch?;
2) MAPPING + E2 → revision?

RAW: min_mechanism1/MM1_TABLE_run2.md, MM1_run2.log,
MM1_run2_trace.jsonl; Run-1 — MM1_TABLE.md, MM1_run.log,
MM1_trace.jsonl (INVALIDATED PARTIAL RUN); дизайн —
MIN_MECHANISM1_DESIGN.md (FREEZE, §9). No code changes слоёв;
Run-2 — только fix прибора драйвера.

---

## S-G4 / MIN-MECHANISM-1: CUT-1 → CUT-2 → CUT-3 — AMORTIZATION ≠ DEVELOPMENT (лестница; 12.09.2026)

**Статус: Cut-1 PASS, Cut-2 PASS, Cut-3 PASS.**

Последовательная causal decomposition на полигоне `tsasvc` показала,
что наблюдавшийся эффект полного контура может быть разложен на три
механизма.

**Cut-1:** persistent action-result mapping воспроизводит acquisition
и cheap repeat (`3 → 1`), но не воспроизводит mismatch rejection или
revision после повторяющегося failure.

**Cut-2:** добавление `applicable_when` сохраняет `3 → 1` и
добавляет context-aware mismatch rejection: знание сохраняется, но
не применяется при несовместимом контексте; после возврата условия
оно снова доступно. Само по себе applicability не вызывает revision
после failure.

**Cut-3:** добавление E2 transition поверх mapping + applicability
добавляет реакцию на повторяющийся non-success:
`fail ×2 → E2 → exploration authorization → BIN acquisition →
new Knowledge → exploit`. Старое Knowledge сохраняется рядом с
новым. E2 не выбирает действие напрямую, а разрешает
exploration/acquisition mechanism.

CAND3 воспроизвёл все обязательные границы FULL: Repeat, Mismatch,
Revision, Old Knowledge preservation и Failure response. Различие с
FULL осталось в реализации mismatch-ветки, но функциональная
граница совпала.

Таким образом, **на данном полигоне наблюдавшийся функциональный
профиль FULL воспроизводится минимальным кандидатом `persistent
action-result mapping + applicability + E2`**. FULL больше не
является единственным возможным объяснением наблюдаемого поведения.

Это не означает, что данные три механизма являются универсально
достаточной архитектурой ScratchAI, и не означает, что каждый
production-layer внутри них минимален. Результат относится к
данному полигону, Gemma4, frozen v0.6.x+A1
acquisition/exploration conditions и измеренным границам MM1.

**Ключевое разделение:** persistent mapping объясняет амортизацию;
applicability объясняет отказ от неприменимого знания; E2 объясняет
переход от повторяющегося failure к revision/exploration.

**Следующий вопрос (research debt, НЕ начат):** какие из этих трёх
механизмов являются необходимыми для **реального преимущества
системы**, а не только для воспроизведения выбранного лабораторного
поведения. Мост: `CAND3 → тот же practical advantage, что у FULL
против plain Gemma (EE-1/EE-2)?` Если да — минимальное ядро
преимущества; если нет — значит, часть FULL, считавшаяся
второстепенной, нужна именно для преимущества.

RAW: min_mechanism1/MM1_CUT2_TABLE.md, MM1_CUT2.log,
MM1_CUT2_trace.jsonl, mm1_cut2_driver.py, mm1_cut2_mapping.py;
MM1_CUT3_TABLE.md, MM1_CUT3.log, MM1_CUT3_trace.jsonl,
mm1_cut3_driver.py, mm1_cut3_mapping.py; дизайны:
MM1_CUT2_DESIGN.md, MM1_CUT3_DESIGN.md (FREEZE). Cut-1 RAW — в
записи выше. No code changes слоёв; все кандидаты — driver-level,
экспериментальные.

---

## S-G4 / MIN-ADVANTAGE-1: PRACTICAL ADVANTAGE OVER PLAIN GEMMA4 (12.09.2026)

**Статус: CLOSED / PASS / ADVANTAGE OBSERVED. H-MA1a PASS; H-MA1b PASS.**

**Question:** Does the minimal causal candidate CAND3 preserve the
practical advantage previously observed with Tsarapina over plain
Gemma4?

**Design:** Fresh paired comparison CAND3 vs plain Gemma4 on
EE-1/EE-2-derived scenes, including acquisition, repeat, noise,
no-change and revision. Same Gemma4, prompt, executor, environment,
action space and episode sequence. CAND3 uses frozen P2 BIN
acquisition policy; bare has no persistent memory, applicability
mechanism, E2 transition or exploration mechanism. 24 paired runs,
2 independent repetitions.

**Result: PASS / ADVANTAGE OBSERVED.** Both CAND3 repetitions were
identical.

- CAND3: A `3→1` success; B `4→1` success; C `8→1` success;
  A′ revision: `fail×2 → E2 → BIN exploration 7 → fix-aq → success
  → repeat 1`. Old knowledge preserved alongside new knowledge.
  Amortization: 3/3. Revision: 1/1. Operator dependence: 0.
  Noise and no-change controls behaved according to protocol.
- BARE: **0/48 verified successes.** All 48 model proposals
  remained diagnostic actions (`systemctl status` /
  `journalctl -xeu`). No therapeutic action was proposed.

**Primary outcome:** CAND3 achieved verified success in the paired
scenes where plain Gemma4 did not. The result supports both H-MA1a
(amortized repeat advantage) and H-MA1b (revision advantage) under
the tested conditions.

**Interpretation:** Practical advantage was observed, not merely
functional reproduction. The result does NOT establish that CAND3
is generally better than Gemma4.

Important decomposition:

1. Repeat advantage isolates a memory component: CAND3 reuses
   verified action knowledge at cost 1, while bare repeatedly fails.
2. Acquisition/revision advantage additionally depends on P2
   exploration.
3. Therefore the total advantage cannot be attributed to persistent
   memory alone.

**Controls / limitations:**

- Bare behavior was highly homogeneous: diagnostic-only proposals
  in 48/48 episodes. This makes the result sensitive to the
  prompt/action contract.
- The experiment therefore establishes a conditional architectural
  advantage, not model superiority.
- EE-2 costs differed from historical values (B=4, C=8 vs 5, 9);
  fresh runs were retained without normalization or adjustment.
- CAND3 includes P2 BIN acquisition by definition of this
  experiment.

**Open question (research debt, НЕ начат): ROBUST-ADVANTAGE-1** —
Does the CAND3 advantage survive a stronger bare-model action
framing? Would explicit instruction («If you have enough evidence,
attempt a concrete corrective action rather than only diagnosing
the service») move bare from 0/48 toward CAND3 — and thereby expose
a decision-framing confound — or leave it near zero, strengthening
the architectural result?

RAW: min_advantage1/MA1_TABLE.md, MA1_run.log, MA1_trace.jsonl,
ma1_driver.py; дизайн: MIN_ADVANTAGE1_DESIGN.md (FREEZE). CAND3 —
min_mechanism1/mm1_cut3_mapping.py (без изменений). No code
changes слоёв.

---

## S-G4 / ROBUST-ADVANTAGE-1: NO FRAMING RESCUE (12.09.2026)

**Статус: CLOSED / PASS for the stated control. No framing rescue
observed.**

**Question:** Does the CAND3 advantage survive stronger bare-model
action framing, where plain Gemma4 is explicitly instructed to
perform corrective action rather than remain diagnostic?

**Design:** Fresh bare-model control using the MA1 scene structure.
Only the bare prompt was changed by adding explicit permission to
perform a concrete corrective action when sufficient evidence
exists. CAND3 was not rerun and remained the MA1 anchor. No
corrective action, target command, search procedure, history,
memory, or CAND3-specific information was disclosed to bare Gemma4.

**Result: CLOSED / PASS for the stated control. No framing rescue
observed.**
BARE-FRAME: 0/96 verified successes.

- Across 96 episodes, Gemma4 produced a corrective proposal in every
  episode, but the proposal was always the same single action:
  `systemctl start tsasvc`.
- No `restart` or `fix-*` action was proposed.
- No alternative corrective strategy emerged after repeated failure.

Compared with MA1 bare: previous bare behavior was diagnostic-only:
0/48 success, diagnostic proposals, typically 2 actions. Action
framing therefore changed the policy space from
`diagnostic-only → corrective-but-wrong`, but did not produce
verified recovery.

**Primary outcome:** The observed CAND3 advantage survives this
stronger bare-model action framing. Explicit permission to perform
corrective actions did not restore success.

**Revision finding:** On the A′ revision scene, framed bare repeated
the same `start` action through six failing episodes and never
discovered `fix-aq` or another alternative corrective action.

**Interpretation:** The result weakens the hypothesis that the MA1
advantage was primarily caused by bare Gemma4 being instructed too
conservatively. Framing changed the first-action policy but did not
provide strategy adaptation, alternative-action discovery, or
recovery after repeated failure.

**Important limitation:** The polygon makes `systemctl start tsasvc`
universally ineffective because the service fails through lock-file
conditions. Therefore the observed framed-bare behavior is
specifically a single-action fixation: the model transitions from
diagnosis to corrective action but remains locked onto one
ineffective action.

The result does not establish that CAND3 is generally superior to
Gemma4. It establishes that, under the tested prompt/action
contract, stronger corrective-action framing alone did not reproduce
the observed CAND3 success.

**Research status:** ROBUST-ADVANTAGE-1 CLOSED. No framing rescue
observed. Framing shift observed. Single-action fixation identified
as an open research question.

**Open question:** Can plain Gemma4 escape a repeatedly failing
corrective action and search for an alternative action when the
prompt explicitly requires adaptation after failure?

**NEXT (research debt, НЕ начат): SINGLE-ACTION-FIXATION-1** —
минимальный вариант: `start → FAIL → model receives result → must
choose next corrective action` (первый ход остаётся `start` — RB1
траектория; поиск модели не даётся). Primary metric: после failure
остаётся ли модель на том же action или меняет action
(fixation → escape → verified success); три исхода: action
fixation / action exploration without success / successful
adaptive search. Граница: если bare сам перейдёт `start → fix-a`
и `fix-a` сработает — это не опровергает CAND3, а означает, что
часть adaptive recovery может возникать непосредственно из
модели при подходящем feedback loop.

RAW: robust_advantage1/RB1_TABLE.md, RB1_run.log,
RB1_trace.jsonl, rb1_driver.py; дизайн: ROBUST_ADVANTAGE1_DESIGN.md
(FREEZE). CAND3 — anchor MA1, не перезапускался. No code changes
слоёв.

---

## S-G4 / SINGLE-ACTION-FIXATION-1: FEEDBACK ≠ EXPLORATION (12.09.2026)

**Статус: CLOSED / PASS. H-SAF1 PASS. Feedback ≠ exploration on
the tested polygon.**

**Question:** Can plain Gemma4 independently escape a repeatedly
unsuccessful corrective action after receiving observed failure, or
is an external E2 mechanism required to transition from repeated
failure into alternative-action search?

**Design:** Plain Gemma4 under the RB1 corrective-action framing.
First action forced to `start`; subsequent actions selected by the
model after receiving the result of the previous interaction. No
persistent memory, CAND3, E2 transition mechanism, P2/BIN
exploration, operator intervention, or explicit instruction to
search for alternatives. Six independent runs, maximum 8 episodes
per run.

**Result: CLOSED / PASS.** All six runs were identical.

```text
E1 start (forced)      → partial
E2 start (automatic)   → failure
DP1 → status           → failure ×2
DP2 → journalctl       → failure ×2
DP3 → restart          → failure ×2
```

verified_success: 0/6. unique_commands: 4. The first corrective
action different from start appeared only at episode 7. No `fix-*`
action was proposed.

**Classification: F2 — Escape Without Success.** The system did not
exhibit pure action fixation: it eventually changed actions.
However, the changes did not constitute successful exploration. Two
of the three decision-point transitions returned to diagnostic
actions (status, journalctl), and the eventual corrective transition
to restart also failed.

**Primary finding:** Feedback alone produced action change but did
not produce solution search.

**Important distinction:** **Action change ≠ exploration.** The
observed model trajectory remained within a narrow neighborhood of
familiar `systemctl` actions and never generated the broader
action-space search required to discover `fix-aq`.

**Comparison with CAND3:** CAND3 uses E2 after repeated non-success
to authorize exploration and then BIN to search the available action
space. In the corresponding revision condition this produced:
`fail ×2 → E2 → BIN → fix-aq → verified success.`

**Interpretation:** On this polygon, the external E2→exploration
mechanism supplies a behavioral transition that was not produced by
the bare feedback loop itself. The experiment therefore supports a
local boundary:

```text
feedback loop            → can change action
                         ✗ does not necessarily produce exploration
E2 + exploration policy  → converts repeated failure into
                           systematic search
```

This does not establish that E2 is universally necessary for
exploration, nor that plain Gemma4 cannot explore under another
prompt, action space, representation, or task. It establishes the
observed boundary under the tested conditions.

**Research status:** SINGLE-ACTION-FIXATION-1 CLOSED. H-SAF1 PASS.
Feedback ≠ exploration on the tested polygon.

**Open question:** What minimal mechanism is sufficient to convert
repeated non-success into systematic alternative-action search?

**NEXT (research debt, НЕ начат): MIN-EXPLORATION-1** — причинное
разделение связки `E2 → BIN`; кандидаты:

- **M1:** E2 → LLM получает разрешение искать альтернативу → LLM
  сама находит `fix-aq` (BIN не нужен);
- **M2:** E2 → BIN → systematic enumeration → `fix-aq` (ключевой
  механизм — внешний systematic search);
- **M3:** E2 + BIN (repeated failure должен не просто замечаться,
  а переключать систему в режим поиска, причём сам поиск должен
  иметь внешний структурированный механизм).

Запуск — отдельным словом; цель: ответить именно на вопрос «что
превращает смену действия в поиск».

RAW: single_action_fixation1/SAF1_TABLE.md, SAF1_run.log,
SAF1_trace.jsonl, saf1_driver.py; дизайн:
SINGLE_ACTION_FIXATION1_DESIGN.md (FREEZE). CAND3 в SAF-1 не
участвовал. No code changes слоёв.

---

## S-G4 / MIN-EXPLORATION-1: SYSTEMATIC SEARCH REQUIRES EXTERNAL ENUMERATION (12.09.2026)

**Статус: CLOSED / PASS. M1: INSUFFICIENT. M2: SUFFICIENT.
M3: SUFFICIENT, behaviorally equivalent to M2.**

**Question:** What converts action change after repeated non-success
into systematic exploration sufficient to discover a new verified
solution?

**Design:** A′ revision polygon with plain Gemma4, frozen
executor/action space, operator=0, same initial failure trajectory
and no persistent memory. Three mechanisms were compared: M1: E2 →
LLM search; M2: E2 → BIN systematic search; M3: E2 + BIN. Three
independent repetitions per mechanism, 9 runs total.

**Result: CLOSED / PASS.**

- **M1 — E2 → LLM search: 0/3 successful exploration.** The model
  produced 8 unique commands after E2: `status → journalctl →
  restart → is-enabled (refused) → show → status --no-pager →
  journalctl --since → stop`. No `fix-*` action was proposed. Even
  after reaching restart, a corrective action, the model returned
  to diagnostic actions.
- **M2 — E2 → BIN: 3/3 successful exploration.** BIN traversed:
  `start → restart → fix-a → fix-b → fix-ab → fix-a2 → fix-aq`,
  with `fix-aq` producing verified success on the 9th episode.
- **M3 — E2 + BIN: 3/3 successful exploration.** Trajectory was
  identical to M2.

**Primary finding:** E2 / exploration authorization without
structured search did not produce successful exploration. External
systematic enumeration did.

**M2 ≡ M3:** Within this polygon and protocol, adding the observed
authorization semantics to BIN produced no measurable behavioral
contribution beyond BIN itself. The observed success is therefore
attributed to the systematic external search mechanism, not to
authorization alone.

**Important refinement to SAF-1:** E2 + authorization substantially
widened action variation: M1 produced 8 unique commands versus 4 in
SAF-1. Nevertheless, no solution was found. Therefore: **action
change, including broad action variation, ≠ exploration.** The
relevant distinction is not whether the system changes actions, but
whether the generated actions systematically cover the available
solution space.

**Local mechanism boundary:**

```text
feedback                  → action change
E2 + LLM authorization    → broader action change
                            ✗ systematic solution search
E2 + BIN                  → systematic enumeration → fix-aq
                            → verified success
```

**Interpretation:** On the tested revision polygon, systematic
external enumeration is the mechanism that converts repeated
non-success into effective exploration. E2 alone, and E2 combined
with LLM authorization, are insufficient. This supports the
CAND3/Cut-3 interpretation that the practical revision effect
depends on an external exploration mechanism rather than merely
giving the model permission to search.

**Limitations:**

- Result is local to the tested polygon, Gemma4, frozen action
  space and BIN implementation.
- M2/M3 equivalence does not establish that authorization is
  universally redundant; it establishes only that no additional
  contribution was observed here.
- BIN's success depends on the completeness/order of the tested
  action space.
- No scalability or general exploration law is claimed.

**Research status:** MIN-EXPLORATION-1 CLOSED. M1: INSUFFICIENT.
M2: SUFFICIENT. M3: SUFFICIENT, behaviorally equivalent to M2.
Core finding: **systematic external search**, not action variation
or authorization alone, produced successful exploration.

**Open question:** Is systematic enumeration itself necessary, or is
it merely one sufficient implementation of an external mechanism
that constrains exploration toward untried actions?

**NEXT (research debt, НЕ начат):** минимальная форма внешнего
ограничения пространства поиска. Кандидат — **EXCLUDE-TRIED-1**:
action space → remove already attempted actions → LLM chooses
among remaining (без полного BIN). Если сработает — механизм
формулируется глубже: не «нужен перебор», а **нужна внешняя
структуризация пространства поиска, исключающая уже проверенные
неуспешные варианты**.

RAW: min_exploration1/MX1_TABLE.md, MX1_run.log, MX1_trace.jsonl,
mx1_driver.py; дизайн: MIN_EXPLORATION1_DESIGN.md (FREEZE).
No code changes слоёв.

---

## S-G4 / EXCLUDE-TRIED-1: REMAINING-SPACE EXPLORATION (16.09.2026)

**Статус: CLOSED / PASS. X1 PASS. EXCLUDE-TRIED: POSSIBLE.
BIN: SUFFICIENT, NOT NECESSARY. Remaining-space choice: effective
exploration observed.**

**Question:** Is full BIN enumeration necessary for effective
exploration, or is an external boundary between tried and untried
actions sufficient?

**Design:** A′ revision polygon, Gemma4, frozen executor/action
space, E2 present, operator=0. Compare EXCLUDE-TRIED against BIN
control. EXCLUDE-TRIED externally removes already attempted actions
and lets the LLM choose from the remaining action space. No BIN
ordering or action hint is provided.

**Result: CLOSED / PASS.**

**EXCLUDE-TRIED: 3/3 identical successful runs.**

```text
start → partial
start → failure
E2 →
  restart → fix-b → fix-a → fix-ab → fix-a2 → fix-aq → SUCCESS
```

Six actions after E2, eight episodes total. `out_of_space = 0`.
No previously tested action was repeated and no action outside the
remaining space was selected.

**BIN control: 3/3 identical.** Exact replication of
MIN-EXPLORATION-1: `start → restart → fix-a → fix-b → fix-ab →
fix-a2 → fix-aq → SUCCESS`. Control did not drift.

**Primary finding:** Full systematic BIN enumeration is not
necessary for effective exploration on the tested polygon. The
observed minimal mechanism is:

```text
external memory of attempted actions
    +
exclusion of already attempted actions
    +
LLM choice from remaining space
```

This mechanism produced verified success in all three repetitions.

**Important observation:** The order of remaining-space actions was
selected by the LLM rather than imposed by BIN. The LLM reached
`fix-aq` in six actions after E2, one fewer than BIN's seven
actions. Therefore: **systematic enumeration is sufficient, but not
necessary.** The critical observed property is an externally
maintained boundary between tested and untested action space.

**Interpretation:** The exploration mechanism can be reduced from
"enumerate the action space" to "prevent revisiting the tested
portion of the action space while allowing the model to choose
within the remainder." This refines MIN-EXPLORATION-1: external
systematic search is one sufficient implementation of exploration,
but effective exploration can also arise from constrained
remaining-space choice. The result does not establish that
exclusion alone is universally sufficient for exploration, nor
that arbitrary remaining-space policies scale to larger action
spaces. It establishes the result on the tested polygon and action
space.

**Research status:** EXCLUDE-TRIED-1 CLOSED. X1 PASS.
EXCLUDE-TRIED: POSSIBLE. BIN: SUFFICIENT, NOT NECESSARY.
Remaining-space choice: effective exploration observed.

**NEXT (research debt, НЕ начат; запуск — отдельным словом):**
**EXPLORATION-BOUNDARY-1** — достаточно ли одной внешней
информации TRIED/UNTRIED, или для эффективной exploration
необходимо также знать результат предыдущих попыток?
Кандидаты:

- **BOUNDARY-ONLY:** внешнее состояние = tried-множество
  (без outcome-истории); LLM выбирает из remaining;
- **RESULT-AWARE:** внешнее состояние = tried + outcome каждого
  attempt.

Если BOUNDARY-ONLY находит `fix-aq` → результат прошлой попытки
не нужен для самой exploration; достаточно знать, что кандидат уже
проверен. Если нет — outcome information является частью
exploration mechanism. **Запуск — не автоматически** (ET-1
закрыт; не превращаем исследование в игру «убрать ещё один
байт»).

RAW: exclude_tried1/ET1_TABLE.md, ET1_run.log, ET1_trace.jsonl,
et1_driver.py; дизайн: EXCLUDE_TRIED1_DESIGN.md (FREEZE).
No code changes слоёв.