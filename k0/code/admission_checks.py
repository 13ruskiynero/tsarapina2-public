#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — проверки технического допуска (автономные; только чтение/прогоны).

Запуск:
    python3 lab/autonomy/k0/code/admission_checks.py

Печатает таблицу [id] статус — материал для протокола допуска.
Модель не вызывается; сеть не используется; пишет только во временные
каталоги; замороженный комплект — только чтение.
Статусы: PASS / FAIL / OPEN / NOTE.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
K0 = HERE.parent
ART = K0 / "artifacts"

from world import BudgetExhausted, Cell, World, cell_outcome, load_battery  # noqa: E402
from journal import Journal, JournalError, read_journal, run_dir_for  # noqa: E402
from channel import (ChannelError, HttpChannel, HttpsChannel,  # noqa: E402
                     LoopbackChannel, _strict_context, extract_content,
                     make_respond, ollama_payload_builder)
from secret_scan import scan_exceptions, scan_text, secret_forms  # noqa: E402
from auditor import audit_run, is_echo_content  # noqa: E402
from session import Session  # noqa: E402

CLOSED_TYPES = {
    "question", "hypothesis", "rejected", "note", "action_requested",
    "prediction_pre", "prediction_before", "prediction_after", "verdict",
    "decision", "final", "history_shown", "probe_outcome", "budget", "stop",
    "state_change", "mode_violation", "verdict_check", "action_rejected",
    "forecast_status",
}

RESULTS = []


def check(cid: str, status: str, note: str = ""):
    RESULTS.append((cid, status, note))
    print(f"[{cid:4s}] {status:4s}  {note}")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


battery = [i.cell for i in load_battery(ART / "heldout_battery.json")]
F1 = "\n".join(f"PREDICT: {c.as_text()} = present" for c in sorted(battery))
F3 = "\n".join(f"PREDICT: {c.as_text()} = {cell_outcome(c)}" for c in sorted(battery))
REG = "\n".join([
    "QUESTION Q1: почему объекты исчезают? REF: t01",
    "HYPOTHESIS H1 OF Q1: правило T PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H2 OF Q1: скрытый p PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H3 OF Q1: материал m PREDICT: O2 T=2 H=1 = disappeared",
])
B1 = "PREDICT: O2 T=2 H=1 = disappeared\nACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2,H3"
B2 = "\n".join([
    "VERDICT: H1 supported AFTER P1",
    "DECISION: probe O4 T=2 H=1 USING V1",
    "PREDICT: O4 T=2 H=1 = present",
    "ACTION: probe O4 T=2 H=1",
])
FINAL = "FINAL: объекты с материалом A исчезают при T=2."

# --- H0: якорь протокола -----------------------------------------------------
vh = sha(K0 / "K0_PROTOCOL.md")          # база v26 (заморожен)
vh27 = sha(K0 / "K0_PROTOCOL_v27.md")    # протокол v27 (база серии v28)
vh28 = sha(K0 / "K0_PROTOCOL_v28.md")    # комплект v28 (база серии v29)
vh29 = sha(K0 / "K0_PROTOCOL_v29.md")    # комплект v29 (база серии v30)
vh30 = sha(K0 / "K0_PROTOCOL_v30.md")    # комплект v30 (база серии v31)
vh31 = sha(K0 / "K0_PROTOCOL_v31.md")    # комплект v31 (база серии v32)
vh32 = sha(K0 / "K0_PROTOCOL_v32.md")    # протокол v32 (база серии v33)
vh33 = sha(K0 / "K0_PROTOCOL_v33.md")    # протокол v33 (база серии v34)
vh34 = sha(K0 / "K0_PROTOCOL_v34.md")    # протокол v34 (база серии v35)
vh35 = sha(K0 / "K0_PROTOCOL_v35.md")    # действующий комплект v35
check("H0", "PASS" if vh.startswith("3d2ab37d") else "FAIL",
      f"K0_PROTOCOL.md (ред. 26) sha256={vh[:16]}…")

# --- V27: действующий протокол отличается от v26 ТОЛЬКО строкой num_predict ----
_v26_lines = (K0 / "K0_PROTOCOL.md").read_text(encoding="utf-8").splitlines()
_v27_path = K0 / "K0_PROTOCOL_v27.md"
_diff_path = K0 / "version-history" / "K0_PROTOCOL_v26_to_v27.diff"
v27_ok = False
if _v27_path.exists() and _diff_path.exists():
    _v27_lines = _v27_path.read_text(encoding="utf-8").splitlines()
    _dl = [i for i, (x, y) in enumerate(zip(_v26_lines, _v27_lines)) if x != y]
    v27_ok = (len(_v26_lines) == len(_v27_lines) and len(_dl) == 1
              and "num_predict" in _v26_lines[_dl[0]]
              and "num_predict" in _v27_lines[_dl[0]]
              and "256" in _v27_lines[_dl[0]])
check("V27", "PASS" if v27_ok else "FAIL",
      "v27: от v26 отличается ровно строкой num_predict (96→256); диф существует")

# --- V28: комплект v28 — правка формата блока F2 в шаблоне промпта (ред. v28) --
_v28_base = (K0 / "K0_PROTOCOL_v27.md").read_text(encoding="utf-8").splitlines()
_v28_path = K0 / "K0_PROTOCOL_v28.md"
_d28_path = K0 / "version-history" / "K0_PROTOCOL_v27_to_v28.diff"
v28_ok = False
if _v28_path.exists() and _d28_path.exists():
    _v28_lines = _v28_path.read_text(encoding="utf-8").splitlines()
    _dl28 = [i for i, (x, y) in enumerate(zip(_v28_base, _v28_lines)) if x != y]
    v28_ok = (len(_v28_base) == len(_v28_lines) and len(_dl28) == 1
              and "грамматика и промпты" in _v28_base[_dl28[0]]
              and "v28" in _v28_lines[_dl28[0]]
              and "PREDICT и ACTION" in _v28_lines[_dl28[0]])
check("V28", "PASS" if v28_ok else "FAIL",
      "v28: от v27 отличается ровно строкой реестра промпт-правки; диф существует")
_p_old = K0 / "version-history" / "K0_PROMPTS_v27.py"
_p_new = K0 / "version-history" / "K0_PROMPTS_v28.py"
p28_ok = False
if _p_old.exists() and _p_new.exists():
    _o = _p_old.read_text(encoding="utf-8").splitlines()
    _n = _p_new.read_text(encoding="utf-8").splitlines()
    _O1 = '    "1. Перед ACTION: probe укажи PREDICT — прогноз исхода этой же клетки.\\n"'
    _N1 = '    "1. Перед ACTION: probe укажи PREDICT — прогноз исхода этой же клетки;\\n"'
    _N2 = '    "PREDICT и ACTION — две ОТДЕЛЬНЫЕ строки (сначала PREDICT, затем\\n"'
    _N3 = '    "ACTION); объединять их в одну строку недопустимо.\\n"'
    if _O1 in _o and _N1 in _n and _N2 in _n and _N3 in _n:
        _i = _o.index(_O1)
        _j = _n.index(_N1)
        p28_ok = (_o[:_i] + _o[_i + 1:] == _n[:_j] + _n[_j + 3:])
