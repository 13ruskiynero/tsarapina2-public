# -*- coding: utf-8 -*-
"""OUTPUT-BUDGET MAP-1: диагностический пробник (11.09.2026).

Цель (вердикт профессора): картировать минимальный completion-
бюджет, необходимый текущему structured proposal contract, при
ФИКСИРОВАННОМ prompt; отдельно от longitudinal Knowledge.

Read-only / isolated provider probe:
* НЕ меняет production adapter (используются его публичные функции
  chat/parse_json/validate как есть);
* НЕ трогает store/executor/слои; никаких эпизодов;
* prompt фиксирован: реальные контексты из starvation-траекторий
  (r2-E507: counter≈3907, available≈189; r1-E513: counter≈3983,
  available≈113). Переменная — max_tokens (completion budget).
* 8 runs: сетка бюджета на «свободном» контексте + 2 точки на
  starvation-контексте (полный доступный бюджет не закрывает
  контракт).

Классификация каждого run: valid / invalid (parse/validate);
фиксируются provider-метаданные (prompt_tokens, completion_tokens)
и фактический обрыв (completion == max_tokens при invalid).

Запуск: python3 obm1_probe.py
Артефакты: OBM1_run1..8.json (рядом, recon1/).
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from llm import adapter  # noqa: E402

DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"

with open(os.path.join(DIR, "RECON1_E507_r2.json"),
          encoding="utf-8") as f:
    CTX_FREE = json.load(f)["context"]
with open(os.path.join(DIR, "RECON1_E513_r1.json"),
          encoding="utf-8") as f:
    CTX_STARVED = json.load(f)["context"]

RUNS = [
    ("E507", CTX_FREE, 60),
    ("E507", CTX_FREE, 80),
    ("E507", CTX_FREE, 100),
    ("E507", CTX_FREE, 120),
    ("E507", CTX_FREE, 140),
    ("E507", CTX_FREE, 160),
    ("E513", CTX_STARVED, 113),
    ("E513", CTX_STARVED, 200),
]


def main():
    url = adapter.PROVIDERS["gemma"]["url"]
    for i, (tag, ctx, mt) in enumerate(RUNS, start=1):
        prompt = adapter.build_prompt(PROBLEM, ctx)
        out = {"run": i, "tag": tag, "max_tokens": mt,
               "context_chars": len(ctx)}
        try:
            raw, meta = adapter.chat(url, "gemma3:4b", prompt,
                                     max_tokens=mt, timeout=180,
                                     with_meta=True)
            out["provider_meta"] = meta
            status = "valid"
            err = ""
            try:
                obj = adapter.parse_json(raw)
                adapter.validate(obj)
            except ValueError as exc:
                status = "invalid"
                err = str(exc)[:200]
            out.update({"status": status, "error": err,
                        "raw_len": len(raw),
                        "raw_tail": raw[-90:]})
        except Exception as exc:
            out.update({"status": "provider_error",
                        "error": str(exc)[:200]})
        p = os.path.join(DIR, "OBM1_run%d.json" % i)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        pm = out.get("provider_meta") or {}
        print("run%d %s max_tokens=%s -> %s | prompt=%s compl=%s "
              "raw_len=%s" % (
                  i, tag, mt, out["status"],
                  pm.get("prompt_tokens"), pm.get("completion_tokens"),
                  out.get("raw_len")), flush=True)


if __name__ == "__main__":
    main()
