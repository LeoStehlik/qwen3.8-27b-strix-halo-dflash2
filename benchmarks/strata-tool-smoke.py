#!/usr/bin/env python3
"""Synthetic API checks; no tools are executed and no OpenClaw turns are sent.

The output cap applies only to these requests, not to the served model.
Run against an isolated listener, not a busy production conversation.
"""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8083/v1')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', default='qwen3.8-flash-next-unsloth')
    parser.add_argument('--key-env', default='STRATA_API_KEY')
    args = parser.parse_args()
    report = {'protocol': 'flash-next-tool-smoke-v1', 'checks': [], 'passed': False}
    headers = {'Content-Type': 'application/json'}
    if os.environ.get(args.key_env):
        headers['Authorization'] = 'Bearer ' + os.environ[args.key_env]

    def chat(messages, tools=None):
        body = {'model': args.model, 'messages': messages, 'temperature': 0,
                'max_tokens': 2048, 'stream': False}
        if tools:
            body.update(tools=tools, tool_choice='auto')
        start = time.monotonic()
        req = urllib.request.Request(args.url.rstrip('/') + '/chat/completions',
                                     json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.load(response)
        if result.get('error'):
            raise RuntimeError(result['error'])
        choice = result['choices'][0]
        report['checks'].append({'elapsed_s': round(time.monotonic() - start, 3),
                                 'finish_reason': choice.get('finish_reason'),
                                 'usage': result.get('usage'),
                                 'timings': result.get('timings'),
                                 'message': choice['message']})
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('Request exhausted its test allowance; no pass inferred')
        return choice['message']

    expected = {'record_id': 'TIER-042', 'include_archived': False,
                'fields': ['status', 'owner']}
    tool = {'type': 'function', 'function': {
        'name': 'lookup_record', 'description': 'Read the current record from the registry.',
        'parameters': {'type': 'object', 'properties': {
            'record_id': {'type': 'string'}, 'include_archived': {'type': 'boolean'},
            'fields': {'type': 'array', 'items': {'type': 'string'}}},
            'required': list(expected), 'additionalProperties': False}}}
    messages = [{'role': 'system', 'content': 'Use the available tools when information must be retrieved.'},
                {'role': 'user', 'content': 'Look up record TIER-042, exclude archived records, and request '
                 'the fields status and owner in that order. After the tool returns, report its '
                 'verification_code exactly; do not invent one.'}]
    try:
        message = chat(messages, [tool])
        calls = message.get('tool_calls') or []
        assert len(calls) == 1, f'Expected one tool call, got {len(calls)}'
        call = calls[0]
        assert call['function']['name'] == 'lookup_record'
        assert json.loads(call['function']['arguments']) == expected, 'Tool arguments differ'
        assert call.get('id'), 'Tool call has no ID'
        report['exact_tool_arguments'] = True
        messages += [message, {'role': 'tool', 'tool_call_id': call['id'],
                              'content': json.dumps({'status': 'READY', 'owner': 'Harper',
                                                     'verification_code': 'R7P2'})}]
        continuation = chat(messages, [tool])
        assert not continuation.get('tool_calls'), 'Unexpected additional tool call'
        assert 'R7P2' in (continuation.get('content') or ''), 'Tool result absent from answer'
        report['tool_result_continuation'] = True
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'report': str(args.out)}))


if __name__ == '__main__':
    main()