check("V28-P", "PASS" if p28_ok else "FAIL",
      "v28: prompts.py отличается от артефакта v27 ровно правкой правила 1")

# --- V29: комплект v29 — обязательный пересмотр гипотезы (мягкий, S) -----------
_v29_base = (K0 / "K0_PROTOCOL_v28.md").read_text(encoding="utf-8").splitlines()
_v29_path = K0 / "K0_PROTOCOL_v29.md"
_d29_path = K0 / "version-history" / "K0_PROTOCOL_v28_to_v29.diff"
v29_ok = False
if _v29_path.exists() and _d29_path.exists():
    _v29_lines = _v29_path.read_text(encoding="utf-8").splitlines()
    _dl29 = [i for i, (x, y) in enumerate(zip(_v29_base, _v29_lines)) if x != y]
    v29_ok = (len(_v29_base) == len(_v29_lines) and len(_dl29) == 1
              and "v28" in _v29_base[_dl29[0]]
              and "v29" in _v29_lines[_dl29[0]]
              and "пересмотр" in _v29_lines[_dl29[0]])
check("V29", "PASS" if v29_ok else "FAIL",
      "v29: от v28 отличается ровно строкой реестра (пересмотр гипотез); диф существует")
_p28_old = K0 / "version-history" / "K0_PROMPTS_v28.py"
_p_new2 = K0 / "version-history" / "K0_PROMPTS_v29.py"
p29_ok = False
if _p28_old.exists() and _p_new2.exists():
    _o2 = _p28_old.read_text(encoding="utf-8").splitlines()
    _n2 = _p_new2.read_text(encoding="utf-8").splitlines()
    _O7 = '    "7. Никаких других строк."'
    _N7 = '    "7. Обязательный шаг: до первой пробы сформулируй вопрос — строка\\n"'
    if _O7 in _o2 and _N7 in _n2:
        _i2 = _o2.index(_O7)
        _j2 = _n2.index(_N7)
        _blk = _n2[_j2:_j2 + 9]
        p29_ok = (_o2[:_i2] + _o2[_i2 + 1:] == _n2[:_j2] + _n2[_j2 + 9:]
                  and any("QUESTION Q1" in x for x in _blk)
                  and any("HYPOTHESIS H1" in x for x in _blk)
                  and any("VERDICT" in x for x in _blk)
                  and any("USING V<n>" in x for x in _blk))
check("V29-P", "PASS" if p29_ok else "FAIL",
      "v29: prompts.py отличается от артефакта v28 ровно блоком правил 7–10 (замороженная пара v28↔v29)")

# --- V30: фидбек отказов (hint) + предохранитель цикла -------------------------
_v30_base = (K0 / "K0_PROTOCOL_v29.md").read_text(encoding="utf-8").splitlines()
_v30_path = K0 / "K0_PROTOCOL_v30.md"
_d30_path = K0 / "version-history" / "K0_PROTOCOL_v29_to_v30.diff"
v30_ok = False
if _v30_path.exists() and _d30_path.exists():
    _v30_lines = _v30_path.read_text(encoding="utf-8").splitlines()
    _dl30 = [i for i, (x, y) in enumerate(zip(_v30_base, _v30_lines)) if x != y]
    v30_ok = (len(_v30_base) == len(_v30_lines) and len(_dl30) == 1
              and "v29" in _v30_base[_dl30[0]]
              and "v30" in _v30_lines[_dl30[0]]
              and "response_loop" in _v30_lines[_dl30[0]])
check("V30", "PASS" if v30_ok else "FAIL",
      "v30: от v29 отличается ровно строкой реестра (фидбек+hint, цикл); диф существует")
_d30p = K0 / "version-history" / "K0_PROMPTS_v29_to_v30.diff"
_s29p = K0 / "version-history" / "K0_PROMPTS_v29.py"
p30_ok = False
if _d30p.exists() and _s29p.exists():
    _dlines = _d30p.read_text(encoding="utf-8").splitlines()
    _plus = [x for x in _dlines if x.startswith("+") and not x.startswith("+++")]
    _minus = [x for x in _dlines if x.startswith("-") and not x.startswith("---")]
    p30_ok = (len(_plus) == 7 and len(_minus) == 1
              and any("hint" in x for x in _plus)
              and "if r.get(\"hint\"):" in (HERE / "prompts.py").read_text(encoding="utf-8"))
check("V30-P", "PASS" if p30_ok else "FAIL",
      "v30: prompts.py отличается от артефакта v29 ровно блоком _rej_lines (+hint)")
_s29s = K0 / "version-history" / "K0_SESSION_v29.py"
s30_ok = False
if _s29s.exists():
    _so = _s29s.read_text(encoding="utf-8")
    _sn = (HERE / "session.py").read_text(encoding="utf-8")
    _r4 = HERE / "tests" / "test_recovery.py"
    s30_ok = ("response_loop" not in _so and "response_loop" in _sn
              and "LOOP_FUSE_K = 3" in _sn
              and "def qh_hint(" in _sn
              and "REJECTION_HINTS" in _sn
              and "last_progress" in _sn and "last_journal_seq" not in _sn
              and _r4.exists()
              and "test_same_invalid_action_is_fused" in _r4.read_text(encoding="utf-8")
              and (K0 / "version-history" / "K0_SESSION_v29_to_v30.diff").exists())
check("V30-S", "PASS" if s30_ok else "FAIL",
      "v30 (ред.2): session: фидбек+hint, предохранитель response_loop (K=3, без сброса на action_rejected); тесты R1–R4")




# --- V35: переход «принятый вердикт → DECISION» (ветка v35-A) ------------------
_v35_base = (K0 / "K0_PROTOCOL_v34.md").read_text(encoding="utf-8").splitlines()
_v35_path = K0 / "K0_PROTOCOL_v35.md"
_d35_path = K0 / "version-history" / "K0_PROTOCOL_v34_to_v35.diff"
v35_ok = False
if _v35_path.exists() and _d35_path.exists():
    _v35_lines = _v35_path.read_text(encoding="utf-8").splitlines()
    _dl35 = [i for i, (x, y) in enumerate(zip(_v35_base, _v35_lines)) if x != y]
    v35_ok = (len(_v35_base) == len(_v35_lines) and len(_dl35) == 1
              and "v34" in _v35_base[_dl35[0]]
              and "v35" in _v35_lines[_dl35[0]]
              and "РЕШЕНИЕ" in _v35_lines[_dl35[0]])
