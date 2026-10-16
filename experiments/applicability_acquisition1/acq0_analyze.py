# -*- coding: utf-8 -*-
"""ACQ-1 / A0 analyzer (FROZEN 07.09.2026).

Читает ACQ0_records.json → ACQ0_ANALYSIS.txt. Сверка с фактами 1-4
раздела 2 DESIGN + cross-check r1/r2 (нормализация). Расхождение с
моделью кода НЕ чинится — фиксируется как результат.
"""
import json
import os
import re

DIR = os.path.dirname(os.path.abspath(__file__))


def norm(rec):
    """Нормализация к applicability-проекции: uuid/timestamps/raw_ref/
    host-телеметрия не сравниваются (детерминизм learn-механики, а не
    хоста). Факты сравниваются структурно (subject/property/source)."""
    r = json.loads(json.dumps(rec))
    r.pop("rep", None)
    r["facts"] = sorted((f.get("subject"), f.get("property"),
                         f.get("source")) for f in r.get("facts", []))
    r.pop("knowledge", None)
    if "knowledge" in rec:
        k = json.loads(json.dumps(rec["knowledge"]))
        k.pop("knowledge_id", None)
        k.pop("content", None)
        k.pop("context", None)
        k.pop("experience_refs", None)
        r["knowledge"] = k
    s = json.dumps(r, ensure_ascii=False, sort_keys=True)
    s = re.sub(r"act_acq0_[0-9a-f]+", "ACT", s)
    s = re.sub(r"\d{4}-\d{2}-\d{2}T[0-9:.]+", "TS", s)
    s = re.sub(r"raw_[0-9A-Za-z]+", "RAW", s)
    s = re.sub(r"exp_[0-9a-f]{12}", "EXP", s)
    return s


