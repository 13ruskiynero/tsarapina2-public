# MVP-1: IMPLEMENTATION PLAN (2026-09-16; код не менялся)

Вход: `MVP_GATE0.md` (заморожен), решения: JSONL-only storage; E2 =
signal в Strategy, boundary+choice в Exploration; demo =
детерминированный сервис-симулятор (без systemctl/root); Aggregation
= DEFER. Политика: **Research code is evidence. Core code is
implementation** — `experiments/` не импортируется в production.

## 1. Target layout (публичный MVP)

```text
tsarapina/
├── core/
│   ├── runtime.py        # оркестратор цикла (BUILD)
│   ├── strategy.py       # S1/S2/S3 + E2 signal (REFACTOR)
│   ├── applicability.py  # eligibility + context (REFACTOR)
│   ├── exploration.py    # tried/untried boundary + LLM choice (BUILD)
│   ├── experience.py     # REUSE
│   ├── knowledge.py      # REUSE
│   ├── evaluation.py     # REUSE
│   └── update.py         # REFACTOR
├── llm/
│   ├── base.py           # интерфейс propose(context)->Proposal (BUILD, тонкий)
│   └── ollama.py         # из adapter.py (REUSE), canned-stub для demo
├── executor/local.py     # REUSE + config
├── observer/local.py     # REUSE структуры
├── storage/jsonl.py      # REFACTOR из store.py
├── schemas/*.json        # копия protocols/*.schema.json (REUSE)
├── examples/service_recovery/{environment.py, actions.py, README.md}
├── cli.py                # tsarapina run|history|knowledge (BUILD)
├── tests/
└── README.md
```

## 2. Runtime cycle (core/runtime.py)

Оркестратор, не место для логики. Один шаг — один вызов компонента:

```python
class Runtime:
    def __init__(self, env, llm, storage, limits): ...
    def run_task(self, goal) -> Episode:
        facts   = env.observe()            # observer.collect-контракт
        exp     = experience.build(...)    # problem/observations
        ctx     = applicability.context(...)         # E, etc.
        d = strategy.decide(storage, problem, ctx)   # S1|S2|S3|E2-signal
        if d.kind == "explore_authorized" or d.kind == "S1":
            rem = exploration.remaining(env.available_actions(), tried)
            prop = llm.propose(context + rem)         # выбор ∈ remaining
        else:
            prop = d.proposal                          # S2: reuse K
        assert executor.permitted(prop)                # permission-гейт
        res = env.execute(prop)                        # state_before/after
        ev  = evaluation.evaluate(res, goal)
        experience.save(exp); update.apply(exp.id, ev.outcome)
        tried = tried | {prop.action}                  # append-only
        return Episode(...)
```

Правила: `tried` — внешнее состояние (персистентно, в storage);
runtime пробрасывает контракты, не интерпретирует их.

## 3. core/exploration.py (по результату EXCLUDE-TRIED-1)

```python
def explore(action_space, tried_actions, llm, context=None) -> Proposal:
    remaining = [a for a in action_space if a not in tried_actions]
    proposal = llm.propose(context + remaining)
    if proposal.action not in remaining:
        return Rejected(proposal)          # фиксируется, не исполняется
    return proposal
```

Запрещено: ranking; heuristics; embeddings; MC/tree search; score.
ET-1 уже показал минимум: внешняя граница + выбор модели.

## 4. Контракты (НЕ менять)

1. **Knowledge schema** (`schemas/knowledge.schema.json`): id,
   status (active/retracted/conflicted), content, applicable_when,
   source, experience_refs; версии не удаляются (append-only).
2. **Experience**: `build(problem, observations, actions, result_ref,
   machine)` + `save`; sha1-детерминизм; «собирает, не объясняет».
3. **Evaluation**: исходы строго `success|failure|partial|no_change|
   not_executed|refused|unknown`; verdict по фактам.
4. **Executor**: `execute(store, action)`; LLM никогда не исполняет
   сам; allowlist + meta-guard + refused-аудит.
5. **LLM**: `propose(context) -> Proposal` (`{ok, candidate_actions
   [{type,command}], rationale, raw, provider_meta}`); strict JSON;
   структурный отказ при мусоре.
6. **Provenance**: raw + observations с провенансом, append-only,
   ссылки по id.
7. **E2 threshold**: 2 последовательных non-success применения
   (reject не считается).

## 5. storage/jsonl.py (JSONL-only)

9 файлов append-only: `raw.jsonl`, `observations.jsonl`,
`interpretations.jsonl`, `actions.jsonl`, `results.jsonl`,
`experiences.jsonl`, `knowledge.jsonl`, `suggestions.jsonl`,
`evaluations.jsonl`.

Интерфейс-минимум (имена сохранить — используются ядром):
`append_raw/read_raw, append_observation/read_facts,
append_action/read_action, append_result/read_result,
append_experience/read_experience/read_experiences,
append_knowledge/read_knowledge/read_knowledge_versions/
read_knowledge_versions_all, append_suggestion/read_suggestions,
append_evaluation/read_evaluations`.
Частота чтений в ядре (по факту): read_experience (11×),
read_knowledge (6×), read_action (6×), read_knowledge_versions_all
(3×) — эти пути покрыть тестами round-trip первыми.

## 6. Migration points (существующее → core)

