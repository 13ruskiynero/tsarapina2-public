#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты транспортного слоя K0 (A20b, офлайн; без модели).

- LoopbackChannel: очередь/исключения/хук отправки;
- HttpChannel против ЛОКАЛЬНОГО http.server-стенда: ok, status500, redirect,
  abort, partial, badjson, badencoding, big, slow (timeout); без ретраев;
- интеграция с сессией: полный цикл через канал, порядок записи
  доказательств (request до отправки, response после), обрыв → FAILED с
  целыми доказательствами, повторный запуск только в новый каталог,
  согласованность паспорта и хэшей.

Внешние соединения не используются. Запуск:
    python3 lab/autonomy/k0/code/tests/test_channel.py -v
"""
from __future__ import annotations

import gzip
import hashlib
import http.server
import inspect
import json
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]
K0_DIR = THIS.parents[2]
sys.path.insert(0, str(CODE_DIR))

from world import cell_outcome, load_battery  # noqa: E402
from channel import (  # noqa: E402
    ChannelError, HttpChannel, HttpsChannel, LoopbackChannel, _strict_context,
    build_prompt, extract_content, make_respond, ollama_payload_builder,
)
from secret_scan import scan_exceptions, scan_tree  # noqa: E402
from journal import Journal, JournalError, read_journal, run_dir_for  # noqa: E402
from session import Session, SessionError  # noqa: E402

ARTIFACTS = K0_DIR / "artifacts"
SEED = 101


def battery():
    return [i.cell for i in load_battery(ARTIFACTS / "heldout_battery.json")]


F1 = "\n".join(f"PREDICT: {c.as_text()} = present" for c in sorted(battery()))
F3 = "\n".join(f"PREDICT: {c.as_text()} = {cell_outcome(c)}" for c in sorted(battery()))
REG = "\n".join([
    "QUESTION Q1: почему объекты исчезают? REF: t01",
    "HYPOTHESIS H1 OF Q1: правило T PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H2 OF Q1: скрытый p PREDICT: O2 T=2 H=1 = present",
    "HYPOTHESIS H3 OF Q1: материал m PREDICT: O2 T=2 H=1 = disappeared",
])
BLOCK = "PREDICT: O2 T=2 H=1 = present\nACTION: probe O2 T=2 H=1"
RESET = "ACTION: reset"
FINAL = "FINAL: итог."
FULL_QUEUE = [F1, REG, BLOCK] + [RESET] * 15 + [F3, FINAL]   # 20 вызовов


class TestLoopback(unittest.TestCase):

    def test_queue_order_and_value(self):
        ch = LoopbackChannel(["первый", "второй"])
        self.assertEqual(ch.send("F2", 1, "p"), "первый")
        self.assertEqual(ch.send("F2", 1, "p"), "второй")
        self.assertEqual([x[0] for x in ch.sent], ["F2", "F2"])

    def test_exhausted(self):
        ch = LoopbackChannel([])
        with self.assertRaises(ChannelError) as cm:
            ch.send("F1", 1, "p")
        self.assertEqual(cm.exception.code, "exhausted")

    def test_error_propagation(self):
        ch = LoopbackChannel([ChannelError("transport", "стенд")])
        with self.assertRaises(ChannelError) as cm:
            ch.send("F1", 1, "p")
        self.assertEqual(cm.exception.code, "transport")

    def test_on_send_hook(self):
        seen = []
        ch = LoopbackChannel(["x"])
        ch.on_send = lambda phase, attempt, prompt: seen.append((phase, attempt, prompt))
        ch.send("F3", 2, "текст")
        self.assertEqual(seen, [("F3", 2, "текст")])


class TestExtractContent(unittest.TestCase):

    def test_forms(self):
        self.assertEqual(extract_content({"content": "a"}), "a")
        self.assertEqual(extract_content(
            {"choices": [{"message": {"content": "b"}}]}), "b")
        self.assertEqual(extract_content({"message": {"content": "c"}}), "c")

    def test_invalid(self):
        for bad in ({}, {"content": 5}, {"choices": []}, {"choices": [{}]},
                    {"message": {}}, {"message": {"content": 5}}, ["x"]):
            with self.assertRaises(ChannelError) as cm:
                extract_content(bad)
            self.assertEqual(cm.exception.code, "malformed_response")


class TestOllamaCompat(unittest.TestCase):
    """Совместимость с целевым локальным /api/chat (Ollama; T0 §3)."""

    def setUp(self):
        self.srv = _StandServer()
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.srv.server_address

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)

    def test_payload_t0(self):
        self.srv.behavior = "ok"
        ch = HttpChannel(self.host, self.port, path="/api/chat",
                         payload_builder=ollama_payload_builder(
                             "gemma4-e4b-heretic:q4km"))
        ch.send("F2", 1, "промпт-тест")
        body = json.loads(self.srv.last_body.decode("utf-8"))
        self.assertEqual(body["model"], "gemma4-e4b-heretic:q4km")
        self.assertEqual(body["messages"],
                         [{"role": "user", "content": "промпт-тест"}])
        self.assertIs(body["stream"], False)
        self.assertIs(body["think"], False)
        self.assertEqual(body["keep_alive"], "30m")
        self.assertEqual(body["options"], {"temperature": 0, "seed": 1729,
                                           "num_predict": 256, "num_ctx": 4096})

    def test_response_shape_and_meta(self):
        self.srv.behavior = "ollama"
        ch = HttpChannel(self.host, self.port, path="/api/chat",
                         payload_builder=ollama_payload_builder("m"))
        self.assertEqual(ch.send("F1", 1, "p"), "OLL-OK")
        self.assertEqual(ch.last_meta,
                         {"prompt_eval_count": 123, "eval_count": 45})


class _StandHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            srv = self.server
            srv.counter += 1
            srv.last_body = raw
            srv.last_headers = dict(self.headers)
            b = srv.behavior
            if b == "slow":
                time.sleep(srv.delay)
            if b == "ok":
                payload = json.dumps({"content": "PHASE-OK"}, ensure_ascii=False).encode()
                self._send(200, payload)
            elif b == "chat":
                payload = json.dumps(
                    {"choices": [{"message": {"content": "CHAT-OK"}}]}).encode()
                self._send(200, payload)
            elif b == "status500":
                self._send(500, b"err")
            elif b == "redirect":
                self.send_response(302)
                self.send_header("Location", "http://example.invalid/")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif b == "abort":
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            elif b == "partial":
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                self.wfile.write(b"{}")
                self.close_connection = True
            elif b == "badjson":
                self._send(200, b"not a json")
            elif b == "badencoding":
                self._send(200, b'{"content": "\xff\xfe"}')
            elif b == "big":
                self._send(200, json.dumps({"content": "x" * 5000}).encode())
            elif b == "gzip":
                body = gzip.compress(json.dumps({"content": "GZ"}).encode())
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif b == "chunked":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                payload = json.dumps({"content": "CHUNK-OK"}).encode()
                for chunk in (payload[:5], payload[5:]):
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            elif b == "chunked_trunc":
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b'5\r\n{"con\r\n')
                self.close_connection = True
            elif b == "script":
                payload_text = srv.script[srv.counter - 1]
                self._send(200, json.dumps({"content": payload_text},
                                           ensure_ascii=False).encode())
            elif b == "ollama":
                payload = json.dumps({
                    "message": {"role": "assistant", "content": "OLL-OK"},
                    "prompt_eval_count": 123, "eval_count": 45}).encode()
                self._send(200, payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _StandServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, handler=None):
        super().__init__(("127.0.0.1", 0), handler or _StandHandler)
        self.behavior = "ok"
        self.delay = 0.0
        self.counter = 0
        self.last_body = b""
        self.last_headers = {}
        self.script = []
        self.connections = 0

    def handle_error(self, request, client_address):
        pass  # тестовый стенд: отказы рукопожатий самоподписанных сертификатов не печатаем


class TestHttpChannel(unittest.TestCase):

    def setUp(self):
        self.srv = _StandServer()
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.srv.server_address[0], self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)

    def channel(self, **kw):
        return HttpChannel(self.host, self.port, **kw)

    def expect(self, code, **kw):
        with self.assertRaises(ChannelError) as cm:
            self.channel(**kw).send("F2", 1, "p")
        self.assertEqual(cm.exception.code, code)

    def test_ok_and_request_format(self):
        self.srv.behavior = "ok"
        out = self.channel().send("F2", 2, "текст запроса")
        self.assertEqual(out, "PHASE-OK")
        body = json.loads(self.srv.last_body.decode("utf-8"))
        self.assertEqual(body, {"phase": "F2", "attempt": 2, "prompt": "текст запроса"})
        self.assertIn("application/json", self.srv.last_headers.get("Content-Type", ""))

    def test_chat_shape(self):
        self.srv.behavior = "chat"
        self.assertEqual(self.channel().send("F1", 1, "p"), "CHAT-OK")

    def test_accept_encoding_identity_only(self):
        self.srv.behavior = "ok"
        self.channel().send("F2", 1, "p")
        self.assertEqual(self.srv.last_headers.get("Accept-Encoding"), "identity")

    def test_gzip_content_encoding_rejected(self):
        self.srv.behavior = "gzip"
        self.expect("encoding")

    def test_chunked_ok(self):
        self.srv.behavior = "chunked"
        self.assertEqual(self.channel().send("F2", 1, "p"), "CHUNK-OK")

    def test_chunked_truncated(self):
        self.srv.behavior = "chunked_trunc"
        self.expect("incomplete")

    def test_status_error(self):
        self.srv.behavior = "status500"
        self.expect("http_status")

    def test_redirect_not_followed(self):
        self.srv.behavior = "redirect"
        self.expect("http_status")
        self.assertEqual(self.srv.counter, 1)      # без скрытого повтора

    def test_abort(self):
        self.srv.behavior = "abort"
        self.expect("transport")

    def test_partial(self):
        self.srv.behavior = "partial"
        self.expect("incomplete")

    def test_bad_json(self):
        self.srv.behavior = "badjson"
        self.expect("malformed_response")

    def test_bad_encoding(self):
        self.srv.behavior = "badencoding"
        self.expect("encoding")

    def test_too_large(self):
        self.srv.behavior = "big"
        self.expect("too_large", max_response_bytes=1000)

    def test_read_timeout(self):
        self.srv.behavior = "slow"
        self.srv.delay = 0.5
        self.expect("timeout", read_timeout=0.05)

    def test_no_retries(self):
        self.srv.behavior = "status500"
        ch = self.channel()
        for _ in range(2):
            with self.assertRaises(ChannelError):
                ch.send("F2", 1, "p")
        self.assertEqual(self.srv.counter, 2)      # ровно один запрос на вызов

    def test_connection_refused(self):
        ch = HttpChannel(self.host, 1, connect_timeout=0.5, read_timeout=0.5)
        with self.assertRaises(ChannelError) as cm:
            ch.send("F2", 1, "p")
        self.assertEqual(cm.exception.code, "transport")


def _make_certs(tmp: Path):
    """CA + серверные сертификаты для HTTPS-стенда (SAN: localhost, 127.0.0.1).
    Тестовые ключи — только для локального стенда; боевые секреты запрещены."""
    ca_key, ca_pem = tmp / "ca.key", tmp / "ca.pem"
    srv_key, srv_csr, srv_pem = tmp / "server.key", tmp / "server.csr", tmp / "server.pem"
    ss_key, ss_pem = tmp / "ss.key", tmp / "ss.pem"
    bad_key, bad_csr, bad_pem = tmp / "bad.key", tmp / "bad.csr", tmp / "bad.pem"
    san = tmp / "san.cnf"
    san.write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\n", encoding="utf-8")
    san_bad = tmp / "san_bad.cnf"
    san_bad.write_text("subjectAltName=DNS:example.com\n", encoding="utf-8")

    def run(*args):
        r = subprocess.run(args, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode())

    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", str(ca_key),
        "-out", str(ca_pem), "-days", "2", "-nodes", "-subj", "/CN=K0-TestCA")
    run("openssl", "req", "-newkey", "rsa:2048", "-keyout", str(srv_key),
        "-out", str(srv_csr), "-nodes", "-subj", "/CN=localhost")
    run("openssl", "x509", "-req", "-in", str(srv_csr), "-CA", str(ca_pem),
        "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(srv_pem),
        "-days", "2", "-extfile", str(san))
    run("openssl", "req", "-newkey", "rsa:2048", "-keyout", str(bad_key),
        "-out", str(bad_csr), "-nodes", "-subj", "/CN=example.com")
    run("openssl", "x509", "-req", "-in", str(bad_csr), "-CA", str(ca_pem),
        "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(bad_pem),
        "-days", "2", "-extfile", str(san_bad))
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", str(ss_key),
        "-out", str(ss_pem), "-days", "2", "-nodes", "-subj", "/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1")
    return dict(ca_pem=str(ca_pem), server_pem=str(srv_pem), server_key=str(srv_key),
                bad_pem=str(bad_pem), bad_key=str(bad_key),
                ss_pem=str(ss_pem), ss_key=str(ss_key))


class _TlsStandServer(_StandServer):
    def __init__(self, certfile, keyfile):
        super().__init__()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        self.socket = ctx.wrap_socket(self.socket, server_side=True)


class TestTlsChannel(unittest.TestCase):
    """Обязательная строгая TLS-верификация; отключение — отсутствует как класс."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.certs = _make_certs(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tls_server(self, certfile, keyfile):
        srv = _TlsStandServer(certfile, keyfile)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)
        self.addCleanup(t.join, 5)
        srv.behavior = "ok"
        return srv

    def send_expect(self, srv, ca_file, code):
        ch = HttpsChannel("127.0.0.1", srv.server_address[1], ca_file=ca_file)
        with self.assertRaises(ChannelError) as cm:
            ch.send("F2", 1, "p")
        self.assertEqual(cm.exception.code, code)

    def test_ca_signed_ok(self):
        srv = self.tls_server(self.certs["server_pem"], self.certs["server_key"])
        ch = HttpsChannel("127.0.0.1", srv.server_address[1],
                          ca_file=self.certs["ca_pem"])
        self.assertEqual(ch.send("F2", 1, "p"), "PHASE-OK")

    def test_self_signed_rejected(self):
        srv = self.tls_server(self.certs["ss_pem"], self.certs["ss_key"])
        self.send_expect(srv, self.certs["ca_pem"], "tls")

    def test_wrong_ca_rejected(self):
        srv = self.tls_server(self.certs["server_pem"], self.certs["server_key"])
        self.send_expect(srv, self.certs["ss_pem"], "tls")

    def test_hostname_mismatch_rejected(self):
        srv = self.tls_server(self.certs["bad_pem"], self.certs["bad_key"])
        self.send_expect(srv, self.certs["ca_pem"], "tls")

    def test_strict_context_defaults(self):
        ctx = _strict_context(None)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_no_insecure_options(self):
        params = set(inspect.signature(HttpsChannel.__init__).parameters)
        self.assertFalse(params & {"verify", "check_hostname", "insecure",
                                   "ssl_verify", "verify_mode", "cert_none"})
        src = (CODE_DIR / "channel.py").read_text(encoding="utf-8")
        self.assertNotIn("CERT_NONE", src)
        self.assertNotIn("check_hostname = False", src)
        self.assertNotIn("check_hostname=False", src)


