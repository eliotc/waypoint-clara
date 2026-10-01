import asyncio
from contextlib import asynccontextmanager
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from evaluation.contracts import ROOT
from evaluation.live_adapter import ClaraLiveAdapter, LiveProtocolError, endpoint_parts
from evaluation.local_database import local_dsn, connect_verified
from evaluation.runner import load_experiment, run_experiment

TARGET = {'adapter':'clara_live','model':'gemini-3.1-flash-live-preview',
          'endpoint':'http://127.0.0.1:8765','require_embeddings':False,'turn_timeout_seconds':5}


class Socket:
    def __init__(self, events):
        self.events = list(events)
        self.sent = []
    async def recv(self):
        if not self.events:
            raise ConnectionError('test socket closed')
        value = self.events.pop(0)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, bytes) else json.dumps(value)
    async def send(self, value):
        self.sent.append(json.loads(value))


def transcript(text, finished=True):
    return {'type':'transcript','role':'agent','text':text,'finished':finished}


class LiveProtocolTests(unittest.IsolatedAsyncioTestCase):
    def adapter_trace(self):
        return ClaraLiveAdapter(TARGET, 'clara-local-seed-v1'), {'observations':{'events':[], 'audio_files':[]}}

    async def test_tool_turn_boundary_waits_for_post_tool_answer(self):
        adapter, trace = self.adapter_trace()
        ws = Socket([{'type':'tool_call','id':'a','name':'search_events','args':{'event_type':'CampusTour'}},
                     {'type':'turn_complete'},
                     {'type':'card','card_type':'events','data':{'count':0}},
                     {'type':'tool_result','id':'a','name':'search_events','response':{'count':0}},
                     b'\x00\x01', transcript('No tours found.'), {'type':'turn_complete'}])
        with tempfile.TemporaryDirectory() as tmp:
            adapter.artifacts = Path(tmp)
            result = await adapter.read_turn(ws, 'Any tours?', trace, '1')
            self.assertEqual(result['tools'][0]['result'], {'count':0})
            self.assertEqual(result['assistant'], 'No tours found.')
            self.assertEqual(len(result['cards']), 1)
            audio = trace['observations']['audio_files'][0]
            self.assertEqual((Path(tmp)/audio['path']).read_bytes(), b'\x00\x01')

    async def test_cumulative_transcripts_are_not_duplicated(self):
        adapter, trace = self.adapter_trace()
        ws = Socket([transcript('Hello', False), transcript('Hello there', False),
                     transcript('Hello there.', True), {'type':'turn_complete'}])
        result = await adapter.read_turn(ws, 'Hi', trace, '1')
        self.assertEqual(result['assistant'], 'Hello there.')

    async def test_wrong_tool_result_is_error(self):
        adapter, trace = self.adapter_trace()
        ws = Socket([{'type':'tool_call','id':'a','name':'search_events','args':{}},
                     {'type':'tool_result','id':'b','name':'search_events','response':{}}])
        with self.assertRaises(LiveProtocolError):
            await adapter.read_turn(ws, 'Hello', trace, '1')
        self.assertEqual(trace['observations']['last_turn']['tools'][0]['name'], 'search_events')

    async def test_disconnect_preserves_partial_text(self):
        adapter, trace = self.adapter_trace()
        with self.assertRaises(ConnectionError):
            await adapter.read_turn(Socket([transcript('Partial', False)]), 'Hi', trace, '1')
        self.assertEqual(trace['observations']['last_turn']['assistant'], 'Partial')

    async def test_silent_completion_is_not_a_pass(self):
        adapter, trace = self.adapter_trace()
        with self.assertRaises(ConnectionError):
            await adapter.read_turn(Socket([{'type':'turn_complete'}]), 'Hi', trace, '1')

    async def test_retry_and_interruption_abort_without_resending(self):
        for kind in ('session_retry','interrupted'):
            adapter, trace = self.adapter_trace()
            ws = Socket([{'type':kind}])
            with self.assertRaises(LiveProtocolError):
                await adapter.read_turn(ws, 'Hi', trace, '1')
            self.assertEqual(ws.sent, [])

    async def test_full_adapter_separates_greeting_and_captures_snapshots(self):
        adapter = ClaraLiveAdapter(TARGET, 'clara-local-seed-v1')
        metadata = {'mode':'readonly_evaluation','model':TARGET['model'], 'protocol_version':1,
                    'dataset_id':'clara-local-seed-v1','database':'test', 'source_hashes':{},
                    'instruction_sha256':'test','snapshot':{'events':[]}}
        ws = Socket([b'hi',transcript('Welcome.'),{'type':'turn_complete'},
                     b'answer',transcript('What interests you?'),{'type':'turn_complete'}])
        @asynccontextmanager
        async def connection(*args, **kwargs):
            self.assertIn('additional_headers', kwargs)
            yield ws
        with patch.dict(os.environ, {'EVAL_HTTP_TOKEN':'test'}), \
             patch('evaluation.live_adapter.read_metadata', return_value=metadata), \
             patch('evaluation.serve.source_hashes', return_value={}), \
             patch('websockets.asyncio.client.connect', connection):
            result = await adapter.run_async({'scenario_id':'a','user_turns':['Hi']}, {})
        self.assertEqual(result['turns'][0]['assistant'], 'What interests you?')
        self.assertEqual(result['observations']['greeting']['assistant'], 'Welcome.')
        self.assertTrue(result['observations']['database_unchanged'])
        self.assertTrue(result['observations']['audio_received'])
        self.assertEqual(ws.sent, [{'type':'text','content':'Hi'}])