| Существующее | Target | Действие |
|---|---|---|
| storage/store.py (SQLite+экспорт) | storage/jsonl.py | перенос API 1:1, без sqlite |
| observer/observer.py + sensors.py | observer/local.py + env config | collect() сохранить; сенсоры → env.observe() |
| executor/executor.py | executor/local.py | execute() сохранить; allowlist → env.available_actions(); snapshot() → env.state() |
| experience.py / evaluation.py / knowledge.py | core/* | перенос как есть (сохранить сигнатуры) |
| strategy/strategy.py (494) | core/strategy.py + core/applicability.py + core/exploration.py | разложить `suggest()` → `decide()`; приватные `_tokens/_symptom_of/_ctx_extra_of/_addr_cmd_of/_relevant/_e2_history/_non_success` → applicability/strategy; `_observe_actions/_last_candidate_action/_aa1_outcome_is_success` → observability |
| strategy/exclusion.py (FilteredStore, GateModule) | core/applicability.py | убрать вызовы приватных функций strategy; публичный интерфейс |
| update/update.py (365) | core/update.py | `apply(store, experience_id, outcome)` сохранить; линия `_lineage_*` и `_acquire` — без изменений семантики |
| llm/adapter.py | llm/ollama.py + base.py | `propose/build_prompt` сохранить; провайдеры → конфиг |

## 7. Красные тесты (исторические; не регрессия механизма)

- `test_strategy.py` t1 — IndexError; **EF-11** (known expected
  mismatch; решение 11.09, D-6). В MVP: переписать под
  `decide()`-интерфейс; до переноса — xfail.
- `test_knowledge.py` K1a/K1c — знание пишется со схемой **0.3**,
  тест ожидает **0.2** (+ raw-факты). Долг тестового слоя.
- `test_update.py` U3 — то же schema-рассогласование 0.2/0.3.
- Решение: зафиксировать схему 0.3 и обновить ожидания тестов при
  переносе (не менять код ради старых тестов).

## 8. Где возможна регрессия

1. **E2-семантика**: 2 consecutive non-success *применений* (reject
   не считается) — покрыть тестом до переноса и после.
2. **ctx_extra → applicable_when**: исторический урок MM1 Run-1
   (действие без `ctx_extra` → `applicable_when` не создаётся →
   невалидная клетка). Инвариантный тест обязателен.
3. **exclusion POOL/TEMP**: двойное исключение (U5b boundary) — тест
   при развязке от strategy.
4. **append-only**: JSONL не должен терять версии knowledge
   (UP-миграции нет — и не будет).
5. **Simulator ≠ polygon**: world-специфика только в `examples/`;
   core не знает слов `tsasvc/fix-aq` (кроме demo-конфига).
6. **Runtime**: логика не прячется в runtime (только оркестрация).

## 9. Тестовые gates и порядок реализации

```text
Gate A (MVP-1A): schemas/ + storage/jsonl.py + core/{experience,
  knowledge, evaluation} + canned-LLM → цикл observe→update e2e
  на симуляторе-заглушке; два прогона детерминированы.
Gate B (MVP-1B): core/exploration.py + E2-signal в strategy →
  ET-1-сценарий: tried={start,restart} → remaining → выбор модели →
  fix-aq; «не повторяет tried», «вне remaining отклоняется».
Gate C (MVP-1C): examples/service_recovery (deterministic simulator)
  + observer/executor generic-config.
Gate D (MVP-1D): CLI run|history|knowledge; smoke-тесты.
Gate E (MVP-1E): demo: (1) exploration → fix-aq → K; (2) повторная
  задача → K-hit → 1 действие. README + e2e.
```

CI-инвариант: `grep -r "experiments" core/ llm/ executor/ observer/
storage/ runtime*` — пусто (research не течёт в core).

## 10. Минимальный путь до `examples/service_recovery`

1. `schemas/` (копия protocols) → 2. `storage/jsonl.py` + round-trip
тесты → 3. `core/{evaluation, experience, knowledge}` (перенос) →
4. `core/applicability.py` (развязка exclusion) → 5. `core/strategy.py`
(S1/S2/S3 + E2) → 6. `core/exploration.py` (ET-1) → 7. `executor/
local.py` + `observer/local.py` (+config) → 8. `examples/
service_recovery` → 9. `core/runtime.py` → 10. `llm/base.py` +
canned-stub → 11. `cli.py` → 12. README + demo (два запуска).

## 11. Открытые развилки (на слово)

1. Имя entrypoint: `core/runtime.py` (как в MVP-1A; рекомендую) vs
   `runtime/agent.py`.
2. LLM в публичном demo: **canned/deterministic stub** (рекомендую —
   zero-deps, воспроизводимо) vs живой Ollama-gemma4 по опции.
3. Симулятор: сохранить имена `fix-a/fix-aq` (доказательная
   преемственность; рекомендую) vs обезличенные действия.
4. Schema: зафиксировать **0.3** (рекомендую) и обновить тесты.
5. `suggestions` (observability-трасса) — оставить в core (рекомендую)
   vs убрать из MVP.

## 12. Что НЕ делаем

Не тащим `experiments/**`; не импортируем baselines; не добавляем
ranking/heuristics/embeddings/MC; aggregation — DEFER; SQLite — не в
MVP; web UI/replay — backlog. **Код не менялся.**
