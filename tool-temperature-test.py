#!/usr/bin/env python3
"""Probe Qwen3.8 tool selection across sampling temperatures."""

import argparse
import json
import os
import urllib.request


TEMPERATURES = (0.0, 0.2, 0.3, 0.7, 1.0)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate an arithmetic expression exactly.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]
CASES = (
    ("explicit", "Use the weather tool to get the current weather in Prague.", "get_weather"),
    ("implicit", "Do I need an umbrella in Seattle today?", "get_weather"),
    ("calculation", "Use an available tool to calculate 18743 * 9327 exactly.", "calculator"),
    ("current", "Who is the current president of France? Check rather than relying on memory.", "web_search"),
    ("control", "In one sentence, explain why leaves look green. Do not use a tool.", None),
)

parser = argparse.ArgumentParser()
parser.add_argument("--case", choices=("all", *(case[0] for case in CASES)), default="all")
parser.add_argument("--trials", type=int, default=1)
parser.add_argument("--model", default="qwen3.8-27b-q4-fast")
parser.add_argument(
    "--base-url",
    default=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8080/v1"),
)
args = parser.parse_args()
selected_cases = CASES if args.case == "all" else tuple(case for case in CASES if case[0] == args.case)


def request(payload):
    req = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


for temperature in TEMPERATURES:
    passed = 0
    total = 0
    print(f"\ntemperature={temperature:.1f}")
    for trial in range(1, args.trials + 1):
        for label, prompt, expected in selected_cases:
            result = request(
                {
                    "model": args.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "top_p": 0.95,
                    "top_k": 20,
                    "min_p": 0.0,
                    "max_tokens": 256,
                }
            )
            choice = result["choices"][0]
            message = choice["message"]
            calls = message.get("tool_calls") or []
            names = [call["function"]["name"] for call in calls]
            ok = (not names) if expected is None else expected in names
            args_ok = True
            for call in calls:
                try:
                    json.loads(call["function"]["arguments"])
                except (TypeError, json.JSONDecodeError):
                    args_ok = False
            success = ok and args_ok and choice.get("finish_reason") != "length"
            passed += success
            total += 1
            print(
                f"  {label:11} trial={trial} {'PASS' if success else 'FAIL'} "
                f"calls={names or '-'} finish={choice.get('finish_reason')} "
                f"args_json={args_ok} reasoning_tokens~={len(message.get('reasoning_content') or '') // 4}"
            )
    print(f"  score={passed}/{total}")
