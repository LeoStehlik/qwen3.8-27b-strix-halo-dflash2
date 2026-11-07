#!/usr/bin/env python3
"""Performance-only public workloads; no tools or OpenClaw agent turns.

The two upstream prompts come from the installed Strata standard-v1 suite.
This custom subset is not a result from the full upstream benchmark protocol.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8084')
    p.add_argument('--model', required=True)
    p.add_argument('--strata-bundle', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--presence-penalty', type=float,
                   help='Explicit request penalty; otherwise retains server defaults')
    p.add_argument('--temperature', type=float, default=0)
    p.add_argument('--thinking', action='store_true')
    a = p.parse_args()
    if a.presence_penalty is not None and not 0 <= a.presence_penalty <= 2:
        p.error('--presence-penalty must be between zero and two')
    requests = a.strata_bundle / 'bench/prompts/standard-v1/requests'
    cases = []
    for name in ('performance-short-r1', 'performance-prompt-16k-r1'):
        raw = (requests / (name + '.json')).read_bytes()
        d = json.loads(raw)
        cases.append((name, d['messages'], hashlib.sha256(raw).hexdigest()))
    coding = [{'role': 'user', 'content': '[case public-lru-cache-v1]\n'
               'Implement an LRU cache in Python using a dictionary and a doubly linked list. '
               'Include get and put with O(1) operations, eviction, capacity validation, '
               'and example assertions covering updates and eviction. Return the complete '
               'code followed by a brief explanation.'}]
    cases.append(('public-lru-cache-v1', coding,
                  hashlib.sha256(json.dumps(coding).encode()).hexdigest()))
    report = {'protocol': 'strata-public-generation-subset-v1', 'runs': [], 'completed': False}
    headers = {'Content-Type': 'application/json'}
    if os.environ.get('STRATA_API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['STRATA_API_KEY']

    def persist():
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2) + '\n')

    try:
        for name, messages, source_hash in cases:
            body = {'model': a.model, 'messages': messages, 'temperature': a.temperature, 'seed': 1,
                    'reasoning_effort': 'medium' if a.thinking else 'none',
                    'chat_template_kwargs': {'enable_thinking': a.thinking},
                    'max_tokens': 512, 'stream': True, 'stream_options': {'include_usage': True}}
            if a.presence_penalty is not None:
                body['presence_penalty'] = a.presence_penalty
            req = urllib.request.Request(a.url.rstrip('/') + '/v1/chat/completions',
                                         json.dumps(body).encode(), headers)
            start = time.monotonic()
            first = usage = timings = finish = None
            output = []
            done = False
            with urllib.request.urlopen(req, timeout=900) as response:
                for line in response:
                    if not line.startswith(b'data:'):
                        continue
                    data = line[5:].strip()
                    if data == b'[DONE]':
                        done = True
                        break
                    event = json.loads(data)
                    if event.get('error'):
                        raise RuntimeError(event['error'])
                    usage = event.get('usage') or usage
                    timings = event.get('timings') or timings
                    for choice in event.get('choices', []):
                        delta = choice.get('delta') or {}
                        text = (delta.get('reasoning_content') or '') + (delta.get('content') or '')
                        if text:
                            if first is None:
                                first = time.monotonic() - start
                            output.append(text)
                        finish = choice.get('finish_reason') or finish
            row = {'case': name, 'source_sha256': source_hash, 'request': body,
                   'usage': usage, 'timings': timings, 'elapsed_s': time.monotonic() - start,
                   'first_token_s': first, 'finish_reason': finish, 'complete_stream': done,
                   'output_sha256': hashlib.sha256(''.join(output).encode()).hexdigest()}
            report['runs'].append(row)
            persist()
            if first is None or not usage or not timings or not done:
                raise RuntimeError('Incomplete stream or missing measurements')
            print(json.dumps({k: v for k, v in row.items() if k != 'request'}), flush=True)
        report['completed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        persist()


if __name__ == '__main__':
    main()