check("V35", "PASS" if v35_ok else "FAIL",
      "v35: от v34 отличается ровно строкой реестра ([РЕШЕНИЕ]); диф существует")
_d35p = K0 / "version-history" / "K0_PROMPTS_v34_to_v35.diff"
_p34 = K0 / "version-history" / "K0_PROMPTS_v34.py"
p35_ok = False
if _d35p.exists() and _p34.exists():
    _o35 = _p34.read_text(encoding="utf-8")
    _n35 = (HERE / "prompts.py").read_text(encoding="utf-8")
    _dl35p = _d35p.read_text(encoding="utf-8").splitlines()
    _plus35 = [x for x in _dl35p if x.startswith("+") and not x.startswith("+++")]
    _minus35 = [x for x in _dl35p if x.startswith("-") and not x.startswith("---")]
    p35_ok = ("[РЕШЕНИЕ]" not in _o35
              and "[РЕШЕНИЕ]" in _n35
              and "F2_DECISION_STEP" in _n35
              and "ctx.decision_step" in _n35
              and len(_minus35) == 1 and len(_plus35) == 14)
check("V35-P", "PASS" if p35_ok else "FAIL",
      "v35: prompts.py — секция [РЕШЕНИЕ] из записи вердикта (V, H, P, клетка, исход)")
_s34 = K0 / "version-history" / "K0_SESSION_v34.py"
_c34 = K0 / "version-history" / "K0_CALLS_v34.py"
s35_ok = False
if _s34.exists() and _c34.exists():
    _so35 = _s34.read_text(encoding="utf-8")
    _sn35 = (HERE / "session.py").read_text(encoding="utf-8")
    _co35 = _c34.read_text(encoding="utf-8")
    _cn35 = (HERE / "calls.py").read_text(encoding="utf-8")
    s35_ok = ("decision_step" not in _so35 and "decision_step" in _sn35
              and "self.decisions" in _sn35
              and '"protocol_version": "v35"' in _sn35
              and "decision_step" not in _co35 and 'payload["decision_step"]' in _cn35
              and (K0 / "version-history" / "K0_SESSION_v34_to_v35.diff").exists()
              and (K0 / "version-history" / "K0_CALLS_v34_to_v35.diff").exists()
              and (HERE / "tests" / "test_decision_feedback.py").exists())
check("V35-S", "PASS" if s35_ok else "FAIL",
      "v35: session/calls — шаг решения в контексте и в JSON-артефакте; тесты решения")

# --- V34: явный переход «раскрытый исход → вердикт» (ветка v34-A) -------------
_v34_base = (K0 / "K0_PROTOCOL_v33.md").read_text(encoding="utf-8").splitlines()
_v34_path = K0 / "K0_PROTOCOL_v34.md"
_d34_path = K0 / "version-history" / "K0_PROTOCOL_v33_to_v34.diff"
v34_ok = False
if _v34_path.exists() and _d34_path.exists():
    _v34_lines = _v34_path.read_text(encoding="utf-8").splitlines()
    _dl34 = [i for i, (x, y) in enumerate(zip(_v34_base, _v34_lines)) if x != y]
    v34_ok = (len(_v34_base) == len(_v34_lines) and len(_dl34) == 1
              and "v33" in _v34_base[_dl34[0]]
              and "v34" in _v34_lines[_dl34[0]]
              and "ВЕРДИКТ" in _v34_lines[_dl34[0]])
check("V34", "PASS" if v34_ok else "FAIL",
      "v34: от v33 отличается ровно строкой реестра ([ВЕРДИКТ]); диф существует")
_d34p = K0 / "version-history" / "K0_PROMPTS_v33_to_v34.diff"
_s33p = K0 / "version-history" / "K0_PROMPTS_v33.py"
p34_ok = False
if _d34p.exists() and _s33p.exists():
    _o34 = _s33p.read_text(encoding="utf-8")
    _n34 = (K0 / "version-history" / "K0_PROMPTS_v34.py").read_text(encoding="utf-8")
    _dl34p = _d34p.read_text(encoding="utf-8").splitlines()
    _plus34 = [x for x in _dl34p if x.startswith("+") and not x.startswith("+++")]
    _minus34 = [x for x in _dl34p if x.startswith("-") and not x.startswith("---")]
    p34_ok = ("[ВЕРДИКТ]" not in _o34
              and "[ВЕРДИКТ]" in _n34
              and "F2_VERDICT_STEP" in _n34
              and "ctx.verdict_step" in _n34
              and len(_minus34) == 1 and len(_plus34) == 12)
check("V34-P", "PASS" if p34_ok else "FAIL",
      "v34: prompts.py — секция [ВЕРДИКТ] из записи (H, P, клетка, прогноз, исход)")
_s33s = K0 / "version-history" / "K0_SESSION_v33.py"
_c33s = K0 / "version-history" / "K0_CALLS_v33.py"
s34_ok = False
if _s33s.exists() and _c33s.exists():
    _so34 = _s33s.read_text(encoding="utf-8")
    _sn34 = (K0 / "version-history" / "K0_SESSION_v34.py").read_text(encoding="utf-8")
    _co34 = _c33s.read_text(encoding="utf-8")
    _cn34 = (K0 / "version-history" / "K0_CALLS_v34.py").read_text(encoding="utf-8")
    s34_ok = ("verdict_step" not in _so34 and "verdict_step" in _sn34
              and '"protocol_version": "v34"' in _sn34
              and "verdict_step" not in _co34 and 'payload["verdict_step"]' in _cn34
              and (K0 / "version-history" / "K0_SESSION_v33_to_v34.diff").exists()
              and (K0 / "version-history" / "K0_CALLS_v33_to_v34.diff").exists()
              and (HERE / "tests" / "test_verdict_feedback.py").exists())
check("V34-S", "PASS" if s34_ok else "FAIL",
      "v34: session/calls — шаг вердикта в контексте и в JSON-артефакте; тесты вердикта")

# --- V33: F1-feedback при повторной попытке (ветка A) --------------------------
_v33_base = (K0 / "K0_PROTOCOL_v32.md").read_text(encoding="utf-8").splitlines()
_v33_path = K0 / "K0_PROTOCOL_v33.md"
_d33_path = K0 / "version-history" / "K0_PROTOCOL_v32_to_v33.diff"
v33_ok = False
if _v33_path.exists() and _d33_path.exists():
    _v33_lines = _v33_path.read_text(encoding="utf-8").splitlines()
    _dl33 = [i for i, (x, y) in enumerate(zip(_v33_base, _v33_lines)) if x != y]
    v33_ok = (len(_v33_base) == len(_v33_lines) and len(_dl33) == 1
              and "v32" in _v33_base[_dl33[0]]
              and "v33" in _v33_lines[_dl33[0]]
              and "F1-feedback" in _v33_lines[_dl33[0]])
