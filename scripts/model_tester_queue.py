"""Run the local experiment jobs serially, with durable status and final summaries."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    """Run all requested benchmarks without competing for the model's single slot."""
    root = Path(__file__).resolve().parents[1]
    exp = root / 'exp/2026-09-15'
    jobs = [
        ('local-pokemon-300', ['--subsets', 'pokemon', '--limit', '300']),
        (
            'local-suite-100',
            [
                '--subsets',
                'mmlu',
                'gsm8k',
                'humaneval',
                'geo_mmlu',
                'law_mmlu',
                'opseval',
                'cifar10',
                'cppe5',
                '--limit',
                '100',
            ],
        ),
    ]
    status = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(), 'jobs': []}
    destination = exp / 'queue-status.json'
    for name, arguments in jobs:
        command = [sys.executable, str(root / 'scripts/run_model_tester.py'), '--run-name', name, *arguments]
        state_path = exp / f'{name}.json'
        if state_path.exists():
            command.append('--resume')
        job = {'name': name, 'status': 'running', 'command': command}
        status['jobs'].append(job)
        destination.write_text(json.dumps(status, indent=2) + '\n')
        with (exp / 'logs' / f'{name}.log').open('a') as log:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        job['returncode'] = result.returncode
        job['status'] = 'completed' if result.returncode == 0 else 'failed'
        if result.returncode:
            status['status'] = 'failed'
            break
    else:
        status['status'] = 'completed'
    status['updated_at'] = datetime.now(timezone.utc).isoformat()
    destination.write_text(json.dumps(status, indent=2) + '\n')
    raise SystemExit(0 if status['status'] == 'completed' else 1)


if __name__ == '__main__':
    main()
