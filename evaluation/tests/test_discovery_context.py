import asyncio
import unittest
from backend import tools


class DiscoveryContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def sink(payload): pass
        for sid in ('context-a','context-b'):
            tools.register_display_callback(sid,asyncio.get_running_loop(),sink)

    async def asyncTearDown(self):
        for sid in ('context-a','context-b'):
            tools.unregister_display_callback(sid)

    async def test_context_isolated_in_worker_threads_and_removed_on_disconnect(self):
        for sid,text in [('context-a','I need part-time study.'),('context-b','I work; my hours vary.')]:
            token=tools.bind_display_session(sid)
            try:
                tools.record_student_message(text,'typed')
                result=await asyncio.to_thread(tools.get_discovery_context)
                self.assertEqual([m['text'] for m in result['messages']],[text])
                result['messages'][0]['text']='mutated'
                self.assertEqual(tools.get_discovery_context()['messages'][0]['text'],text)
            finally:tools.reset_display_session(token)
        tools.unregister_display_callback('context-a')
        token=tools.bind_display_session('context-a')
        try:self.assertFalse(tools.get_discovery_context()['available'])
        finally:tools.reset_display_session(token)

    async def test_preserves_corrections_and_labels_incomplete_history(self):
        token=tools.bind_display_session('context-a')
        try:
            tools.record_student_message('I want full-time.','typed')
            tools.record_student_message('Actually I need part-time.','transcribed')
            tools.record_student_message('Actually I need part-time.','transcribed')
            result=tools.get_discovery_context()
            self.assertEqual(len(result['messages']),2)
            self.assertEqual(result['messages'][1]['source'],'transcribed')
            for i in range(65):tools.record_student_message(str(i),'typed')
            result=tools.get_discovery_context()
            self.assertEqual(len(result['messages']),64)
            self.assertFalse(result['history_complete'])
            tools.record_student_message('x'*8001,'typed')
            self.assertTrue(tools.get_discovery_context()['messages'][-1]['truncated'])
        finally:tools.reset_display_session(token)
