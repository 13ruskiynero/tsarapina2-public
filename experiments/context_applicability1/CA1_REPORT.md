# TSARAPINA CONTEXT-APPLICABILITY-1 (CA-1): ОТЧЁТ (06.09.2026)

Дизайн: CONTEXT_APPLICABILITY1_DESIGN.md (frozen). Ветка:
context_applicability1/ (strategy_v6.py; основная Strategy v0.3 НЕ
изменялась). Порядок: журнал (CA1_run.txt, CA1_run.log — сырые
траектории) → вердикт. Регрессия 9/9 — зелёная.

## 1. Сырые траектории (ключевые строки)

```
L1 LEARN a fix-a  ctx=absent  ok     (K1)
L2 LEARN a fix-a2 ctx=present ok     (K2; учили ПОЗЖЕ K1)
T1 SUGGEST S2 cmd=fix-a  ctx=absent  rule=known_fix_context
T1 EPISODE S2 fix-a success           ← перевёртыш: свежайший fix-a2 НЕ выбран
T2 SUGGEST S2 cmd=fix-a2 ctx=present  → success
T3 6/6: absent→fix-a, present→fix-a2, 1 действие каждый раз
SWAP: S2 fix-a (знание, модель не участвует)
DET: повторный suggest идентичен
T4a known A: S2 fix-a (1 действие)
T4b AB: S2 fix-ab
T4c C: гипотеза fix-b (partial) → EXPLORATION_GRANTED → перебор
     (start/restart/fix-a/fix-b/fix-ab/fix-a2 — failure) → fix-c success
     (8 действий; SEB-механика сохранена); C после: S2 fix-c
T4d S3: объявленный конфликт (два знания ОДНОГО ctx) → S3 сохранён
```

Во всех контекстных выборах context_filter_used=true.

## 2. Вердикт: PASS

Формулировка (по протоколу):

> Контекст применимости может использоваться как часть адреса
> проверенного знания, позволяя выбрать правильный exact-кандидат
> независимо от его recency.

Проверено:
- T1 (recency-перевёртыш): K2 (fix-a2) учили ПОЗЖЕ K1, но при
  ctx=absent выбран fix-a — recency НЕ управляет выбором при
  различающихся контекстах;
- T2/T3: выбор по паре (symptom, context) — 6/6 чередований по
  1 действию, без залипания на свежайшем;
- T4 (старые свойства v0.3 не разрушены): known A, AB, C→
  exploration (SEB intact), S3-конфликт, swap, determinism — все
  PASS; знания без ctx (старые) продолжают работать (не
  фильтруются);
- регрессия 9/9 юнит-наборов.

**Первый чистый эксперимент, где новая структура метаданных
памяти (условие проверки) меняет выбор поведения, не меняя
содержимое знания, его provenance или веса модели.**

Границы сохранены: Knowledge API не менялся; ctx не выводился из
результата (фиксировался как наблюдаемый факт среды при проверке
действия); «нет пригодного exact → S3» (не exploration) — в CA-1
не проверялся отдельным сценарием (ветка существует в v6: rule
context_mismatch; цена — новый learn; stale-recovery остаётся
вопросом STALE-EXACT-1/ES-1-маршрута, здесь не смешивался).

## 3. Артефакты

CONTEXT_APPLICABILITY1_DESIGN.md (frozen), context_applicability1/
strategy_v6.py, ca1_driver.py, CA1_run.txt, CA1_run.log,
CA1_REPORT.md (этот файл). Основная Strategy v0.3 и слои не
изменены; полигон: extra наблюдаем envfact (политика E1/CA-1).

**CA-1: PASS. Вопрос интеграции v6 в основную Strategy (адрес
(symptom, context) вместо recency при наличии ctx-данных) — по
решению профессора.**
