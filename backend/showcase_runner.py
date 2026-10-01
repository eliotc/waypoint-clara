"""Bounded fixed-script Live session. No offline harness dependencies."""
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import time

from agent import INSTRUCTION, MODEL
from scenarios import get_scenario
from showcase_judge import SHOWCASE_JUDGE_MODEL, SHOWCASE_JUDGE_TIMEOUT_SECONDS, evaluate_run
from tools import (bind_display_session, reset_display_session, register_display_callback,
                   unregister_display_callback, record_student_message, set_connection_provider,
                   reset_connection_provider, get_discovery_context, get_course_detail,
                   search_courses, recommend_courses, search_knowledge, search_scholarships)

log = logging.getLogger(__name__)
SHOWCASE_TOOLS = [get_discovery_context, get_course_detail, search_courses,
                  recommend_courses, search_knowledge, search_scholarships]
_RUN_TIMEOUT_SECONDS = 120
_PLAYBACK_TIMEOUT_SECONDS = 45
_active_showcase_runs = 0
_ip_hourly_starts = {}


def check_rate_limit(ip):
    now = time.monotonic()
    for key in list(_ip_hourly_starts):
        _ip_hourly_starts[key] = [t for t in _ip_hourly_starts[key] if now-t < 3600]
        if not _ip_hourly_starts[key]:
            del _ip_hourly_starts[key]
    if len(_ip_hourly_starts.get(ip, [])) >= 5:
        return 'Live example limit reached. Please try again later.'
    if len(_ip_hourly_starts) >= 10000 and ip not in _ip_hourly_starts:
        return 'Live examples are temporarily busy.'
    return None


def reserve(ip):
    # Synchronous reservation within the event loop: no start/check race.
    global _active_showcase_runs
    error = check_rate_limit(ip)
    if error:
        raise RuntimeError(error)
    if _active_showcase_runs >= 2:
        raise RuntimeError('Live examples are currently busy. Please try again later.')
    _active_showcase_runs += 1
    _ip_hourly_starts.setdefault(ip, []).append(time.monotonic())


@contextmanager
def _create_readonly_connection():
    import psycopg2
    dsn = os.getenv('SHOWCASE_READONLY_DATABASE_URL')
    if not dsn:
        raise RuntimeError('Read-only configuration missing')
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5s'")
            cur.execute('SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname=current_user')
            if any(cur.fetchone()):
                raise RuntimeError('Privileged database role is not allowed')
            cur.execute("SELECT has_database_privilege(current_database(), 'CREATE'), has_database_privilege(current_database(), 'TEMP')")
            if any(cur.fetchone()):
                raise RuntimeError('Database creation privileges are not allowed')
            cur.execute("""SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname NOT LIKE 'pg_%'
                AND nspname <> 'information_schema' AND has_schema_privilege(oid,'CREATE')),
                EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
                AND c.relkind IN ('r','p','v','m','f') AND
                (pg_has_role(c.relowner,'USAGE') OR has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')))""")
            if any(cur.fetchone()):
                raise RuntimeError('Writable database role is not allowed')
            for table in ('courses', 'events', 'scholarships', 'knowledge_docs'):
                cur.execute('SELECT has_table_privilege(%s, %s)', (table, 'SELECT'))
                if not cur.fetchone()[0]:
                    raise RuntimeError('Required catalog permission missing')
            cur.execute('SET default_transaction_read_only = on')
        yield conn
    finally:
        conn.close()


def preflight_readonly():
    with _create_readonly_connection():
        pass


