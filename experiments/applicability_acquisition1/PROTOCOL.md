# TSARAPINA APPLICABILITY-ACQUISITION-1 (ACQ-1): A0 PROTOCOL (FROZEN 07.09.2026)

База: APPLICABILITY_ACQUISITION1_DESIGN.md (FROZEN 07.09; разделы 2, 4,
10). Этап: **A0 read-only recorder**, реплики r1/r2, cross-check,
анализ. A1/A2/A3 — ТОЛЬКО после подтверждения A0-механики (слово
профессора). v0.5 и слои не изменяются.

## 1. Вопрос A0

Что текущий learn РЕАЛЬНО записывает в адрес/Knowledge на learn-
моментах? Эмпирическая проверка фактов 1-4 раздела 2 DESIGN.

## 2. Learn-последовательность (на реплику)

```
w1 ×2, затем wY ×2     (verified-success демонстрации; порядок и
                        состав — решение 1 DESIGN, раздел 8)
```

Каждый learn-момент — КАНОНИЧЕСКИЙ v0.5-путь (cs1_driver.learn,
with_ctx=True — текущая CA-1-адресация), байт-в-байт:
1. env_set(world): systemctl stop tsasvc, сброс /run/tsasvc.lock.*,
   флаги мира, /run/tsasvc.envver, reset-failed;
2. problem = "tsasvc.service inactive symptom=<S>" (S из sensor_symptom);
3. facts = observer.collect(store) — наблюдения ДО действия;
4. действие fix-a с args.ctx_extra = sensor_envfact (оператор
   записывает E — как в v0.5-цикле);
5. executor.execute → stable_active → evaluation.evaluate;
6. experience.build/save → update.apply(outcome) → Knowledge-запись.

Регистратор добавляет ТОЛЬКО чтение: сигналы E/V/S до действия,
состав Knowledge-записей и производный адрес после каждого момента.

## 3. Read-only гарантии

- контур: world → Observer → существующий learn → recorder;
- recorder не вызывает knowledge.create / update.apply вне
  канонического learn-пути (шаг 6 — штатное создание знания);
- нет записи в Knowledge/Strategy, нет applicable_when, нет новых
  правил, нет контекста сверх v0.5;
- audit: sha256 слоёв (strategy, update, knowledge, experience,
  executor, evaluation, observer, polygon_sensor, storage.store) ДО и
  ПОСЛЕ прогона → ACQ0_audit.txt (совпадение обязательно);
- assert на каждый созданный Knowledge: полей applicable_when/
  condition нет.

## 4. Запись (ACQ0_records.json)

На каждый learn-момент (rep, idx, world):
- signals: E, V, S (значения ДО действия);
- ok, outcome (вердикт контура);
- facts: count + (subject, property, value, source, raw_ref);
- созданное знание: knowledge_id, fields (список полей записи),
  has_applicable_when, source/observer, content, context,
  experience_refs, derived_addr = strategy._addr_cmd_of
  (symptom-sorted, ctx, command) — производный адрес, без записи.

## 5. Cross-check r1 ↔ r2

Нормализация (uuid/timestamps/history/raw_ref) → записи реплик
должны быть идентичны (детерминированный полигон).

## 6. Анализ (acq0_analyze.py → ACQ0_ANALYSIS.txt)

Сверка с фактами раздела 2 DESIGN:
- ф1: Knowledge-запись НЕ содержит applicable_when/condition;
- ф2: content детерминирован update.apply (паттерн «действие …
  перевело …» / «НЕ перевело …»);
- ф3: адрес НЕ хранится, вычисляется (derived_addr из опыта/args);
- ф4: в адресе S и E; V (envver) нигде не фиксируется;
- оператор выбирает E: ctx_extra в args == E на learn-моменте.
Расхождение с моделью кода НЕ чинится — фиксируется как результат
(расхождение модели системы и системы).

## 7. Артефакты

PROTOCOL.md (этот файл, FROZEN), acq0_recorder.py, acq0_analyze.py,
ACQ0_run.log, ACQ0_records.json, ACQ0_audit.txt, ACQ0_ANALYSIS.txt.
Слои и Strategy v0.5 не изменяются.