check("V33", "PASS" if v33_ok else "FAIL",
      "v33: от v32 отличается ровно строкой реестра (F1-feedback); диф существует")
_d33p = K0 / "version-history" / "K0_PROMPTS_v32_to_v33.diff"
_s32p = K0 / "version-history" / "K0_PROMPTS_v32.py"
p33_ok = False
if _d33p.exists() and _s32p.exists():
    _o33 = _s32p.read_text(encoding="utf-8")
    _n33 = (K0 / "version-history" / "K0_PROMPTS_v33.py").read_text(encoding="utf-8")
    _dl33p = _d33p.read_text(encoding="utf-8").splitlines()
    _plus33 = [x for x in _dl33p if x.startswith("+") and not x.startswith("+++")]
    _minus33 = [x for x in _dl33p if x.startswith("-") and not x.startswith("---")]
    p33_ok = ("[ОТКАЗ F1]" not in _o33
              and "[ОТКАЗ F1]" in _n33
              and "def build_f1(ctx, attempt: int = 1)" in _n33
              and 'builder(ctx, attempt) if phase == "F1"' in _n33
              and len(_minus33) == 10 and len(_plus33) == 17)
check("V33-P", "PASS" if p33_ok else "FAIL",
      "v33: prompts.py — блок [ОТКАЗ F1] со 2-й попытки (attempt в F1-билдере)")
_s32s = K0 / "version-history" / "K0_SESSION_v32.py"
_c32s = K0 / "version-history" / "K0_CALLS_v32.py"
s33_ok = False
if _s32s.exists() and _c32s.exists():
    _so33 = _s32s.read_text(encoding="utf-8")
    _sn33 = (K0 / "version-history" / "K0_SESSION_v33.py").read_text(encoding="utf-8")
    _co33 = _c32s.read_text(encoding="utf-8")
    _cn33 = (K0 / "version-history" / "K0_CALLS_v33.py").read_text(encoding="utf-8")
    s33_ok = ("f1_rejection" not in _so33 and "f1_rejection" in _sn33
              and "fc.bad_raw" in _sn33
              and '"protocol_version": "v33"' in _sn33
              and "f1_rejection" not in _co33 and 'payload["f1_rejection"]' in _cn33
              and (K0 / "version-history" / "K0_SESSION_v32_to_v33.diff").exists()
              and (K0 / "version-history" / "K0_CALLS_v32_to_v33.diff").exists()
              and (HERE / "tests" / "test_f1_feedback.py").exists())
check("V33-S", "PASS" if s33_ok else "FAIL",
      "v33: session/calls — причина отказа F1 в контексте и в JSON-артефакте; тесты F1")

_s32par = K0 / "version-history" / "K0_PARSER_v32.py"
_d33par = K0 / "version-history" / "K0_PARSER_v32_to_v33.diff"
_n33par = (HERE / "parser.py").read_text(encoding="utf-8")
v33d_ok = False
if _s32par.exists() and _d33par.exists():
    _po33 = _s32par.read_text(encoding="utf-8")
    v33d_ok = (sha(_s32par) == "39ce6c8c03383ff3e4ffe53aaf0d92be9dc68e308aa7de83572fab473ee4ccb0"
               and "bad_raw" not in _po33 and "bad_raw" in _n33par
               and "line_of" in _n33par
               and "bad_raw" in _d33par.read_text(encoding="utf-8"))
check("V33-D", "PASS" if v33d_ok else "FAIL",
      "v33: parser.py — bad_raw от замороженного v32 (39ce6c8c…); диф существует")

# --- V32: следующий шаг привязан к записи H1 ----------------------------------
_v32_base = (K0 / "K0_PROTOCOL_v31.md").read_text(encoding="utf-8").splitlines()
_v32_path = K0 / "K0_PROTOCOL_v32.md"
_d32_path = K0 / "version-history" / "K0_PROTOCOL_v31_to_v32.diff"
v32_ok = False
if _v32_path.exists() and _d32_path.exists():
    _v32_lines = _v32_path.read_text(encoding="utf-8").splitlines()
    _dl32 = [i for i, (x, y) in enumerate(zip(_v32_base, _v32_lines)) if x != y]
    v32_ok = (len(_v32_base) == len(_v32_lines) and len(_dl32) == 1
              and "v31" in _v32_base[_dl32[0]]
              and "v32" in _v32_lines[_dl32[0]]
              and "H1" in _v32_lines[_dl32[0]])
check("V32", "PASS" if v32_ok else "FAIL",
      "v32: от v31 отличается ровно строкой реестра (привязка к H1); диф существует")
_d32p = K0 / "version-history" / "K0_PROMPTS_v31_to_v32.diff"
_s31p = K0 / "version-history" / "K0_PROMPTS_v31.py"
p32_ok = False
if _d32p.exists() and _s31p.exists():
    _o32 = _s31p.read_text(encoding="utf-8")
    _n32 = (K0 / "version-history" / "K0_PROMPTS_v32.py").read_text(encoding="utf-8")
    _dl32p = _d32p.read_text(encoding="utf-8").splitlines()
    _plus32 = [x for x in _dl32p if x.startswith("+") and not x.startswith("+++")]
    _minus32 = [x for x in _dl32p if x.startswith("-") and not x.startswith("---")]
    p32_ok = ("Проверь именно эту клетку" not in _o32
              and "Проверь именно эту клетку" in _n32
              and "ctx.hypotheses" in _n32
              and len(_minus32) == 7 and len(_plus32) == 8)
check("V32-P", "PASS" if p32_ok else "FAIL",
      "v32: prompts.py — секция строится из записи H1 (клетка/прогноз реестра)")
_c31 = K0 / "version-history" / "K0_CALLS_v31.py"
_s31s = K0 / "version-history" / "K0_SESSION_v31.py"
s32_ok = False
if _s31s.exists() and _c31.exists():
    _so32 = _s31s.read_text(encoding="utf-8")
    _sn32 = (K0 / "version-history" / "K0_SESSION_v32.py").read_text(encoding="utf-8")
    _co32 = _c31.read_text(encoding="utf-8")
    _cn32 = (K0 / "version-history" / "K0_CALLS_v32.py").read_text(encoding="utf-8")
    s32_ok = ('hypotheses: tuple = ()   # v32' in _sn32
              and 'hypotheses: tuple = ()   # v32' not in _so32
              and 'hypotheses=(hyp if phase == "F2" else ())' in _sn32
              and '"protocol_version": "v32"' in _sn32
              and 'payload["hypotheses"]' in _cn32
              and 'payload["hypotheses"]' not in _co32
              and (K0 / "version-history" / "K0_SESSION_v31_to_v32.diff").exists()
              and (K0 / "version-history" / "K0_CALLS_v31_to_v32.diff").exists()
              and "test_t4_probe_matches_hypothesis_cell" in
                  (HERE / "tests" / "test_transition.py").read_text(encoding="utf-8"))
