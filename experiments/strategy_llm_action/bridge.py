# -*- coding: utf-8 -*-
"""LLM Bridge (STRATEGY → LLM → ACTION; PROTOCOL FROZEN 11.09.2026).

Мост = отдельный оркестратор между внешним policy (LLMRequest) и
executor'ом. Роль: transform strategy suggestion into an executable
proposal WITHOUT bypassing permission.

Правила (из DESIGN/PROTOCOL):
- strategy НЕ импортируется мостом и НЕ трогается (T7-дух);
- LLM — только генератор proposal; право — у executor-ворот;
- fail closed: любой сбой LLM → NO ACTION (никогда не implicit
  fallback execution);
- LLM failure ≠ Explore: мост не эмитит S3/Explore-события;
- G-a/G-b/G-c — bridge-side guards; G-d — сам executor
  (permitted + allowlist + МЕTА); обходов нет.
"""
import os
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from executor import executor  # noqa: E402
from llm import adapter  # noqa: E402


class Bridge(object):
    def __init__(self, store, allowed_action_space=None,
                 excluded_commands=None, provider="gemma"):
        self.store = store
        self.allowed = tuple(allowed_action_space or
                             executor.ALLOWED_PREFIXES)
        self.excluded = set(excluded_commands or [])
        self.provider = provider

    # --- получение предложения (три маршрута; файлы не меняются) ---
    def _llm_call(self, prompt, raw_override=None, url_override=None,
                  timeout=120, max_tokens=None):
        meta = {"provider": self.provider, "route": "",
                "url": adapter.PROVIDERS.get(self.provider,
                                             {}).get("url")}
        if raw_override is not None:
            # adapter-level controlled (N1): НАСТОЯЩИЕ parse/validate
            raw = raw_override
            try:
                obj = adapter.parse_json(raw)
                val = adapter.validate(obj)
                out = {"ok": True, "candidate_actions":
                       val["candidate_actions"],
                       "rationale": val["rationale"], "raw": raw,
                       "error": ""}
            except ValueError as exc:
                out = {"ok": False, "candidate_actions": [],
                       "rationale": "", "raw": raw,
                       "error": "parse/validate: %s" % str(exc)[:200]}
            meta["route"] = "adapter_parse_controlled"
            return out, meta
        if url_override:
            # реальный сетевой отказ (N3): временная подмена url
            saved = dict(adapter.PROVIDERS[self.provider])
            adapter.PROVIDERS[self.provider]["url"] = url_override
            try:
                out = adapter.propose(self.provider, prompt,
                                      max_tokens=max_tokens,
                                      timeout=timeout)
            finally:
                adapter.PROVIDERS[self.provider] = saved
            meta["route"] = "adapter_network_override"
            meta["url"] = url_override
            return out, meta
        out = adapter.propose(self.provider, prompt,
                              max_tokens=max_tokens, timeout=timeout)
        meta["route"] = "adapter_live"
        return out, meta

    # --- полный проход эпизода ---
    def invoke(self, task, context, episode_id, grant=True,
               raw_override=None, url_override=None, timeout=120):
        rec = {"episode_id": episode_id,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "request": {"task": task, "context": context,
                           "allowed_action_space": list(self.allowed),
                           "excluded_commands": sorted(self.excluded),
                           "grant": bool(grant)},
               "provider": self.provider, "llm_meta": None,
               "raw": "", "llm_error": "", "parsed": None,
               "gates": [], "decision": None, "no_action_reason": None,
               "action": None, "result": None, "executed": False}
        prompt = adapter.build_prompt(task, context)
        out, meta = self._llm_call(prompt, raw_override, url_override,
                                   timeout)
        rec["llm_meta"] = meta
        rec["raw"] = out.get("raw", "")
        rec["llm_error"] = out.get("error", "")
        rec["provider_meta"] = out.get("provider_meta")

        # G-a: структурная валидность (+ usable command)
        action_cmd = None
        acts = out.get("candidate_actions") or []
        if out.get("ok") and acts:
            a0 = acts[0]
            if (isinstance(a0, dict)
                    and a0.get("type", "command") == "command"
                    and isinstance(a0.get("command"), str)
                    and a0["command"].strip()):
                action_cmd = a0["command"].strip()
        rec["parsed"] = {"ok": bool(out.get("ok")),
                         "action": action_cmd, "arguments": {}}
        if action_cmd is None:
            rec["gates"].append({"gate": "G-a", "ok": False,
                                 "reason": out.get("error")
                                 or "no usable action"})
            rec["decision"] = "no_action"
            rec["no_action_reason"] = "G-a"
            return rec
        rec["gates"].append({"gate": "G-a", "ok": True})

        # G-b: allowed_action_space (префикс-матч, как у executor)
        if not action_cmd.startswith(self.allowed):
            rec["gates"].append({"gate": "G-b", "ok": False,
                                 "reason": "action outside "
                                 "allowed_action_space"})
            rec["decision"] = "no_action"
            rec["no_action_reason"] = "G-b"
            return rec
        rec["gates"].append({"gate": "G-b", "ok": True})

        # G-c: command-match guard (excluded candidates)
        if action_cmd in self.excluded:
            rec["gates"].append({"gate": "G-c", "ok": False,
                                 "reason": "command matches excluded "
                                 "candidate (command-level)"})
            rec["decision"] = "no_action"
            rec["no_action_reason"] = "G-c"
            return rec
        rec["gates"].append({"gate": "G-c", "ok": True})

        # G-d: единственный путь исполнения — executor
        act = {"schema_version": "0.1",
               "action_id": "act_llm1_%s" % uuid.uuid4().hex[:8],
               "strategy_id": None, "proposed_by": "llm-bridge",
               "type": "command", "command": action_cmd,
               "args": {"goal": {}, "ctx_extra": "absent"},
               "permitted": bool(grant),
               "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "rationale": "LLM proposal (bridge)"}
        rec["action"] = act
        self.store.append_action(act)
        res = executor.execute(self.store, act)
        rec["result"] = {"result_id": res.get("result_id"),
                         "refused": res.get("refused"),
                         "exit_code": res.get("exit_code"),
                         "stderr": (res.get("stderr") or "")[:200],
                         "outcome": res.get("outcome")}
        rec["executed"] = not res.get("refused")
        if res.get("refused"):
            rec["gates"].append({"gate": "G-d", "ok": False,
                                 "reason": rec["result"]["stderr"]})
            rec["decision"] = "no_action"
            rec["no_action_reason"] = "G-d"
        else:
            rec["gates"].append({"gate": "G-d", "ok": True})
            rec["decision"] = "executed"
        return rec