def main():
    with open(os.path.join(DIR, "ACQ0_records.json"), encoding="utf-8") as f:
        data = json.load(f)
    recs = data["records"]
    audit_same = (data.get("audit_before") == data.get("audit_after"))
    out = []
    def w(s=""):
        out.append(s)

    w("ACQ-1 / A0: АНАЛИЗ (FROZEN протокол; сверка с DESIGN раздел 2)")
    w("layers_unchanged=%s" % audit_same)
    w("")

    all_ok = True
    per_rep = {}
    for rep in ("r1", "r2"):
        rows = recs[rep]
        w("=== реплика %s (%d learn-моментов) ===" % (rep, len(rows)))
        checks = {"ф1_no_applicable_when": True,
                  "ф2_update_content": True,
                  "ф3_addr_not_stored": True,
                  "ф4_S_E_only": True,
                  "op_selects_E": True,
                  "one_knowledge_per_moment": True,
                  "success_verified": True}
        for r in rows:
            k = r.get("knowledge")
            w("  [%d] %-3s E=%s V=%s S=%s ok=%s outcome=%s ctx_extra=%s"
              % (r["idx"], r["world"], r["signals_before"]["E"],
                 r["signals_before"]["V"], r["signals_before"]["S"],
                 r["ok"], r["outcome"], r["action_ctx_extra"]))
            if r["outcome"] != "success" or not r["ok"]:
                checks["success_verified"] = False
            if not k:
                checks["one_knowledge_per_moment"] = False
                w("    ! знания не создано")
                continue
            # ф1
            if k["has_applicable_when"] or "applicable_when" in k["fields"] \
                    or "condition" in k["fields"]:
                checks["ф1_no_applicable_when"] = False
                w("    ! applicable_when/condition в полях: %s"
                  % k["fields"])
            # ф2: content детерминирован update.apply
            c = k.get("content") or ""
            if not ("перевело" in c or "выполнено" in c):
                checks["ф2_update_content"] = False
                w("    ! content вне паттерна update: %r" % c)
            # ф3: адрес не хранится в записи (поля без addr/ctx)
            stored = set(k["fields"])
            if stored & {"addr", "address", "ctx", "ctx_extra",
                         "applicable", "applicable_when"}:
                checks["ф3_addr_not_stored"] = False
                w("    ! адресные поля в записи: %s" % k["fields"])
            # ф4 + оператор выбирает E: derived addr symptom={a},
            #    ctx == E-сигнал момента, command=fix-a
            a = k["derived_addr"]
            exp_ctx = r["signals_before"]["E"]
            w("    knowledge: fields=%d source=%s observer=%s" % (
                len(k["fields"]), k.get("source"), k.get("observer")))
            w("    derived_addr: symptom=%s ctx=%s command=%s"
              % (a["symptom"], a["ctx"], a["command"]))
            if a["symptom"] != ["a"]:
                checks["ф4_S_E_only"] = False
                w("    ! symptom адреса != [a]: %s" % a["symptom"])
            if a["ctx"] != exp_ctx:
                checks["op_selects_E"] = False
                w("    ! ctx адреса %r != E сигнала %r"
                  % (a["ctx"], exp_ctx))
            if a["command"] != "fix-a":
                checks["ф4_S_E_only"] = False
                w("    ! команда адреса != fix-a: %s" % a["command"])
            # V нигде: ctx_extra == E (absent) — V=1/2 никогда не в args
            if r["signals_before"]["V"] not in ("1", "2"):
                checks["ф4_S_E_only"] = False
                w("    ! V-сигнал вне ожидания: %r"
                  % r["signals_before"]["V"])
            w("")
        per_rep[rep] = checks
        for name, val in checks.items():
            if not val:
                all_ok = False
            w("  %s = %s" % (name, val))
        w("")

    # cross-check r1 vs r2
    n1 = [norm(r) for r in recs["r1"]]
    n2 = [norm(r) for r in recs["r2"]]
    w("=== cross-check r1 vs r2 (applicability-проекция) ===")
    w("Сравниваются: E/V/S, ctx, outcome, схема Knowledge, адрес,")
    w("структура фактов. НЕ сравниваются: значения host-телеметрии")
    w("(df/meminfo/load) — недетерминированы по wall-clock; raw_ref с")
    w("timestamp. Наблюдение A0: observer.collect включает непрерывные")
    w("host-факты — по AS-1 кандидаты на отсев (свойства 5/7).")
    w("r1 == r2 по проекции: %s" % (n1 == n2))
    if n1 != n2:
        all_ok = False
        for i, (a, b) in enumerate(zip(n1, n2)):
            if a != b:
                w("  первое расхождение на моменте %d" % (i + 1))
                break
    w("")

    w("=== СВОДКА (сверка с разделом 2 DESIGN) ===")
    w("ф1 Knowledge без applicable_when/condition: %s"
      % all(per_rep[r]["ф1_no_applicable_when"] for r in per_rep))
    w("ф2 content детерминирован update.apply: %s"
      % all(per_rep[r]["ф2_update_content"] for r in per_rep))
    w("ф3 адрес не хранится (вычисляется): %s"
      % all(per_rep[r]["ф3_addr_not_stored"] for r in per_rep))
    w("ф4 в адресе S и E (V нигде): %s"
      % all(per_rep[r]["ф4_S_E_only"] for r in per_rep))
    w("оператор выбирает E (ctx_extra == E момента): %s"
      % all(per_rep[r]["op_selects_E"] for r in per_rep))
    w("1 знание на learn-момент, verified success: %s"
      % (all(per_rep[r]["one_knowledge_per_moment"] for r in per_rep)
         and all(per_rep[r]["success_verified"] for r in per_rep)))
    w("layers unchanged (audit): %s" % audit_same)
    w("")
    w("ИТОГ A0: %s" % ("МЕХАНИКА ПОДТВЕРЖДЕНА — соответствует разделу 2"
                       if all_ok
                       else "РАСХОЖДЕНИЕ с разделом 2 — зафиксировать, "
                            "не чинить"))
    with open(os.path.join(DIR, "ACQ0_ANALYSIS.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out), flush=True)


if __name__ == "__main__":
    main()
