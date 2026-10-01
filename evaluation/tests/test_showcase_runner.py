"""Hermetic live-showcase tests; all model and DB transports are substituted."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
import showcase_runner as runner
import showcase_judge as judge
import tools as course_tools


class Socket:
    def __init__(self): self.events=[];self.session=None
    async def send_json(self, event):
        self.events.append(event)
        if event['type']=='agent_turn_complete':
            # An immediate ACK must not be lost.
            assert self.session.acknowledge(event['run_id'],event['turn_id'])
            assert not self.session.acknowledge(event['run_id'],event['turn_id'])


class Transport:
    instances=[]
    def __init__(self): self.messages=[];self.closed=False;self.__class__.instances.append(self)
    async def __aenter__(self):return self
    async def __aexit__(self,*args):self.closed=True
    async def turn(self,text):
        self.messages.append(text)
        assert len(course_tools._current_student_messages())==len(self.messages)
        yield {'type':'audio','data':b'\x00\x00'}
        yield {'type':'transcript','text':'Eligibility remains unknown.'}
        yield {'type':'tool_call','id':'call','name':'search_courses','args':{'query':'cloud'}}
        yield {'type':'tool_result','id':'call','name':'search_courses','result':{'courses':[{'entry_requirements':'Two years professional IT experience'}]}}
        yield {'type':'complete'}


class LiveRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner._active_showcase_runs=0;runner._ip_hourly_starts.clear();Transport.instances=[]
        self.network=patch('socket.socket.connect',side_effect=AssertionError('Network forbidden'))
        self.network.start();self.addCleanup(self.network.stop)

    def session(self,**options):
        socket=Socket();traces=[]
        async def evaluate(data,**kw):
            self.assertIn('result',data['tools'][0]);return judge.fallback('Test judge unavailable')
        session=runner.ShowcaseSession(socket,'test','returning-to-study-smoke',transport_factory=options.pop('transport_factory',Transport),
            preflight=options.pop('preflight',lambda:None),judge=options.pop('judge',evaluate),trace_writer=traces.append)
        socket.session=session
        return session,socket,traces

    async def test_complete_two_turns_one_transport_and_bound_evidence(self):
        session,socket,traces=self.session();await session.start()
        self.assertEqual(len(Transport.instances),1)
        self.assertEqual(len(Transport.instances[0].messages),2)
        self.assertTrue(Transport.instances[0].closed)
        result=next(e for e in socket.events if e['type']=='results')
        self.assertTrue(result['technical_checks']['expected_turns_completed'])
        self.assertEqual(traces[0]['status'],'completed')
        self.assertEqual(len(traces[0]['tools']),2)
        self.assertNotIn(session.run_id,course_tools._student_messages)
        self.assertEqual(runner._active_showcase_runs,0)
        serialized=json.dumps(socket.events)
        self.assertNotIn('Two years professional',serialized)

    async def test_public_story_completes_six_turns_and_retains_correction(self):
        session,socket,traces=self.session()
        session.scenario=runner.get_scenario('returning-to-study')
        await session.start()
        self.assertEqual(session.completed,6)
        self.assertEqual(len(Transport.instances),1)
        self.assertEqual(len(Transport.instances[0].messages),6)
        self.assertIn('one year of professional',Transport.instances[0].messages[3])
        self.assertEqual(traces[0]['provenance']['scenario_version'],'2.0.0')
        self.assertTrue(next(e for e in socket.events if e['type']=='results')['technical_checks']['expected_turns_completed'])

    async def test_stop_stalled_stream_releases_slot(self):
        started=asyncio.Event()
        class Stalled(Transport):
            async def turn(self,text):
                started.set();await asyncio.Event().wait()
                yield {}
        session,_,traces=self.session(transport_factory=Stalled)
        session.start();await started.wait();await session.stop()
        self.assertEqual(runner._active_showcase_runs,0)
        self.assertEqual(traces[0]['status'],'stopped')

    async def test_judge_cancelled_on_stop(self):
        started=asyncio.Event();cancelled=asyncio.Event()
        async def stalled(*args,**kw):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        session,_,_=self.session(judge=stalled);session.start();await started.wait();await session.stop()
        self.assertTrue(cancelled.is_set())

    async def test_readonly_failure_prevents_model_start_and_redacts_error(self):
        def fail():raise RuntimeError('secret-connection-string')
        session,socket,_=self.session(preflight=fail)
        with self.assertLogs(runner.log,level='ERROR'):await session.start()
        self.assertEqual(Transport.instances,[])
        self.assertNotIn('secret-connection-string',json.dumps(socket.events))

    async def test_ack_timeout_stops_without_judging(self):
        session,socket,traces=self.session()
        async def capture(event):socket.events.append(event)
        socket.send_json=capture
        with patch.object(runner,'_PLAYBACK_TIMEOUT_SECONDS',0.01),self.assertLogs(runner.log,level='ERROR'):
            await session.start()
        self.assertEqual(traces[0]['status'],'failed')
        self.assertFalse(any(e['type']=='results' for e in socket.events))

    async def test_admission_is_atomic_and_rate_applies_each_start(self):
        runner.reserve('one');runner.reserve('two')
        with self.assertRaises(RuntimeError):runner.reserve('three')
        runner._active_showcase_runs=0
        runner._ip_hourly_starts['repeat']=[__import__('time').monotonic()]*5
        with self.assertRaises(RuntimeError):runner.reserve('repeat')

    async def test_endpoint_rejects_extra_fields_and_duplicate_start(self):
        import ast
        from fastapi import WebSocketDisconnect
        tree=ast.parse((Path(__file__).resolve().parents[2]/'backend/main.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='showcase_live_endpoint')
        function.decorator_list=[]
        created=[]
        class Session:
            def __init__(self,*args):created.append(self);self.stopped=False
            def start(self):pass
            async def stop(self):self.stopped=True
        class EndpointSocket:
            client=SimpleNamespace(host='test')
            def __init__(self):
                self.messages=iter([{'action':'start','scenario_id':'returning-to-study','text':'injected'},
                    {'action':'start','scenario_id':'returning-to-study'},
                    {'action':'start','scenario_id':'returning-to-study'}]);self.output=[]
            async def accept(self):pass
            async def receive_text(self):
                try:return json.dumps(next(self.messages))
                except StopIteration:raise WebSocketDisconnect()
            async def send_json(self,event):self.output.append(event)
        namespace=dict(WebSocket=object,WebSocketDisconnect=WebSocketDisconnect,json=json,
                       ShowcaseSession=Session,_ip_active={})
        exec(compile(ast.Module(body=[function],type_ignores=[]),'endpoint','exec'),namespace)
        socket=EndpointSocket();await namespace['showcase_live_endpoint'](socket)
        self.assertEqual(len(created),1);self.assertTrue(created[0].stopped)
        self.assertEqual(len(socket.output),2)
        self.assertTrue(all(item['type']=='error' for item in socket.output))

    async def test_immediate_stop_releases_reserved_capacity(self):
        session,_,_=self.session();session.start();await session.stop()
        self.assertEqual(runner._active_showcase_runs,0)

    async def test_privileged_database_role_rejected(self):
        from unittest.mock import MagicMock
        connection=MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value=(True,False,False,False)
        with patch.dict('os.environ',{'SHOWCASE_READONLY_DATABASE_URL':'test-only'}),patch('psycopg2.connect',return_value=connection):
            with self.assertRaises(RuntimeError):
                with runner._create_readonly_connection():pass
        connection.close.assert_called_once()

    async def test_stale_ack_rejected(self):
        session,_,_=self.session();session.pending_ack_turn=2
        self.assertFalse(session.acknowledge('old',2));self.assertFalse(session.acknowledge(session.run_id,1))
        self.assertFalse(session.acknowledge(session.run_id,True))

    async def test_production_adk_adapter_keeps_single_iterator(self):
        from google.genai import types
        from google.adk.events import Event
        from google.adk.runners import Runner
        from google.adk.agents.live_request_queue import LiveRequestQueue
        events=[Event(author='Clara',output_transcription=types.Transcription(text='First.'),turn_complete=True),
                Event(author='Clara',output_transcription=types.Transcription(text='Recap.'),turn_complete=True)]
        async def fake_live(*args,**kwargs):
            for event in events:yield event
        with patch.object(Runner,'run_live',fake_live),patch.object(LiveRequestQueue,'send_content') as send:
            async with runner.ADKTransport() as transport:
                first=[e async for e in transport.turn('one')]
                second=[e async for e in transport.turn('two')]
                self.assertEqual(send.call_count,2)
                self.assertEqual(first[0]['text'],'First.')
                self.assertEqual(second[0]['text'],'Recap.')

    async def test_transcript_partial_aggregation_no_duplication(self):
        class StreamingTransport(Transport):
            async def turn(self, text):
                yield {'type': 'audio', 'data': b'\x00\x00'}
                # Two partial chunks
                yield {'type': 'transcript', 'text': 'You might want to look into ', 'partial': True}
                yield {'type': 'transcript', 'text': 'the Cloud Computing course.', 'partial': True}
                # Final consolidated chunk
                yield {'type': 'transcript', 'text': 'You might want to look into the Cloud Computing course.', 'partial': False}
                yield {'type': 'tool_call', 'id': 'call', 'name': 'search_courses', 'args': {'query': 'cloud'}}
                yield {'type': 'tool_result', 'id': 'call', 'name': 'search_courses', 'result': {'courses': []}}
                yield {'type': 'complete'}
        session, socket, traces = self.session(transport_factory=StreamingTransport)
        await session.start()
        agent_turns = [t for t in traces[0]['turns'] if t['role'] == 'agent']
        self.assertEqual(len(agent_turns), 2)
        # Verify text was NOT doubled
        self.assertEqual(agent_turns[0]['text'], 'You might want to look into the Cloud Computing course.')

    async def test_connection_provider_reaches_real_tool_boundary(self):
        from contextlib import contextmanager
        marker=object()
        @contextmanager
        def provider():yield marker
        token=course_tools.set_connection_provider(provider)
        try:
            with patch.object(course_tools,'_get_pg_pool',side_effect=AssertionError('Writer fallback')):
                with course_tools._get_conn() as conn:self.assertIs(conn,marker)
        finally:course_tools.reset_connection_provider(token)


def validate_findings_with_quality(raw, catalog):
    """Complete legacy fixtures with the new conversation-quality criterion."""
    completed = list(raw)
    if not any(item.get('criterion_id') == 'conversation_quality' for item in completed if isinstance(item, dict)):
        transcript = next((entry for entry in catalog if entry.get('kind') == 'transcript'), None)
        if transcript:
            completed.append({
                'criterion_id': 'conversation_quality',
                'status': 'supported',
                'summary': 'Response quality checked.',
                'evidence': [{'id': transcript['id'], 'quote': transcript['text']}]
            })
    return judge.validate_findings(completed, catalog)


class JudgeTests(unittest.IsolatedAsyncioTestCase):
    def data(self):return dict(scenario={},turns=[dict(turn_id=1,role='agent',text='Eligibility is unknown.')],tools=[dict(id='tool-1',name='search_courses',turn_id=1,result={'entry_requirements':'Two years','private_secret':'hidden'})])
    def findings(self):
        return [
            dict(
                criterion_id=c,
                status='supported',
                summary='Checked',
                evidence=[{'id':'turn-1','quote':'Eligibility is unknown.'}]+([{'id':'tool-1:result.entry_requirements','quote':'Two years'}] if c=='grounded_advice' else []),
                **({'claims': [{'claim': 'Eligibility is unknown.', 'turn_id': 1, 'status': 'supported', 'material': True}],
                    'claim_coverage': {'complete': True, 'omitted_claims': []}} if c == 'grounded_advice' else {})
            )
            for c in judge.CRITERIA_IDS
        ]
    async def test_conversation_quality_accepts_instruction_leak_finding(self):
        run = dict(
            scenario={},
            turns=[dict(
                turn_id=5,
                role='agent',
                text='Wait, the instruction says I need to call get_discovery_context first.'
            )],
            tools=[]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id=criterion_id,
                status='supported',
                summary='Checked.',
                evidence=[{
                    'id': 'turn-5',
                    'quote': 'Wait, the instruction says I need to call get_discovery_context first.'
                }]
            )
            for criterion_id in ('preserved_facts', 'grounded_advice', 'honest_uncertainty')
        ]
        findings.append(dict(
            criterion_id='conversation_quality',
            status='issue_observed',
            summary='Clara exposed internal instructions and tool-selection reasoning.',
            evidence=[{
                'id': 'turn-5',
                'quote': 'Wait, the instruction says I need to call get_discovery_context first.'
            }]
        ))
        validated = judge.validate_findings(findings, catalog)
        quality = next(f for f in validated if f['criterion_id'] == 'conversation_quality')
        self.assertEqual(quality['status'], 'issue_observed')
        self.assertIn('internal instructions', quality['summary'])

    async def test_valid_evidence_and_private_field_exclusion(self):
        catalog=judge.evidence_catalog(self.data());self.assertNotIn('hidden',json.dumps(catalog))
        self.assertTrue(all(f['status']=='supported' for f in validate_findings_with_quality(self.findings(),catalog)))
    async def test_fabricated_quote_downgrades_status(self):
        raw=self.findings();raw[0]['evidence'][0]['quote']='invented'
        self.assertEqual(validate_findings_with_quality(raw,judge.evidence_catalog(self.data()))[0]['status'],'unable_to_assess')
    async def test_mock_uses_same_validator_and_timeout(self):
        async def bad(data):return [{'status':'supported'}]
        result=await judge.evaluate_run(self.data(),mock_judge_fn=bad)
        self.assertTrue(all(f['status']=='unable_to_assess' for f in result))
        async def stalled(data):await asyncio.Event().wait()
        result=await judge.evaluate_run(self.data(),timeout_seconds=.01,mock_judge_fn=stalled)
        self.assertTrue(all(f['status']=='unable_to_assess' for f in result))
    async def test_unconfigured_judge_no_request(self):
        with patch.object(judge,'SHOWCASE_JUDGE_MODEL',''),patch('socket.socket.connect',side_effect=AssertionError('Network')):
            result=await judge.evaluate_run(self.data())
        self.assertTrue(all(f['status']=='unable_to_assess' for f in result))

    async def test_null_valued_evidence_catalog(self):
        run = dict(scenario={}, turns=[], tools=[dict(id='tool-1', name='search_courses', turn_id=1,
                   result=dict(courses=[dict(name='Data Analytics', entry_requirements=None)]))])
        catalog = judge.evidence_catalog(run)
        item = next(e for e in catalog if e['id'] == 'tool-1:result.courses[0].entry_requirements')
        self.assertEqual(item['text'], 'null')

    async def test_find_unambiguous_span(self):
        source = "You've told me that you do not have a bachelor's degree, and that you worked in IT support."
        # Case variation at start of sentence
        span = judge.find_unambiguous_span("That you do not have a bachelor's degree", source)
        self.assertEqual(span, "that you do not have a bachelor's degree")
        # Collapsed whitespace
        span_ws = judge.find_unambiguous_span("worked   in \n IT support", source)
        self.assertEqual(span_ws, "worked in IT support")
        # Ambiguous word
        self.assertIsNone(judge.find_unambiguous_span("that", source))
        # Non-matching quote
        self.assertIsNone(judge.find_unambiguous_span("nonexistent quote", source))

    async def test_temporal_grounding_rejects_forward_reference_from_later_tool_call(self):
        # Claim spoken at Turn 1, but tool lookup only retrieved at Turn 4
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.')
            ],
            tools=[
                dict(id='tool-4', name='search_courses', turn_id=4, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        # Mock judge finding attempting to justify Turn 1 claim with Turn 4 lookup
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Agent asserted 2-year entry requirement grounded in tool evidence.',
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-4:result.entry_requirements', 'quote': 'Two years'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-1', 'quote': 'industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-1', 'quote': 'industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded_finding = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Must be rejected because tool-4 (turn 4) > claim turn-1 (forward reference)
        self.assertEqual(grounded_finding['status'], 'unable_to_assess')
        self.assertIn('forward reference', grounded_finding['summary'])
        self.assertEqual(grounded_finding['evidence'], [])

    async def test_temporal_grounding_rejects_forward_reference_with_unrelated_later_transcript_bypass(self):
        # Regression: Turn 1 claim + Turn 4 tool cannot be bypassed by adding unrelated Turn 6 transcript
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=6, role='agent', text='Here is the recap of the options.')
            ],
            tools=[
                dict(id='tool-4', name='search_courses', turn_id=4, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        # 1. Without explicit supports (ambiguous across multiple claims)
        findings_ambiguous = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Agent asserted 2-year entry requirement.',
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'turn-6', 'quote': 'Here is the recap of the options.'},
                    {'id': 'tool-4:result.entry_requirements', 'quote': 'Two years'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'Here is the recap of the options.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'Here is the recap of the options.'}])
        ]
        val_ambiguous = validate_findings_with_quality(findings_ambiguous, catalog)
        grounded = next(f for f in val_ambiguous if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded['status'], 'unable_to_assess')

        # 2. With explicit supports='turn-1' (tool-4 turn 4 > claim turn 1)
        findings_bound = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Agent asserted 2-year entry requirement.',
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'turn-6', 'quote': 'Here is the recap of the options.'},
                    {'id': 'tool-4:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'Here is the recap of the options.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'Here is the recap of the options.'}])
        ]
        val_bound = validate_findings_with_quality(findings_bound, catalog)
        grounded_bound = next(f for f in val_bound if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded_bound['status'], 'unable_to_assess')

    async def test_temporal_grounding_rejects_forward_reference_with_unrelated_earlier_tool_bypass(self):
        # Regression: Turn 1 claim + Turn 4 tool cannot be bypassed by adding unrelated Turn 1 tool result
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.')
            ],
            tools=[
                dict(id='tool-1', name='search_courses', turn_id=1, result={'name': 'Cloud Computing'}),
                dict(id='tool-4', name='search_courses', turn_id=4, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Agent asserted 2-year entry requirement.',
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.name', 'quote': 'Cloud Computing'},
                    {'id': 'tool-4:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-1', 'quote': 'industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-1', 'quote': 'industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # tool-4 turn 4 > claim turn 1 -> forward reference rejected despite tool-1 turn 1 present
        self.assertEqual(grounded['status'], 'unable_to_assess')

    async def test_temporal_grounding_accepts_prior_and_same_turn_evidence(self):
        # Tool lookup at Turn 1 grounds Turn 1 claim AND Turn 6 recap claim
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=6, role='agent', text='To recap, the course requires two years.')
            ],
            tools=[
                dict(id='tool-1', name='search_courses', turn_id=1, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Turn 6 recap is supported by Turn 1 lookup.',
                claims=[
                    {'claim': 'Entry requires two years of industry experience.', 'turn_id': 1, 'status': 'supported', 'material': True},
                    {'claim': 'To recap, the course requires two years.', 'turn_id': 6, 'status': 'supported', 'material': True}
                ],
                claim_coverage={'complete': True, 'omitted_claims': []},
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'},
                    {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-6'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded_finding = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Accepted: tool-1 (turn 1) <= claim turn-6 (turn 6)
        self.assertEqual(grounded_finding['status'], 'supported')
        self.assertEqual(len(grounded_finding['evidence']), 4)

    async def test_temporal_grounding_accepts_multi_claim_multi_evidence_pairs(self):
        # Multi-claim positive test: Turn 1 claim supported by Turn 1 tool + Turn 6 claim supported by Turn 4 tool
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=6, role='agent', text='To recap, the course requires two years.')
            ],
            tools=[
                dict(id='tool-1', name='search_courses', turn_id=1, result={'entry_requirements': 'Two years'}),
                dict(id='tool-4', name='search_courses', turn_id=4, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Both Turn 1 and Turn 6 claims are properly temporally grounded.',
                claims=[
                    {'claim': 'Entry requires two years of industry experience.', 'turn_id': 1, 'status': 'supported', 'material': True},
                    {'claim': 'To recap, the course requires two years.', 'turn_id': 6, 'status': 'supported', 'material': True}
                ],
                claim_coverage={'complete': True, 'omitted_claims': []},
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'},
                    {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'},
                    {'id': 'tool-4:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-6'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                           {'id': 'turn-6', 'quote': 'To recap, the course requires two years.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded_finding = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded_finding['status'], 'supported')
        self.assertEqual(len(grounded_finding['evidence']), 4)

    async def test_calibration_fixture_full_time_program_marked_unsupported(self):
        # Requirement 2: Calibration fixture where agent claims "it describes it as a full-time program"
        # but the source describes "suitable for full-time professionals", not course workload.
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=3, role='agent', text='While the catalogue lists the Graduate Certificate in Cloud Computing as Online, it describes it as a full-time program. It doesn\'t mention part-time availability, so that would still be unconfirmed.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={
                    'name': 'Graduate Certificate in Cloud Computing',
                    'study_mode': 'Online',
                    'description': 'A six-month online program designed for working IT professionals... Delivery is 100% asynchronous, making it suitable for full-time professionals.'
                })
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',  # Judge attempted unqualified supported
                summary='The guidance was grounded directly in the university course catalog.',
                claims=[
                    dict(
                        claim='it describes it as a full-time program',
                        turn_id=3,
                        status='supported',  # Raw claim proposed as supported
                        material=True,
                        evidence=[
                            {'id': 'turn-3', 'quote': 'it describes it as a full-time program'},
                            {'id': 'tool-1:result.description', 'quote': 'suitable for full-time professionals', 'supports': 'turn-3'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-3', 'quote': 'it describes it as a full-time program'},
                    {'id': 'tool-1:result.description', 'quote': 'suitable for full-time professionals', 'supports': 'turn-3'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-3', 'quote': 'Online, it describes it as a full-time program'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-3', 'quote': 'It doesn\'t mention part-time availability, so that would still be unconfirmed.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Evaluator must mark the claim unsupported because source describes professionals, not workload
        self.assertEqual(grounded['claims'][0]['status'], 'unsupported')
        self.assertIn('describes full-time professionals, not course workload', grounded['claims'][0]['reason'])
        # Material unsupported claim must prevent an unqualified "supported" verdict
        self.assertEqual(grounded['status'], 'issue_observed')
        self.assertIn('unsupported claim was identified', grounded['summary'])

    async def test_positive_control_catalogue_explicitly_confirms_full_time_study(self):
        # Requirement 3: Positive control where catalogue explicitly confirms full-time study
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=3, role='agent', text='The catalogue confirms the Bachelor of Computer Science is a full-time program.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={
                    'name': 'Bachelor of Computer Science',
                    'study_mode': 'Full-time',
                    'description': 'An intensive full-time degree program on campus.'
                })
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='The guidance was grounded directly in the university course catalog.',
                claim_coverage={'complete': True, 'omitted_claims': []},
                claims=[
                    dict(
                        claim='confirms the Bachelor of Computer Science is a full-time program',
                        turn_id=3,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-3', 'quote': 'confirms the Bachelor of Computer Science is a full-time program'},
                            {'id': 'tool-1:result.study_mode', 'quote': 'Full-time', 'supports': 'turn-3'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-3', 'quote': 'confirms the Bachelor of Computer Science is a full-time program'},
                    {'id': 'tool-1:result.study_mode', 'quote': 'Full-time', 'supports': 'turn-3'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-3', 'quote': 'Bachelor of Computer Science is a full-time program'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-3', 'quote': 'Bachelor of Computer Science is a full-time program'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded['claims'][0]['status'], 'supported')
        self.assertEqual(grounded['status'], 'supported')

    async def test_positive_control_correctly_leaves_workload_unknown(self):
        # Requirement 3: Positive control where Clara correctly leaves workload unknown
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=3, role='agent', text='While listed as Online, the catalogue does not confirm part-time study; workload availability remains unconfirmed.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={
                    'name': 'Graduate Certificate in Cloud Computing',
                    'study_mode': 'Online',
                    'description': 'A six-month online program designed for working IT professionals... suitable for full-time professionals.'
                })
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Workload availability was correctly left unconfirmed.',
                claim_coverage={'complete': True, 'omitted_claims': []},
                claims=[
                    dict(
                        claim='workload availability remains unconfirmed',
                        turn_id=3,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-3', 'quote': 'workload availability remains unconfirmed'},
                            {'id': 'tool-1:result.study_mode', 'quote': 'Online', 'supports': 'turn-3'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-3', 'quote': 'workload availability remains unconfirmed'},
                    {'id': 'tool-1:result.study_mode', 'quote': 'Online', 'supports': 'turn-3'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-3', 'quote': 'workload availability remains unconfirmed'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-3', 'quote': 'workload availability remains unconfirmed'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded['claims'][0]['status'], 'supported')
        self.assertEqual(grounded['status'], 'supported')

    async def test_substantive_claims_individually_assessed_derive_overall_finding(self):
        # Requirement 4: Individual claims assessed; a material unsupported claim prevents "supported"
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=3, role='agent', text='it describes it as a full-time program.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={
                    'entry_requirements': 'Two years',
                    'description': 'suitable for full-time professionals.'
                })
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',  # Raw claim proposed supported
                summary='All advice was checked against the catalog.',
                claims=[
                    dict(
                        claim='Entry requires two years of industry experience.',
                        turn_id=1,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                            {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                        ]
                    ),
                    dict(
                        claim='it describes it as a full-time program.',
                        turn_id=3,
                        status='unsupported',
                        material=True,
                        reason='The source describes full-time professionals, not course workload.',
                        evidence=[
                            {'id': 'turn-3', 'quote': 'it describes it as a full-time program.'},
                            {'id': 'tool-1:result.description', 'quote': 'suitable for full-time professionals.', 'supports': 'turn-3'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'},
                    {'id': 'turn-3', 'quote': 'it describes it as a full-time program.'},
                    {'id': 'tool-1:result.description', 'quote': 'suitable for full-time professionals.', 'supports': 'turn-3'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Overall status derived as issue_observed because claim 2 is unsupported
        self.assertEqual(grounded['status'], 'issue_observed')
        self.assertEqual(len(grounded['claims']), 2)
        self.assertEqual(grounded['claims'][0]['status'], 'supported')
        self.assertEqual(grounded['claims'][1]['status'], 'unsupported')

    async def test_incomplete_claim_coverage_reported_explicitly(self):
        # Requirement 5: Incomplete claim coverage reported explicitly rather than treating omitted claims as checked
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.')
            ],
            tools=[
                dict(id='tool-1', name='search_courses', turn_id=1, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='Entry requirements verified.',
                claims=[
                    dict(
                        claim='Entry requires two years of industry experience.',
                        turn_id=1,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                            {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                        ]
                    )
                ],
                claim_coverage=dict(
                    complete=False,
                    evaluated_claims_count=1,
                    omitted_claims=['it describes it as a full-time program']
                ),
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Incomplete coverage must prevent an unqualified supported verdict -> unable_to_assess
        self.assertEqual(grounded['status'], 'unable_to_assess')
        self.assertIn('Evaluation incomplete', grounded['summary'])
        self.assertIn('it describes it as a full-time program', grounded['summary'])
        self.assertFalse(grounded['claim_coverage']['complete'])

    async def test_probe_omitted_claim_from_transcript_prevents_supported_verdict(self):
        # Probe 1: An omitted claim from transcript must prevent an unqualified supported verdict
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=3, role='agent', text='While the catalogue lists the Graduate Certificate in Cloud Computing as Online, it describes it as a full-time program.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        # Judge raw output only evaluates Turn 1 claim, completely omitting Turn 3 substantive claim
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',  # Judge attempted unqualified supported
                summary='All reviewed advice was verified.',
                claims=[
                    dict(
                        claim='Entry requires two years of industry experience.',
                        turn_id=1,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                            {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # An omitted claim must prevent an unqualified supported verdict -> unable_to_assess
        self.assertEqual(grounded['status'], 'unable_to_assess')
        self.assertIn('Evaluation incomplete', grounded['summary'])
        self.assertIn('turn-3', grounded['summary'])

    async def test_probe_explicitly_unassessed_material_claim_prevents_supported_verdict(self):
        # Probe 2: An explicitly unassessed material claim must prevent an unqualified supported verdict
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='Entry requires two years of industry experience.'),
                dict(turn_id=3, role='agent', text='it describes it as a full-time program.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={'entry_requirements': 'Two years'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',  # Judge attempted unqualified supported
                summary='Entry requirements were verified.',
                claims=[
                    dict(
                        claim='Entry requires two years of industry experience.',
                        turn_id=1,
                        status='supported',
                        material=True,
                        evidence=[
                            {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                            {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                        ]
                    ),
                    dict(
                        claim='it describes it as a full-time program.',
                        turn_id=3,
                        status='unassessed',  # Explicitly unassessed material claim
                        material=True
                    )
                ],
                evidence=[
                    {'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'},
                    {'id': 'tool-1:result.entry_requirements', 'quote': 'Two years', 'supports': 'turn-1'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'Entry requires two years of industry experience.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        # Explicitly unassessed material claim must prevent an unqualified supported verdict -> unable_to_assess
        self.assertEqual(grounded['status'], 'unable_to_assess')
        self.assertIn('material claim remains unassessed', grounded['summary'].lower())
        self.assertIn('it describes it as a full-time program', grounded['summary'])

    async def test_omission_regression_unqualified_support_requires_claims_and_coverage(self):
        # Codex Finding 1 regression:
        # A transcript saying "The course is online. It is a full-time program." with Online and audience-only
        # catalogue evidence receives unable_to_assess when the finding cites only the online claim and omits claims/coverage.
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=1, role='agent', text='The course is online. It is a full-time program.')
            ],
            tools=[
                dict(id='tool-1', name='get_course_detail', turn_id=1, result={
                    'study_mode': 'Online',
                    'description': 'suitable for full-time professionals.'
                })
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',
                summary='The course was confirmed to be online.',
                evidence=[
                    {'id': 'turn-1', 'quote': 'The course is online.'},
                    {'id': 'tool-1:result.study_mode', 'quote': 'Online'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-1', 'quote': 'The course is online.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-1', 'quote': 'The course is online.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded['status'], 'unable_to_assess')
        self.assertIn('Evaluation incomplete', grounded['summary'])

    async def test_probe_unrelated_unsupported_claim_gets_specific_reason_not_workload_explanation(self):
        # Probe 3: An unrelated unsupported claim gets its specific reason, not the full-time/workload explanation
        run = dict(
            scenario={},
            turns=[
                dict(turn_id=5, role='agent', text='Postgraduate applications opened on August 1st this year.')
            ],
            tools=[
                dict(id='tool-1', name='search_knowledge', turn_id=5, result={'text': 'Applications are open year-round.'})
            ]
        )
        catalog = judge.evidence_catalog(run)
        findings = [
            dict(
                criterion_id='grounded_advice',
                status='supported',  # Judge attempted unqualified supported
                summary='Application details discussed.',
                claims=[
                    dict(
                        claim='Postgraduate applications opened on August 1st this year.',
                        turn_id=5,
                        status='unsupported',
                        material=True,
                        reason='Catalog and knowledge base do not state an August 1st opening date.',
                        evidence=[
                            {'id': 'turn-5', 'quote': 'Postgraduate applications opened on August 1st this year.'}
                        ]
                    )
                ],
                evidence=[
                    {'id': 'turn-5', 'quote': 'Postgraduate applications opened on August 1st this year.'}
                ]
            ),
            dict(criterion_id='preserved_facts', status='supported', summary='Facts preserved.',
                 evidence=[{'id': 'turn-5', 'quote': 'Postgraduate applications opened on August 1st this year.'}]),
            dict(criterion_id='honest_uncertainty', status='supported', summary='Uncertainty handled.',
                 evidence=[{'id': 'turn-5', 'quote': 'Postgraduate applications opened on August 1st this year.'}])
        ]
        validated = validate_findings_with_quality(findings, catalog)
        grounded = next(f for f in validated if f['criterion_id'] == 'grounded_advice')
        self.assertEqual(grounded['status'], 'issue_observed')
        # Must include the specific unsupported claim and reason
        self.assertIn('Postgraduate applications opened on August 1st this year', grounded['summary'])
        self.assertIn('do not state an August 1st opening date', grounded['summary'])
        # Must NOT mention the full-time/workload explanation
        self.assertNotIn('full-time professionals', grounded['summary'])
        self.assertNotIn('course workload', grounded['summary'])


class ToolPolicyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = runner.get_scenario('returning-to-study')['expected_tool_policy']

    def test_compliant_run_with_search_courses_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'application steps'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['actual_lookups_made'], 2)
        self.assertEqual(res['unnecessary_calls_count'], 0)

    def test_compliant_run_with_get_course_detail_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate'}},
            {'id': 'tool-2', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'postgrad admission'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)

    def test_spurious_tool_call_on_conversational_turn_fails(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 2, 'name': 'search_scholarships', 'args': {'query': 'online'}}, # Irrelevant tool!
            {'id': 'tool-3', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'application steps'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertFalse(res['passed'])
        self.assertEqual(res['turns_compliant'], 5)
        self.assertEqual(res['unnecessary_calls_count'], 1)
        self.assertFalse(res['turn_evaluations'][1]['passed'])

    def test_compliant_run_with_discovery_context_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 4, 'name': 'get_discovery_context', 'args': {}},
            {'id': 'tool-3', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'postgrad admission'}},
            {'id': 'tool-4', 'turn_id': 6, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['unnecessary_calls_count'], 0)

    def test_compliant_run_with_course_detail_reverifications_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate in Cloud Computing'}},
            {'id': 'tool-2', 'turn_id': 2, 'name': 'get_discovery_context', 'args': {}},
            {'id': 'tool-3', 'turn_id': 3, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate in Cloud Computing'}},
            {'id': 'tool-4', 'turn_id': 4, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate in Cloud Computing'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'how to apply for postgraduate courses'}},
            {'id': 'tool-6', 'turn_id': 6, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['unnecessary_calls_count'], 0)

    def test_turn_2_search_courses_with_online_constraint_passes_and_records_efficiency(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 2, 'name': 'search_courses', 'args': {'query': 'cloud', 'study_mode_preference': 'Online'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'postgraduate application steps'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['unnecessary_calls_count'], 0)
        self.assertTrue(res['turn_evaluations'][1]['passed'])
        self.assertEqual(res['repeat_lookups_count'], 1)
        self.assertEqual(res['efficiency_telemetry'][0]['turn_id'], 2)
        self.assertIn("acceptable alternative", res['efficiency_telemetry'][0]['note'])

    def test_turn_2_zero_tools_reuses_prior_search_and_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'postgraduate application steps'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['unnecessary_calls_count'], 0)
        self.assertTrue(res['turn_evaluations'][1]['passed'])

    def test_legitimate_knowledge_search_and_course_search_passes(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate in Cloud Computing'}},
            {'id': 'tool-3', 'turn_id': 3, 'name': 'search_knowledge', 'args': {'query': 'is Graduate Certificate in Cloud Computing available part time'}},
            {'id': 'tool-4', 'turn_id': 4, 'name': 'search_courses', 'args': {'query': 'Cloud Computing graduate certificate entry requirements'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'how to apply for postgraduate courses'}},
            {'id': 'tool-6', 'turn_id': 6, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['turns_compliant'], 6)
        self.assertEqual(res['unnecessary_calls_count'], 0)
        self.assertTrue(res['turn_evaluations'][2]['passed'])
        self.assertTrue(res['turn_evaluations'][3]['passed'])
        self.assertEqual(res['turn_evaluations'][2]['outcome'], 'Observed tool call: search_knowledge')
        self.assertEqual(res['turn_evaluations'][2]['semantic_status'], 'not_assessed')
        self.assertIn("search_knowledge", res['turn_evaluations'][2]['technical_detail'])
        self.assertEqual(res['turn_evaluations'][3]['outcome'], 'Observed tool call: search_courses')
        self.assertEqual(res['turn_evaluations'][3]['semantic_status'], 'not_assessed')
        self.assertIn("search_courses", res['turn_evaluations'][3]['technical_detail'])

    def test_genuinely_disallowed_tool_calls_fail(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'get_course_detail', 'args': {'course_name': 'Graduate Certificate in Cloud Computing'}},
            {'id': 'tool-3', 'turn_id': 3, 'name': 'search_scholarships', 'args': {'query': 'part-time scholarship'}},
            {'id': 'tool-4', 'turn_id': 4, 'name': 'book_campus_tour', 'args': {'tour_id': '123'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'how to apply for postgraduate courses'}},
            {'id': 'tool-6', 'turn_id': 6, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertFalse(res['passed'])
        self.assertEqual(res['turns_compliant'], 4)
        self.assertEqual(res['unnecessary_calls_count'], 2)
        self.assertFalse(res['turn_evaluations'][2]['passed'])
        self.assertFalse(res['turn_evaluations'][3]['passed'])
        self.assertIn("search_scholarships", res['turn_evaluations'][2]['technical_detail'])
        self.assertIn("book_campus_tour", res['turn_evaluations'][3]['technical_detail'])

    def test_turn_5_redundant_discovery_lookup_is_warning_not_failure(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'application steps'}},
            {'id': 'tool-3', 'turn_id': 5, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        turn_five = res['turn_evaluations'][4]
        self.assertTrue(res['passed'])
        self.assertTrue(turn_five['passed'])
        self.assertEqual(turn_five['protocol_status'], 'redundant_lookup_warning')
        self.assertEqual(res['unnecessary_calls_count'], 1)
        self.assertIn('unnecessary read-only context', turn_five['efficiency_notes'][0])

    def test_max_calls_is_enforced(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-2', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'application steps'}},
            {'id': 'tool-3', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'postgraduate dates'}},
            {'id': 'tool-4', 'turn_id': 5, 'name': 'get_discovery_context', 'args': {}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        turn_five = res['turn_evaluations'][4]
        self.assertFalse(res['passed'])
        self.assertFalse(turn_five['passed'])
        self.assertEqual(turn_five['protocol_status'], 'max_calls_exceeded')

    def test_missing_required_tool_fails(self):
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}}
            # Missing Turn 5 knowledge lookup!
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertFalse(res['passed'])
        self.assertFalse(res['turn_evaluations'][4]['passed'])

    def test_tool_policy_semantic_status_always_not_assessed_and_no_percentage_appropriateness(self):
        # Even with no tools supplied on Turn 4, semantic status must be not_assessed
        res = runner.evaluate_tool_policy([], {4: self.policy[4]})
        self.assertTrue(res['passed'])
        self.assertEqual(res['semantic_status'], 'not_assessed')
        self.assertEqual(res['turn_evaluations'][0]['semantic_status'], 'not_assessed')
        self.assertEqual(res['turn_evaluations'][0]['observed_activity'], 'No tools invoked (conversational response)')
        # Summary must state tool telemetry compliance and NOT claim conversational appropriateness percentage
        self.assertNotIn("100% Appropriate", res['summary'])
        self.assertIn("Semantic quality not assessed by tool telemetry", res['summary'])
        # Must not assert semantic conclusions
        self.assertNotIn("updated eligibility", res['turn_evaluations'][0]['outcome'].lower())

    def test_tool_policy_with_no_transcripts_does_not_claim_conversational_correctness(self):
        # A fully compliant tool run with no answers supplied still reports semantic_status="not_assessed"
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'admissions'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        self.assertTrue(res['passed'])
        self.assertEqual(res['semantic_status'], 'not_assessed')
        for t in res['turn_evaluations']:
            self.assertEqual(t['semantic_status'], 'not_assessed')

    def test_tool_argument_diagnostics_detects_omitted_constraints_and_inferred_scope(self):
        # Turn 4 tool call omitting active online constraint and inferring postgraduate scope
        tools = [
            {'id': 'tool-1', 'turn_id': 1, 'name': 'search_courses', 'args': {'query': 'cloud'}},
            {'id': 'tool-4', 'turn_id': 4, 'name': 'search_courses', 'args': {'query': 'cloud', 'target_level': 'Postgraduate'}},
            {'id': 'tool-5', 'turn_id': 5, 'name': 'search_knowledge', 'args': {'query': 'admissions'}}
        ]
        res = runner.evaluate_tool_policy(tools, self.policy)
        turn_4_eval = res['turn_evaluations'][3]
        self.assertTrue(turn_4_eval['passed'])
        self.assertEqual(turn_4_eval['semantic_status'], 'not_assessed')
        # Diagnostic flags omitted constraint and inferred scope
        self.assertIn("search_courses: omitted study_mode_preference", turn_4_eval['argument_diagnostics'])
        self.assertIn("search_courses: target_level='Postgraduate' (inferred scope)", turn_4_eval['argument_diagnostics'])
        self.assertIn("Diagnostics:", turn_4_eval['technical_detail'])


