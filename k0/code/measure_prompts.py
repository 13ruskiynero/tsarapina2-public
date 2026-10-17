#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — измерение укладки промптов (метод T0 evidence-2; офлайн).

Строит промпты F1–F4 на реальных истории и батарее + синтетических
наблюдениях/заметках (несколько уровней наполнения), оборачивает в
серверную строку T0-стиля `<|turn>user\\n{content}<turn|>\\n<|turn>model\\n`
и считает токены локальным `llama-tokenize` (та же сборка llama.cpp и тот
же GGUF, что у модели). Модель НЕ вызывается; сеть не используется.

Запуск: python3 lab/autonomy/k0/code/measure_prompts.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parent
K0_DIR = THIS.parent.parent
sys.path.insert(0, str(CODE_DIR))

from world import load_battery, load_history  # noqa: E402
from session import AgentContext  # noqa: E402
import prompts  # noqa: E402

MODEL = "/root/models/gemma4-e4b-heretic-q4km.gguf"
TOKENIZER = "/root/llama.cpp/build/bin/llama-tokenize"
ARTIFACTS = K0_DIR / "artifacts"

C1 = 4096
TARGET = 4000


def count_tokens(server_text: str):
    """Число токенов серверной строки (llama-tokenize; BOS добавляется
    инструментом — возвращаем (с BOS, без BOS)). None при недоступности."""
    try:
        r = subprocess.run([TOKENIZER, "-m", MODEL, "--stdin"],
                           input=server_text.encode("utf-8"),
                           capture_output=True, timeout=180)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    n = len([l for l in r.stdout.decode("utf-8", "replace").splitlines() if "->" in l])
    return n, max(0, n - 1)


def server_wrap(content: str) -> str:
    return f"<|turn>user\n{content}<turn|>\n<|turn>model\n"


def make_ctx(phase, obs_n=0, notes_n=0, note_len=150, budget=16):
    history = tuple(load_history(ARTIFACTS / "history_101.jsonl"))
    battery = tuple(sorted(c.as_text() for c in
                           [i.cell for i in load_battery(ARTIFACTS / "heldout_battery.json")]))
    obs_cells = [f"O{(i % 4) + 1} T={(i // 4) % 3} H={i % 3}" for i in range(obs_n)]
    observations = tuple((c, "present" if i % 2 == 0 else "disappeared")
                         for i, c in enumerate(obs_cells))
    base = "заметка агента: наблюдал клетку O1 T=0 H=0 -> present; гипотеза проверяется."
    notes = tuple((base + f" №{i+1}").ljust(note_len, "·")[:note_len] for i in range(notes_n))
    return AgentContext(
        phase=phase, history=history, observations=observations,
        rejections=({"requested": "probe O3 T=0 H=0", "reason": "predict_invalid"},),
        budget_remaining=budget, last_probe=obs_cells[-1] if obs_cells else None,
        notes=notes, battery=battery if phase in ("F1", "F3") else (),
        last_labels=(1, 3, max(0, obs_n), 0),
    )


def main():
    scenarios = [
        ("F1 типовой", "F1", dict()),
        ("F3 (16 набл., 16 заметок)", "F3", dict(obs_n=16, notes_n=16)),
        ("F3 (16 набл., 32 заметки×300)", "F3", dict(obs_n=16, notes_n=32, note_len=300)),
        ("F4 (16 набл., 16 заметок)", "F4", dict(obs_n=16, notes_n=16)),
        ("F2 пустой опыт", "F2", dict()),
        ("F2 типовой (4 набл., 2 заметки)", "F2", dict(obs_n=4, notes_n=2)),
        ("F2 (16 набл., 8 заметок)", "F2", dict(obs_n=16, notes_n=8)),
        ("F2 (16 набл., 16 заметок×150)", "F2", dict(obs_n=16, notes_n=16)),
        ("F2 (16 набл., 32 заметки×300) — потолок", "F2", dict(obs_n=16, notes_n=32, note_len=300)),
    ]
    print(f"C1={C1}, target<={TARGET} токенов; серверная обёртка T0-стиля; "
          f"токенизатор: {TOKENIZER}")
    print(f"{'сценарий':44s} {'байт':>6s} {'ток(BOS)':>9s} {'ток(−BOS)':>10s}  итог")
    worst = 0
    for name, phase, kw in scenarios:
        ctx = make_ctx(phase, **kw)
        text = prompts._BUILDERS[phase](ctx)
        n = count_tokens(server_wrap(text))
        size = len(text.encode("utf-8"))
        if n is None:
            print(f"{name:44s} {size:6d}   токенизатор недоступен")
            continue
        with_bos, without = n
        worst = max(worst, with_bos)
        verdict = "OK" if with_bos <= TARGET else ("≤C1" if with_bos <= C1 else "ПРЕВЫШЕНИЕ C1")
        print(f"{name:44s} {size:6d} {with_bos:9d} {without:10d}  {verdict}")
    print(f"\nМаксимум по сценариям: {worst} токенов (с BOS).")


if __name__ == "__main__":
    main()
