# RESOURCE-RESPONSE-1: PROTOCOL (FROZEN 11.09.2026)

База: RESOURCE_RESPONSE1_DESIGN.md (FROZEN 11.09; поправки 1–4
внесены). Read-only реплей; store/executor/слои не мутируются.
Изменения кода — нет (используются публичные функции adapter как
есть; max_tokens фиксирован как production, НЕ варьируется).

## 1. Стенд: контексты (заморожены ДО прогона)

```
NORMAL   = recon1/RECON1_E507_r2.json   (B_available = 189; > 140)
MARGINAL = recon1/RECON1_E513_r2.json   (B_available = 129;
           ∈ (120,140); ближайшая к mid-point 130 среди всех
           записей обеих серий: |129−130| = 1)
STARVED  = recon1/RECON1_E513_r1.json   (B_available = 113; ≤ 120)
Правила выбора — DESIGN §3/§7; записей задним числом не создаём.
```

## 2. Матрица

```
{policies: R0, R1} × {states: NORMAL, MARGINAL, STARVED} ×
{reps: r1, r2} = 12 runs.  Клетка: --cell "R1|STARVED|r1".
НЕ расширять автоматически; R0 ≡ R1 — валидный отрицательный
результат.
```

## 3. Прогон клетки (механика)

```
1. sha256(source record) ДО; контекст из записи;
   prompt = adapter.build_prompt(PROBLEM, ctx);
   context_hash = sha256(сериализованного контекста);
   K-set = context_source(kid) записи; K_hash = sha256(sorted K-set);
2. вызов: adapter.chat(url, model, prompt, max_tokens=300,
   with_meta=True)  # 300 = production-значение (propose default);
   temp=0 (production);
3. parsed = adapter.parse_json+validate → valid | invalid;
   P = prompt_tokens, C = completion_tokens (метаданные);
4. D1 = (P + C >= 4096) AND invalid        # B5 присутствует
   D2 = D1                                  # детектор по правилу
   D3 = «в NORMAL детектор молчит»: state==NORMAL → D2==False;
        иначе фиксируется как есть;
5. policy:
   R0: event = "starvation_no_action" if D2 else "none";
       halted=False; loop_available=True;
   R1: event = "resource_impossible" if D2 else "none";
       halted=D2; (no retry; no executor; no recovery);
6. action=0; executor_invocations=0; retry=False;
7. sha(source record) ПОСЛЕ; context_hash ПОСЛЕ; K_hash ПОСЛЕ;
8. checks: K_after=K_before; context unchanged; source unchanged;
   executor_invocations==0; D3-контроль; MISS-контроль
   (не-NORMAL → D2 == D1).
```

## 4. Запись клетки (RR1_<policy>_<state>_<rep>.json)

```
cell, policy, state, rep, source_record, B_available,
prompt_tokens, completion_tokens, window=4096, valid/invalid,
raw_tail, D1, D2, D3, event, halted, loop_available,
action=0, executor_invocations=0, retry=False,
hashes: source_sha_before/after, context_hash_before/after,
K_hash_before/after, checks{...}, ts.
```

## 5. Стоп-условия (действуют в прогоне)

```
S1 изменение knowledge при detection/recovery → стоп, FAIL;
S2 implicit fallback (action при invalid) → стоп, FAIL;
S3 R0 ≡ R1 → фиксируется (не расширять автоматически);
S4 любое «улучшение» по ходу → стоп.
```

## 6. Preflight и процедура

```
preflight: 1 клетка (R1|STARVED|r1) — проверить, что invalid
воспроизводится, поля и hashes заполняются.
Затем: полная матрица 12 → RR1_ANALYSIS.txt (детерминизм,
D1/D2/D3 по клеткам, R0/R1-сравнение, checks, стоп-условия) →
RESOURCE_RESPONSE1_REPORT.md. R2/R4 — отдельным словом.
```

## 7. Артефакты

```
resource_response1/PROTOCOL.md (этот файл), rr1_driver.py,
RR1_*.json (12), RR1_ANALYSIS.txt,
RESOURCE_RESPONSE1_REPORT.md. Слои/store/записи recon1 и long3
не трогаются (read-only).
```
