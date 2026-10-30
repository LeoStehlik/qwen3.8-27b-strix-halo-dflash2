#!/usr/bin/env python3
"""Exercise concurrent slots and exact-request coalescing through the public API."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import threading
import time
import urllib.request


DEFAULT_PROMPT = (
    "Explain continuous batching and speculative decoding in a compact technical "
    "paragraph. Finish with one sentence about latency versus aggregate throughput."
)


def fetch_metrics(origin: str) -> dict[str, float]:
    try:
        with urllib.request.urlopen(f"{origin.rstrip('/')}/coalescer/metrics", timeout=5) as response:
            text = response.read().decode()
    except Exception:
        return {}
    result: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, value = line.split(None, 1)
        result[name] = float(value)
    return result


def run_request(base_url: str, payload: bytes, barrier: threading.Barrier) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    barrier.wait()
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=1800) as response:
        result = json.load(response)
    elapsed = time.monotonic() - started
    timings = result.get("timings", {})
    usage = result.get("usage", {})
    return {
        "elapsed_seconds": elapsed,
        "prompt_tokens": usage.get("prompt_tokens", timings.get("prompt_n", 0)),
        "completion_tokens": usage.get("completion_tokens", timings.get("predicted_n", 0)),
        "prompt_tokens_cached": usage.get("prompt_tokens_cached", 0),
        "prompt_per_second": timings.get("prompt_per_second", 0),
        "predicted_per_second": timings.get("predicted_per_second", 0),
        "drafted": timings.get("draft_n", 0),
        "accepted": timings.get("draft_n_accepted", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--duplicates", action="store_true", help="send byte-identical bodies")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8080/v1"),
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")

    origin = args.base_url.removesuffix("/v1").rstrip("/")
    metrics_before = fetch_metrics(origin)
    payloads = []
    for index in range(args.concurrency):
        prompt = args.prompt if args.duplicates else f"{args.prompt}\nRequest variant: {index}."
        payloads.append(
            json.dumps(
                {
                    "model": args.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "top_k": 20,
                    "min_p": 0.0,
                    "max_tokens": args.max_tokens,
                    "seed": 12345,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                separators=(",", ":"),
            ).encode()
        )

    barrier = threading.Barrier(args.concurrency)
    wall_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run_request, args.base_url, payload, barrier) for payload in payloads]
        rows = [future.result() for future in futures]
    wall_elapsed = time.monotonic() - wall_started
    metrics_after = fetch_metrics(origin)

    total_completion = sum(row["completion_tokens"] for row in rows)
    model_completion = rows[0]["completion_tokens"] if args.duplicates else total_completion
    drafted = sum(row["drafted"] for row in rows)
    accepted = sum(row["accepted"] for row in rows)
    metric_delta = {
        key: metrics_after.get(key, 0) - metrics_before.get(key, 0)
        for key in (
            "qwen_coalescer_upstream_requests_total",
            "qwen_coalescer_followers_total",
            "qwen_coalescer_upstream_errors_total",
        )
        if key in metrics_after
    }
    print(
        json.dumps(
            {
                "model": args.model,
                "concurrency": args.concurrency,
                "duplicates": args.duplicates,
                "wall_seconds": wall_elapsed,
                "delivered_completion_tokens_per_second": total_completion / wall_elapsed,
                "estimated_model_completion_tokens_per_second": model_completion / wall_elapsed,
                "mean_request_seconds": statistics.mean(row["elapsed_seconds"] for row in rows),
                "mean_reported_decode_tokens_per_second": statistics.mean(
                    row["predicted_per_second"] for row in rows
                ),
                "draft_acceptance": accepted / drafted if drafted else 0,
                "coalescer_metric_delta": metric_delta,
                "requests": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
