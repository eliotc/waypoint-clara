"""Summarize recorded comparison execution metrics, without grading semantics."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median


def summarize(run):
    report=json.loads((run/'report.json').read_text())
    if report.get('protocol_version') != 3:
        raise ValueError('Expected a protocol3 comparison report')
    groups=defaultdict(lambda: {'cases':0,'statuses':defaultdict(int),'requests':0,
                              'responses_with_metrics':0,'latencies_ms':[],
                              'tokens':defaultdict(int),'usage_records':0})
    for row in report['results']:
        group=groups[row['simulator_model']]
        group['cases']+=1;group['statuses'][row['status']]+=1
        case=run/row['case_id']
        group['requests']+=len(list(case.glob('*-request.json')))
        for path in case.glob('*-metrics.json'):
            value=json.loads(path.read_text());group['responses_with_metrics']+=1
            group['latencies_ms'].append(value['elapsed_ms'])
            if value.get('usage'):
                group['usage_records']+=1
                for key in ('prompt_token_count','candidates_token_count','thoughts_token_count','total_token_count'):
                    group['tokens'][key]+=value['usage'].get(key) or 0
    for value in groups.values():
        latencies=value.pop('latencies_ms')
        value['median_response_ms']=round(median(latencies),2) if latencies else None
        value['limits']='Latency includes successful API response only, not failed requests or Clara turns; token totals cover available usage records. No semantic quality or dollar-cost verdict.'
    return dict(groups)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    print(json.dumps(summarize(args.run),indent=2))
