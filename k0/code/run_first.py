#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — раннер серии K0-M3/104 (v37-A).

Одна серия K0-M3, сид 101; модель gemma4-e4b-heretic:q4km (ID e8bb5f9335d7);
канал строго loopback: http://127.0.0.1:11434/api/chat; внешних сетевых
вызовов нет. Порядок:
  0) PREFLIGHT (до первого обращения к модели): STOP-файл, каталог запуска,
     хэши обязательных файлов против утверждённого снимка, идентичность модели
     (digest из /api/tags, а не только имя). Любая ошибка → выход без вызова
     модели;
  1) канареечный вызов F1 — сверка prompt_eval_count с локальной оценкой
     (llama-tokenize); расхождение >10% → СТОП без сессии;
  2) прогон сессии (лимиты и STOP — из протокола, без исключений);
  3) печать сводки по фактическим артефактам (без интерпретаций).
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
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
MODEL_PIN = "e8bb5f9335d7"           # утверждённый digest-префикс идентичности модели
HOST, PORT, API_PATH = "127.0.0.1", 11434, "/api/chat"
SEED = 101
BASE = K0 / "runs"
RUN_NAME = "run_K0-M3_104_v37"   # тот же сид 101; v37: пригодная цель после решения
ARTIFACTS = K0 / "artifacts"
TOLERANCE = 0.10

# Утверждённый снимок обязательных файлов (хэши из акта v37-A и дополнений).
# run_first.py в снимок не входит: самопроверка собственного хэша циркулярна;
# его хэш фиксируется публикацией и сверяется ревьюером.
SNAPSHOT = {
    "code/prompts.py": "c79c28d6f6383f91f63dbf94d958b52742fab9fcec83144db7ce5d78293bce51",
    "code/session.py": "c06f9ec5e1a501b2927b1a7490035ffd89f4437e94dad4bf96016a1ef541a6f8",
    "code/journal.py": "b19de14a7fe16c2a444e9b2b3dad99a0dce68457e0b1cbb9c0c9975fc3e7652d",
    "code/parser.py": "d21b426e064beabdf448a1f7e86592341d8ed4094d79cb9f928bfbd0de6a2d86",
    "code/calls.py": "0e18e665cd833df1d0f54c05f28b0786edc8cf8c20622bc89297d3c7dcab8e3f",
    "code/channel.py": "f7d21e28870340b0e4b793a8b1aea99bebabbacca03a56523111abfc89dbd91e",
    "code/world.py": "054709565396ac89a9d9a2eb972556f1a9155f3ebfda75bc963d2096c558e38a",
    "code/auditor.py": "c716ccca97df9f60f07e6b727de82f4372a10067e2e73c3d575c310d4dfe83c9",
    "K0_PROTOCOL_v37.md": "918fac28586b2265119ef13af588b081daa73b3c80d6d8c7458d120a616d07f0",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ollama_model_digest(host: str = HOST, port: int = PORT,
                         timeout: float = 5.0):
    """Digest модели из /api/tags (идентичность, не только имя)."""
    url = f"http://{host}:{port}/api/tags"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for m in data.get("models", []):
        if m.get("name") == MODEL:
            return m.get("digest")
    return None


def preflight(k0_root, run_dir, stop_path, snapshot, model_digest_getter=None):
    """Проверки ДО первого обращения к модели. Возвращает список проблем."""
    problems = []
    if Path(stop_path).exists():
        problems.append("STOP: файл остановки присутствует")
    if Path(run_dir).exists():
        problems.append(f"run_dir_exists: {run_dir}")
    if not snapshot:
        problems.append("snapshot_empty")
    for rel, expected in sorted((snapshot or {}).items()):
        p = Path(k0_root) / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif _sha(p) != expected:
            problems.append(f"sha_mismatch: {rel}")
    if model_digest_getter is None:
        problems.append("model_check_missing")
    else:
        try:
            digest = model_digest_getter()
        except Exception as exc:  # noqa: BLE001 — любая ошибка проверки = стоп
            problems.append(f"model_check_error: {type(exc).__name__}")
        else:
            if not digest:
                problems.append("model_unavailable")
            elif not str(digest).startswith(MODEL_PIN):
                problems.append(f"model_identity: {str(digest)[:16]}")
    return problems


def f1_prompt() -> str:
    """F1-промпт РОВНО тем же путём, что промпт сессии: тот же порядок
    батареи (порядок загрузки, как в Session._context) и тот же диспетчер
    prompts.build_prompt."""
    history = tuple(load_history(ARTIFACTS / "history_101.jsonl"))
    battery = tuple(item.cell.as_text()
                    for item in load_battery(ARTIFACTS / "heldout_battery.json"))
    ctx = AgentContext(phase="F1", history=history, battery=battery)
    return prompts.build_prompt(ctx, "F1", 1)


def main() -> int:
    run_dir = BASE / RUN_NAME

    problems = preflight(K0, run_dir, K0 / "STOP", SNAPSHOT,
                         _ollama_model_digest)
    if problems:
        print("[СТОП] preflight не пройден (модель не вызывалась):")
        for p in problems:
            print("  -", p)
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
        print("[СТОП] счётчики недоступны для сверки — сессия не запускается")
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
