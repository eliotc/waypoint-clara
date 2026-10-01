"""Opt-in checks against a marked, disposable local database."""
import asyncio
import os
from pathlib import Path
import unittest

from evaluation.local_database import state_file, database_uri, connect_verified


@unittest.skipUnless(os.environ.get('EVAL_TEST_STATE'), 'requires prepared local evaluation DB')
class LocalDatabaseIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_uri_works_for_both_drivers_and_reader_cannot_write(self):
        import asyncpg
        import psycopg2
        state = state_file(Path(os.environ['EVAL_TEST_STATE']))
        connect_verified(state).close()
        uri = database_uri(state['readonly_dsn'])
        with psycopg2.connect(uri) as conn, conn.cursor() as cur:
            cur.execute('SELECT current_database()')
            self.assertEqual(cur.fetchone()[0], state['database'])
        conn = await asyncpg.connect(uri)
        try:
            self.assertEqual(await conn.fetchval('SELECT current_database()'), state['database'])
            self.assertEqual(await conn.fetchval('SHOW transaction_read_only'), 'on')
            with self.assertRaises(asyncpg.ReadOnlySQLTransactionError):
                await conn.execute('UPDATE events SET spots_left = spots_left WHERE false')
            if state['embeddings_ready']:
                for table in ('courses', 'knowledge_docs', 'scholarships'):
                    counts = await conn.fetchrow(f'SELECT count(*) AS total, count(embedding) AS embedded FROM {table}')
                    self.assertGreater(counts['total'], 0)
                    self.assertEqual(counts['total'], counts['embedded'])
        finally:
            await conn.close()

    async def test_course_tools_exclude_known_mismatches_and_share_card_evidence(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from backend import tools
        state = state_file(Path(os.environ['EVAL_TEST_STATE']))
        @contextmanager
        def connection():
            conn = connect_verified(state)
            try:
                yield conn
            finally:
                conn.close()
        # A stored real embedding avoids an external model dependency for this SQL test.
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT embedding::text FROM courses WHERE name='Bachelor of Cybersecurity'")
            embedding=tuple(float(v) for v in cur.fetchone()[0].strip('[]').split(','))
        session_id = 'test-db-integration'
        async def sink(payload): pass
        tools.register_display_callback(session_id, asyncio.get_running_loop(), sink)
        token = tools.bind_display_session(session_id)
        try:
            tools.record_student_message("I do not have a bachelor's degree and I have no IT experience.", "typed")
            for invoke in (
                lambda: tools.search_courses('cybersecurity', student_atar=82, study_mode_preference='Online', has_bachelor_degree=False, professional_it_years=0),
                lambda: tools.recommend_courses('cybersecurity','maths', student_atar=82, study_mode_preference='Online', has_bachelor_degree=False, professional_it_years=0),
            ):
                with patch.object(tools,'_get_conn',connection), patch.object(tools,'_embed',return_value=embedding), patch.object(tools,'_send_card') as send:
                    result=invoke()
                    card=send.call_args.args[0]['data']['courses']
                    self.assertTrue(card)
                    self.assertIsNotNone(result['eligibility_notice'])
                    self.assertTrue(all(c['study_mode']=='Online' for c in card))
                    self.assertNotIn('Graduate Certificate in Cloud Computing',[c['name'] for c in card])
                    self.assertEqual([c['suitability'] for c in card],[c['suitability'] for c in result['courses']])
                    self.assertTrue(all(c['suitability']['status']=='unknown' for c in card))
        finally:
            tools.reset_display_session(token)
            tools.unregister_display_callback(session_id)

    async def test_model_receives_course_descriptions_and_complete_knowledge(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from backend import tools
        state = state_file(Path(os.environ['EVAL_TEST_STATE']))
        @contextmanager
        def connection():
            conn = connect_verified(state)
            try: yield conn
            finally: conn.close()
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT embedding::text, description FROM courses WHERE name='Bachelor of Cybersecurity'")
            raw, description = cur.fetchone()
            course_embedding=tuple(float(v) for v in raw.strip('[]').split(','))
            cur.execute("SELECT embedding::text, content FROM knowledge_docs WHERE length(content)>500 ORDER BY length(content) DESC LIMIT 1")
            raw, content = cur.fetchone()
            knowledge_embedding=tuple(float(v) for v in raw.strip('[]').split(','))
        with patch.object(tools,'_get_conn',connection), patch.object(tools,'_embed',return_value=course_embedding):
            detail=tools.get_course_detail('Bachelor of Cybersecurity')
            self.assertEqual(detail['description'],description)
        with patch.object(tools,'_get_conn',connection), patch.object(tools,'_embed',return_value=knowledge_embedding):
            result=tools.search_knowledge('stored document')
            self.assertEqual(result['excerpt'],content)
            self.assertGreater(len(result['excerpt']),500)
            self.assertEqual(result['sections'][0]['content'],content)
            from datetime import date
            date.fromisoformat(result['observed_date'])
