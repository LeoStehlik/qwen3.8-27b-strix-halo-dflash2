#!/usr/bin/env python3
"""Small repeatable generation/acceptance benchmark for DFlash2 tuning."""

import argparse
import json
import os
import statistics
import urllib.request


PROMPTS = (
    "Write a compact but technically precise explanation of speculative decoding, including acceptance, rejection, and why the output distribution remains correct.",
    "Design a robust Python service that consumes jobs from a queue. Explain idempotency, retries, backpressure, graceful shutdown, and observability in concrete terms.",
)


def complete(base_url: str, model: str, prompt: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "max_tokens": 192,
        "seed": 12345,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8080/v1"),
    )
    parser.add_argument("--label", help="Optional configuration label in JSON output")
    args = parser.parse_args()

    rows = []
    for prompt in PROMPTS:
        result = complete(args.base_url, args.model, prompt)
        timing = result["timings"]
        drafted = timing.get("draft_n", 0)
        accepted = timing.get("draft_n_accepted", 0)
        rows.append(
            {
                "tokens_per_second": timing["predicted_per_second"],
                "drafted": drafted,
                "accepted": accepted,
                "acceptance": accepted / drafted if drafted else 0,
            }
        )

    print(
        json.dumps(
            {
                "model": args.model,
                "label": args.label,
                "tokens_per_second": statistics.mean(
                    row["tokens_per_second"] for row in rows
                ),
                "draft_acceptance": sum(row["accepted"] for row in rows)
                / sum(row["drafted"] for row in rows),
                "runs": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
