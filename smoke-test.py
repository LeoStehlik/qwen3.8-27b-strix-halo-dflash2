#!/usr/bin/env python3
"""Small OpenAI-compatible text/vision smoke test for the local router."""

import argparse
import base64
import json
import mimetypes
import os
import time
import urllib.request


parser = argparse.ArgumentParser()
parser.add_argument("model", help="API model id or alias")
parser.add_argument("--image")
parser.add_argument("--max-tokens", type=int, default=128)
parser.add_argument(
    "--base-url",
    default=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8080/v1"),
)
args = parser.parse_args()

if args.image:
    mime = mimetypes.guess_type(args.image)[0] or "image/png"
    with open(args.image, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    content = [
        {"type": "text", "text": "In one short sentence, identify the image, including any text or logo."},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
    ]
else:
    content = "In two sentences, explain why speculative decoding is lossless."

payload = {
    "model": args.model,
    "messages": [{"role": "user", "content": content}],
    "temperature": 0,
    "max_tokens": args.max_tokens,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    f"{args.base_url.rstrip('/')}/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)

started = time.monotonic()
with urllib.request.urlopen(request, timeout=1800) as response:
    result = json.load(response)
elapsed = time.monotonic() - started

message = result["choices"][0]["message"]
print(message.get("content", ""))
if message.get("reasoning_content"):
    print("\n[reasoning extracted]")
    print(message["reasoning_content"])
print(f"\nElapsed: {elapsed:.2f}s")
print("Usage:", json.dumps(result.get("usage", {}), sort_keys=True))
if result.get("timings"):
    print("Timings:", json.dumps(result["timings"], sort_keys=True))