class _KaHandler(_StandHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        self.server.connections += 1
        super().setup()


class TestKeepAlive(unittest.TestCase):
    """Стенд с keep-alive (HTTP/1.1): модель канала — «соединение на вызов»;
    порядок и попарность доказательств не зависят от переиспользования."""

    def setUp(self):
        self.srv = _StandServer(_KaHandler)
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)

    def test_multiple_calls_stable(self):
        self.srv.behavior = "ok"
        ch = HttpChannel(self.srv.server_address[0], self.srv.server_address[1])
        for _ in range(3):
            self.assertEqual(ch.send("F2", 1, "p"), "PHASE-OK")
        self.assertEqual(self.srv.counter, 3)
        self.assertEqual(self.srv.connections, 3)     # одно соединение на вызов


SECRET = "K0TEST-SECRET-abcdef-123456"


class TestNoSecretLeak(unittest.TestCase):
    """Аварийные пути и артефакты не содержат секрета (скан, не только eye-ball)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.srv = _StandServer()
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.headers = {"Authorization": "Bearer " + SECRET, "X-Api-Key": SECRET}

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def channel(self, **kw):
        return HttpChannel(self.srv.server_address[0], self.srv.server_address[1], **kw)

    def test_auth_header_really_sent(self):
        self.srv.behavior = "ok"
        self.channel(headers=self.headers).send("F2", 1, "p")
        self.assertEqual(self.srv.last_headers.get("Authorization"),
                         "Bearer " + SECRET)

    def test_errors_do_not_contain_secret(self):
        errors = []
        for behavior in ("status500", "redirect", "abort", "partial",
                         "badjson", "badencoding", "big"):
            self.srv.behavior = behavior
            try:
                self.channel(headers=self.headers,
                             max_response_bytes=1000).send("F2", 1, "p")
            except ChannelError as e:
                errors.append(e)
        self.srv.behavior = "slow"
        self.srv.delay = 0.5
        try:
            self.channel(headers=self.headers,
                         read_timeout=0.05).send("F2", 1, "p")
        except ChannelError as e:
            errors.append(e)
        refused = HttpChannel("127.0.0.1", 1, connect_timeout=0.3,
                              read_timeout=0.3, headers=self.headers)
        try:
            refused.send("F2", 1, "p")
        except ChannelError as e:
            errors.append(e)
        self.assertGreaterEqual(len(errors), 8)
        self.assertEqual(scan_exceptions(errors, SECRET), [])

    def test_run_artifacts_clean_of_secret(self):
        self.srv.behavior = "script"
        self.srv.script = [F1, REG, BLOCK] + [RESET] * 15 + [F3, FINAL]
        run = run_dir_for(self.base, "K0-M1", SEED)
        ch = self.channel(headers=self.headers)
        sess = Session(run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        self.assertEqual(scan_tree(self.base, SECRET), [])


class TestO1Retries(unittest.TestCase):
    """O1: повторы ≤2 только для `no_response`; прочие классы — без повторов."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def meta_classes(self, run):
        out = []
        for p in sorted((run / "raw" / "calls").glob("*.meta.json")):
            out.append(json.loads(p.read_text(encoding="utf-8"))["class"])
        return out

    def test_no_response_retried_then_ok(self):
        err = ChannelError("timeout", "нет ответа", stage="connect")
        ch = LoopbackChannel([err, F1, REG, BLOCK] + [RESET] * 15 + [F3, FINAL])
        run = run_dir_for(self.base, "K0-M1", 501)
        sess = Session(run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        classes = self.meta_classes(run)
        self.assertEqual(classes.count("no_response"), 1)
        # две попытки F1: разные номера вызовов, один attempt
        reqs = sorted(p.name for p in (run / "raw" / "calls").glob("000[12]_F1_a1.request.txt"))
        self.assertEqual(len(reqs), 2)
        resps = sorted(p.name for p in (run / "raw" / "calls").glob("*_F1_a1.response.txt"))
        self.assertEqual(len(resps), 1)                     # ответ только у второй попытки

    def test_no_response_exhausted(self):
        err = ChannelError("timeout", "нет ответа", stage="pre_status")
        ch = LoopbackChannel([err, err, err, "не должно вызываться"])
        run = run_dir_for(self.base, "K0-M1", 502)
        sess = Session(run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "no_response")
        self.assertEqual(len(ch.sent), 3)                   # ровно 3 попытки
        classes = self.meta_classes(run)
        self.assertEqual(classes.count("no_response"), 3)

    def test_refusal_not_retried(self):
        err = ChannelError("http_status", "HTTP 500", stage="body")
        ch = LoopbackChannel([err, "не должно вызываться"])
        run = run_dir_for(self.base, "K0-M1", 503)
        sess = Session(run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "server_refusal")
        self.assertEqual(len(ch.sent), 1)

    def test_indeterminate_not_retried(self):
        err = ChannelError("incomplete", "обрыв в теле", stage="body")
        ch = LoopbackChannel([err, "не должно вызываться"])
        run = run_dir_for(self.base, "K0-M1", 504)
        sess = Session(run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "indeterminate")
        self.assertEqual(len(ch.sent), 1)


class TestSessionOverChannel(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.run = run_dir_for(self.base, "K0-M1", SEED)

    def tearDown(self):
        self.tmp.cleanup()

    def calls_dir(self):
        return self.run / "raw" / "calls"

    def pair_names(self, suffix):
        return sorted(p.name.replace(suffix, "") for p in self.calls_dir().glob(f"*{suffix}"))

    def test_full_cycle_over_channel(self):
        ch = LoopbackChannel(list(FULL_QUEUE))
        sess = Session(self.run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        self.assertEqual(len(ch.sent), 20)
        req, resp = self.pair_names(".request.txt"), self.pair_names(".response.txt")
        self.assertEqual(len(req), 20)
        self.assertEqual(req, resp)                       # пары 1:1
        rows = read_journal(self.run / "raw" / "journal.jsonl")
        self.assertEqual([r["type"] for r in rows].count("budget"), 16)

    def test_request_written_before_send_response_after(self):
        violations = []
        ch = LoopbackChannel(list(FULL_QUEUE))

        def hook(phase, attempt, prompt):
            n = len(ch.sent)
            stem = f"{n:04d}_{phase}_a{attempt}"
            if not (self.calls_dir() / (stem + ".request.txt")).exists():
                violations.append(("no_request", n))
            if (self.calls_dir() / (stem + ".response.txt")).exists():
                violations.append(("early_response", n))

        ch.on_send = hook
        sess = Session(self.run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        self.assertEqual(violations, [])

    def test_abort_leaves_evidence_intact(self):
        # обрыв без stage ⇒ indeterminate (O1): стоп без повторов; доказательства целы
        ch = LoopbackChannel([F1, REG, ChannelError("transport", "обрыв стенда")])
        sess = Session(self.run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "halted")
        self.assertEqual(res.stop_reason, "indeterminate")
        self.assertEqual(sess.state, "HALTED")
        self.assertEqual(len(self.pair_names(".request.txt")), 3)
        self.assertEqual(len(self.pair_names(".response.txt")), 2)   # у 3-го нет ответа
        rows = read_journal(self.run / "raw" / "journal.jsonl")      # журнал читаем
        types = [r["type"] for r in rows]
        self.assertNotIn("budget", types)
        self.assertEqual(types[-1], "stop")
        passport = json.loads((self.run / "passport" / "passport.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(passport["status"], "halted")
        # возобновление запрещено; журнал не перезаписывается
        before = (self.run / "raw" / "journal.jsonl").read_bytes()
        with self.assertRaises(SessionError):
            sess.run()
        with self.assertRaises(JournalError):
            Journal(self.run).open()
        self.assertEqual((self.run / "raw" / "journal.jsonl").read_bytes(), before)
        # новый прогон — только новый каталог
        run2 = run_dir_for(self.base, "K0-M1", SEED + 1)
        ch2 = LoopbackChannel([F1, "чепуха", "чепуха", "чепуха"])
        sess2 = Session(run2, make_respond(ch2), seed=SEED, max_invalid_f2=3)
        res2 = sess2.run()
        self.assertEqual(res2.status, "halted")

    def test_passport_hashes_consistent(self):
        ch = LoopbackChannel(list(FULL_QUEUE))
        sess = Session(self.run, make_respond(ch), seed=SEED)
        res = sess.run()
        self.assertEqual(res.status, "completed")
        passport = json.loads((self.run / "passport" / "passport.json")
                              .read_text(encoding="utf-8"))
        v36 = hashlib.sha256((K0_DIR / "K0_PROTOCOL_v36.md").read_bytes()).hexdigest()
        v26 = hashlib.sha256((K0_DIR / "K0_PROTOCOL.md").read_bytes()).hexdigest()
        self.assertEqual(passport["protocol_version"], "v36")
        self.assertEqual(passport["protocol_sha256"], v36)
        self.assertEqual(passport["protocol_base_sha256"], v26)
        self.assertIn("context", passport)
        self.assertGreater(passport["context"]["approx_tokens_max"], 0)
        bat = hashlib.sha256((ARTIFACTS / "heldout_battery.json").read_bytes()).hexdigest()
        self.assertEqual(passport["artifacts"]["heldout_battery.json"], bat)
        self.assertEqual(passport["status"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
