# -*- coding: utf-8 -*-
"""Storage: SQLite-ядро + JSONL-экспорт (Tsarapina, этап 1).

Принципы: append-only (raw и observations не редактируются);
raw (сырые выходы источников) отдельно от фактов; факт ссылается на
raw через provenance.raw_ref. Интерпретации никогда не пишутся в
observations (отдельный поток type=interpretation).
"""
import json
import os
import sqlite3
import time
import uuid


class Store:
    def __init__(self, db_path, jsonl_dir):
        os.makedirs(jsonl_dir, exist_ok=True)
        self.db_path = db_path
        self.raw_jsonl = os.path.join(jsonl_dir, "raw.jsonl")
        self.obs_jsonl = os.path.join(jsonl_dir, "observations.jsonl")
        self._init_db()

    def _init_db(self):
        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE IF NOT EXISTS raw ("
                    "id TEXT PRIMARY KEY, ts TEXT, source TEXT, text TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS observations ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
                    "json TEXT)")
        con.commit()
        con.close()

    # ---- raw: append-only, неизменяем ----
    def append_raw(self, source, text):
        rid = "raw_%s_%s" % (time.strftime("%Y%m%dT%H%M%S"),
                             uuid.uuid4().hex[:8])
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        rec = {"id": rid, "ts": ts, "source": source, "text": text}
        with open(self.raw_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO raw (id, ts, source, text) VALUES (?,?,?,?)",
                    (rid, ts, source, text))
        con.commit()
        con.close()
        return rid

    def read_raw(self, rid):
        con = sqlite3.connect(self.db_path)
        row = con.execute("SELECT text FROM raw WHERE id=?", (rid,)).fetchone()
        con.close()
        return row[0] if row else None

    # ---- observations: факты (type=fact) ----
    def append_observation(self, fact):
        ts = fact.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(self.obs_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(fact, ensure_ascii=False) + "\n")
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO observations (ts, json) VALUES (?,?)",
                    (ts, json.dumps(fact, ensure_ascii=False)))
        con.commit()
        con.close()

    def read_facts(self):
        con = sqlite3.connect(self.db_path)
        rows = con.execute("SELECT json FROM observations").fetchall()
        con.close()
        return [json.loads(r[0]) for r in rows]

    # ---- интерпретации: отдельный поток, никогда не в observations ----
    def append_interpretation(self, rec):
        """Интерпретация (модель/правило). Хранится отдельно, не
        смешивается с фактами; обязана ссылаться на факты/raw."""
        rec.setdefault("type", "interpretation")
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "interpretations.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- actions (этап 2: ссылки; этап 6/7: исполнитель) ----
    def append_action(self, action):
        path = os.path.join(os.path.dirname(self.obs_jsonl), "actions.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(action, ensure_ascii=False) + "\n")
        return action["action_id"]

    def read_action(self, aid):
        path = os.path.join(os.path.dirname(self.obs_jsonl), "actions.jsonl")
        if not os.path.exists(path):
            return None
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("action_id") == aid:
                return rec
        return None

    # ---- results (этап 2: ссылка; фактический результат отдельно
    # от оценки) ----
    def append_result(self, result):
        path = os.path.join(os.path.dirname(self.obs_jsonl), "results.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result["result_id"]

    def read_result(self, rid):
        path = os.path.join(os.path.dirname(self.obs_jsonl), "results.jsonl")
        if not os.path.exists(path):
            return None
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("result_id") == rid:
                return rec
        return None

    # ---- experiences: append-only, dedup по experience_id ----
    def append_experience(self, exp):
        """Добавить эпизод. Если experience_id уже существует — НЕ
        перезаписывать (append-only; «нельзя незаметно изменить
        старый эпизод»). Возвращает True, если добавлен."""
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "experiences.jsonl")
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                if json.loads(line).get("experience_id") == \
                        exp["experience_id"]:
                    return False
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp, ensure_ascii=False) + "\n")
        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE IF NOT EXISTS experiences ("
                    "id TEXT PRIMARY KEY, json TEXT)")
        con.execute("INSERT OR IGNORE INTO experiences (id, json) "
                    "VALUES (?,?)", (exp["experience_id"],
                                     json.dumps(exp, ensure_ascii=False)))
        con.commit()
        con.close()
        return True

    def read_experience(self, eid):
        con = sqlite3.connect(self.db_path)
        try:
            row = con.execute("SELECT json FROM experiences WHERE id=?",
                              (eid,)).fetchone()
        except sqlite3.OperationalError:
            row = None
        con.close()
        return json.loads(row[0]) if row else None

    def read_experiences(self):
        con = sqlite3.connect(self.db_path)
        rows = con.execute("SELECT json FROM experiences").fetchall()
        con.close()
        return [json.loads(r[0]) for r in rows]

    # ---- knowledge: append-only, версии (kid стабилен, version ↑) ----
    def append_knowledge(self, rec):
        """Добавить версию знания. Дубликат (knowledge_id+version)
        отклоняется; update-пути нет. Возвращает True, если добавлен."""
        kid = rec["knowledge_id"]
        ver = rec["version"]
        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE IF NOT EXISTS knowledge ("
                    "kid TEXT, version INTEGER, json TEXT, "
                    "PRIMARY KEY (kid, version))")
        cur = con.execute("SELECT 1 FROM knowledge WHERE kid=? AND version=?",
                          (kid, ver))
        exists = cur.fetchone() is not None
        if not exists:
            con.execute("INSERT INTO knowledge (kid, version, json) "
                        "VALUES (?,?,?)",
                        (kid, ver, json.dumps(rec, ensure_ascii=False)))
            con.commit()
        con.close()
        return not exists

    def read_knowledge(self, kid):
        """Последняя версия записи."""
        con = sqlite3.connect(self.db_path)
        row = con.execute(
            "SELECT json FROM knowledge WHERE kid=? "
            "ORDER BY version DESC LIMIT 1", (kid,)).fetchone()
        con.close()
        return json.loads(row[0]) if row else None

    def read_knowledge_versions(self, kid):
        con = sqlite3.connect(self.db_path)
        rows = con.execute(
            "SELECT json FROM knowledge WHERE kid=? ORDER BY version",
            (kid,)).fetchall()
        con.close()
        return [json.loads(r[0]) for r in rows]

    def read_knowledge_versions_all(self):
        """Все версии всех записей knowledge (для снапшотов)."""
        con = sqlite3.connect(self.db_path)
        try:
            rows = con.execute("SELECT json FROM knowledge").fetchall()
        except sqlite3.OperationalError:
            rows = []
        con.close()
        return [json.loads(r[0]) for r in rows]

    # ---- suggestions (этап 5 Strategy): append-only ----
    def append_suggestion(self, sug):
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "suggestions.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sug, ensure_ascii=False) + "\n")
        return sug["suggestion_id"]

    def read_suggestions(self):
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "suggestions.jsonl")
        if not os.path.exists(path):
            return []
        return [json.loads(line) for line in open(path, encoding="utf-8")]

    # ---- evaluations (этап 7): append-only, Result не меняется ----
    def append_evaluation(self, ev):
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "evaluations.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev["evaluation_id"]

    def read_evaluations(self, result_id=None):
        path = os.path.join(os.path.dirname(self.obs_jsonl),
                            "evaluations.jsonl")
        if not os.path.exists(path):
            return []
        out = []
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            if result_id is None or rec.get("result_id") == result_id:
                out.append(rec)
        return out