check("V32-S", "PASS" if s32_ok else "FAIL",
      "v32: session/calls — hypotheses в контексте и в JSON-артефакте; тест T4")


# --- V31: переход «регистрация → действие» (секция [СЛЕДУЮЩИЙ ШАГ]) ------------
_v31_base = (K0 / "K0_PROTOCOL_v30.md").read_text(encoding="utf-8").splitlines()
_v31_path = K0 / "K0_PROTOCOL_v31.md"
_d31_path = K0 / "version-history" / "K0_PROTOCOL_v30_to_v31.diff"
v31_ok = False
if _v31_path.exists() and _d31_path.exists():
    _v31_lines = _v31_path.read_text(encoding="utf-8").splitlines()
    _dl31 = [i for i, (x, y) in enumerate(zip(_v31_base, _v31_lines)) if x != y]
    v31_ok = (len(_v31_base) == len(_v31_lines) and len(_dl31) == 1
              and "v30" in _v31_base[_dl31[0]]
              and "v31" in _v31_lines[_dl31[0]]
              and "СЛЕДУЮЩИЙ ШАГ" in _v31_lines[_dl31[0]])
check("V31", "PASS" if v31_ok else "FAIL",
      "v31: от v30 отличается ровно строкой реестра (переход к действию); диф существует")
_d31p = K0 / "version-history" / "K0_PROMPTS_v30_to_v31.diff"
_s30p = K0 / "version-history" / "K0_PROMPTS_v30.py"
p31_ok = False
if _d31p.exists() and _s30p.exists():
    _o31 = _s30p.read_text(encoding="utf-8")
    _n31 = (HERE / "prompts.py").read_text(encoding="utf-8")
    _dl31p = _d31p.read_text(encoding="utf-8").splitlines()
    _plus31 = [x for x in _dl31p if x.startswith("+") and not x.startswith("+++")]
    _minus31 = [x for x in _dl31p if x.startswith("-") and not x.startswith("---")]
    p31_ok = ("[СЛЕДУЮЩИЙ ШАГ]" not in _o31 and "[СЛЕДУЮЩИЙ ШАГ]" in _n31
              and "F2_NEXT_STEP" in _n31
              and len(_minus31) == 1 and 6 <= len(_plus31) <= 12)
check("V31-P", "PASS" if p31_ok else "FAIL",
      "v31: prompts.py — одна правка (константа + вставка в F2 при Q≥1, H≥1, P=0)")
_t31 = HERE / "tests" / "test_transition.py"
_s30s = K0 / "version-history" / "K0_SESSION_v30.py"
s31_ok = False
if _s30s.exists() and _t31.exists():
    _so31 = _s30s.read_text(encoding="utf-8")
    _sn31 = (K0 / "version-history" / "K0_SESSION_v31.py").read_text(encoding="utf-8")
    _t31t = _t31.read_text(encoding="utf-8")
    s31_ok = ("K0-M3" not in _so31 and "K0-M3" in _sn31
              and '"protocol_version": "v31"' in _sn31
              and "test_t1_hint_after_registration" in _t31t
              and "test_t2_valid_action_passes_after_registration" in _t31t
              and "test_t3_refused_registration_does_not_block_action" in _t31t
              and (K0 / "version-history" / "K0_SESSION_v30_to_v31.diff").exists())
check("V31-S", "PASS" if s31_ok else "FAIL",
      "v31: session — метки K0-M3/v31; тесты перехода T1–T3 (предохранитель v30 — отдельно)")

# --- A1..A12: сквозной прогон -------------------------------------------------
tmp = tempfile.TemporaryDirectory()
base = Path(tmp.name)
run = run_dir_for(base, "K0-M1", 101)
calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}


def full_agent(phase, ctx, attempt):
    calls[phase] += 1
    if phase == "F1":
        return F1
    if phase == "F2":
        i = calls["F2"]
        return REG if i == 1 else B1 if i == 2 else B2 if i == 3 else "ACTION: reset"
    if phase == "F3":
        return F3
    if phase == "F4":
        return FINAL
    raise AssertionError(phase)


sess = Session(run, full_agent, seed=101)
res = sess.run()
rows = read_journal(run / "raw" / "journal.jsonl")
types = [r["type"] for r in rows]
by_seq = {r["seq"]: r for r in rows}

check("A1", "PASS" if res.status == "completed" and calls ==
      {"F1": 1, "F2": 17, "F3": 1, "F4": 1} else "FAIL",
      f"сквозной F1→F4: status={res.status}, вызовы={calls}")

check("A2", "PASS" if set(types) <= CLOSED_TYPES else "FAIL",
      "типы записей ⊆ закрытого списка §11 (20 типов)")

pre_ok = True
for r in rows:
    if r["type"] == "action_requested" and r.get("label"):
        ref = r.get("prediction_ref")
        pre = by_seq.get(ref) if ref else None
        if pre is None or pre.get("type") != "prediction_pre" or pre["seq"] >= r["seq"]:
            pre_ok = False
check("A3", "PASS" if pre_ok else "FAIL",
      "∀ оцениваемая проба: prediction_pre существует и seq(pre) < seq(action)")

resets = [r for r in rows if r["type"] == "action_requested" and r.get("label") is None]
check("A4", "PASS" if resets and all("prediction_ref" not in r for r in resets) else "FAIL",
      f"{len(resets)} reset без prediction_ref (минимальная схема, к утверждению)")

outcomes = [r for r in rows if r["type"] == "probe_outcome"]
per_act = {}
last = None
ok5 = True
for r in rows:
    if r["type"] == "action_requested":
        last = r
        per_act.setdefault(r["seq"], 0)
    elif r["type"] == "probe_outcome":
        if last is None:
            ok5 = False
        else:
            per_act[last["seq"]] += 1
for r in rows:
    if r["type"] == "action_requested":
        want = 1 if r.get("label") else 0
        if per_act.get(r["seq"]) != want:
            ok5 = False
check("A5", "PASS" if ok5 and len(outcomes) == 2 else "FAIL",
      "ровно один probe_outcome на probe/repeat; у reset — ни одного")

budgets = [r for r in rows if r["type"] == "budget"]
per_b = {}
for b in budgets:
    per_b[b["action_ref"]] = per_b.get(b["action_ref"], 0) + 1
acts = {r["seq"] for r in rows if r["type"] == "action_requested"}
ok6 = (len(budgets) == 16 and all(c == 1 for c in per_b.values())
       and all(b["cost"] == 1 for b in budgets)
       and budgets[-1]["remaining"] == 0
       and all(b["action_ref"] in acts for b in budgets))
check("A6", "PASS" if ok6 else "FAIL",
      "budget: ровно одна запись на исполнение, cost=1, action_ref валиден, сумма=16, остаток=0")