class ADKTransport:
    """One session, queue and event iterator for the complete conversation."""
    async def __aenter__(self):
        from google.adk import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.agents.live_request_queue import LiveRequestQueue
        from google.adk.agents.run_config import RunConfig, StreamingMode
        from google.genai import types
        self.types = types
        self.service = InMemorySessionService()
        self.id = secrets.token_hex(16)
        self.session = await self.service.create_session(app_name='WaypointShowcase', user_id=self.id, session_id=self.id)
        agent = Agent(name='ClaraShowcase', model=MODEL, instruction=INSTRUCTION, tools=SHOWCASE_TOOLS)
        self.runner = Runner(agent=agent, app_name='WaypointShowcase', session_service=self.service)
        self.queue = LiveRequestQueue()
        config = RunConfig(streaming_mode=StreamingMode.BIDI, response_modalities=['AUDIO'],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Aoede')), language_code='en-AU'),
            output_audio_transcription=types.AudioTranscriptionConfig())
        self.events = self.runner.run_live(user_id=self.id, session_id=self.id,
                                          live_request_queue=self.queue, run_config=config)
        return self

    async def turn(self, text):
        self.queue.send_content(self.types.Content(role='user', parts=[self.types.Part(text=text)]))
        has_content = False
        async for event in self.events:
            if event.content:
                for part in event.content.parts or []:
                    if part.inline_data and (part.inline_data.mime_type or '').startswith('audio/'):
                        has_content = True
                        yield {'type': 'audio', 'data': part.inline_data.data}
            for call in event.get_function_calls() or []:
                yield {'type': 'tool_call', 'id': call.id, 'name': call.name, 'args': call.args}
            for result in event.get_function_responses() or []:
                yield {'type': 'tool_result', 'id': result.id, 'name': result.name, 'result': result.response}
            if event.output_transcription and event.output_transcription.text:
                has_content = True
                is_partial = getattr(event, 'partial', True)
                yield {'type': 'transcript', 'text': event.output_transcription.text, 'partial': is_partial}
            if event.turn_complete and has_content:
                yield {'type': 'complete'}
                return
        raise RuntimeError('Model stream ended before turn completion')

    async def __aexit__(self, *exc):
        self.queue.close()
        await self.events.aclose()
        await self.service.delete_session(app_name='WaypointShowcase', user_id=self.id, session_id=self.id)


def provenance(scenario):
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ('agent.py','tools.py','degree_status.py','experience_status.py','showcase_runner.py','showcase_judge.py','scenarios.py'):
        digest.update(name.encode()); digest.update((root/name).read_bytes())
    return dict(model_id=MODEL, judge_model=SHOWCASE_JUDGE_MODEL or None,
                scenario_version=scenario['version'], application_source_sha256=digest.hexdigest(),
                revision=os.getenv('K_REVISION') or os.getenv('APPLICATION_REVISION'))


