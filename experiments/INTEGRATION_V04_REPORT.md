# TSARAPINA INTEGRATION GATE v0.4: ОТЧЁТ (06.09.2026)

Strategy v0.4 = v0.3 (contextual exploitation + insufficiency
routing) + applicability addressing (CA-1). Основной strategy.py
изменён по CA-1-дизайну; контур передаёт ctx_now (envfact-сенсор);
ctx_now=None → поведение v0.3 без изменений.

## 1. Изменения strategy.py (задокументированы)

1. `suggest(..., ctx_now=None)`: ctx_now — текущий наблюдаемый
   контекст применимости (extra present/absent);
2. `_ctx_extra_of(store, rec)`: контекст проверки знания по цепочке
   knowledge → опыт → последнее действие → args.ctx_extra; None —
   старое знание;
3. S2-эксплуатация exact-пула: при exact и ctx_now — eligible =
   знания с ctx==ctx_now плюс знания без ctx (legacy); eligible
   непуст → S2 (recency только внутри eligible; флаг
   context_filter_used=true ТОЛЬКО если фильтр реально отсеял
   кандидатов); eligible пуст → S3 (rule context_mismatch; цена —
   новый learn; НЕ exploration);
4. sug: поля ctx_now, context_filter_used, ctx_mismatch;
   strategy_version="0.4".
Знания без ctx не отбрасываются и не получают искусственный
контекст (T4e; filter off, rule known_fix, ctx знания None).

## 2. Гейт (11/11 PASS; GATE_V04_run2.txt)

- T1 reversed recency: ctx=absent → S2 fix-a (fix-a2 свежее);
- T2: ctx=present → S2 fix-a2;
- T3: чередование ×6 → 1 действие, filter=true;
- SWAP: S2 (модель не участвует); DET: идентичный suggestion_id;
- T4a: known A → 1 действие fix-a; T4b: AB → fix-ab;
- T4c: C → broad-гипотеза (partial) → exploration → перебор →
  fix-c (8 действий; SEB-механика цела); после: S2 fix-c;
- T4d: S3 объявленного конфликта сохранён;
- T4e: legacy-знание без ctx → S2 fix-a, ctx знания None, filter
  off (не отброшено, без искусственного контекста).

## 3. Регрессия

9/9 юнит-наборов (observer/experience/knowledge/strategy 19/19/
llm_adapter/executor/evaluation/update/aggregation) — зелёная на
v0.4. Knowledge API не менялся; Knowledge/Update/Experience не
тронуты; ctx не выводится из результата (наблюдаемый факт,
фиксируемый при проверке действия).

## 4. Вердикт

**Strategy v0.4 FROZEN = contextual exploitation + insufficiency
routing + applicability addressing.**

Адрес знания: (symptom, context) при наличии ctx-данных; legacy-
знания работают по v0.3. Единственное новое изменение поведения
объясняется (symptom, context) — reversed recency подтверждает,
что «бери последнее» больше не управляет выбором, когда контексты
различаются.

Ряд: R1 (где искать) → AGG-1 (как компактно хранить доказанное)
→ ES-1 (когда информации недостаточно) → CA-1 (какая информация
делает адресацию различимой) → v0.4 (адрес применимости в основе).
TRUST-1 / STALE-EXACT-1 — границы; GENERALIZATION-1 —
отрицательный результат.

**Следующий вопрос (по слову профессора): stale-знание — у
системы теперь есть адрес применимости (fix-a под ctx=absent),
а не только recency; возврат к stale-вопросу с новой адресацией —
кандидат в следующий эксперимент.**