sc = [r for r in rows if r["type"] == "state_change"]
check("A7", "PASS" if len(sc) == 14 and all("restored" in r for r in sc) else "FAIL",
      f"state_change: {len(sc)} записей; у reset — restored (в т.ч. пустой)")

ok8 = True
for r in rows:
    t, lb = r["type"], r["label_by"]
    if t in ("action_requested", "verdict") and r.get("label") and lb != "driver":
        ok8 = False
    if t in ("prediction_pre", "decision", "final", "note", "rejected") and lb != "none":
        ok8 = False
    if t in ("question", "hypothesis") and lb != "agent":
        ok8 = False
check("A8", "PASS" if ok8 else "FAIL",
      "label_by: P/V→driver; Q/H→agent (K0-M1); pre/decision/final/note/rejected→none")

vc = [r for r in rows if r["type"] == "verdict_check"]
vv = [r for r in rows if r["type"] == "verdict"]
check("A9", "PASS" if len(vv) == 1 and len(vc) == 1 and vc[0]["value"] == "match" else "FAIL",
      "verdict_check при вердикте: значение match")

pb = [r for r in rows if r["type"] == "prediction_before"]
pa = [r for r in rows if r["type"] == "prediction_after"]
check("A10", "PASS" if sorted(r["cell"] for r in pb) == sorted(c.as_text() for c in battery)
      and sorted(r["cell"] for r in pa) == sorted(c.as_text() for c in battery) else "FAIL",
      "prediction_before/after: ровно 9, клетки = батарея")

a = res.audit
check("A11", "PASS" if (a is not None and a.structural_full and a.agent_full
                        and a.correct_s4 == "match" and a.s6_complete is True) else "FAIL",
      "аудит: structural_full ∧ agent_full ∧ correct=match; s6_complete=true (решение 2026-10-15)")
print("      разрезы сквозного прогона:", json.dumps(
    {"structural_full": a.structural_full, "agent_full": a.agent_full,
     "agent_valid_full": a.agent_valid_full, "correct_s4": a.correct_s4,
     "s6_complete": a.s6_complete, "status_hint": a.status_hint},
    ensure_ascii=False))

m = res.metrics
check("A12", "PASS" if (m["n_E"] == 7 and abs(m["acc_before"] - 3/7) < 1e-9
                        and m["acc_after"] == 1.0 and abs(m["improvement"] - 4/7) < 1e-9
                        and m["o1_pass"] is True) else "FAIL",
      f"metrics: |E|=7, acc {m['acc_before']:.3f}→{m['acc_after']:.3f}, Δ={m['improvement']:.3f}, O1 pass")

# --- A13: невалидные ответы не мутируют журнал --------------------------------
run2 = run_dir_for(base, "K0-M1", 911)


def bad_agent(phase, ctx, attempt):
    if phase == "F1":
        return F1
    return "чепуха вне грамматики"


sess2 = Session(run2, bad_agent, seed=101, max_invalid_f2=3)
res2 = sess2.run()
rows2 = read_journal(run2 / "raw" / "journal.jsonl")
no_actions = not any(r["type"] in ("action_requested", "probe_outcome", "budget")
                     for r in rows2)
check("A13", "PASS" if res2.status == "halted" and no_actions else "FAIL",
      "невалидные F2-ответы: ноль записей исполнения; halt по предохранителю")

# --- A14: STOP останавливает до исполнения ------------------------------------
run3 = run_dir_for(base, "K0-M1", 912)


def stop_agent(phase, ctx, attempt):
    if phase == "F1":
        return F1
    (run3 / "STOP").write_text("", encoding="utf-8")
    return "ACTION: reset"


sess3 = Session(run3, stop_agent, seed=101)
res3 = sess3.run()
rows3 = read_journal(run3 / "raw" / "journal.jsonl")
check("A14", "PASS" if (res3.status == "halted" and rows3[-1]["type"] == "stop"
                        and not any(r["type"] == "action_requested" for r in rows3)) else "FAIL",
      "STOP: блок не исполнен; последняя запись — stop")

# --- A15: эхо меток в контексте (§7) ------------------------------------------
lab_first = sess.sent_contexts[0].last_labels
lab_last = sess.sent_contexts[-1].last_labels
f2ctx = [c for c in sess.sent_contexts if c.phase == "F2"]
lab_mid = f2ctx[1].last_labels if len(f2ctx) > 1 else None
ok15 = (lab_first == (0, 0, 0, 0) and lab_mid == (1, 3, 0, 0)
        and lab_last == (1, 3, 2, 1))
check("A15", "PASS" if ok15 else "FAIL",
      f"§7 «эхо меток»: (Q,H,P,V) в контексте: старт {lab_first}, после регистраций {lab_mid}, финал {lab_last}")

# --- A16: повреждённый журнал -------------------------------------------------
with open(run2 / "raw" / "journal.jsonl", "a", encoding="utf-8") as f:
    f.write('{"seq": 999, "type": "que')
try:
    read_journal(run2 / "raw" / "journal.jsonl")
    ok16 = False
except JournalError:
    ok16 = True
check("A16", "PASS" if ok16 else "FAIL",
      "обрезка записи → JournalError (без молчаливого пропуска)")

# --- A17: бюджет не «грабится» ------------------------------------------------
w = World(battery)
for _ in range(16):
    w.probe(Cell("O4", 0, 0))
try:
    w.probe(Cell("O4", 0, 0))
    ok17 = False
except BudgetExhausted:
    ok17 = True
check("A17", "PASS" if ok17 else "FAIL", "17-е действие: BudgetExhausted")

# --- A18/N1: прогноз не для клетки пробы → not_checked -------------------------
run4 = run_dir_for(base, "K0-M1", 913)
calls4 = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}


def cell_agent(phase, ctx, attempt):
    calls4[phase] += 1
    if phase == "F1":
        return F1
    if phase == "F2":
        i = calls4["F2"]
        if i == 1:
            return REG
        if i == 2:
            return "PREDICT: O4 T=2 H=1 = present\nACTION: probe O4 T=2 H=1"
        if i == 3:
            return "VERDICT: H1 supported AFTER P1"
        return "ACTION: reset"
    if phase == "F3":
        return F3
    if phase == "F4":
        return FINAL
    raise AssertionError(phase)


sess4 = Session(run4, cell_agent, seed=101)
res4 = sess4.run()
rows4 = read_journal(run4 / "raw" / "journal.jsonl")
check("A18", "PASS" if (res4.audit.correct_s4 == "not_checked"
                        and not any(r["type"] == "verdict_check" for r in rows4)) else "FAIL",
      "N1/N2 (доп. №1 v1.0): проба не на клетке прогноза → verdict_check не пишется, correct=not_checked")

# --- N4: «эхо текста» (узкое определение, доп. №1 v1.0) ------------------------
ok_n4 = (is_echo_content(" Present ", ["present"])
         and not is_echo_content("гипотеза H1 supported", ["present"]))
