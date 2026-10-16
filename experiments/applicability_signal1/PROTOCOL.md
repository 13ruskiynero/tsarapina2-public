# APPLICABILITY-SIGNAL-1: PROTOCOL (FROZEN 06.09.2026)

Измерительный протокол; дизайн: APPLICABILITY_SIGNAL1_DESIGN.md.
v0.5 и слои НЕ изменяются; measurement-only; кандидаты наблюдаются
только в измерении, в контур не вводятся.

**Кандидаты (чтение до действия, каждый эпизод):**
E = env_extra (sensor_envfact); V = envver (sensor_envver);
N = lock.n существует; D = /run/tsasvc.dbg существует;
P = /run/tsasvc.pulse содержимое (в C5 — два чтения с паузой);
S = symptom; L = cpu.load1 (непрерывный, RESEARCHABLE-заметка).
Эталоны (мир w1): E=absent, V=1, N=нет, D=нет, S=a.

**Серии (ground truth применимости fix-a):**
C1: w1×8 (T×8); C2: w1×3 → w2×5 (T,T,T,F,F,F,F,F; смена эп.4);
C3: w1×3, noise×1, w1×3, noise×1 (T×8; адресно применим всегда);
C4: w1×2, (a+dbg)×3, w1×3 (T×8); C5: w1×6 (T×6; pulse-запись
между чтениями). Каждая серия ×2 повтора (r1, r2). Эпизод: env →
чтение кандидатов → фиксированное fix-a через Executor (полный
канал; результат сохраняется; опыт/знания НЕ создаются).

**Метрики (по дельтам эпизодов t≥2):** F_delta = F_t != F_{t-1};
gt_delta = gt_t != gt_{t-1}; FP = F_delta & ~gt_delta;
FN = gt_delta & ~F_delta; consistency = (F_delta == gt_delta).
Пригоден: FP=0, FN=0, consistency=1.0 на всех сериях × повторах
и свойства 1–5, 7 по конструкции.

**Порядок анализа:** RAW → сверка ground truth → FP/FN/consistency
→ семь свойств → сравнение E/V/N/D/P/S → A/B/C. Никакой
интеграции в v0.5 по отдельной серии.

**Политика полигона:** /run/tsasvc.dbg (не lock.*, демон не
читает; декоративный); /run/tsasvc.pulse (пишется драйвером —
имитация внешнего писателя); envver файл (демон не читает);
N-чтение lock.n напрямую (только измерение). Политика заморожена
вместе с протоколом.

Артефакты: as1_driver.py, AS1_run.log, AS1_candidates.json,
as1_analyze.py, AS1_ANALYSIS.txt, APPLICABILITY_SIGNAL1_REPORT.md.
