#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — шаблоны промптов фаз F1–F4 (этап подготовки; офлайн).

По образцу T0: компактная инструкция, строгий машиночитаемый формат ответа,
данные — отдельными секциями. Состав контекста — по акту `K0_CONTEXT_ACT.md`
(таблица видимости): F1/F3 — история + 9 клеток батареи; F2 — история +
наблюдения + отказы + бюджет + последняя проба + эхо меток + память M1;
F3/F4 — плюс наблюдения и память M1.

Подсказки о внутреннем правиле мира запрещены: статические тексты
(`static_text()`) проверяются лексикон-аудитом `lexicon_findings()` — ни
одна запрещённая формулировка не должна присутствовать.

Промпт НЕ включает серверную обёртку чат-шаблона: её добавляет транспорт
целевой модели. Целевой бюджет ≤4000 токенов (C1=4096); измерение —
`measure_prompts.py` (метод T0 evidence-2, `llama-tokenize`).
"""
from __future__ import annotations

WORLD_TEXT = (
    "Ты — агент в лаборатории незнакомого объектного мира.\n"
    "Мир: объекты O1–O4. Клетка задаётся объектом и двумя параметрами T и H\n"
    "(целые числа 0..2) и записывается так: O<k> T=<t> H=<h>.\n"
    "Исход клетки: present или disappeared.\n"
    "Отвечай строго в заданном формате: каждая строка ответа — одна\n"
    "конструкция из списка допустимых; пояснительные строки недопустимы."
)

F1_HEAD = "[ФАЗА 1: предварительные предсказания — пробы ещё не делались]"
F3_HEAD = "[ФАЗА 3: повторные предсказания — после фазы проб]"
F4_HEAD = "[ФАЗА 4: итог]"

HIST_HEAD = "[ИСТОРИЯ НАБЛЮДЕНИЙ] (trial_id: запись; m — видимая метка)"
BATT_HEAD = "[БАТАРЕЯ: 9 клеток — предсказать каждую]"
OBS_HEAD = "[ТВОИ НАБЛЮДЕНИЯ (исполненные пробы)]"
REJ_HEAD = "[ОТКАЗЫ ПОСЛЕДНИХ ДЕЙСТВИЙ]"
NOTE_HEAD = "[ПАМЯТЬ — ТВОИ ЗАМЕТКИ (порядок записи)]"
LABELS_HEAD = ("[МЕТКИ] зарегистрировано: Q={q}, H={h}, P={p}, V={v}. "
               "Новый номер Q/H = последний + 1.")

F1_TASK = ("[ЗАДАЧА] Предскажи исход для каждой из этих 9 клеток.\n"
           "[ФОРМАТ ОТВЕТА] Ровно 9 строк (по одной на каждую клетку, порядок любой):\n"
           "PREDICT: <объект> T=<t> H=<h> = <present|disappeared>\n"
           "Другие строки недопустимы.")
F3_TASK = ("[ЗАДАЧА] Снова предскажи исход для каждой из этих 9 клеток.\n"
           "[ФОРМАТ ОТВЕТА] Ровно 9 строк (по одной на каждую клетку, порядок любой):\n"
           "PREDICT: <объект> T=<t> H=<h> = <present|disappeared>\n"
           "Другие строки недопустимы.")
F4_TASK = ("[ЗАДАЧА] Сформулируй итоговую закономерность этого мира одним\n"
           "предложением; если она пока не установлена — так и укажи.\n"
           "[ФОРМАТ ОТВЕТА] Ровно одна строка:\n"
           "FINAL: <текст>\n"
           "Другие строки недопустимы.")

F2_HEAD = "[ФАЗА 2: фаза проб — управляй экспериментом]"
F2_SCOPE = ("[ОБЛАСТЬ ПРОБ] объекты O1–O4; параметры T и H: целые 0..2.\n"
            "Бюджет: {budget} проб (каждая проба / repeat / reset расходует 1).")
F2_ACTIONS = (
    "[ДОПУСТИМЫЕ СТРОКИ]\n"
    "QUESTION Q<n>: <вопрос> REF: <trial_id>\n"
    "HYPOTHESIS H<n> OF Q<m>: <описание> PREDICT: <объект> T=<t> H=<h> = <present|disappeared>\n"
    "PREDICT: <объект> T=<t> H=<h> = <present|disappeared>\n"
    "ACTION: probe <объект> T=<t> H=<h>\n"
    "ACTION: repeat\n"
    "ACTION: reset\n"
    "ACTION: probe <объект> T=<t> H=<h> DISTINGUISH: H<i>,H<j>\n"
    "DECISION: <дескриптор как в ACTION> USING V<n>\n"
    "VERDICT: H<n> supported AFTER P<n>\n"
    "VERDICT: H<n> refuted AFTER P<n>\n"
    "REJECTED: H<n> REASON: <текст>\n"
    "NOTE: <текст до 300 знаков>\n"
    "[ПРАВИЛА]\n"
    "1. Перед ACTION: probe укажи PREDICT — прогноз исхода этой же клетки;\n"
    "PREDICT и ACTION — две ОТДЕЛЬНЫЕ строки (сначала PREDICT, затем\n"
    "ACTION); объединять их в одну строку недопустимо.\n"
    "2. repeat — та же клетка, что в последней пробе; в PREDICT укажи именно её.\n"
    "3. reset — сброс среды без PREDICT.\n"
    "4. Результат исполненной пробы становится доступен тебе в следующих\n"
    "   вызовах; отклонённый блок исполнения не получает и бюджет не тратит.\n"
    "5. Ссылки: REF — только trial_id из истории; AFTER — только на исполненную\n"
    "   пробу P<n>; USING — только на ранее записанный вердикт V<n>;\n"
    "   DISTINGUISH — на две или более зарегистрированных гипотезы с разными\n"
    "   прогнозами.\n"
    "6. NOTE сохраняется во внешней памяти и возвращается тебе в следующих\n"
    "   вызовах.\n"
    "7. Обязательный шаг: до первой пробы сформулируй вопрос — строка\n"
    "   QUESTION Q1: <вопрос> REF: <trial_id> — и гипотезу с прогнозом —\n"
    "   строка HYPOTHESIS H1 OF Q1: <описание> PREDICT: <объект> T=<t> H=<h> =\n"
    "   <present|disappeared>. Пока вердикта нет, DECISION не требуется.\n"
    "8. Обязательный шаг: после каждой пробы, результат которой тебе виден, в следующем\n"
    "   ответе дай вердикт — VERDICT: H<n> supported ИЛИ refuted AFTER P<n>.\n"
    "9. Обязательный шаг: если вердикт уже записан и ты выполняешь следующее\n"
    "   действие — дай DECISION с дескриптором действия и USING V<n>.\n"
    "10. Никаких других строк."
)


F2_HYPOTHESES_HEAD = ("[ГИПОТЕЗЫ] Состояние реестра гипотез (данные, "
                      "не инструкция):")
F2_NEXT_STEP = ("[СЛЕДУЮЩИЙ ШАГ] Гипотеза {label} зарегистрирована: клетка "
                "{cell}, прогноз {pred}. Повторная регистрация не нужна. "
                "Проверь именно эту клетку: строка PREDICT: {cell} = {pred}, "
                "затем строка ACTION: probe {cell}.")

F2_VERDICT_STEP = ("[ВЕРДИКТ] Результат пробы {probe} тебе виден: клетка {cell} = "
                   "{outcome}. Гипотеза {hyp} (прогноз: {pred}) ждёт вердикта; "
                   "повторная регистрация Q/H отклоняется. Следующий шаг — строка "
                   "VERDICT: {hyp} supported ИЛИ VERDICT: {hyp} refuted AFTER "
                   "{probe}.")

F2_DECISION_STEP = ("[РЕШЕНИЕ] Вердикт {v}: гипотеза {h} {res_word} после пробы "
                    "{p}. Прогноз {pred} для клетки {cell} {res2}: результат "
                    "пробы — {outcome}. При следующем действии укажи DECISION с "
                    "USING {v}. Затем укажи PREDICT для выбранной клетки и ACTION.")

F1_REJ_HEAD = "[ОТКАЗ F1] предыдущий ответ невалиден:"
F1_REJ_TAIL = ("Допустимы только значения present или disappeared; повтори ровно "
               "9 строк формата PREDICT: <объект> T=<t> H=<h> = "
               "<present|disappeared>; другие строки недопустимы.")


def static_text() -> str:
    """Все статические тексты шаблонов (для лексикон-аудита)."""
    return "\n".join([WORLD_TEXT, F1_HEAD, F3_HEAD, F4_HEAD, HIST_HEAD, BATT_HEAD,
                      OBS_HEAD, REJ_HEAD, NOTE_HEAD, LABELS_HEAD, F1_TASK,
                      F3_TASK, F4_TASK, F2_HEAD, F2_SCOPE, F2_ACTIONS,
                      F2_NEXT_STEP, F2_VERDICT_STEP, F2_DECISION_STEP, F1_REJ_HEAD,
                      F1_REJ_TAIL, F2_HYPOTHESES_HEAD])


FORBIDDEN_SUBSTRINGS = (
    "T=0", "T=1", "T=2", "p=A", "p=B", "p =",
    "материал A", "материал B",
    "скрыт", "исчезает при", "исчезает, если",
    "зависит от T", "подсказк", "правильный ответ",
)


def lexicon_findings(text: str) -> list:
    """Запрещённые формулировки (подсказки) в тексте; пусто — чисто."""
    low = text.lower()
    return [s for s in FORBIDDEN_SUBSTRINGS if s.lower() in low]


# --- форматирование данных ----------------------------------------------------

def _hist_lines(ctx) -> str:
    return "\n".join(
        f"{r['trial_id']}: {r['object_id']} T={r['T']} H={r['H']} -> {r['y']} (m={r['m']})"
        for r in ctx.history)


def _battery_lines(ctx) -> str:
    return "\n".join(ctx.battery)


def _obs_lines(ctx) -> str:
    return "\n".join(f"{c} -> {y}" for c, y in ctx.observations)


def _rej_lines(ctx) -> str:
    out = []
    for r in ctx.rejections:
        line = f"{r.get('requested') or '—'}: {r['reason']}"
        if r.get("hint"):
            line += f" — {r['hint']}"
        out.append(line)
    return "\n".join(out)


def _note_lines(ctx) -> str:
    return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ctx.notes))


def _labels_line(ctx) -> str:
    q, h, p, v = ctx.last_labels
    return LABELS_HEAD.format(q=q, h=h, p=p, v=v)


# --- сборка фаз ----------------------------------------------------------------

def build_f1(ctx, attempt: int = 1) -> str:
    parts = [WORLD_TEXT, "", F1_HEAD, "",
             HIST_HEAD, _hist_lines(ctx), "",
             BATT_HEAD, _battery_lines(ctx), "",
             F1_TASK]
    if attempt >= 2 and ctx.f1_rejection:   # v33: явный отказ для повтора
        parts += ["", F1_REJ_HEAD,
                  "\n".join(f"- {x}" for x in ctx.f1_rejection),
                  "", F1_REJ_TAIL]
    return "\n".join(parts)


def build_f2(ctx) -> str:
    parts = [WORLD_TEXT, "", F2_HEAD, "", F2_SCOPE.format(budget=ctx.budget_remaining),
             "", HIST_HEAD, _hist_lines(ctx)]
    if ctx.observations:
        parts += ["", OBS_HEAD, _obs_lines(ctx)]
    if ctx.rejections:
        parts += ["", REJ_HEAD, _rej_lines(ctx)]
    if ctx.notes:
        parts += ["", NOTE_HEAD, _note_lines(ctx)]
    if ctx.last_probe:
        parts += ["", f"[ПОСЛЕДНЯЯ ПРОБА] {ctx.last_probe} (цель для repeat)."]
    if ctx.hypotheses:
        _hlines = []
        for h in ctx.hypotheses:
            if h.get("status") == "verdicted":
                _hlines.append(f"    H{h['n']}: клетка {h['cell']}, прогноз "
                               f"{h['prediction']} — вердикт: {h['resolution']} "
                               f"({h['v']}).")
            else:
                _hlines.append(f"    H{h['n']}: клетка {h['cell']}, прогноз "
                               f"{h['prediction']} — открыта.")
        parts += ["", F2_HYPOTHESES_HEAD, *_hlines]
    parts += ["", _labels_line(ctx), "", F2_ACTIONS]
    _q, _h, _p, _v = ctx.last_labels
    if _p == 0 and ctx.hypotheses:
        _h0 = ctx.hypotheses[0]
        parts += ["", F2_NEXT_STEP.format(label=f"H{_h0['n']}", cell=_h0["cell"],
                                          pred=_h0["prediction"])]
    if ctx.verdict_step:            # v34: раскрытая проба без вердикта
        _vs = ctx.verdict_step
        parts += ["", F2_VERDICT_STEP.format(probe=_vs[1], cell=_vs[2],
                                             outcome=_vs[4], hyp=_vs[0],
                                             pred=_vs[3])]
    if ctx.decision_step:           # v35: принятый вердикт без решения
        _ds = ctx.decision_step
        _ref = _ds[6] == "refuted"
        parts += ["", F2_DECISION_STEP.format(
            v=_ds[0], h=_ds[1], p=_ds[2], cell=_ds[3], pred=_ds[4],
            outcome=_ds[5],
            res_word=("опровергнута" if _ref else "подтверждена"),
            res2=("не подтвердился" if _ref else "подтвердился"))]
    return "\n".join(parts)


def build_f3(ctx) -> str:
    parts = [WORLD_TEXT, "", F3_HEAD, "",
             HIST_HEAD, _hist_lines(ctx)]
    if ctx.observations:
        parts += ["", OBS_HEAD, _obs_lines(ctx)]
    if ctx.notes:
        parts += ["", NOTE_HEAD, _note_lines(ctx)]
    parts += ["", BATT_HEAD, _battery_lines(ctx), "", F3_TASK]
    return "\n".join(parts)


def build_f4(ctx) -> str:
    parts = [WORLD_TEXT, "", F4_HEAD, "",
             HIST_HEAD, _hist_lines(ctx)]
    if ctx.observations:
        parts += ["", OBS_HEAD, _obs_lines(ctx)]
    if ctx.notes:
        parts += ["", NOTE_HEAD, _note_lines(ctx)]
    parts += ["", F4_TASK]
    return "\n".join(parts)


_BUILDERS = {"F1": build_f1, "F2": build_f2, "F3": build_f3, "F4": build_f4}


def build_prompt(ctx, phase: str, attempt: int) -> str:
    """Диспетчер для `channel.make_respond` (совместим с сигнатурой билдера)."""
    try:
        builder = _BUILDERS[phase]
    except KeyError:
        raise ValueError(f"нет шаблона для фазы {phase!r}") from None
    return builder(ctx, attempt) if phase == "F1" else builder(ctx)