check("N4", "PASS" if ok_n4 else "FAIL",
      "«эхо текста»: полное совпадение после нормализации = эхо; утверждение о H — не эхо")

# --- N6: rejections.json --------------------------------------------------------
rej_path = run / "derived" / "rejections.json"
rej_ok = rej_path.exists() and json.loads(rej_path.read_text(encoding="utf-8")) == []
check("N6", "PASS" if rej_ok else "FAIL",
      "derived/rejections.json пишется (пуст без отказов Q/H/V; наполнение — test_session)")


# --- N8: несколько блоков в одном ответе (сессия + журнал + аудит) -------------
def _n8_run(run_dir, f2_map):
    calls = {"F1": 0, "F2": 0, "F3": 0, "F4": 0}

    def respond(phase, ctx, attempt):
        calls[phase] += 1
        if phase == "F1":
            return F1
        if phase == "F2":
            i = calls["F2"]
            if i in f2_map:
                return f2_map[i]
            return "ACTION: reset"
        if phase == "F3":
            return F3
        if phase == "F4":
            return FINAL
        raise AssertionError(phase)

    sess = Session(run_dir, respond, seed=101)
    res = sess.run()
    rows = read_journal(run_dir / "raw" / "journal.jsonl")
    return res, rows


TWO = ("PREDICT: O2 T=2 H=1 = present\n"
       "ACTION: probe O2 T=2 H=1 DISTINGUISH: H1,H2,H3\n"
       "QUESTION Q2: продолжение? REF: t01\n"
       "PREDICT: O4 T=2 H=1 = present\nACTION: probe O4 T=2 H=1")
res5, rows5 = _n8_run(run_dir_for(base, "K0-M1", 921), {1: REG, 2: TWO})
ok_n8_1 = (len([r for r in rows5 if r["type"] == "probe_outcome"]) == 2
           and res5.audit.links["S3"].structural and res5.audit.links["S3"].agent
           and res5.audit.links["S6"].structural)
check("N8-1", "PASS" if ok_n8_1 else "FAIL",
      "два блока в одном ответе: оба исполнены по порядку; S3/S6 структурно ok")

PARTIAL = ("PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1\n"
           "QUESTION Q2: продолжение? REF: t01\n"
           "ACTION: probe O4 T=2 H=1\n"
           "NOTE: не должна пройти")
res6, rows6 = _n8_run(run_dir_for(base, "K0-M1", 922), {1: REG, 2: PARTIAL})
types6 = [r["type"] for r in rows6]
ok_n8_2 = (types6.count("probe_outcome") == 1
           and types6.count("action_rejected") == 1
           and types6.count("note") == 0
           and res6.audit.links["S6"].structural)
check("N8-2", "PASS" if ok_n8_2 else "FAIL",
      "частичное исполнение: блок1 исполнен, блок2 отвергнут (action_rejected), NOTE не записаны")

LAST = ("ACTION: reset\nQUESTION Q2: да? REF: t01\n"
        "PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1")
res7, rows7 = _n8_run(run_dir_for(base, "K0-M1", 923), {1: REG, 17: LAST})
budgets7 = [r for r in rows7 if r["type"] == "budget"]
descs7 = [r.get("descriptor") for r in rows7 if r["type"] == "action_requested"]
ok_n8_3 = (len(budgets7) == 16 and budgets7[-1]["remaining"] == 0
           and "probe O2 T=2 H=1" not in descs7)
check("N8-3", "PASS" if ok_n8_3 else "FAIL",
      "стоп между блоками (бюджет): блок 2 не исполнен, записей блока 2 нет")

PROBE1 = "PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1"
FUTURE = ("DECISION: probe O3 T=2 H=1 USING V1\n"
          "PREDICT: O3 T=2 H=1 = present\n"
          "ACTION: probe O3 T=2 H=1\n"
          "FINAL: разделитель\n"
          "VERDICT: H1 supported AFTER P1")
res8, rows8 = _n8_run(run_dir_for(base, "K0-M1", 924), {1: REG, 2: PROBE1, 3: FUTURE})
rej8 = [r for r in rows8 if r["type"] == "action_rejected"]
vc8 = [r for r in rows8 if r["type"] == "verdict_check"]
ok_n8_4 = (len(rej8) == 1 and rej8[0]["reason"] == "decision_invalid"
           and len(vc8) == 1 and vc8[0]["value"] == "match"
           and all(r.get("descriptor") != "probe O3 T=2 H=1"
                   for r in rows8 if r["type"] == "action_requested"))
check("N8-4", "PASS" if ok_n8_4 else "FAIL",
      "USING V на вердикт ниже по тексту: блок отклонён (decision_invalid); вердикт записан")

# --- S6-NEG: аудитор ловит «воскрешение» опровергнутой (полнота проверок S6) ---
run9 = run_dir_for(base, "K0-M1", 925)
j9 = Journal(run9).open()
j9.history_shown(101, ["t01"])
j9.question(1, "вопрос?", "t01")
j9.hypothesis(1, 1, "h1", Cell("O2", 2, 1), "present")
j9.hypothesis(2, 1, "h2", Cell("O2", 2, 1), "present")
pre9 = j9.prediction_pre(Cell("O2", 2, 1), "present")
ar9 = j9.action_requested("probe O2 T=2 H=1", prediction_ref=pre9, p_label="P1")
j9.probe_outcome(Cell("O2", 2, 1), "present", False, True)
j9.budget(1, 15, action_ref=ar9["seq"])
v9 = j9.verdict("V1", 2, "refuted", 1)
j9.verdict_check("match", v9["seq"])
pre9b = j9.prediction_pre(Cell("O4", 2, 1), "present")
ar9b = j9.action_requested("probe O4 T=2 H=1", prediction_ref=pre9b, p_label="P2")
j9.probe_outcome(Cell("O4", 2, 1), "present", False, True)
j9.budget(1, 14, action_ref=ar9b["seq"])
v9b = j9.verdict("V2", 2, "supported", 2)
j9.verdict_check("match", v9b["seq"])
j9.close()
rep9 = audit_run(run9)
check("S6-NEG", "PASS" if (rep9.links["S6"].structural is False
                           and rep9.links["S6"].details["reuse_refuted"] is False) else "FAIL",
      "негатив S6: «воскрешение» опровергнутой ловится аудитором (S6=false)")

# --- CH: офлайн-проверки канала (A20b, контракт K0_CHANNEL_CONTRACT.md) --------
run_ch1 = run_dir_for(base, "K0-M1", 931)
ch1 = LoopbackChannel([F1, REG, B1] + ["ACTION: reset"] * 15 + [F3, FINAL])
sess_ch1 = Session(run_ch1, make_respond(ch1), seed=101)
res_ch1 = sess_ch1.run()
reqs = sorted(p.name.replace(".request.txt", "")
              for p in (run_ch1 / "raw" / "calls").glob("*.request.txt"))
