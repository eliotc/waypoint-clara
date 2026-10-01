import json
import unittest
from unittest.mock import patch

from evaluation.contracts import ROOT
from evaluation.live_adapter import visible_conversation
from evaluation.persona_simulation import load_design, parse_answer


class PersonaBoundaryTests(unittest.TestCase):
    def test_projection_excludes_evaluator_and_unrendered_card_fields(self):
        trace={'observations':{'greeting':{'assistant':'Welcome','tools':[{'secret':1}]},
            'server_before':{'snapshot':'private truth'},'events':['private']},
            'turns':[{'user':'Hello','assistant':'Explore this','tools':['private'],
                      'cards':[{'hidden_ranking':99}]}]}
        self.assertEqual(visible_conversation(trace),[
            {'role':'assistant','text':'Welcome'}, {'role':'user','text':'Hello'},
            {'role':'assistant','text':'Explore this'}])

    def test_invalid_simulator_output_is_error(self):
        for raw in ('null','{}','{"message":""}','{"message":1}',
                    '{"message":"Hi","extra":"hidden"}'):
            with self.assertRaises(ValueError): parse_answer(raw,['message'])
        self.assertEqual(parse_answer('{"message":"Hi"}',['message']), {'message':'Hi'})

    def test_validation_is_offline_and_bounds_calls(self):
        with patch('evaluation.live_adapter.read_metadata', side_effect=AssertionError('network')):
            design, profiles, _ = load_design(ROOT/'evaluation/experiments/EXP-SIM-002/config.json')
        self.assertLessEqual(len(profiles['personas'])*(design['adaptive_turns']+1),20)
        self.assertEqual(len({p['id'] for p in profiles['personas']}),4)


class AdaptiveTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_turn_uses_only_visible_history_and_same_session(self):
        import os
        from contextlib import asynccontextmanager
        from evaluation.live_adapter import ClaraLiveAdapter
        from evaluation.tests.test_live import Socket, TARGET, transcript
        metadata={'mode':'readonly_evaluation','model':TARGET['model'],'protocol_version':1,
                  'dataset_id':'test','database':'test','source_hashes':{},
                  'instruction_sha256':'test','snapshot':{'events':['evaluator-only']}}
        ws=Socket([transcript('Welcome'),{'type':'turn_complete'},
                   transcript('What interests you?'),{'type':'turn_complete'},
                   transcript('Let us explore'),{'type':'turn_complete'}])
        seen=[]
        async def provider(index, history):
            seen.append(history)
            return ['Hello','Computing'][index-1]
        @asynccontextmanager
        async def connection(*args, **kwargs): yield ws
        with patch.dict(os.environ, {'EVAL_HTTP_TOKEN':'secret'}), \
             patch('evaluation.live_adapter.read_metadata', return_value=metadata), \
             patch('evaluation.serve.source_hashes', return_value={}), \
             patch('websockets.asyncio.client.connect', connection):
            trace=await ClaraLiveAdapter(TARGET,'test').run_async(
                {'scenario_id':'adaptive','user_turns':['placeholder']*2},{},provider)
        self.assertEqual([t['user'] for t in trace['turns']],['Hello','Computing'])
        self.assertEqual(seen[0],[{'role':'assistant','text':'Welcome'}])
        self.assertEqual(seen[1][-1],{'role':'assistant','text':'What interests you?'})
        self.assertNotIn('evaluator-only',json.dumps(seen))
        self.assertEqual(ws.sent,[{'type':'text','content':'Hello'}, {'type':'text','content':'Computing'}])


class PersonaFailureTests(unittest.TestCase):
    def test_setup_failure_returns_incomplete_without_sensitive_error_text(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import AsyncMock
        from evaluation.persona_simulation import main
        output=io.StringIO()
        with patch('sys.argv',['persona','config.json','--run','--state','private.json']), \
             patch('evaluation.persona_simulation.execute',new=AsyncMock(side_effect=ValueError('secret-dsn'))), \
             redirect_stdout(output):
            self.assertEqual(main(),2)
        self.assertNotIn('secret-dsn',output.getvalue())
        self.assertIn('incomplete',output.getvalue())


class SimulatorComparisonTests(unittest.TestCase):
    def test_balanced_order_and_fresh_case_ids(self):
        from evaluation.persona_simulation import case_schedule
        design, profiles, _ = load_design(ROOT/'evaluation/experiments/EXP-SIM-003/config.json')
        cases=case_schedule(design,profiles)
        self.assertEqual(len(cases),8)
        self.assertEqual(len({cid for cid,_,_ in cases}),8)
        self.assertEqual([m for _,_,m in cases[:4]],
                         ['gemini-2.5-flash','gemini-3.8-flash','gemini-3.8-flash','gemini-2.5-flash'])
        self.assertEqual(len(cases)*(design['adaptive_turns']+1),40)

    def test_model_specific_thinking_is_explicit_and_sdk_valid(self):
        from evaluation.persona_simulation import generation_settings
        from google.genai.types import ThinkingConfig
        a=generation_settings('gemini-2.5-flash'); b=generation_settings('gemini-3.8-flash')
        self.assertEqual(a['thinking'],{'thinking_budget':0})
        self.assertEqual(b['thinking'],{'thinking_level':'low'})
        ThinkingConfig(**b['thinking'])
        with self.assertRaises(ValueError):generation_settings('unknown-model')
