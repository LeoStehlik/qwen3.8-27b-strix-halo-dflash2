#!/usr/bin/env python3

from __future__ import annotations

import http.client
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "coalescing-proxy.py"


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class MockBackendHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    request_count = 0
    count_lock = threading.Lock()
    first_chunk_sent = threading.Event()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        payload = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        with self.count_lock:
            type(self).request_count += 1

        chunks = [b'data: {"token":"one"}\n\n', b'data: {"token":"two"}\n\n', b"data: [DONE]\n\n"]
        payload_length = sum(map(len, chunks))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(payload_length))
        self.end_headers()
        self.wfile.write(chunks[0])
        self.wfile.flush()
        type(self).first_chunk_sent.set()
        time.sleep(0.35)
        for chunk in chunks[1:]:
            self.wfile.write(chunk)
            self.wfile.flush()


class CoalescingProxyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        MockBackendHandler.request_count = 0
        MockBackendHandler.first_chunk_sent.clear()
        cls.backend = ThreadingHTTPServer(("127.0.0.1", 0), MockBackendHandler)
        cls.backend_thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.backend_thread.start()
        cls.proxy_port = unused_port()
        env = os.environ.copy()
        env.update(
            {
                "COALESCE_LISTEN_HOST": "127.0.0.1",
                "COALESCE_LISTEN_PORT": str(cls.proxy_port),
                "COALESCE_UPSTREAM_HOST": "127.0.0.1",
                "COALESCE_UPSTREAM_PORT": str(cls.backend.server_port),
                "COALESCE_UPSTREAM_TIMEOUT": "10",
            }
        )
        cls.proxy = subprocess.Popen(
            [sys.executable, str(PROXY)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                connection = http.client.HTTPConnection("127.0.0.1", cls.proxy_port, timeout=0.2)
                connection.request("GET", "/health")
                response = connection.getresponse()
                response.read()
                connection.close()
                if response.status == 200:
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("proxy did not become ready")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proxy.terminate()
        try:
            cls.proxy.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.proxy.kill()
            cls.proxy.wait(timeout=3)
        cls.backend.shutdown()
        cls.backend.server_close()

    def request(self, body: bytes) -> tuple[int, bytes, str | None]:
        connection = http.client.HTTPConnection("127.0.0.1", self.proxy_port, timeout=5)
        connection.request(
            "POST",
            "/v1/chat/completions",
            body=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        )
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        role = response.getheader("X-Qwen-Coalescer")
        connection.close()
        return status, payload, role

    def test_concurrent_duplicates_share_one_upstream_then_expire(self) -> None:
        body = b'{"model":"test","stream":true,"messages":[{"role":"user","content":"hi"}]}'
        results: list[tuple[int, bytes, str | None]] = []

        first = threading.Thread(target=lambda: results.append(self.request(body)))
        first.start()
        self.assertTrue(MockBackendHandler.first_chunk_sent.wait(timeout=2))
        second = threading.Thread(target=lambda: results.append(self.request(body)))
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(MockBackendHandler.request_count, 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][:2], results[1][:2])
        self.assertEqual({results[0][2], results[1][2]}, {"leader", "follower"})
        self.assertEqual(results[0][0], 200)
        self.assertIn(b'data: {"token":"one"}', results[0][1])
        self.assertTrue(results[0][1].endswith(b"data: [DONE]\n\n"))

        status, payload, role = self.request(body)
        self.assertEqual(status, 200)
        self.assertEqual(role, "leader")
        self.assertTrue(payload.endswith(b"data: [DONE]\n\n"))
        self.assertEqual(MockBackendHandler.request_count, 2)

        retry_body = body.replace(b'"hi"', b'"retry-after-disconnect"')
        MockBackendHandler.first_chunk_sent.clear()
        abandoned = http.client.HTTPConnection("127.0.0.1", self.proxy_port, timeout=5)
        abandoned.request(
            "POST",
            "/v1/chat/completions",
            body=retry_body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        )
        abandoned_response = abandoned.getresponse()
        self.assertEqual(abandoned_response.getheader("X-Qwen-Coalescer"), "leader")
        self.assertTrue(MockBackendHandler.first_chunk_sent.wait(timeout=2))
        retry_results: list[tuple[int, bytes, str | None]] = []
        retry = threading.Thread(target=lambda: retry_results.append(self.request(retry_body)))
        retry.start()
        abandoned.close()
        retry.join(timeout=5)
        self.assertFalse(retry.is_alive())
        self.assertEqual(MockBackendHandler.request_count, 3)
        self.assertEqual(retry_results[0][0], 200)
        self.assertEqual(retry_results[0][2], "follower")
        self.assertIn(b'data: {"token":"one"}', retry_results[0][1])
        self.assertTrue(retry_results[0][1].endswith(b"data: [DONE]\n\n"))

        connection = http.client.HTTPConnection("127.0.0.1", self.proxy_port, timeout=2)
        connection.request("GET", "/coalescer/metrics")
        response = connection.getresponse()
        metrics = response.read().decode()
        connection.close()
        self.assertIn("qwen_coalescer_followers_total 2", metrics)
        self.assertIn("qwen_coalescer_upstream_requests_total 3", metrics)


if __name__ == "__main__":
    unittest.main()
