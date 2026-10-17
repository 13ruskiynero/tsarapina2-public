#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — транспортный слой агента (A20b, офлайн-этап; контракт — K0_CHANNEL_CONTRACT.md).

Никаких вызовов модели: модуль реализует транспорт и его офлайн-проверку.
- Channel.send(phase, attempt, prompt) -> str — один вызов = один ход фазы;
- LoopbackChannel — синтетический стенд (очередь ответов/исключений);
- HttpChannel — HTTP-транспорт (chat-совместимый контракт): POST JSON,
  раздельные connect/read-таймауты, строгий UTF-8, лимит размера, НЕТ
  редиректов и автоматических повторов; все транспортные сбои — ChannelError;
- make_respond(channel, prompt_builder) — адаптер к интерфейсу сессии
  `respond(phase, ctx, attempt)`; доказательства (raw/calls) пишет сессия,
  транспорт в файлы не пишет.

Ошибочные коды ChannelError: transport | timeout | incomplete | http_status |
malformed_response | encoding | tls | too_large | exhausted.

HTTPS (этап подготовки к живому каналу): `HttpsChannel` использует
`ssl.create_default_context` — строгая верификация сертификата и хоста
(CERT_REQUIRED + check_hostname); опция отключения верификации в коде
ОТСУТСТВУЕТ как класс (контроль — тестами и мета-проверкой исходника).
Сжатие не поддерживается: `Accept-Encoding` не отправляется; при
`Content-Encoding ≠ identity` ответ отвергается (код `encoding`).
"""
from __future__ import annotations

import http.client
import json
import socket
import ssl
from typing import Callable, Optional, Sequence

from calls import render_context

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 120.0
DEFAULT_MAX_RESPONSE_BYTES = 1 << 20  # 1 MiB


class ChannelError(Exception):
    """Ошибка транспорта. `code` — машинное имя (см. докстринг модуля);
    `stage` — фаза запроса: connect | send | pre_status | body | None
    (используется классификатором O1 `classify_error`)."""

    def __init__(self, code: str, message: str, stage: Optional[str] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.stage = stage


def classify_error(e: BaseException) -> str:
    """Класс исхода вызова по акту O1 (K0_CHANNEL_O1_ACT.md):

    - `server_refusal` — HTTP ≠ 200 (ответ получен);
    - `no_response` — однозначное отсутствие ответа: ошибки фазы connect
      (запрос не отправлен) или обрыв/таймаут ДО статусной строки;
    - `indeterminate` — все прочие (TLS, обрыв/таймаут после начала ответа,
      неполный ответ, некорректный ответ, кодировка, размер и т.п.).
    """
    if not isinstance(e, ChannelError):
        return "indeterminate"
    if e.code == "http_status":
        return "server_refusal"
    if e.stage in ("connect", "pre_status") and e.code in ("transport", "timeout"):
        return "no_response"
    return "indeterminate"


def extract_content(obj) -> str:
    """Строковый контент ответа: {"content": "..."}; chat-совместимо
    {"choices":[{"message":{"content":"..."}}]}; Ollama /api/chat
    {"message":{"content":"..."}}."""
    if isinstance(obj, dict):
        c = obj.get("content")
        if isinstance(c, str):
            return c
        msg = obj.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"]
        ch = obj.get("choices")
        if isinstance(ch, list) and ch and isinstance(ch[0], dict):
            m2 = ch[0].get("message")
            if isinstance(m2, dict) and isinstance(m2.get("content"), str):
                return m2["content"]
    raise ChannelError("malformed_response", "нет строкового поля контента")


class Channel:
    """Базовый транспорт."""

    name = "abstract"

    def send(self, phase: str, attempt: int, prompt: str) -> str:
        raise NotImplementedError


class LoopbackChannel(Channel):
    """Синтетический канал: очередь ответов (str) и исключений (Exception).

    `on_send(phase, attempt, prompt)` вызывается в момент отправки — до
    выдачи ответа (используется для проверки порядка записи доказательств).
    """

    name = "loopback"

    def __init__(self, responses: Sequence):
        self.queue = list(responses)
        self.sent = []                  # [(phase, attempt, prompt)]
        self.on_send: Optional[Callable] = None
        self.last_meta = None           # O1: метаданные последнего ответа

    def send(self, phase: str, attempt: int, prompt: str) -> str:
        self.last_meta = None
        self.sent.append((phase, attempt, prompt))
        if self.on_send is not None:
            self.on_send(phase, attempt, prompt)
        if not self.queue:
            raise ChannelError("exhausted", "очередь ответов пуста")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Connection(http.client.HTTPConnection):
    """HTTPConnection с раздельными connect/read-таймаутами."""

    def __init__(self, host, port, connect_timeout, read_timeout):
        super().__init__(host, port)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port),
                                             self._connect_timeout)
        self.sock.settimeout(self._read_timeout)


class _TLSConnection(http.client.HTTPSConnection):
    """HTTPSConnection со строгой верификацией и раздельными таймаутами.

    Контекст — только `_strict_context(ca_file)`: добавление доверенного CA
    допустимо; отключение верификации — нет (такой опции не существует)."""

    def __init__(self, host, port, connect_timeout, read_timeout, ca_file=None):
        super().__init__(host, port, context=_strict_context(ca_file))
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def connect(self):
        sock = socket.create_connection((self.host, self.port),
                                        self._connect_timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise
        self.sock.settimeout(self._read_timeout)


def _strict_context(ca_file: Optional[str]) -> ssl.SSLContext:
    """Строгий TLS-контекст: CERT_REQUIRED + check_hostname (по умолчанию
    `create_default_context`); `ca_file` лишь ДОБАВЛЯЕТ доверенный CA."""
    return ssl.create_default_context(cafile=ca_file)


class HttpChannel(Channel):
    """HTTP-транспорт (chat-совместимый; без редиректов и повторов)."""

    name = "http"

    def __init__(self, host: str, port: int, path: str = "/",
                 connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
                 read_timeout: float = DEFAULT_READ_TIMEOUT,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
                 headers: Optional[dict] = None,
                 payload_builder: Optional[Callable] = None):
        self.host = host
        self.port = int(port)
        self.path = path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_response_bytes = max_response_bytes
        self.headers = dict(headers or {})
        self.payload_builder = payload_builder
        self.last_meta = None           # O1: {"prompt_eval_count","eval_count"} | None

    @staticmethod
    def _default_payload(phase: str, attempt: int, prompt: str) -> dict:
        return {"phase": phase, "attempt": attempt, "prompt": prompt}

    def _make_connection(self):
        return _Connection(self.host, self.port,
                           self.connect_timeout, self.read_timeout)

    @staticmethod
    def _extract_meta(obj) -> Optional[dict]:
        """Счётчики токенов из ответа сервера (если присутствуют)."""
        if not isinstance(obj, dict):
            return None
        meta = {k: obj[k] for k in ("prompt_eval_count", "eval_count")
                if isinstance(obj.get(k), int)}
        return meta or None

    def send(self, phase: str, attempt: int, prompt: str) -> str:
        payload = (self._default_payload(phase, attempt, prompt)
                   if self.payload_builder is None
                   else self.payload_builder(phase, attempt, prompt))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8",
                   "Accept": "application/json",
                   "Accept-Encoding": "identity"}
        headers.update(self.headers)
        conn = self._make_connection()
        self.last_meta = None
        resp = None
        try:
            # фаза 1: установление соединения (classify → no_response при сбое)
            try:
                conn.connect()
            except ssl.SSLError as e:
                raise ChannelError("tls", f"{type(e).__name__}: {e}", stage="connect") from e
            except (socket.timeout, TimeoutError) as e:
                raise ChannelError("timeout", f"{type(e).__name__}: {e}", stage="connect") from e
            except OSError as e:
                raise ChannelError("transport", f"{type(e).__name__}: {e}", stage="connect") from e
            # фаза 2: отправка запроса (classify → indeterminate)
            try:
                conn.request("POST", self.path, body=body, headers=headers)
            except (socket.timeout, TimeoutError) as e:
                raise ChannelError("timeout", f"{type(e).__name__}: {e}", stage="send") from e
            except (http.client.HTTPException, OSError) as e:
                raise ChannelError("transport", f"{type(e).__name__}: {e}", stage="send") from e
            # фаза 3: ожидание статусной строки (classify → no_response)
            try:
                resp = conn.getresponse()
            except (socket.timeout, TimeoutError) as e:
                raise ChannelError("timeout", f"{type(e).__name__}: {e}", stage="pre_status") from e
            except (http.client.HTTPException, ConnectionError, OSError) as e:
                raise ChannelError("transport", f"{type(e).__name__}: {e}", stage="pre_status") from e
            # фаза 4: статус, заголовки, тело
            if resp.status != 200:                      # включая 3xx: редиректы запрещены
                raise ChannelError("http_status", f"HTTP {resp.status}", stage="body")
            ce = resp.getheader("Content-Encoding")
            if ce is not None and ce.strip().lower() not in ("", "identity"):
                raise ChannelError("encoding",
                                   f"Content-Encoding: {ce!r} (сжатие не поддерживается)",
                                   stage="body")
            cl = resp.getheader("Content-Length")
            if cl is not None:
                try:
                    if int(cl) > self.max_response_bytes:
                        raise ChannelError("too_large",
                                           f"Content-Length {cl} > {self.max_response_bytes}",
                                           stage="body")
                except ValueError:
                    pass
                data = resp.read()          # при недоборе CL http.client → IncompleteRead
            else:
                data = resp.read(self.max_response_bytes + 1)
                if len(data) > self.max_response_bytes:
                    raise ChannelError("too_large", "ответ превышает лимит", stage="body")
            try:
                text = data.decode("utf-8")             # строгий UTF-8
            except UnicodeDecodeError as e:
                raise ChannelError("encoding", f"UTF-8: {e}", stage="body") from e
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as e:
                raise ChannelError("malformed_response", f"не JSON: {e}", stage="body") from e
            self.last_meta = self._extract_meta(obj)
            return extract_content(obj)
        except ChannelError:
            raise
        except http.client.IncompleteRead as e:
            raise ChannelError("incomplete", f"IncompleteRead: {e}", stage="body") from e
        except (socket.timeout, TimeoutError) as e:
            raise ChannelError("timeout", f"{type(e).__name__}: {e}", stage="body") from e
        except ssl.SSLError as e:
            raise ChannelError("tls", f"{type(e).__name__}: {e}") from e
        except (http.client.HTTPException, ConnectionError, OSError) as e:
            raise ChannelError("transport", f"{type(e).__name__}: {e}", stage="body") from e
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass


class HttpsChannel(HttpChannel):
    """HTTPS-транспорт: та же логика, строгий TLS (см. `_TLSConnection`)."""

    name = "https"

    def __init__(self, host: str, port: int, path: str = "/",
                 connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
                 read_timeout: float = DEFAULT_READ_TIMEOUT,
                 max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
                 headers: Optional[dict] = None,
                 ca_file: Optional[str] = None):
        super().__init__(host, port, path, connect_timeout, read_timeout,
                         max_response_bytes, headers)
        self.ca_file = ca_file

    def _make_connection(self):
        return _TLSConnection(self.host, self.port, self.connect_timeout,
                              self.read_timeout, self.ca_file)


#: v27 (2026-10-16): num_predict 96→256 — единственное изменение относительно
#: T0 §3 (см. акт K0_PROTOCOL_v27_ACT.md); остальные параметры — как в T0.
OLLAMA_T0_OPTIONS = {"temperature": 0, "seed": 1729, "num_predict": 256, "num_ctx": 4096}


def ollama_payload_builder(model: str, options: Optional[dict] = None,
                           keep_alive: str = "30m", think: bool = False):
    """Тело запроса Ollama /api/chat (T0 §3: параметры по умолчанию).
    Возвращает callable(phase, attempt, prompt) -> dict для HttpChannel."""
    opts = dict(OLLAMA_T0_OPTIONS)
    if options:
        opts.update(options)

    def build(phase: str, attempt: int, prompt: str) -> dict:
        return {"model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": think,
                "keep_alive": keep_alive,
                "options": opts}

    return build


def build_prompt(ctx, phase: str, attempt: int) -> str:
    """Синтетический билдер промпта текущего этапа (реальные шаблоны «T0» —
    отдельный этап; здесь — детерминированная сериализация контекста)."""
    return f"PHASE {phase}\nATTEMPT {attempt}\n" + render_context(ctx)


def make_respond(channel: Channel, prompt_builder: Optional[Callable] = None):
    """Адаптер к интерфейсу сессии: respond(phase, ctx, attempt) -> str."""

    def respond(phase, ctx, attempt):
        builder = prompt_builder or build_prompt
        prompt = builder(ctx, phase, attempt)
        respond.last_prompt = prompt    # мониторинг объёма контекста (session)
        text = channel.send(phase, attempt, prompt)
        respond.last_meta = getattr(channel, "last_meta", None)
        return text

    respond.last_meta = None            # O1: проброс метаданных последнего вызова
    respond.last_prompt = None
    return respond
