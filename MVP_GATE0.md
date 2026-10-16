# MVP-GATE-0: инвентаризация `lab/tsarapina` (рентген; код не менялся)

**Дата: 2026-09-16. Статус: GATE-0 READY (карта составлена; НИКАКИХ
изменений кода на этом шаге).** Задача: определить, какие текущие
компоненты переносятся в MVP, какие остаются research-only, какие
требуют переписывания, и как выглядит минимальный target runtime.

---

## 0. Факты

- Верхний уровень `lab/tsarapina`: `observer/`, `experience/`,
  `knowledge/`, `strategy/`, `llm/`, `executor/`, `evaluation/`,
  `update/`, `aggregation/`, `storage/`, `protocols/`, `tests/`,
  `experiments/` (89 подкаталогов), `README.md`.
- Общий вес: **278 МБ** (в основном — сторы/логи/данные
  экспериментов). Ядро (без experiments) — **2320 строк**:

```text
strategy/strategy.py        494
update/update.py            365
storage/store.py            238
strategy/exclusion.py       222
aggregation/aggregation.py  217
knowledge/knowledge.py      217
llm/adapter.py              165
executor/executor.py        154
evaluation/evaluation.py    115
observer/observer.py         68
experience/experience.py     65
```

- Мусор/осадок: пустой каталог `{observer,...}` (артефакт shell,
  сен 6); `tests/tmp_*` (рабочие сторы тестов); baselines
  `strategy_v04/v05/v06x_baseline.py`, `knowledge_v06_baseline.py`,
  `update_v06_baseline.py`, `strategy_v2.py`; `llm/diag_*.py`.
- `README.md` **устарел**: заявляет «код модулей не начат» —
  при том что пройдены этапы 1–9 и построен исследовательский
  контур v0.6.x+A1.

---

## 1. REUSE (переносится в MVP почти как есть)

- `protocols/*.schema.json` — 6 схем (fact / experience / knowledge /
  action / result / provenance) — **стандарт данных, база JSONL-формата**.
- `experience/experience.py` — сборка эпизодов, sha1-детерминизм,
  принцип «собирает, не объясняет».
- `knowledge/knowledge.py` — версии, retract / declare_conflict,
  provenance-обход.
- `evaluation/evaluation.py` — вердикт строго по фактам
  (success / failure / partial / no_change / not_executed / refused /
  unknown); чистая функция.
- `llm/adapter.py` — провайдеры (gemma4; extra_body), strict-JSON,
  структурный `ok=False`; привести к интерфейсу `LLM.propose(context)`.
- `executor/executor.py` — permission + allowlist + запрет
  метасимволов + refused-аудит + state_before/after; **allowlist → конфиг**.
- `observer/observer.py` — raw + fact + provenance (append-only);
  сенсоры вынести в дженерик.
- `storage/store.py` — append-only, raw отдельно от фактов;
  SQLite-ядро + JSONL-экспорт (см. §8 — формат MVP).

## 2. REFACTOR (переносится с переработкой)

- `strategy/strategy.py` (494) → `core/strategy.py` **+ выделить
  `core/exploration.py`**: принцип ET-1 (`tried/untried boundary +
  LLM choice`) в production **не выделен** — живёт как
  driver-level политика в экспериментах.
- `strategy/exclusion.py` (222) → core: развязать от приватных
  `_`-функций strategy (`_snapshot/_tokens/_relevant/_symptom_of/
  _ctx_extra_of/...`) — сейчас сильная связка.
- `update/update.py` (365) → `core/update.py`: оставить
  applicable_when-линию (L1–L6, ACQ-1), убрать исторический шум.
- `observer/sensors.py` → `observer/linux.py`: полигонные сенсоры
  (ssh / tsasvc / envver) → конфиг полигона
  `examples/service_recovery/`.
- `storage/` → `storage/jsonl.py` для MVP (см. §8).
- `tests/` → зелёный набор; известные FAIL: strategy t1 (EF-11,
  known expected mismatch), knowledge K1a/K1c, update U3 (schema
  0.2 vs 0.3).
- `README.md` → переписать под MVP.
- `aggregation/` (217) → **DEFER**: production-качество, но не
  входит в минимальный runtime MVP-1.

## 3. RESEARCH ONLY (остаётся в `experiments/`; в MVP-репо не тащить)

