"""Run with python -m evaluation; no application imports or credential loading."""
import argparse
import json
from pathlib import Path
import sys

from evaluation.contracts import ROOT
from evaluation.runner import load_experiment, run_experiment


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run"):
        command = commands.add_parser(name)
        command.add_argument("experiment", type=Path)
        if name == "run":
            command.add_argument("--state", type=Path, help="Private local database state for the Live adapter")
            command.add_argument("--out", type=Path, default=ROOT / "evaluation/runs")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            loaded = load_experiment(args.experiment)
            print(f"Valid: {loaded['config']['experiment_id']} ({len(loaded['cases'])} scenarios; {loaded['config']['target']['adapter']})")
            return 0
        if args.state:
            import os
            from evaluation.local_database import state_file
            state = state_file(args.state)
            if state['status'] != 'ready':
                raise ValueError('Database state is not ready')
            os.environ['EVAL_HTTP_TOKEN'] = state['http_token']
        run_dir, code = run_experiment(args.experiment, args.out)
        print(f"Evaluation report: {run_dir / 'report.json'}")
        print("Exit codes: 0=all checks passed; 1=failed; 2=incomplete/error/review needed.")
        return code
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Evaluation could not complete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
