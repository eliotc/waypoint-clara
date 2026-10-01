"""Actual Clara WebSocket adapter: scripted text in, Live audio/transcripts out.

This covers the real Live transport but not speech recognition or browser playback.
It never retries a failed session or a tool action.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import uuid4


class LiveProtocolError(RuntimeError):
    pass


def endpoint_parts(endpoint):
    parts = urlsplit(endpoint)
    if (parts.scheme != 'http' or parts.hostname not in ('127.0.0.1','localhost','::1')
        or parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment):
        raise ValueError('Live evaluation requires a plain localhost HTTP endpoint')
    return parts


def read_metadata(endpoint, token):
    endpoint_parts(endpoint)
    request = Request(endpoint.rstrip('/') + '/evaluation/metadata', headers={'x-waypoint-evaluation':token})
    # Do not use proxy environment variables for the local evaluation service.
    from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=10) as response:
        return json.load(response)


class ClaraLiveAdapter:
    def __init__(self, target, dataset_id):
        endpoint_parts(target['endpoint'])
        self.target = target
        self.dataset_id = dataset_id
        self.artifacts = None
        self.last_trace = None

    def run(self, scenario, persona):
        return asyncio.run(self.run_async(scenario, persona))

    async def run_async(self, scenario, persona, turn_provider=None):
        from websockets.asyncio.client import connect
        token = os.environ.get('EVAL_HTTP_TOKEN', '')
        self.last_trace = {'schema_version':'1.1','scenario_id':scenario['scenario_id'],
                           'turns':[], 'observations':{'events':[], 'audio_files':[]}}
        trace = self.last_trace
        if not token:
            raise ValueError("Set EVAL_HTTP_TOKEN from the private database state")
        before = await asyncio.to_thread(read_metadata, self.target['endpoint'], token)
        trace['observations']['server_before'] = before
        if (before.get('mode') != 'readonly_evaluation' or before.get('model') != self.target['model']
            or before.get('dataset_id') != self.dataset_id or before.get('protocol_version') != 1):
            raise LiveProtocolError('Server identity/model/dataset does not match the experiment')
        if self.target['require_embeddings'] and not before.get('embeddings_ready'):
            raise LiveProtocolError('This experiment requires prepared embeddings')
        from evaluation.serve import source_hashes
        if before.get('source_hashes') != source_hashes():
            raise LiveProtocolError('Running server source differs from this checkout; restart the evaluation server')
        client_id = 'eval-' + uuid4().hex
        trace['observations']['client_id'] = client_id
        ws_url = self.target['endpoint'].replace('http://','ws://',1).rstrip('/') + '/ws/' + client_id
        async with connect(ws_url, additional_headers={'x-waypoint-evaluation':token},
                           open_timeout=10, max_size=8*1024*1024, proxy=None) as ws:
            # Consume the proactive greeting so it cannot be mistaken for turn 1.
            await self.read_turn(ws, '(greeting)', trace, 'greeting')
            for index, user in enumerate(scenario['user_turns'], 1):
                if turn_provider is not None:
                    # Only transcripts cross this boundary, never tools or DB metadata.
                    user = await turn_provider(index, visible_conversation(trace))
                    if not isinstance(user, str) or not user.strip():
                        raise ValueError('Persona supplied an empty user message')
                await ws.send(json.dumps({'type':'text','content':user}))
                turn = await self.read_turn(ws, user, trace, str(index))
                trace['turns'].append(turn)
        after = await asyncio.to_thread(read_metadata, self.target['endpoint'], token)
        trace['observations']['server_after'] = after
        if any(before.get(k) != after.get(k) for k in ('database','model','instruction_sha256','source_hashes')):
            raise LiveProtocolError('Server changed during the scenario')
        trace['observations']['database_unchanged'] = all(
            before['snapshot'].get(k) == after['snapshot'].get(k)
            for k in ('courses','events','tour_bookings','event_registrations','knowledge_docs','scholarships'))
        trace['observations']['audio_received'] = any(
            e['kind'] == 'audio' and e['turn'] != 'greeting' for e in trace['observations']['events'])
        return trace

    async def read_turn(self, ws, user, trace, label):
        start = time.monotonic()
        deadline = start + self.target['turn_timeout_seconds']
        turn = {'user':user,'assistant':'','tools':[],'cards':[]}
        pending = {}
        audio = bytearray()
        completed_text = []
        current_text = ''
        first_audio = first_card = None
        observations = trace['observations']
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Live turn did not complete')
                message = await asyncio.wait_for(ws.recv(), remaining)
                elapsed = round((time.monotonic()-start)*1000, 3)
                if isinstance(message, bytes):
                    if first_audio is None:
                        first_audio = elapsed
                    audio.extend(message)
                    observations['events'].append({'turn':label,'elapsed_ms':elapsed,'kind':'audio','bytes':len(message)})
                    continue
                event = json.loads(message)
                kind = event.get('type')
                observations['events'].append({'turn':label,'elapsed_ms':elapsed,'kind':kind,'event':event})
                if kind == 'error':
                    raise LiveProtocolError('Clara server reported an error; see raw event evidence')
                if kind in ('interrupted', 'session_retry'):
                    raise LiveProtocolError('Unexpected interruption in a sequential text scenario')
                if kind == 'transcript' and event.get('role') == 'agent':
                    # The bridge emits cumulative text, not raw deltas.
                    current_text = event.get('text','')
                    if event.get('finished'):
                        completed_text.append(current_text)
                        current_text = ''
                    turn['assistant'] = ' '.join(completed_text + ([current_text] if current_text else []))
                elif kind == 'card':
                    if first_card is None:
                        first_card = elapsed
                    turn['cards'].append(event)
                elif kind == 'tool_call':
                    call_id = event.get('id') or f"anonymous-{len(turn['tools'])}"
                    if call_id in pending:
                        raise LiveProtocolError('Duplicate outstanding tool call ID')
                    call = {'name':event['name'], 'arguments':event.get('args',{}), 'result':{}}
                    pending[call_id] = call
                    turn['tools'].append(call)
                elif kind == 'tool_result':
                    call_id = event.get('id')
                    if not call_id:
                        matches = [k for k,c in pending.items() if c['name'] == event['name']]
                        if len(matches) != 1:
                            raise LiveProtocolError('Ambiguous tool result without call ID')
                        call_id = matches[0]
                    if call_id not in pending or pending[call_id]['name'] != event['name']:
                        raise LiveProtocolError('Tool result does not match an outstanding call')
                    pending.pop(call_id)['result'] = event.get('response',{})
                elif kind == 'turn_complete' and turn['assistant'].strip() and not pending:
                    break
            return turn
        finally:
            # Retain partial evidence on timeout/disconnect, including PCM bytes.
            observations.setdefault('turn_timings',[]).append({
                'turn':label,'first_audio_chunk_ms':first_audio,'first_card_ms':first_card,
                'elapsed_ms':round((time.monotonic()-start)*1000,3),
                'audio_bytes':len(audio), 'pending_tools':list(pending),
            })
            if label == 'greeting':
                observations['greeting'] = turn
            else:
                observations['last_turn'] = turn
            if audio and self.artifacts:
                name = f"audio-{uuid4().hex}.pcm"
                (self.artifacts/name).write_bytes(audio)
                observations['audio_files'].append({'turn':label,'path':name,'format':'pcm_s16le','sample_rate':24000,'channels':1})


def visible_conversation(trace):
    """Transcript-only exposure; card payloads can contain non-rendered fields."""
    messages = []
    greeting = trace.get('observations', {}).get('greeting', {}).get('assistant')
    if greeting:
        messages.append({'role': 'assistant', 'text': greeting})
    for turn in trace.get('turns', []):
        messages.append({'role': 'user', 'text': turn['user']})
        messages.append({'role': 'assistant', 'text': turn['assistant']})
    return messages
