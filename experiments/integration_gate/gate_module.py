# -*- coding: utf-8 -*-
"""INTEGRATION GATE module (FROZEN 10.09.2026): механизмы
permission-алгебры поверх A1-базы (strategy_aa).

Интерфейс (No-new-policy):
    external trigger → gate mechanism → state transition → guards
Модуль НЕ принимает policy-решений: он не решает, «достаточно ли
evidence для R/S». Право выдаётся ИЗВНЕ (драйвер вызывает
exclude(kid)); модуль исполняет: eligibility-фильтр, TEMP state/slot,
S3-детекцию (после фактической проверки пула), Explore dispatch,
guards. Exclusion semantics — конфигурация: POOL | TEMP.

Гарантии:
  * стор не мутируется; события append-only (events[]);
  * pool empty проверяется ДО S3 (eligible-конструкция), затем
    согласованность с существующим selector'ом (guard);
  * SOL — только success ЧЛЕНА L (fix-aq-линии не считаются);
  * attempt ровно один; failure ⇒ остаётся excluded (no second slot);
  * при расхождении механизации с ожиданием — guard_violation
    (наблюдаемое состояние сохраняется, решение НЕ додумывается).
"""
import importlib.util
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # .../lab/tsarapina
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

DIR = os.path.dirname(os.path.abspath(__file__))
AA1_PATH = os.path.join(BASE, "experiments", "applicability_addressing1",
                        "strategy_aa.py")


def load_strategy_aa():
    spec = importlib.util.spec_from_file_location("strategy_aa_mod",
                                                  AA1_PATH)
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)
    return st


class FilteredStore(object):
    """Eligibility-фильтр: исключённые kid'ы невидимы для чтения
    кандидатов (POOL и TEMP используют один и тот же контур)."""

    def __init__(self, store, exclude_kids):
        self._store = store
        self._ex = set(exclude_kids or [])

    def read_knowledge_versions_all(self):
        return [v for v in self._store.read_knowledge_versions_all()
                if v["knowledge_id"] not in self._ex]

    def __getattr__(self, name):
        return getattr(self._store, name)