- `experiments/**` — 89 каталогов: драйверы (MM1, EE-1/2, MA1,
  RB1, SAF-1, MX-1, ET-1, …), сторы, логи, отчёты — **доказательство
  происхождения механизмов**.
- Frozen baselines: `strategy_v04/v05/v06x_baseline.py`,
  `knowledge_v06_baseline.py`, `update_v06_baseline.py`,
  `strategy_v2.py` (ветка RELEVANCE-1).
- Diagnostics: `llm/diag_qwen*.py`, `llm/diag_gemma4.py`,
  `llm/swap_check.py`.
- Полигонный инструментарий: `observer/polygon_sensor.py`,
  `tests/mini_ctxmismatch.py`,
  `experiments/applicability_addressing1/strategy_aa.py` (AA-1,
  не интегрирована).

## 4. REMOVE / DEPRECATE (цель для MVP-репо; лабораторию не трогаем)

- пустой каталог `{observer,...}` (артефакт);
- `tests/tmp_*` (временные сторы тестов);
- `__pycache__/` повсеместно;
- дубли baselines (см. §3) — в MVP-репо не попадают по определению.

## 5. Зависимости (карта)

```text
storage           ← observer, executor, update, knowledge,
                    aggregation, strategy (через API)
observer.sensors  ← executor (snapshot)
knowledge         ← update, aggregation
strategy          ← exclusion (приватные _-функции)   [!]
llm               ← никто из ядра (изолирован; только experiments)
evaluation        ← никто (чистая функция)
experience        ← никто (чистый build)
```

Проблемные связки: `exclusion → strategy(private)`;
`executor → observer.sensors` (полигон жёстко вшит).

## 6. Разрывы (чего нет для MVP)

1. **`runtime/agent.py` отсутствует**: оркестрация существует только
   в 89 драйверах; нет ни одного production-цикла
   OBSERVE → … → UPDATE.
2. **`core/exploration.py` отсутствует как модуль**: ET-1-принцип
   доказан, но не перенесён в код ядра.
3. Нет generic observer/executor config (allowlist и сенсоры —
   полигонные).
4. Нет CLI.
5. Нет `examples/service_recovery/`.
6. README не отражает реальность.

## 7. TARGET runtime (предложение) + маппинг

```text
Observer → Experience → Knowledge → Applicability → Boundary/Exploration
   → Strategy → LLM → Permission → Executor → Evaluation → Update ↺
```

| Существующее | Target | Класс |
|---|---|---|
| observer/observer.py + sensors.py | observer/linux.py + config | REFACTOR |
| experience/experience.py | core/experience.py | REUSE |
| knowledge/knowledge.py | core/knowledge.py | REUSE |
| update (aw-линия) + exclusion (eligibility) | core/applicability.py | REFACTOR |
| strategy.py (S1/S2/S3, E2) | core/strategy.py | REFACTOR |
| ET-1 принцип (driver-level) | core/exploration.py | **BUILD** |
| llm/adapter.py | llm/ollama.py (LLM.propose) | REUSE |
| executor/executor.py | executor/local.py + config | REUSE |
| evaluation/evaluation.py | core/evaluation.py | REUSE |
| update/update.py | core/update.py | REFACTOR |
| storage/store.py | storage/jsonl.py | REFACTOR |
| 89 драйверов experiments/ | runtime/agent.py | **BUILD** |
| protocols/*.schema.json | schemas/ | REUSE |

## 8. Решения на вход (на слово; код не менялся)

1. **Storage MVP:** JSONL-only (рекомендую — прозрачно, diffable,
   Git-friendly) vs текущий SQLite+экспорт.
2. **Где живёт E2:** signal в `core/strategy.py`, boundary+choice в
   `core/exploration.py` (рекомендую) vs всё в strategy.
3. **Сенсоры demo:** сервис-симулятор в
   `examples/service_recovery/` (на базе tsasvc-полигона).
4. **Aggregation:** DEFER после MVP-1 (не тащить).
5. **Интерфейс LLM:** `propose(context) -> Proposal` — зафиксировать
   как единственную точку (adapter уже почти так работает).

## 9. Статус

Код **не изменялся** (только чтение). Это рентген. Следующий шаг по
слову: **MVP-1 implementation plan → минимальный runtime → первый
публичный demo** (`examples/service_recovery`).