def retain_trace(trace):
    root = Path('/tmp/waypoint-showcase-runs')
    root.mkdir(mode=0o700, exist_ok=True)
    files = sorted(root.glob('showcase-*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    for i, path in enumerate(files):
        if i >= 99 or time.time()-path.stat().st_mtime > 3600:
            path.unlink(missing_ok=True)
    path = root / (trace['run_id']+'.json')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(trace,f,default=str)


def evaluate_tool_policy(tools: list[dict], expected_policy: dict) -> dict:
    """
    Deterministically evaluates whether the tool calls made by Clara align with
    the expected tool invocation policy for each conversational turn.

    Note: This evaluates tool invocation telemetry and protocol adherence ONLY.
    Semantic quality (whether Clara's spoken advice was grounded, accurate, or compliant
    with student disclosures) is NOT assessed by this function and must be evaluated
    by the LLM judge over the full transcript and retrieved results.
    """
    turn_results = []
    all_passed = True
    total_expected_lookups = 0
    actual_lookups_made = 0
    unnecessary_calls_count = 0

    tools_by_turn: dict[int, list[dict]] = {}
    for t in tools:
        tid = int(t.get('turn_id', 1))
        tools_by_turn.setdefault(tid, []).append(t)

    repeat_lookups = []
    seen_course_lookups = set()

    for turn_idx, policy in sorted(expected_policy.items(), key=lambda x: int(x[0])):
        turn_idx = int(turn_idx)
        invoked = tools_by_turn.get(turn_idx, [])
        invoked_names = [str(c.get('name') or '') for c in invoked]
        allowed = [str(a) for a in policy.get('allowed_tools', [])]
        min_calls = policy.get('min_calls', 0)
        max_calls = policy.get('max_calls')
        is_reasoning_only = policy.get('conversational_reasoning_only', False)

        turn_passed = True
        protocol_status = 'compliant'
        arg_diagnostics = []
        turn_efficiency_notes = []

        # Observed tool activity (neutral factual description)
        if len(invoked_names) > 0:
            observed_activity = f"Observed tool call: {', '.join(invoked_names)}"
        else:
            observed_activity = "No tools invoked (conversational response)"

        # Check argument diagnostics (e.g. omitted constraints or inferred parameters)
        # and record repeat lookups as efficiency telemetry
        for call in invoked:
            cname = call.get('name')
            args = call.get('args') or {}
            if cname in ('search_courses', 'recommend_courses'):
                if 'study_mode_preference' not in args and turn_idx >= 2:
                    arg_diagnostics.append(f"{cname}: omitted study_mode_preference")
                if 'target_level' in args:
                    arg_diagnostics.append(f"{cname}: target_level='{args['target_level']}' (inferred scope)")

            if cname in ('search_courses', 'get_course_detail'):
                key = (cname, tuple(sorted((str(k), str(v)) for k, v in args.items())))
                if seen_course_lookups:
                    if turn_idx == 2 and cname == 'search_courses':
                        note = "Turn 2 repeated course search under new online constraint (acceptable alternative to reusing prior evidence)."
                    else:
                        note = f"Repeated course lookup ({cname}) in Turn {turn_idx}; prior course evidence already retrieved."
                    turn_efficiency_notes.append(note)
                    repeat_lookups.append({
                        'turn_id': turn_idx,
                        'tool': cname,
                        'args': args,
                        'note': note
                    })
                seen_course_lookups.add(key)

        diagnostic = ""
        if is_reasoning_only:
            if len(invoked) > 0:
                turn_passed = False
                protocol_status = 'unallowlisted_call'
                unnecessary_calls_count += len(invoked)
                diagnostic = f"Expected conversational reasoning; observed tool call: {', '.join(invoked_names)}."
            else:
                diagnostic = "Conversational response observed without tool calls."
        else:
            if min_calls > 0:
                total_expected_lookups += 1

            allowed_invoked = [n for n in invoked_names if n in allowed]
            disallowed = [n for n in invoked_names if n not in allowed]
            redundant_read_only = [n for n in disallowed if n == 'get_discovery_context']
            prohibited = [n for n in disallowed if n not in redundant_read_only]

            if len(allowed_invoked) < min_calls:
                turn_passed = False
                protocol_status = 'missing_required_call'
                diagnostic = f"Missing required lookup: expected at least {min_calls} call from {allowed}."
            elif max_calls is not None and len(invoked) > max_calls:
                turn_passed = False
                protocol_status = 'max_calls_exceeded'
                excess = len(invoked) - max_calls
                unnecessary_calls_count += excess
                diagnostic = f"Exceeded maximum tool calls: observed {len(invoked)}, allowed {max_calls}."
            elif prohibited:
                turn_passed = False
                protocol_status = 'unallowlisted_tool'
                unnecessary_calls_count += len(disallowed)
                purpose = policy.get('expected_purpose', '')
                purpose_hint = f" ({purpose})" if purpose else ""
                diagnostic = f"Invoked unallowlisted tool(s) {prohibited}; expected subset of {allowed}{purpose_hint}."
            else:
                if len(invoked) > 0:
                    actual_lookups_made += 1
                    diagnostic = f"Invoked {', '.join(invoked_names)}; required lookup completed within allowed scope {allowed}."
                else:
                    diagnostic = "Conversational response within allowed scope (0 tool calls)."
                if redundant_read_only:
                    protocol_status = 'redundant_lookup_warning'
                    unnecessary_calls_count += len(redundant_read_only)
                    note = (
                        f"Required lookup completed; unnecessary read-only context lookup(s) "
                        f"observed: {', '.join(redundant_read_only)}."
                    )
                    turn_efficiency_notes.append(note)
                    repeat_lookups.append({
                        'turn_id': turn_idx,
                        'tool': ', '.join(redundant_read_only),
                        'args': {},
                        'note': note
                    })

        if not turn_passed:
            all_passed = False

        tech_parts = [diagnostic]
        if arg_diagnostics:
            tech_parts.append(f"Diagnostics: {'; '.join(arg_diagnostics)}")
        technical_detail = " | ".join(tech_parts)

        turn_results.append({
            'turn_id': turn_idx,
            'phase': policy.get('phase', f'Turn {turn_idx}'),
            'status': 'compliant' if turn_passed else 'flagged',
            'passed': turn_passed,
            'protocol_status': protocol_status,
            'semantic_status': 'not_assessed',
            'invoked_tools': invoked_names,
            'allowed_tools': allowed,
            'is_reasoning_only': is_reasoning_only,
            'purpose': policy.get('expected_purpose', ''),
            'observed_activity': observed_activity,
            'diagnostic': diagnostic,
            'argument_diagnostics': arg_diagnostics,
            'efficiency_notes': turn_efficiency_notes,
            'outcome': observed_activity,
            'technical_detail': technical_detail,
            'notes': observed_activity,
        })

    compliant_turns = sum(1 for t in turn_results if t['passed'])
    total_turns = len(turn_results)
    if all_passed:
        compliance_summary = f"Tool telemetry: {compliant_turns}/{total_turns} turns compliant with invocation policy. Semantic quality not assessed by tool telemetry."
    else:
        compliance_summary = f"Tool telemetry flagged {unnecessary_calls_count} unallowlisted call(s) or missing lookup(s) across {total_turns - compliant_turns} turn(s). Semantic quality not assessed by tool telemetry."

    return {
        'passed': all_passed,
        'tool_protocol_compliant': all_passed,
        'semantic_status': 'not_assessed',
        'summary': compliance_summary,
        'turns_compliant': compliant_turns,
        'total_turns': total_turns,
        'total_expected_lookups': total_expected_lookups,
        'actual_lookups_made': actual_lookups_made,
        'unnecessary_calls_count': unnecessary_calls_count,
        'repeat_lookups_count': len(repeat_lookups),
        'efficiency_telemetry': repeat_lookups,
        'turn_evaluations': turn_results
    }


class ShowcaseSession:
    def __init__(self, websocket, client_ip, scenario_id, *, transport_factory=ADKTransport,
                 preflight=preflight_readonly, judge=evaluate_run, trace_writer=retain_trace):
        self.ws, self.client_ip = websocket, client_ip
        self.scenario = get_scenario(scenario_id)
        self.transport_factory, self.preflight, self.judge, self.trace_writer = transport_factory, preflight, judge, trace_writer
        self.run_id = 'showcase-'+secrets.token_hex(8)
        self.seq = 0
        self.pending_ack_turn = None
        self.ack = asyncio.Event()
        self.turns, self.tools = [], []
        self.completed = 0
        self.audio_bytes = 0
        self.is_running = False
        self.task = None

    async def send_event(self, kind, **data):
        self.seq += 1
        await self.ws.send_json(dict(type=kind, run_id=self.run_id, seq=self.seq, **data))

    def start(self):
        if not self.scenario:
            raise RuntimeError('Unknown example')
        reserve(self.client_ip)
        self.is_running = True
        self.task = asyncio.create_task(self.run())
        def release(task):
            global _active_showcase_runs
            _active_showcase_runs -= 1
            self.is_running = False
        self.task.add_done_callback(release)
        return self.task

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def acknowledge(self, run_id, turn_id):
        if run_id != self.run_id or type(turn_id) is not int or turn_id != self.pending_ack_turn or self.ack.is_set():
            return False
        self.ack.set()
        return True

    async def run(self):
        global _active_showcase_runs
        status = 'failed'
        findings = []
        display_token = conn_token = None
        async def ignore_card(payload):
            pass # Never stream raw tool cards; public evidence is validated after judging.
        try:
            register_display_callback(self.run_id, asyncio.get_running_loop(), ignore_card)
            display_token = bind_display_session(self.run_id)
            conn_token = set_connection_provider(_create_readonly_connection)
            await self.send_event('status', state='connecting')
            async with asyncio.timeout(min(self.scenario.get("conversation_timeout_seconds", _RUN_TIMEOUT_SECONDS), 360)):
                await asyncio.to_thread(self.preflight)
                async with self.transport_factory() as transport:
                    for idx, message in enumerate(self.scenario['student_messages'],1):
                        record_student_message(message, 'typed')
                        self.turns.append(dict(turn_id=idx, role='student', text=message))
                        await self.send_event('turn_start', turn_id=idx, text=message)
                        text, tx_buf, finished, turn_audio = '', '', False, 0
                        async for ev in transport.turn(message):
                            kind = ev['type']
                            if kind == 'audio':
                                data = ev['data']; self.audio_bytes += len(data); turn_audio += len(data)
                                if self.audio_bytes > 20_000_000:
                                    raise RuntimeError('Audio size limit exceeded')
                                await self.send_event('audio', turn_id=idx, data=base64.b64encode(data).decode())
                            elif kind == 'transcript':
                                chunk = re.sub(r'<ctrl\d+>', '', ev['text'])
                                if chunk and not chunk.strip().startswith('**'):
                                    is_partial = ev.get('partial', True)
                                    if not is_partial:
                                        text = chunk.strip()
                                        tx_buf = ''
                                    else:
                                        tx_buf += chunk
                                        text = tx_buf.strip()
                                    await self.send_event('transcript', turn_id=idx, text=text)
                            elif kind in ('tool_call','tool_result'):
                                call_id = ev.get('id')
                                call = next((c for c in self.tools if c['call_id']==call_id and c['turn_id']==idx and c['name']==ev['name']), None)
                                if call is None:
                                    call = dict(id=f'tool-{len(self.tools)+1}', call_id=call_id, turn_id=idx, name=ev['name'])
                                    self.tools.append(call)
                                call['args' if kind=='tool_call' else 'result'] = ev.get('args' if kind=='tool_call' else 'result')
                                payload = {'turn_id': idx, 'name': ev['name'], 'id': call['id']}
                                if call_id: payload['call_id'] = call_id
                                if kind == 'tool_call' and 'args' in ev: payload['args'] = ev['args']
                                if kind == 'tool_result':
                                    res = ev.get('result')
                                    if isinstance(res, dict) and 'courses' in res:
                                        courses = res['courses']
                                        payload['response'] = {
                                            'count': len(courses),
                                            'courses': [c.get('name') for c in courses if isinstance(c, dict) and c.get('name')]
                                        }
                                    elif isinstance(res, dict):
                                        payload['response'] = {k: v for k, v in res.items() if k not in ('entry_requirements',)}
                                    else:
                                        payload['response'] = {'status': 'completed'}
                                await self.send_event(kind, **payload)
                            elif kind == 'complete':
                                finished = True
                        if not finished or not turn_audio:
                            raise RuntimeError('Incomplete model response')
                        self.turns.append(dict(turn_id=idx, role='agent', text=text))
                        self.pending_ack_turn = idx; self.ack.clear()
                        await self.send_event('agent_turn_complete', turn_id=idx)
                        await asyncio.wait_for(self.ack.wait(), _PLAYBACK_TIMEOUT_SECONDS)
                        self.pending_ack_turn = None
                        self.completed += 1
            await self.send_event('status', state='checking')
            run = dict(scenario=self.scenario, turns=self.turns, tools=self.tools)
            findings = await self.judge(run, timeout_seconds=SHOWCASE_JUDGE_TIMEOUT_SECONDS)
            status = 'completed'
            scenario_dict = self.scenario or {}
            tool_eval = evaluate_tool_policy(self.tools, scenario_dict.get('expected_tool_policy', {}))
            await self.send_event('results', provenance=provenance(self.scenario), quality_findings=findings,
                tool_evaluation=tool_eval,
                technical_checks=dict(audio_received=self.audio_bytes>0,
                    expected_turns_completed=self.completed==len(self.scenario['student_messages']),
                    tool_invocations=sorted({c['name'] for c in self.tools}),
                    tool_evaluation=tool_eval,
                    run_status=status))
            await self.send_event('status', state='completed')
        except asyncio.CancelledError:
            status = 'stopped'
            raise
        except Exception:
            log.exception('Showcase failed: %s', self.run_id)
            try:
                await self.send_event('error', message='The live example could not complete. Please try again.', error='run_failed')
            except Exception:
                pass
        finally:
            self.pending_ack_turn = None
            self.is_running = False
            if conn_token is not None: reset_connection_provider(conn_token)
            if display_token is not None: reset_display_session(display_token)
            unregister_display_callback(self.run_id)
            try:
                self.trace_writer(dict(run_id=self.run_id, scenario=self.scenario,
                    provenance=provenance(self.scenario), status=status, completed_turns=self.completed,
                    turns=self.turns, tools=self.tools, findings=findings, audio_bytes=self.audio_bytes,
                    created_at=time.time()))
            except Exception:
                log.exception('Could not retain showcase trace')
