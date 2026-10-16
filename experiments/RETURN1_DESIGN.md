# O3 / RETURN-TO-PREVIOUS-HYPOTHESIS: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора по OT внесён:
OT-1 ACCEPT (relevant again = envver→V1);
OT-2 MODIFY (ступенчатая классификация R0..R5; strategy_refs —
отдельное механическое наблюдение, НЕ доказательство влияния;
совместное присутствие ≠ причинность);
OT-3 ACCEPT (RETURN-NULL — обязательный counterfactual control;
формулировка «associated with», не causal proof);
OT-4 ACCEPT (механический PASS отделён от O3 behavioral outcome);
OT-5 ACCEPT (20 runs, без расширения; divergence r1/r2 —
результат).
Pre-FREEZE gate: **narrative-leakage** (§7) — внесён.

## 1. Вопрос

> **Can longitudinal externally stored Knowledge cause Tsarapina to
> return to a previously explored hypothesis when subsequent
> environmental conditions make that hypothesis relevant again?**

Фиксация: изменение proposal само по себе — НЕ обучение; R1-класс
не означает «выучено»; внутренние состояния Gemma не наблюдаемы.

## 2. Конструкции (FROZEN)

```
RETURN-K (r1/r2):
  E0  seed w1 V1: fix-a → SUCCESS        K1 (fix-a/success;
                                         aw={E:absent,V:1})
  E1  LLM  w2 V2: свободный эпизод       K2
  E2  LLM  w2 V2: свободный эпизод       K3
  E3  LLM  w2 V2: свободный эпизод       K4
  E4  LLM  w1 V1: условия снова совпадают с применимостью K1

RETURN-NULL (n1/n2): тот же эксперимент, кроме E0:
  E0' seed w2 V2: fix-a → PARTIAL        success-знания fix-a НЕТ
  E1'..E4' — среды/структура идентичны RETURN-K.
Ось различия: только наличие/отсутствие verified success K1.
```

«Relevant again» (OT-1): envver проходит 1 → 2,2,2 → 1; возврат
к значению применимости K1 — без новой семантики applicability.

## 3. Ступенчатая причинная классификация (OT-2, FROZEN)

```
R0  K1 существует с E0 и остаётся traceable (kid→exp→episode);
R1  K1 retrieved at E4 (K1 ∈ context_source(E4));
R2  K1 transported into E4 prompt (K1-строка в отправленном
    prompt-тексте; границей может быть truncation — см.
    D-context-1);
R3  proposal/action at E4 совместим с K1 (parsed action ==
    команда K1);
R4  permission passes (executor executed, не refused);
R5  verified consequence (evaluation outcome записан).

strategy_refs(E4) ∋ K1 — ОТДЕЛЬНОЕ механическое наблюдение
(не обязательное доказательство; Strategy может найти K1 и сам —
это applicability-серия, не O3).
Сохраняются ВСЕ уровни (высший достигнутый — отдельно), чтобы
классифицировать по месту обрыва.
```

## 4. Counterfactual control (OT-3, FROZEN)

```
На E4 сравнивается весь наблюдаемый путь RETURN-K vs RETURN-NULL:

  RETURN-K     RETURN-NULL    Интерпретация
  fix-a        не fix-a       evidence consistent with memory effect
  fix-a        fix-a          возврат неотделим от Gemma/default
                              context effect
  не fix-a     не fix-a       Knowledge транспортировано; behavioral
                              return не наблюдался
  не fix-a     fix-a          против ожидаемого; отрицательный
                              результат (сохраняем)

Формулировка результата уровня: «return behavior associated with
presence of prior verified Knowledge under the controlled
construction» — НЕ causal proof (2 реплики + 1 NULL-контроль =
controlled evidence, не идентификация внутренней причинности LLM).
```

## 5. Наблюдаемость (FROZEN)

```
Как LONG-3 + retrieval-поля:
  K1_kid; K1_first_seen (=0); R0..R5 (bool по эпизоду E4);
  context(E4) полный; context_source(E4) ∋ K1;
  strategy_before/after(E4) refs ∋ K1 (отдельное наблюдение);
  proposal (raw+parsed); permission; action; consequence;
  proposal_diff E1..E4; knowledge_diff; audit; r1/r2.
```

## 6. Критерии (OT-4, FROZEN)

```
Механический PASS (PROTOCOL PASS):
  M1  все 20 episode-записей полны; audit clean;
  M2  K1 создан только из verified success (в RETURN-K);
  M3  K1 старый: first_seen_episode=0; никаких E4-подмен;
  M4  retrieval/context/provenance/permission цепочки полностью
      восстановимы (R0..R5 — зафиксированы);
  M5  append-only/A1/Executor/Evaluation/Update/L-chain не
      нарушены;
  M6  r1/r2 сравниваются; расхождение фиксируется, не скрывается.

O3 outcome (отдельно от PASS):
  RETURN OBSERVED / RETURN NOT OBSERVED / RETURN AMBIGUOUS /
  RETURN COUNTERCONTROL
Возможен полноценный результат «PROTOCOL PASS / RETURN NOT
OBSERVED». proposal == fix-a НЕ является PASS-критерием.
```

## 7. Narrative-leakage gate (pre-FREEZE, добавлено)

> **E4 prompt construction MUST NOT contain an explicit marker
> that the environment has "returned", that K1 was previously
> successful, or that the agent should reconsider an earlier
> action, except insofar as this information is already
> mechanically present in the normal Knowledge serialization.**

Механически: E4-context строится ТЕМ ЖЕ build_context, что в
LONG-серии; анализатор дополнительно проверяет отсутствие
маркеров-фраз (список — §5 PROTOCOL). Драйвер сам сюжет не
рассказывает.

## 8. Запреты

```
никаких выводов об «обучении»/понимании модели; никаких
изменений контекст-механизма/strategy.py/слоёв; D-2/D-3/D-4/D-6/
EF-12/D-context-1 не открываются «заодно»; targeted boundary
(N≈400) — второй акт, после O3; пороги — не двигать; при
divergence r1/r2 — не «добирать» прогоны.
```

## 9. Числа (OT-5, FROZEN)

```
20 runs = 2 конструкции (K/NULL) × 2 реплики × 5 эпизодов
(E0..E4). Расширение не предусмотрено.
```

## 10. Процедура

```
FROZEN (этот файл) → PROTOCOL (return1/) → return1_driver.py →
return1_analyze.py → preflight → RUN 20 → RETURN1_ANALYSIS.txt →
RETURN1_REPORT.md → решение (targeted boundary / cross-series /
иное) — отдельным словом.
```

## 11. Артефакты

RETURN1_DESIGN.md (FROZEN), return1/PROTOCOL.md,
return1_driver.py, return1_analyze.py, RETURN1_E*_*.json (20),
RETURN1_ANALYSIS.txt, RETURN1_REPORT.md. Слои и experimental-
каталоги не трогаются.
