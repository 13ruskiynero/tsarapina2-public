#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — раннер первого локального прогона (разрешение постановщика 2026-10-16).

Одна серия K0-M1, сид 101; модель gemma4-e4b-heretic:q4km (ID e8bb5f9335d7);
канал строго loopback: http://127.0.0.1:11434/api/chat; внешних сетевых
вызовов нет. Порядок (проект решения §7):
  1) канареечный вызов F1 — сверка prompt_eval_count с локальной оценкой
     (evidence-2, llama-tokenize); расхождение >10% → СТОП без сессии;
  2) прогон сессии (лимиты и STOP — из проекта, без исключений);
  3) печать сводки по фактическим артефактам (без интерпретаций).

Новая логика не добавляется: только сборка готовых модулей и печать фактов.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
K0 = HERE.parent
sys.path.insert(0, str(HERE))

from world import load_battery, load_history              # noqa: E402
from session import AgentContext, Session                 # noqa: E402
from channel import HttpChannel, make_respond, ollama_payload_builder  # noqa: E402
from measure_prompts import count_tokens, server_wrap      # noqa: E402
import prompts                                              # noqa: E402

MODEL = "gemma4-e4b-heretic:q4km"
HOST, PORT, API_PATH = "127.0.0.1", 11434, "/api/chat"
SEED = 101
BASE = K0 / "runs"
RUN_NAME = "run_K0-M3_101_v33"   # новая серия того же сида: отдельный каталог
ARTIFACTS = K0 / "artifacts"
TOLERANCE = 0.10


def f1_prompt() -> str:
    """F1-промпт РОВНО тем же путём, что промпт сессии: тот же порядок
    батареи (порядок загрузки, как в Session._context) и тот же диспетчер
    prompts.build_prompt (фикс канарейки, решение 2026-10-16)."""
    history = tuple(load_history(ARTIFACTS / "history_101.jsonl"))
    battery = tuple(item.cell.as_text()
                    for item in load_battery(ARTIFACTS / "heldout_battery.json"))
    ctx = AgentContext(phase="F1", history=history, battery=battery)
    return prompts.build_prompt(ctx, "F1", 1)


def main() -> int:
    run_dir = BASE / RUN_NAME
    if run_dir.exists():
        print(f"[СТОП] каталог запуска занят: {run_dir}")
        return 1

    channel = HttpChannel(HOST, PORT, path=API_PATH,
                          payload_builder=ollama_payload_builder(MODEL))
    prompt = f1_prompt()
    local = count_tokens(server_wrap(prompt))
    print(f"[канарейка] F1: {len(prompt.encode('utf-8'))} Б; локальная оценка: {local}")

    text = channel.send("F1", 1, prompt)          # первый вызов модели (loopback)
    meta = dict(channel.last_meta or {})
    srv = meta.get("prompt_eval_count")
    print(f"[канарейка] сервер: prompt_eval_count={srv}, eval_count={meta.get('eval_count')}")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preflight_canary.json").write_text(json.dumps({
        "model": MODEL, "host": HOST, "port": PORT, "path": API_PATH,
        "prompt_bytes": len(prompt.encode("utf-8")),
        "local_tokens_with_bos": (local[0] if local else None),
        "server_prompt_eval_count": srv,
        "server_eval_count": meta.get("eval_count"),
        "response_head": text[:500],
        "tolerance": TOLERANCE,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    if local is None or srv is None:
        print("[СТОП] счётчики недоступны для сверки (F2 чек-листа) — сессия не запускается")
        return 2
    n_local = local[0]
    diff = abs(srv - n_local) / max(1, n_local)
    print(f"[канарейка] расхождение: |{srv} − {n_local}| / {n_local} = {diff:.1%} (порог 10%)")
    if diff > TOLERANCE:
        print("[СТОП] расхождение >10% — пауза, разбор причины до продолжения")
        return 3
    print("[канарейка] сверка пройдена; запускаю серию")
    print(f"[канарейка] фрагмент ответа: {text[:200]!r}")

    sess = Session(run_dir, make_respond(channel, prompts.build_prompt), seed=SEED,
                   require_token_counts=True)
    res = sess.run()

    print("=== СВОДКА ===")
    print("status:", res.status, "| stop_reason:", res.stop_reason)
    print("respond_calls:", res.respond_calls, "| total_tokens:", sess.total_tokens)
    print("final_present:", res.final_present)
    print("metrics:", json.dumps(res.metrics, ensure_ascii=False))
    if res.audit is not None:
        a = res.audit
        print("audit:", f"structural_full={a.structural_full}",
              f"agent_full={a.agent_full}", f"agent_valid_full={a.agent_valid_full}",
              f"s6_complete={a.s6_complete}", f"correct_s4={a.correct_s4}")
    print("run_dir:", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