resps = sorted(p.name.replace(".response.txt", "")
               for p in (run_ch1 / "raw" / "calls").glob("*.response.txt"))
ok_ch1 = (res_ch1.status == "completed" and len(ch1.sent) == 20
          and len(reqs) == 20 and reqs == resps
          and (run_ch1 / "passport" / "passport.json").exists())
check("CH-1", "PASS" if ok_ch1 else "FAIL",
      "канал (loopback): 20 вызовов, пары request/response 1:1, паспорт записан")

run_ch2 = run_dir_for(base, "K0-M1", 932)
ch2 = LoopbackChannel([F1, REG, ChannelError("transport", "смоделированный обрыв")])
sess_ch2 = Session(run_ch2, make_respond(ch2), seed=101)
res_ch2 = sess_ch2.run()
reqs2 = len(list((run_ch2 / "raw" / "calls").glob("*.request.txt")))
resps2 = len(list((run_ch2 / "raw" / "calls").glob("*.response.txt")))
try:
    read_journal(run_ch2 / "raw" / "journal.jsonl")
    j2_ok = True
except JournalError:
    j2_ok = False
passport2 = json.loads((run_ch2 / "passport" / "passport.json").read_text(encoding="utf-8"))
ok_ch2 = (res_ch2.status == "halted" and res_ch2.stop_reason == "indeterminate"
          and sess_ch2.state == "HALTED" and reqs2 == 3 and resps2 == 2
          and j2_ok and passport2["status"] == "halted")
check("CH-2", "PASS" if ok_ch2 else "FAIL",
      "канал: обрыв ⇒ indeterminate → стоп; request без response; паспорт halted")

run_ch3 = run_dir_for(base, "K0-M1", 933)
err3 = ChannelError("timeout", "нет ответа", stage="connect")
ch3 = LoopbackChannel([err3, F1, REG, B1] + ["ACTION: reset"] * 15 + [F3, FINAL])
sess_ch3 = Session(run_ch3, make_respond(ch3), seed=101)
res_ch3 = sess_ch3.run()
metas3 = [json.loads(p.read_text(encoding="utf-8"))
          for p in sorted((run_ch3 / "raw" / "calls").glob("*.meta.json"))]
ok_ch3 = (res_ch3.status == "completed"
          and [m["class"] for m in metas3].count("no_response") == 1
          and len(list((run_ch3 / "raw" / "calls").glob("000[12]_F1_a1.request.txt"))) == 2)
check("CH-3", "PASS" if ok_ch3 else "FAIL",
      "O1: no_response — ровно один повтор; обе попытки в calls")

# --- TLS/SCN: подготовка к живому каналу (K0_LIVE_CHANNEL_PREP_ACT.md) ---------
_ctx = _strict_context(None)
_src = (HERE / "channel.py").read_text(encoding="utf-8")
tls_ok = (_ctx.verify_mode == ssl.CERT_REQUIRED and _ctx.check_hostname is True
          and "CERT_NONE" not in _src
          and "check_hostname=False" not in _src
          and "check_hostname = False" not in _src)
check("TLS-1", "PASS" if tls_ok else "FAIL",
      "строгая TLS-верификация; отключение отсутствует в исходнике канала")

_secret = "K0ADM-SECRET-zz99"
_hits = scan_text("вот " + secret_forms(_secret)["hex"], _secret)
scn_ok = ("hex" in _hits and scan_text("чисто", _secret) == []
          and scan_exceptions([ValueError("boom " + _secret)], _secret) != []
          and scan_exceptions([ValueError("ok")], _secret) == [])
check("SCN-1", "PASS" if scn_ok else "FAIL",
      "сканер секретов: формы (hex) ловятся; аварийные пути проверяются")

# --- OLL-1: совместимость с целевым локальным /api/chat (Ollama) ----------------
_oll_body = ollama_payload_builder("gemma4-e4b-heretic:q4km")("F2", 1, "промпт")
oll_ok = (extract_content({"message": {"content": "x"}}) == "x"
          and HttpChannel._extract_meta({"prompt_eval_count": 10, "eval_count": 5})
          == {"prompt_eval_count": 10, "eval_count": 5}
          and _oll_body["model"] == "gemma4-e4b-heretic:q4km"
          and _oll_body["messages"] == [{"role": "user", "content": "промпт"}]
          and _oll_body["stream"] is False
          and _oll_body["options"]["seed"] == 1729
          and _oll_body["options"]["num_ctx"] == 4096
          and _oll_body["options"]["num_predict"] == 256)
check("OLL-1", "PASS" if oll_ok else "FAIL",
      "целевой /api/chat: тело T0 §3, форма message.content, счётчики из корня")

# --- A19: номенклатура фаз -----------------------------------------------------
check("A19", "NOTE",
      "фаза постобработки в коде — «F5»; в отчётах обозначается postprocess/audit (рекомендация доп. №1 принята; код без изменений)")

# --- A20: raw/calls и passport (§11) ------------------------------------------
calls_dir = run / "raw" / "calls"
names = sorted(p.name for p in calls_dir.iterdir())
req_ok = len([n for n in names if n.endswith(".request.txt")]) == 20
resp_ok = len([n for n in names if n.endswith(".response.txt")]) == 20
meta_ok = len([n for n in names if n.endswith(".meta.json")]) == 20     # O1
pp_path = run / "passport" / "passport.json"
pp = json.loads(pp_path.read_text(encoding="utf-8")) if pp_path.exists() else {}
a20_ok = (len(names) == 60 and req_ok and resp_ok and meta_ok
          and (calls_dir / "0001_F1_a1.response.txt").read_text(encoding="utf-8") == F1
          and (calls_dir / "0020_F4_a1.response.txt").read_text(encoding="utf-8") == FINAL
          and pp.get("protocol_version") == "v35"
          and pp.get("protocol_sha256") == vh35
          and pp.get("protocol_diff_sha256") == sha(
              K0 / "version-history" / "K0_PROTOCOL_v34_to_v35.diff")
          and pp.get("driver_sha256", {}).get("parser.py") == sha(HERE / "parser.py")
          and pp.get("protocol_base_sha256") == vh
          and pp.get("status") == "completed"
          and pp.get("n_E") == 7
          and bool(pp.get("spec_sha256")) and bool(pp.get("prompts_sha256"))
          and isinstance(pp.get("driver_sha256"), dict)
          and pp.get("t0_params", {}).get("seed") == 1729)
check("A20", "PASS" if a20_ok else "FAIL",
      "§11: calls 20×(request/response/meta); passport: v35+спека+промпты+драйвер+параметры")
check("A20b", "OPEN",
      "реальные байты канала модели (сеть/вызовы) — до подключения канала и отдельного разрешения")

print()
counts = {}
for _, st, _ in RESULTS:
    counts[st] = counts.get(st, 0) + 1
print("Сводка:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
