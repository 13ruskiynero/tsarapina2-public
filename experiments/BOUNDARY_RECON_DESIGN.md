# BOUNDARY RECONNAISSANCE: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора внесён полностью:
OT-1 → **B ACCEPT** (fast pre-fill тем же production path без
LLM-proposal; `episode_mode = PREFILL_OPERATOR`; поведенческие
результаты pre-fill НЕ смешивать с LLM trajectory; confound
«pre-history is operator-generated rather than LLM-proposed» — не
устранять, а не притворяться, что его нет);
OT-2 → **Mixed pre-fill ACCEPT** (смесь линий; НЕ добавлять новую
семантику selection; НЕ раскладывать K_F/K_G по позициям под
границу; тот же production serialization/history pattern,
просто больше эпизодов);
OT-3 → окно: ~85/90/95% + B2b + 1/2/3; сохранить последние
LLM-эпизоды непосредственно перед B2b;
OT-4 → классы I-1..I-4 + **I-0** (B2b ≠ behavioral degradation);
OT-5 → одна серия r1; r2 только при effect/ambiguity (ambiguity —
тоже основание для r2);
S1/S2/S3 — строго раздельно; «выпавшие строки» НЕ реконструировать
(пишем «consistent with loss of some context information»);
D-selection-1 — не модифицировать; LONG-3 baseline — заморозить
как RECON-BASELINE (RECON1_BASELINE.txt; не пересчитывать).

## 1. Вопрос (FROZEN)

> **How does the observed Retrieval → Strategy → Proposal
> separation behave as provider context delivery approaches and
> crosses the known silent-truncation boundary?**

## 2. Серия и фазы

```
Серия: ПРОДОЛЖЕНИЕ LONG-3 r1 (тот же store, data_long3_r1) с
эпизода 75. Baseline N=1..75 — часть этой же серии.

Фаза PREFILL: эпизоды mode=PREFILL_OPERATOR (forced, без LLM):
  production path (env_set → executor → evaluation → experience →
  update), команды — фиксированное чередование [fix-a, fix-aq]
  (смесь двух valid-линий; без подгонки позиций под границу).
  Блоками; между блоками — PROBE (измерение counter).
Фаза LLM: обычные эпизоды (bridge, живой gemma3:4b) от ~84%
  утилизации до первого B2b, затем +3 эпизода; внутри — точки
  85/90/95% (естественно), последние ~3 перед B2b сохраняются.

PROBE: LLM-вызов (max_tokens=1) с текущим контекстом; фиксирует
counter/utilization; НЕ эпизод траектории (без действия и
knowledge).
```

## 3. Разделение S1/S2/S3 (FROZEN)

```
S1  полный context построен: context, context_source,
    strategy refs (от полного стора);
S2  фактическая доставка: counter, plateau-флаг, недоставлено
    ≈ counter_expected − counter (оценка, не реконструкция);
S3  proposal при фактически доставленном промпте.
Запрещено: «K_F был усечён» — не наблюдаемо. Максимум:
«provider delivery truncated; proposal changed — consistent with
loss of some context information».
```

## 4. Классы (FROZEN; I-0 добавлен)

```
I-0  no observable degradation: B2b наступил, proposal
     остаётся в baseline-вариативности (контроль; B2b ≠
     behavioral degradation);
I-1  delivery boundary без proposal effect (S2=B2b; S3≈baseline):
     граница есть — наблюдаемой behavioral consequence в данном
     тесте нет;
I-2  proposal divergence (S3 выходит из baseline pattern);
I-3  layer divergence (retrieval unchanged, strategy refs
     unchanged, proposal changed) — особенно важно для
     D-selection-1;
I-4  recovery after boundary (proposal возвращается к прежнему
     паттерну при дальнейшем накоплении) — не объяснять.
Малое окно у границы: классы — наблюдения, не статистика;
указывать размер окна в каждом выводе.
```

## 5. Три потенциальные картины (для отчёта)

```
A: до/после границы — retrieval ≠ selection ≠ proposal (то же):
   разрыв, вероятно, не зависит от context pressure в диапазоне.
B: около границы proposal резко меняется: delivery —
   потенциальный фактор proposal behavior.
C: линии теряются из доставленного prompt, proposal прежний:
   неполная доставка ≠ немедленная behavioral change.
```

## 6. Метрики

```
per-эпизод (все фазы): mode, counter, utilization, плато-флаг,
  context_source_n, strategy refs (какие линии), proposal,
  decision, evaluation; для LLM-фазы — S1/S2/S3 раздельно.
Окно: точки ~85/90/95%, последние 3 до B2b, B2b, +1/+2/+3.
Baseline: RECON-BASELINE (заморожен; proposal==top-ref 35/75,
  блоки 5/7/8/7/8; те же serializer/model/temperature/provider/
  Strategy/proposal contract/context construction).
```

## 7. Запреты

```
без изменений контекст-механизма/слоёв/strategy.py; D-selection-1
запрет в силе; не смешивать prefill и LLM trajectory в выводах;
не реконструировать выпавшие строки; не «доказывать B2b»;
baseline не пересчитывать; r2 — только при effect/ambiguity;
при B2b — не продолжать «до красивой картинки».
```

## 8. OT (закрыты 11.09)

```
OT-1 B ACCEPT; OT-2 mixed ACCEPT; OT-3 окно ACCEPT; OT-4 +I-0;
OT-5 r1-first (r2 при effect/ambiguity); baseline freeze ACCEPT.
```

## 9. Процедура

```
FROZEN (этот файл) → PROTOCOL (recon1/) → RECON-BASELINE
зафиксирован → recon1_driver.py (резюмируемый: --phase
prefill|llm) → recon1_analyze.py → RUN (prefill блоками, затем
LLM до B2b+3) → RECON1_ANALYSIS.txt → RECON1_REPORT.md →
решение — отдельным словом.
```

## 10. Артефакты

BOUNDARY_RECON_DESIGN.md (FROZEN), recon1/PROTOCOL.md,
recon1/RECON1_BASELINE.txt, recon1_driver.py, recon1_analyze.py,
RECON1_E*.json (+ probe-записи), RECON1_ANALYSIS.txt,
RECON1_REPORT.md. Слои и experimental-каталоги (кроме дописи
long3_r1 store и новых recon1-записей) не трогаются.

## 11. ПОПРАВКИ 11.09 (вердикт профессора после r1)

```
* Классификация: новый класс I-5 — proposal-channel collapse /
  output-budget starvation (НЕ I-2: Knowledge из входного
  контекста не терялась; отказ локализован в бюджете генерации).
* B2b: NOT OBSERVED (критерий не переписывать задним числом;
  STOP.txt по B2b не писался — верно).
* Новый mechanical boundary B5: output-budget starvation:
  prompt_tokens + completion_tokens = num_ctx AND required
  structured response cannot complete AND proposal channel
  produces structural failure AND no execution occurs.
  First event E489; stable E491+ (23/23).
* Equilibrium: proposal-channel starvation equilibrium
  (self-maintaining; не чинить до завершения r2).
* r2: обязательна, targeted: long3_r2 → prefill до ~0.94
  num_ctx → LLM до первого B5 + 5 → сравнение (first starvation
  ep; prompt/completion; raw signature; structural failure;
  execution count; Knowledge growth; equilibrium persistence).
* N≈404: статус — гипотетическая prompt-saturation boundary;
  не достигнута из-за более ранней output-budget boundary.
* Новый долг: D-context-2 (coupled input/output budget).
* Выход разведки: OUTPUT-BOUNDARY OBSERVED (не
  PROMPT-TRUNCATION BOUNDARY OBSERVED).
```
