# RECON-1: PROTOCOL (FROZEN 11.09.2026)

База: BOUNDARY_RECON_DESIGN.md (FROZEN 11.09: OT-1→B, mixed
pre-fill, окно 85/90/95 + B2b +1..3, I-0..I-4, r1-first,
baseline freeze). Вопрос: поведение разрыва Retrieval → Strategy
→ Proposal при подходе к silent-truncation границе и её
пересечении.

## 1. Серия

```
recon1 = ПРОДОЛЖЕНИЕ LONG-3 r1: store data_long3_r1, эпизоды с
E75. Baseline (N=1..75) — заморожен: RECON1_BASELINE.txt
(sha256 всех 150 long3-записей; proposal==top-ref 35/75;
блоки 5/7/8/7/8; те же serializer/model/temperature=0/provider/
Strategy/proposal contract/context construction). Не
пересчитывать.
```

## 2. Фазы и режимы

```
PREFILL (mode=PREFILL_OPERATOR): forced-эпизоды, чередование
  [fix-a, fix-aq] (смесь линий; позиции НЕ подгоняются);
  production path; envver="1"; мир w1. Блоки по 60 эпизодов;
  после блока — PROBE.
LLM (mode=LLM): от ~84% утилизации (оценка по последнему
  PROBE) до первого B2b + 3 эпизода; bridge (живой gemma3:4b,
  temperature=0); при исполнении — обычный путь
  evaluation→experience→update.
PROBE (mode=PROBE): LLM-вызов max_tokens=1 с текущим контекстом;
  counter/utilization; НЕ эпизод; RECON1_probe<k>.json.
```

## 3. Детекторы

```
B2b: counter(n) ≤ counter(n−1) при context_chars(n) >
  context_chars(n−1); counter = prompt_eval_count or prompt_tokens.
STOP: первый B2b → ещё 3 LLM-эпизода (+1..+3) → стоп.
Аварийный B1 (K_store−K_context>0): стоп (не ожидается).
```

## 4. Регистрация

```
RECON1_E<k>_r1.json (k от 75): mode, world, envver,
  knowledge_state_before/after, context, context_source,
  strategy_before/after, llm{raw,parsed}, gates, decision,
  result, evaluation, knowledge_diff, proposal_diff,
  counter, utilization, plateau(B2b), provider_meta, audit.
probe-записи: {n_episodes_total, counter, utilization,
  context_chars}.
Окно-точки: ближайшие LLM-эпизоды к 85/90/95% (по counter);
  последние 3 до B2b; B2b; +1/+2/+3.
```

## 5. Классы (определения для анализа)

```
I-0  B2b наступил; proposal в baseline-вариативности;
I-1  delivery boundary без proposal effect (S2=B2b, S3≈baseline);
I-2  proposal divergence (S3 вне baseline pattern; окно мало —
     класс-наблюдение);
I-3  layer divergence (retrieval и strategy refs без изменений,
     proposal изменился) — в интересах D-selection-1;
I-4  recovery (после изменения proposal возвращается к паттерну
     при дальнейшем накоплении).
Baseline pattern: три режима {fix-a, restart, start}; доля
proposal==top-ref ~47% (окно мало — указывать n).
S1/S2/S3 раздельно; выпавшие строки НЕ реконструировать;
формулировка максимум: «consistent with loss of some context
information».
```

## 6. Запреты

```
D-selection-1 не модифицировать; prefill ≠ LLM trajectory
(в выводах раздельно); не реконструировать невидимое; baseline
не пересчитывать; r2 — только при effect/ambiguity; пороги не
двигать; при B2b не продолжать сверх +3.
```

## 7. Процедура

```
FROZEN (этот файл) → baseline зафиксирован → recon1_driver.py
(резюмируемый: --phase prefill --budget N | --phase llm
--upto-b2b) → recon1_analyze.py → RUN → RECON1_ANALYSIS.txt →
RECON1_REPORT.md → решение — отдельным словом.
```

## 8. Артефакты

recon1/PROTOCOL.md (этот файл), RECON1_BASELINE.txt,
recon1_driver.py, recon1_analyze.py, RECON1_E*.json,
RECON1_probe*.json, RECON1_ANALYSIS.txt, RECON1_REPORT.md.

## 9. ПОПРАВКИ 11.09 (вердикт после r1)

```
r1 результат: OUTPUT-BOUNDARY OBSERVED (I-5/B5; equilibrium);
B2b NOT OBSERVED. r2 — targeted: --series r2 (long3_r2),
prefill до ~0.94 num_ctx, LLM до первого B5 + 5; STOP-файл
теперь RECON1_STOP_<series>.txt (запись B5_output_starvation).
Детали и сравнение — RECON1_ANALYSIS.txt §11, RECON1_REPORT.md §6.
```
