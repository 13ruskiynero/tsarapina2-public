# -*- coding: utf-8 -*-
"""LLM Adapter (Tsarapina, этап 4).

Предельно узкая роль: Strategy (S5) → llm_request → модель →
structured response → candidate Action.

Правила (FIXED):
- модель НЕ знает о хранилище: адаптер не принимает store и не
  импортирует knowledge/experience/storage/executor;
- модель МОЖЕТ предложить действие, но НЕ может записать Knowledge,
  изменить Experience или считать действие выполненным;
- ответ — строго заданный формат (JSON), парсится устойчиво;
- провайдер сменный (gemma3:4b / gemma4 / qwen3:4b — ollama): код один,
  меняется конфиг (url, model);
- ошибки модели (не-JSON, пусто) возвращаются структурно (ok=False),
  не роняют систему.

RESEARCHABLE (не здесь): выбор модели, оценка качества ответов,
использование reasoning-режимов.
"""
import json
import re
import urllib.error
import urllib.request

PROVIDERS = {
    # gemma3:4b — legacy-провайдер (baseline VERTICAL-1/LONG-3);
    # с 12.09.2026 модель снята с диска; конфиг сохранён для истории
    # и детерминированных тестов.
    "gemma": {"url": "http://localhost:11434/v1/chat/completions",
              "model": "gemma3:4b", "max_tokens": 300},
    # gemma4-e4b-heretic:q4km — основной провайдер с 12.09.2026
    # (V-SWAP-G4: поведение совпало с gemma3 на сценариях vertical1).
    # По умолчанию включает thinking; reasoning_effort=none отключает
    # думание (диагностика: diag_gemma4.py). max_tokens=300 — тот же
    # контракт, что у gemma, с запасом.
    "gemma4": {"url": "http://localhost:11434/v1/chat/completions",
               "model": "gemma4-e4b-heretic:q4km", "max_tokens": 300,
               "extra_body": {"reasoning_effort": "none"}},
    # qwen3:4b — думающая модель: думание на JSON-задачу 2500-5000+
    # токенов (см. diag_qwen3-5); малый лимит даёт пустой ответ
    "qwen": {"url": "http://localhost:11434/v1/chat/completions",
             "model": "qwen3:4b", "max_tokens": 8000},
    # qwen2.5:3b — не думает; прямой контракт JSON
    "qwen25": {"url": "http://localhost:11434/v1/chat/completions",
               "model": "qwen2.5:3b", "max_tokens": 300},
}

SYSTEM = ("Ты — процессор предложения действий диагностической "
          "системы. Ты НЕ выполняешь действий и НЕ имеешь доступа к "
          "хранилищу. По задаче предложи 1-3 кандидата действия. "
          "Верни ТОЛЬКО JSON без пояснений, в формате: "
          '{"candidate_actions": [{"type": "command", "command": '
          '"<команда>"}], "rationale": "<почему>"}.')


def chat(url, model, prompt, max_tokens=300, temperature=0.0,
         timeout=120, with_meta=False, extra_body=None):
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if extra_body:
        body.update(extra_body)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"].strip()
    if with_meta:
        usage = data.get("usage") or {}
        meta = {"prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count")}
        return content, meta
    return content


def parse_json(raw):
    """Устойчивый парсинг: допускает текст вокруг JSON-блока."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON-блок не найден")
    return json.loads(raw[start:end + 1])


def validate(obj):
    """Проверка структуры ответа."""
    if not isinstance(obj, dict):
        raise ValueError("ответ не объект")
    acts = obj.get("candidate_actions")
    if not isinstance(acts, list) or not acts:
        raise ValueError("candidate_actions пуст или не список")
    out = []
    for a in acts:
        if not isinstance(a, dict):
            raise ValueError("действие не объект")
        atype = a.get("type", "command")
        cmd = a.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            raise ValueError("действие без command")
        out.append({"type": atype, "command": cmd.strip()})
    rationale = obj.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = ""
    return {"candidate_actions": out, "rationale": rationale.strip()}


def propose(provider, prompt, max_tokens=None, timeout=120):
    """Вызвать модель, вернуть структурированное предложение.

    max_tokens=None → лимит провайдера (gemma 300, qwen 1200).
    Возвращает dict: {ok, candidate_actions, rationale, raw, error,
    provider_meta} (provider_meta — существующие метаданные ответа
    провайдера: prompt_tokens/completion_tokens/total_tokens/
    prompt_eval_count/eval_count; отсутствующие — None).
    Никогда не бросает исключений наружу (кроме конфиг-ошибок)."""
    try:
        cfg = PROVIDERS[provider]
    except KeyError:
        return {"ok": False, "candidate_actions": [], "rationale": "",
                "raw": "", "error": "unknown provider: %s" % provider,
                "provider_meta": None}
    if max_tokens is None:
        max_tokens = cfg.get("max_tokens", 300)
    try:
        _res = chat(cfg["url"], cfg["model"], prompt,
                    max_tokens=max_tokens, timeout=timeout,
                    with_meta=True,
                    extra_body=cfg.get("extra_body"))
        if isinstance(_res, tuple) and len(_res) == 2:
            raw, meta = _res
        else:  # совместимость с моками/чатами без метаданных
            raw, meta = _res, None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return {"ok": False, "candidate_actions": [], "rationale": "",
                "raw": "", "error": "chat: %s" % str(exc)[:200],
                "provider_meta": None}
    try:
        obj = parse_json(raw)
        val = validate(obj)
        return {"ok": True, "candidate_actions": val["candidate_actions"],
                "rationale": val["rationale"], "raw": raw, "error": "",
                "provider_meta": meta}
    except (ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "candidate_actions": [], "rationale": "",
                "raw": raw, "error": "parse/validate: %s" % str(exc)[:200],
                "provider_meta": meta}


def build_prompt(task, context=None):
    """Собрать запрос: задача + (опционально) контекст, который
    подготовила СИСТЕМА (не модель): релевантные знания/наблюдения."""
    parts = ["Текущая задача: %s" % task]
    if context:
        parts.append("Доступный контекст (подготовлен системой):")
        parts.append(context)
    return "\n".join(parts)