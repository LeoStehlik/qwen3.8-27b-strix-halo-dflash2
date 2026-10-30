#!/usr/bin/env python3
"""Streaming reverse proxy with exact in-flight request coalescing.

The first copy of an inference request is sent to llama-server. Concurrent
byte-identical copies subscribe to the same upstream response. Responses are
not cached after completion, so two intentional identical requests made at
different times still produce independent generations.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar


LISTEN_HOST = os.environ.get("COALESCE_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("COALESCE_LISTEN_PORT", "8080"))
UPSTREAM_HOST = os.environ.get("COALESCE_UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.environ.get("COALESCE_UPSTREAM_PORT", "8081"))
UPSTREAM_TIMEOUT = int(os.environ.get("COALESCE_UPSTREAM_TIMEOUT", "7200"))
MAX_BODY_BYTES = int(os.environ.get("COALESCE_MAX_BODY_BYTES", str(64 * 1024 * 1024)))

COALESCED_PATHS = {
    "/completion",
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/messages",
    "/v1/responses",
}

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

KEY_HEADERS = (
    "authorization",
    "x-api-key",
    "anthropic-version",
    "openai-organization",
    "openai-project",
)


@dataclass
class Flight:
    condition: threading.Condition = field(default_factory=threading.Condition)
    status: int | None = None
    reason: str | None = None
    headers: list[tuple[str, str]] = field(default_factory=list)
    chunks: list[bytes] = field(default_factory=list)
    done: bool = False
    error: str | None = None


class ProxyState:
    lock: ClassVar[threading.Lock] = threading.Lock()
    flights: ClassVar[dict[str, Flight]] = {}
    started_at: ClassVar[float] = time.monotonic()
    upstream_requests: ClassVar[int] = 0
    coalesced_followers: ClassVar[int] = 0
    completed_flights: ClassVar[int] = 0
    upstream_errors: ClassVar[int] = 0

    @classmethod
    def join_or_create(cls, key: str) -> tuple[Flight, bool]:
        with cls.lock:
            existing = cls.flights.get(key)
            if existing is not None:
                cls.coalesced_followers += 1
                return existing, False
            flight = Flight()
            cls.flights[key] = flight
            cls.upstream_requests += 1
            return flight, True

    @classmethod
    def finish(cls, key: str, flight: Flight, error: bool) -> None:
        with cls.lock:
            if cls.flights.get(key) is flight:
                del cls.flights[key]
            cls.completed_flights += 1
            if error:
                cls.upstream_errors += 1


class CoalescingProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "QwenCoalescer/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(
            "%s coalescer [%s] %s\n"
            % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), self.address_string(), fmt % args)
        )

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path.split("?", 1)[0] == "/coalescer/metrics":
            self._serve_metrics()
            return
        self._proxy_without_coalescing(b"")

    def do_HEAD(self) -> None:  # noqa: N802
        self._proxy_without_coalescing(b"")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._proxy_without_coalescing(b"")

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_body()
        if body is None:
            return
        path = self.path.split("?", 1)[0]
        if path not in COALESCED_PATHS:
            self._proxy_without_coalescing(body)
            return

        key = self._request_key(body)
        flight, leader = ProxyState.join_or_create(key)
        role = "leader" if leader else "follower"
        self.log_message("%s request %s", role, key[:12])
        if leader:
            worker = threading.Thread(
                target=self._run_upstream_flight,
                args=(key, flight, body),
                name=f"upstream-{key[:12]}",
                daemon=True,
            )
            worker.start()
        self._stream_flight(flight, role)

    def do_PUT(self) -> None:  # noqa: N802
        body = self._read_body()
        if body is not None:
            self._proxy_without_coalescing(body)

    def do_DELETE(self) -> None:  # noqa: N802
        body = self._read_body()
        if body is not None:
            self._proxy_without_coalescing(body)

    def _read_body(self) -> bytes | None:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self.send_error(413, "request body too large")
            return None
        return self.rfile.read(length)

    def _request_key(self, body: bytes) -> str:
        digest = hashlib.sha256()
        digest.update(self.command.encode())
        digest.update(b"\0")
        digest.update(self.path.encode())
        digest.update(b"\0")
        for name in KEY_HEADERS:
            digest.update(name.encode())
            digest.update(b"=")
            digest.update(self.headers.get(name, "").encode())
            digest.update(b"\0")
        digest.update(body)
        return digest.hexdigest()

    def _upstream_headers(self, body: bytes) -> dict[str, str]:
        headers: dict[str, str] = {}
        for name, value in self.headers.items():
            lowered = name.lower()
            if lowered in HOP_BY_HOP_HEADERS or lowered == "host" or lowered == "accept-encoding":
                continue
            headers[name] = value
        headers["Host"] = f"{UPSTREAM_HOST}:{UPSTREAM_PORT}"
        headers["Accept-Encoding"] = "identity"
        headers["Content-Length"] = str(len(body))
        headers["Connection"] = "close"
        return headers

    def _run_upstream_flight(self, key: str, flight: Flight, body: bytes) -> None:
        connection: http.client.HTTPConnection | None = None
        had_error = False
        try:
            connection = http.client.HTTPConnection(
                UPSTREAM_HOST,
                UPSTREAM_PORT,
                timeout=UPSTREAM_TIMEOUT,
            )
            connection.request(self.command, self.path, body=body, headers=self._upstream_headers(body))
            response = connection.getresponse()
            response_headers = [
                (name, value)
                for name, value in response.getheaders()
                if name.lower() not in HOP_BY_HOP_HEADERS
            ]
            with flight.condition:
                flight.status = response.status
                flight.reason = response.reason
                flight.headers = response_headers
                flight.condition.notify_all()

            while True:
                chunk = response.read1(16 * 1024)
                if not chunk:
                    break
                with flight.condition:
                    flight.chunks.append(chunk)
                    flight.condition.notify_all()
        except Exception as exc:
            had_error = True
            with flight.condition:
                flight.error = f"upstream failure: {type(exc).__name__}: {exc}"
                if flight.status is None:
                    flight.status = 502
                    flight.reason = "Bad Gateway"
                    payload = (flight.error + "\n").encode()
                    flight.headers = [("Content-Type", "text/plain; charset=utf-8")]
                    flight.chunks.append(payload)
                flight.condition.notify_all()
        finally:
            if connection is not None:
                connection.close()
            with flight.condition:
                flight.done = True
                flight.condition.notify_all()
            ProxyState.finish(key, flight, had_error)

    def _stream_flight(self, flight: Flight, role: str) -> None:
        with flight.condition:
            while flight.status is None and not flight.done:
                flight.condition.wait()
            status = flight.status or 502
            reason = flight.reason or "Bad Gateway"
            headers = list(flight.headers)

        self.send_response(status, reason)
        for name, value in headers:
            if name.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(name, value)
        self.send_header("X-Qwen-Coalescer", role)
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        index = 0
        client_connected = True
        while True:
            with flight.condition:
                while index >= len(flight.chunks) and not flight.done:
                    flight.condition.wait()
                chunks = flight.chunks[index:]
                index += len(chunks)
                done = flight.done and index >= len(flight.chunks)

            if client_connected:
                for chunk in chunks:
                    try:
                        self._write_chunk(chunk)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        client_connected = False
                        break
            if done:
                break

        if client_connected:
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    def _write_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.wfile.write(f"{len(chunk):X}\r\n".encode())
        self.wfile.write(chunk)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _proxy_without_coalescing(self, body: bytes) -> None:
        connection = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=UPSTREAM_TIMEOUT)
        response_started = False
        try:
            connection.request(self.command, self.path, body=body, headers=self._upstream_headers(body))
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(name, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            response_started = True
            self.close_connection = True
            if self.command != "HEAD":
                while True:
                    chunk = response.read1(16 * 1024)
                    if not chunk:
                        break
                    self._write_chunk(chunk)
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except Exception as exc:
            if not response_started and not self.wfile.closed:
                try:
                    self.send_error(502, f"upstream failure: {type(exc).__name__}")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
        finally:
            connection.close()

    def _serve_metrics(self) -> None:
        with ProxyState.lock:
            active = len(ProxyState.flights)
            upstream = ProxyState.upstream_requests
            followers = ProxyState.coalesced_followers
            completed = ProxyState.completed_flights
            errors = ProxyState.upstream_errors
        uptime = time.monotonic() - ProxyState.started_at
        payload = (
            "# TYPE qwen_coalescer_active_flights gauge\n"
            f"qwen_coalescer_active_flights {active}\n"
            "# TYPE qwen_coalescer_upstream_requests_total counter\n"
            f"qwen_coalescer_upstream_requests_total {upstream}\n"
            "# TYPE qwen_coalescer_followers_total counter\n"
            f"qwen_coalescer_followers_total {followers}\n"
            "# TYPE qwen_coalescer_completed_flights_total counter\n"
            f"qwen_coalescer_completed_flights_total {completed}\n"
            "# TYPE qwen_coalescer_upstream_errors_total counter\n"
            f"qwen_coalescer_upstream_errors_total {errors}\n"
            "# TYPE qwen_coalescer_uptime_seconds gauge\n"
            f"qwen_coalescer_uptime_seconds {uptime:.3f}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 256


def main() -> None:
    server = ProxyServer((LISTEN_HOST, LISTEN_PORT), CoalescingProxyHandler)
    print(
        f"coalescer listening on {LISTEN_HOST}:{LISTEN_PORT}, "
        f"upstream http://{UPSTREAM_HOST}:{UPSTREAM_PORT}",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
