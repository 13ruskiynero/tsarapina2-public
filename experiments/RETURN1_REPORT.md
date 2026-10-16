# RETURN-1 / O3: ОТЧЁТ (11.09.2026)

**Статус: PROTOCOL PASS / RETURN OBSERVED → CLOSED (вердикт
профессора, 11.09)** (20 runs; M1–M6 без нарушений;
narrative-leak чисто; r1 ≡ r2 полностью).

Вклад в лестницу (формулировка профессора): Knowledge теперь не
просто «растёт вверх по списку» — RETURN-1 добавил **условный
возврат** (повторное использование старого знания после периода,
в котором оно не было актуально):

```
verified success → persistent K1 → environment changes →
K1 temporarily irrelevant → environment returns → K1 retrieved →
proposal returns to K1's action → verified success
```

Следующая ступень: **COMPETE-1** (конкуренция двух verified-
success линий; выбор — следующий вопрос). Boundary N≈404 — не
трогается; после COMPETE-1 он получит доп. смысл (деградация
transport-слоя × конкуренция).

Вопрос:

> **Can longitudinal externally stored Knowledge cause Tsarapina to
> return to a previously explored hypothesis when subsequent
> environmental conditions make that hypothesis relevant again?**

Ответ (уровень формулировки): **return behavior associated with
the presence of prior verified Knowledge under the controlled
construction** — в обеих репликах RETURN-K вернулись к fix-a в
момент возврата условий, а RETURN-NULL — нет. Это controlled
evidence, не causal proof.

## 1. Траектории (идентичны между репликами)

```
RETURN-K (K_r1 = K_r2):
  E0 w1/V1: fix-a (seed) → SUCCESS        K1
  E1 w2/V2: start        → partial
  E2 w2/V2: fix-a        → partial
  E3 w2/V2: restart      → partial
  E4 w1/V1: fix-a        → SUCCESS        ← возврат

RETURN-NULL (N_r1 = N_r2):
  E0 w2/V2: fix-a (seed) → partial        (success-знания НЕТ)
  E1 w2/V2: restart      → partial
  E2 w2/V2: fix-a        → partial
  E3 w2/V2: start        → partial
  E4 w1/V1: restart      → partial        ← возврата нет
```

## 2. R-лестница (E4, RETURN-K; обе реплики)

```
R0 True  K1 traceable (kid→exp→episode)
R1 True  K1 ∈ context_source(E4)
R2 True  K1-строка в отправленном prompt-тексте
R3 True  proposal(E4) == fix-a (команда K1)
R4 True  permission passed (executed)
R5 True  verified consequence (success)
strategy_ref_hit True — ОТДЕЛЬНОЕ наблюдение (Strategy тоже
выбрал K1 при V=1; не входит в доказательство памяти).
```

## 3. Counterfactual (главная таблица)

```
пара r1: K=fix-a / NULL=restart → evidence consistent with
         memory effect (associated with prior verified Knowledge)
пара r2: K=fix-a / NULL=restart → то же
NULL-контроль чист: fix-a/success знаний в N-сторах нет.
```

## 4. M-проверки

```
M1  записи полны; audit 20/20 — ок;
M2  K1 — только из verified success (K); N — без success — ок;
M3  first_seen(K1)=0; пересозданий нет — ок;
M4  R0..R5 зафиксированы для E4 всех серий — ок;
M5  append-only / L-chain / A1 / executor / evaluation / update —
    нарушений нет;
M6  r1/r2 сопоставлены (полная идентичность) — ок.
```

## 5. Наблюдения

```
O1  Обе конструкции в E1..E3 «пробовали» разные действия при
    V=2 (fix-a/start/restart; все partial) — поведение в фазе
    расхождения похоже; РАЗЛИЧИЕ возникает ровно на E4.
O2  Реплики идентичны по ВСЕМ 4 сериям (включая выборы модели) —
    replication чист.
O3  K1 при V=2 не выбирался Strategy (aw={E,V1}), но оставался
    транспортированным в контексте; на E4 (V=1) K1 стал
    применимым — strategy_ref_hit=True (наблюдение).
```

## 6. Ограничения

```
* 2 реплики; одна модель (gemma3:4b);
* command-совпадение (не semantic provenance);
* «associated with» ≠ causal identification внутренней
  причинности LLM;
* E4-среда w1/V1: K1 применимо по aw — механическая часть
  цепочки известна (strategy-наблюдение), вклад Gemma не
  изолируем и не заявляется.
```

## 7. Whiteboard

```
RETURN-1 establishes:
  return behavior associated with prior verified Knowledge under
  the controlled construction (обе реплики);
  полная R-цепочка (R0..R5) восстановима для E4;
  NULL-контроль: без K1 возврат не наблюдался (restart/partial).
RETURN-1 does NOT establish:
  causal proof / «модель поняла» / обучение;
  generalization на другие гипотезы и среды;
  поведение при нескольких конкурирующих старых знаниях.
```

## 8. Дальше (по слову)

```
Варианты: targeted boundary-прогон (N≈404; второй акт);
cross-series persistence; конкуренция старых знаний (два
success-знания разных линий — какой выбирается при возврате);
или пауза-обобщение. Ни одно не решается здесь.
```

## 9. Артефакты

```
return1/PROTOCOL.md (FROZEN), return1_driver.py, return1_analyze.py,
RETURN1_E0..E4_{K_r1,K_r2,N_r1,N_r2}.json (20),
RETURN1_ANALYSIS.txt, RETURN1_DESIGN.md (FROZEN). Слои не
изменялись (audit 20/20).
```
