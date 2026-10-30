#!/usr/bin/env python3
"""Measure short-request latency while another slot performs a cold long prefill."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
import urllib.request


def complete(base_url: str, model: str, prompt: str, max_tokens: int) -> dict:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "max_tokens": max_tokens,
            "seed": 12345,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        separators=(",", ":"),
    ).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=1800) as response:
        result = json.load(response)
    return {"elapsed_seconds": time.monotonic() - started, "result": result}


def summarize(run: dict) -> dict:
    result = run["result"]
    timings = result.get("timings", {})
    usage = result.get("usage", {})
    return {
        "elapsed_seconds": run["elapsed_seconds"],
        "prompt_tokens": usage.get("prompt_tokens", timings.get("prompt_n", 0)),
        "completion_tokens": usage.get("completion_tokens", timings.get("predicted_n", 0)),
        "prompt_per_second": timings.get("prompt_per_second", 0),
        "predicted_per_second": timings.get("predicted_per_second", 0),
        "drafted": timings.get("draft_n", 0),
        "accepted": timings.get("draft_n_accepted", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--long-words", type=int, default=32768)
    parser.add_argument("--short-max-tokens", type=int, default=32)
    parser.add_argument("--stagger-seconds", type=float, default=0.5)
    parser.add_argument("--label", default=str(time.time_ns()))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8080/v1"),
    )
    args = parser.parse_args()
    if args.long_words < 1 or args.short_max_tokens < 1 or args.stagger_seconds < 0:
        parser.error("word/token counts must be positive and stagger must be non-negative")

    vocabulary = "alpha beta gamma delta epsilon zeta eta theta "
    repeated = (vocabulary * ((args.long_words // 8) + 1)).split()
    long_prompt = f"Cold-prefix marker {args.label}. " + " ".join(repeated[: args.long_words])
    long_prompt += "\nReply with only: acknowledged"
    short_prompt = (
        f"Fairness marker {args.label}. In one compact paragraph, explain why "
        "a serving scheduler should interleave decode work with long prefills."
    )

    wall_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        long_future = executor.submit(complete, args.base_url, args.model, long_prompt, 1)
        time.sleep(args.stagger_seconds)
        short_started = time.monotonic()
        short_future = executor.submit(
            complete,
            args.base_url,
            args.model,
            short_prompt,
            args.short_max_tokens,
        )
        long_run = long_future.result()
        short_run = short_future.result()

    print(
        json.dumps(
            {
                "model": args.model,
                "label": args.label,
                "configured_long_words": args.long_words,
                "stagger_seconds": args.stagger_seconds,
                "wall_seconds": time.monotonic() - wall_started,
                "short_start_offset_seconds": short_started - wall_started,
                "long_request": summarize(long_run),
                "short_request": summarize(short_run),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