class GateModule(object):
    def __init__(self, store, semantics):
        assert semantics in ("POOL", "TEMP"), semantics
        self.store = store
        self.semantics = semantics
        self.st = load_strategy_aa()
        self.exclusions = []          # append-only, порядок выдачи
        self.slot_state = {}          # TEMP: kid -> none|open|consumed
        self.events = []              # append-only события механизма
        self.explore_pending = False
        self.guards = []

    # --- external triggers (право выдаёт драйвер; модуль исполняет) ---
    def exclude(self, kid, trigger_ref="E1"):
        if kid in self.exclusions:
            return
        self.exclusions.append(kid)
        if self.semantics == "TEMP":
            self.slot_state[kid] = "none"
        self.events.append({"event": "exclusion",
                            "knowledge_id": kid,
                            "semantics": self.semantics,
                            "trigger_ref": trigger_ref})

    # --- eligible pool construction (механизм; шаг ДО S3) ---
    def eligible_pool(self, problem, ctx_now, obs_now):
        src = FilteredStore(self.store, self.exclusions)
        snap = self.st._snapshot(src)
        tokens = self.st._tokens(problem)
        ex = set(self.exclusions)
        recs = []
        for s in snap:
            rec = src.read_knowledge(s["knowledge_id"])
            if rec is None or rec["knowledge_id"] in ex:
                continue
            recs.append(rec)
        rel = [r for r in recs
               if self.st._relevant(self.store, r, tokens)]
        out = {"n_snapshot": len(snap), "n_rel": len(rel)}
        task_sym = self.st._symptom_of(problem)
        exact = []
        if task_sym:
            exact = [r for r in rel
                     if self.st._rec_symptom(self.store, r) == task_sym]
        out["n_exact"] = len(exact)
        pool = exact if exact else rel
        pool = [r for r in pool if self.st._aa1_outcome_is_success(r)]
        out["n_pool_a1"] = len(pool)
        obs = obs_now
        elig = []
        for r in pool:
            aw = r.get("applicable_when")
            if aw is not None:
                if obs is None:
                    continue
                if all(obs.get(k) == v for k, v in aw.items()):
                    elig.append(r)
            else:
                c = self.st._ctx_extra_of(self.store, r)
                if c is None or c == ctx_now:
                    elig.append(r)
        out["n_eligible"] = len(elig)
        out["eligible_ids"] = [r["knowledge_id"] for r in elig]
        out["excluded_seen"] = [r["knowledge_id"] for r in snap
                                if r["knowledge_id"] in
                                set(self.exclusions)]
        return elig, out

    # --- механизм-решение эпизода ---
    def decide(self, problem, ctx_now, obs_now, by="gate"):
        """Возвращает (suggestion|None, info). Если eligible пуст —
        S3 фиксируется механизмом (после ФАКТИЧЕСКОЙ проверки) и
        включается Explore dispatch; иначе — ordinary selection через
        существующий selector (strategy_aa.suggest)."""
        elig, info = self.eligible_pool(problem, ctx_now, obs_now)
        empty = len(elig) == 0
        info["pool_empty"] = empty
        if empty:
            if self.exclusions:
                self.events.append({"event": "s3_detected",
                                    "pool_empty": True})
                self.explore_pending = True
                info["s3_triggered"] = True
            else:
                info["s3_triggered"] = False
            return None, info
        src = FilteredStore(self.store, self.exclusions)
        sug = self.st.suggest(src, {"problem": problem}, by=by,
                              ctx_now=ctx_now, obs_now=obs_now)
        consistent = sug.get("strategy_id") in ("S2",)
        self.guards.append({"guard": "s3_consistency",
                            "pool_empty": empty,
                            "strategy_id": sug.get("strategy_id"),
                            "ok": consistent})
        info["strategy_id"] = sug.get("strategy_id")
        refs = list(sug.get("knowledge_refs") or [])
        self.guards.append({"guard": "excluded_not_selected",
                            "ok": not (set(refs) &
                                       set(self.exclusions)),
                            "refs": refs})
        return sug, info

    # --- обновления состояния после эпизода ---
    def line_member_ids(self):
        """Члены L=(a,absent,fix-a) через A1-адресацию."""
        latest = {}
        for v in self.store.read_knowledge_versions_all():
            latest[v["knowledge_id"]] = v
        out = []
        for v in latest.values():
            if v.get("status") not in ("active", "conflicted"):
                continue
            try:
                a = self.st._addr_cmd_of(self.store, v)
            except Exception:
                a = None
            if not a:
                continue
            syms = sorted(a[0]) if hasattr(a[0], "__iter__") else [a[0]]
            if "a" in syms and a[1] == "absent" and a[2] == "fix-a":
                out.append(v["knowledge_id"])
        return out

    def on_episode(self, step):
        """Механизм после эпизода: SOL (TEMP) по success-ЧЛЕНА-L
        (mode=='S2'). Возвращает список новых событий механизма."""
        added = []
        if (self.semantics == "TEMP" and self.exclusions
                and step.get("mode") == "S2"
                and step.get("outcome") == "success"):
            ref0 = (step.get("knowledge_refs") or [None])[0]
            k0 = self.exclusions[0]
            if (ref0 is not None and ref0 != k0
                    and self.slot_state.get(k0) == "none"
                    and ref0 in self.line_member_ids()):
                self.slot_state[k0] = "open"
                self.events.append({"event": "sol", "knowledge_id": ref0})
                self.events.append({"event": "slot",
                                    "knowledge_id": k0,
                                    "trigger_ref": "E1"})
                added += ["sol", "slot"]
        return added

    def attempt_needed(self):
        return (self.semantics == "TEMP" and self.exclusions and
                self.slot_state.get(self.exclusions[0]) == "open")

    def process_attempt(self, kid, success):
        """attempt ровно один; success → eligible; failure → remains."""
        if success:
            self.slot_state[kid] = "consumed"
            self.exclusions = [k for k in self.exclusions if k != kid]
            self.events.append({"event": "eligible", "knowledge_id": kid})
        else:
            self.slot_state[kid] = "consumed"
            self.events.append({"event": "attempt",
                                "knowledge_id": kid, "result": "failure",
                                "remains_excluded": True})

    def pop_explore(self):
        if self.explore_pending:
            self.explore_pending = False
            return True
        return False