class IsolationBoundaryTests(unittest.TestCase):
    def test_remote_websocket_targets_are_rejected(self):
        for endpoint in ('https://waypoint.example','http://example.com','http://127.0.0.1@evil.com',
                         'http://127.0.0.1:8765/?target=production'):
            with self.assertRaises(ValueError):
                endpoint_parts(endpoint)

    def test_remote_db_and_connection_overrides_are_rejected(self):
        for dsn in ('postgresql://host.example/postgres','host=127.0.0.1 hostaddr=10.0.0.1 dbname=postgres',
                    'host=127.0.0.1 options=-csearch_path=public dbname=postgres'):
            with self.assertRaises(ValueError):
                local_dsn(dsn)
        with self.assertRaises(ValueError):
            local_dsn('postgresql://localhost/production', database=True)

    def test_database_marker_and_write_privileges_are_verified(self):
        state = {'readonly_dsn':'postgresql://reader@localhost/waypoint_eval_'+'0'*32,
                 'database':'waypoint_eval_'+'0'*32,'identity':'marker','dataset_id':'dataset'}
        for rows, should_pass in (([('marker','dataset'), ('on',)] + [(False,)]*6, True),
                                  ([('wrong','dataset')], False),
                                  ([('marker','dataset'), ('off',)], False),
                                  ([('marker','dataset'), ('on',), (True,)], False)):
            connection = MagicMock()
            connection.cursor.return_value.__enter__.return_value.fetchone.side_effect = rows
            with patch('psycopg2.connect', return_value=connection):
                if should_pass:
                    self.assertIs(connect_verified(state), connection)
                else:
                    with self.assertRaises(ValueError):
                        connect_verified(state)
                    connection.close.assert_called_once()

    def test_postgres_environment_cannot_override_loopback(self):
        with patch.dict(os.environ, {'PGHOSTADDR':'10.0.0.1'}):
            with self.assertRaises(ValueError):
                local_dsn('postgresql://localhost/postgres')

    def test_live_validation_never_connects(self):
        with patch('evaluation.live_adapter.read_metadata', side_effect=AssertionError('must not connect')):
            loaded = load_experiment(ROOT/'evaluation/experiments/EXP-LIVE-001/config.json')
            self.assertEqual(len(loaded['cases']), 2)

    def test_missing_live_credentials_records_error_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            directory, code = run_experiment(ROOT/'evaluation/experiments/EXP-LIVE-001/config.json', Path(tmp))
            report = json.loads((directory/'report.json').read_text())
            self.assertEqual(code, 2)
            self.assertEqual(report['evidence_kind'], 'live_text_input')
            self.assertEqual(report['summary']['statuses']['ERROR'], 2)


class DisplayIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_connections_and_threaded_tools_receive_only_their_cards(self):
        sys.path.insert(0, str(ROOT/'backend'))
        import tools
        received = {'a':[], 'b':[]}
        loop = asyncio.get_running_loop()
        async def receive_a(payload): received['a'].append(payload)
        async def receive_b(payload): received['b'].append(payload)
        tools.register_display_callback('a', loop, receive_a)
        tools.register_display_callback('b', loop, receive_b)
        async def send(session):
            token = tools.bind_display_session(session)
            try:
                await asyncio.to_thread(tools._send_card, {'owner':session})
            finally:
                tools.reset_display_session(token)
        try:
            await asyncio.gather(send('a'), send('b'))
            await asyncio.sleep(0)
            self.assertEqual(received, {'a':[{'owner':'a'}], 'b':[{'owner':'b'}]})
            tools._send_card({'owner':'unbound'})
            await asyncio.sleep(0)
            self.assertEqual(len(received['a']), 1)
            self.assertEqual(len(received['b']), 1)
        finally:
            tools.unregister_display_callback('a')
            tools.unregister_display_callback('b')


if __name__ == '__main__':
    unittest.main()
