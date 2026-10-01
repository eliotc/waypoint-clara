import json
from pathlib import Path
import tempfile
import unittest
from evaluation.persona_comparison_summary import summarize


class ComparisonMetricsTests(unittest.TestCase):
    def test_failed_calls_are_not_zero_latency_successes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'case';case.mkdir()
            (root/'report.json').write_text(json.dumps({'protocol_version':3,'results':[
                {'case_id':'case','simulator_model':'model','status':'ERROR'}]}))
            (case/'turn-1-request.json').write_text('{}')
            value=summarize(root)['model']
            self.assertEqual(value['requests'],1)
            self.assertEqual(value['responses_with_metrics'],0)
            self.assertIsNone(value['median_response_ms'])
            self.assertEqual(value['statuses']['ERROR'],1)

    def test_counts_available_usage_without_inventing_missing_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'case';case.mkdir()
            (root/'report.json').write_text(json.dumps({'protocol_version':3,'results':[
                {'case_id':'case','simulator_model':'model','status':'NEEDS_HUMAN'}]}))
            for i,usage in enumerate([{'prompt_token_count':10,'candidates_token_count':5,'total_token_count':15},None]):
                (case/f'{i}-metrics.json').write_text(json.dumps({'elapsed_ms':100+i*100,'usage':usage}))
            value=summarize(root)['model']
            self.assertEqual(value['median_response_ms'],150)
            self.assertEqual(value['usage_records'],1)
            self.assertEqual(value['tokens']['total_token_count'],15)
