# TSARAPINA INTEGRATION V0.5: ОТЧЁТ (06.09.2026)

**Strategy v0.5 = v0.4 (contextual exploitation + insufficiency
routing + applicability addressing) + transition event E2** (TE-1):
2-й последовательный non-success того же (адрес, команда) в истории
знаний → suggestion получает exploration=True (право искать).
Событие НЕ объявляет знание устаревшим и НЕ меняет выбор/кандидата:
оно только даёт право перейти к поиску; routing не-success = failure
И partial; счёт адресно-командный (M4: разные команды не
суммируются; successes сбрасывают серию).

Baseline: strategy/strategy_v04_baseline.py (копия v0.4; артефакт
сравнения; не импортируется). Основной strategy.py = v0.5
(def suggest: strategy_version "0.5"; E2-пост-обработка в S2-пути).

## Гейт (эксперименты/gate_v05.py)

**Часть A — полный набор v0.4 на v0.5: 11/11 PASS**
T1 ctx=absent → fix-a (reversed recency); T2 ctx=present → fix-a2;
T3 6/6; SWAP; DET (v0.5); T4a known A; T4b AB; T4c C SEB (8
действ.); T4c2 S2 fix-c; T4d S3; T4e legacy (без ctx — не
отброшено, без искусственного контекста).

**Часть B — TE-часть на основной v0.5: 14/14 PASS**
- base: KNOWN 1 действие; AB; SEBC exploration → ok (≥5); SEBC2 S2 1
  действие; S3 сохранён без события; DET идентичен;
- STALE: событие E2 произошло (2-й w2-f), перебор → fix-aq;
  последующие 2 эпизода: S2 по 1 действию;
- SINGLE 0 переходов; ALT 0; DOUBLE 1 (ложный на 3-м эпизоде, цена
  +2, знание цело: следующий эпизод ok); MIX 1 (только 3-й w2-f);
- M4: fix-a 1f + fix-b 1f → события НЕТ (адресно-командный счёт).

**Регрессия: юнит-наборы 9/9 зелёные** (observer/experience/
knowledge/strategy/llm_adapter/executor/evaluation/update/
aggregation).

## Вердикт

Интеграция v0.5 выполнена по гейту профессора: v0.4-поведение
сохранено (часть A), переходы работают на основной стратегии
(часть B). Стратегия заморожена как v0.5; v0.4 сохранён как
baseline для сравнения (strategy_v04_baseline.py). Контур:
contextual S2 → действие → последствие → история (второе same-
событие) → TE-transition → exploration → проверенное последствие →
learn → S2.

## Артефакты

strategy/strategy.py (v0.5), strategy/strategy_v04_baseline.py (v0.4),
experiments/gate_v05.py, GATE_V05_runA.txt (11/11),
GATE_V05_runB.txt (14/14), gate_v05_data/GATE_V05_te.log;
experiments/transition_event1/ (ветка TE-1: TRANSITION_EVENT1_DESIGN,
strategy_v7.py, te1_driver.py, TE1_REPORT.md, TE1_*_run*.txt —
артефакты ветки).
