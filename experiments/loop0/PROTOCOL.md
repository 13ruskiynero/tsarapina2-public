# LOOP-0: PROTOCOL (FROZEN 11.09.2026)

База: LOOP0_DESIGN.md (FROZEN 11.09; frozen question; fixed-список
F1–F10; PASS requires P1–P10; PASS does NOT require). Операция:
проверка замыкания петли. Среды/шаги — реализация рамки (см. §1);
числа: E0..E3 × r1/r2 = 8 runs (запись на эпизод).

## 1. Серия и среды

```
Серия r1 (и r2 — независимый свежий store):
  E0  seed:  среда w1 (a; позитив). Действие seed = fix-a
             (принудительно драйвером; НЕ через Gemma; Knowledge
             только через production path).
  E1  LLM:   среда w1; context = minimal frozen (§3 дизайна) с
             Knowledge из E0.
  E2  LLM:   среда шум (a+n: заявленное лечение не сработает) —
             повторное использование в изменившемся мире.
  E3  LLM:   среда w1 (возврат в позитив; persistence check).
```

Мир-переключатель: env_set(world, noise) с lock-файлами
(/run/tsasvc.*) — механика полигона, как в llm1_driver.

## 2. Эпизод (последовательность)

```
env_set(world); envver="1";
observer.collect (наблюдения, для experience);
strategy_before = strategy.suggest(store, task, ctx_now="absent",
                                   obs_now={"E":"absent","V":"1"});
snapshot_before (knowledge versions);
[E0] seed action fix-a (permitted=True) → executor.execute →
     evaluation → experience → update.apply;  mode="seed";
[E1..E3] context = build_context(store, prev_episode) (§3);
     bridge.invoke(task, context, grant=True, provider="gemma") —
     живой вызов; mode="llm";
snapshot_after; knowledge_diff = diff(snapshot_before, after);
strategy_after = strategy.suggest(...) (для следующего эпизода);
запись LOOP0_E<k>_<r>.json (episode record, §4).
```

## 3. build_context (механически; minimal frozen)

```
text:
  "Текущая задача: tsasvc.service inactive symptom=a"
  "Предыдущий эпизод: <команда> → <исход>"
  "Известные результаты (линия fix-a):" затем по строке на знание:
  "  <команда> → <исход>";
набор знаний: все latest-члены линии L=(a,absent,fix-a) из store
(механически: strategy._addr_cmd_of — адресация v0.6.x+A1),
исход — из context записи (outcome=...);
context_source = [kid...] (в record; Gemma не видит);
НИКАКИХ kid/gen/provenance/strategy-деталей в текст.
Для E1 "Предыдущий эпизод" = seed (fix-a → success).
```

## 4. Episode record (append-only; полная наблюдаемость)

```
series, ep (0..3), mode (seed|llm), world, envver, episode_id;
observed: observer-факты (extract: E/V/locks);
strategy_before (strategy_id, knowledge_refs);
context (полный текст) + context_source (kid list);
llm: provider, raw, parsed (ok/action/arguments), llm_error;
gates (G-a..G-d), decision, no_action_reason;
action (если есть), result (result_id/refused/exit/stderr);
evaluation (outcome) — из production-пути;
experience_id; update (created_knowledge_id; результат apply);
knowledge_diff: added[] / changed[] / retracted[] / conflicted[] /
  restored[]  (kid + ключевые поля: outcome, aw, obs-типы,
  experience_refs, lineage_generation, status);
strategy_after (strategy_id, knowledge_refs);
proposal_diff (для N-эпизода vs N-1: changed true/false,
  fields_changed) — OBSERVATION;
audit_before / audit_after (слои; sha).
```

## 5. Проверки (analyzer; P1–P10 дизайна + инвариант §4 дизайна)

```
A1  E0: mode=seed; outcome=success; added ≥ 1 (K1); K1 →
    experience_refs → experience (E0) → result → action (seed).
A2  Транспорт: context_source(E1) ∋ K1 (added в E0); для E2/E3:
    context_source(N+1) ∋ минимум один kid, существовавший после
    N (механически: kid ∈ store-состояние после N).
A3  strategy_before(N+1) фиксирует состояние после N (refs/
    strategy_id согласованы с состоянием store).
A4  Context(N+1) содержит строку prev-эпизода; текст не содержит
    kid/provenance (проверка: ни один kid из context_source не
    встречается в тексте context).
A5  Каждый added/changed kid: experience_refs → experience →
    эпизод (mechanical invariant, обе стороны).
A6  Ворота: если decision=executed → gates все ok и result без
    refused; если no_action → fail closed (reason из G-a..G-d);
    ни одного обхода (executed только через executor).
A7  audit чистый в каждом эпизоде; записи append-only (episode_id
    уникальны; серии не перезаписывают друг друга).
A8  r1 ≡ r2: структурные поля (mode, world, decision, executed,
    gates, strategy_id, diff-counts, context_has_prev=true) —
    детерминированы; raw/proposal — observation.
A9  proposal_diff сохранён для E1..E3 (observation; вердикт не
    зависит).
```

## 6. PASS/FAIL

PASS = A1–A9 (и, следовательно, P1–P10 дизайна).
FAIL-классификация: механизм (нарушен инвариант) vs observation
(иные raw/proposal) vs execution finding (ошибка регистрации).
Числа: 8 runs; расширений нет.

## 7. Процедура

```
FROZEN (этот файл) → loop0_driver.py + loop0_analyze.py →
preflight (seed-эпизод + E1 live smoke) → RUN 8 → LOOP0_ANALYSIS
→ LOOP0_REPORT.md → longitudinal — отдельным словом.
```

## 8. Артефакты

loop0/PROTOCOL.md (этот файл), loop0_driver.py, loop0_analyze.py,
LOOP0_E*_r*.json (8), LOOP0_ANALYSIS.txt, LOOP0_REPORT.md.
Слои и experimental-каталоги не трогаются.
