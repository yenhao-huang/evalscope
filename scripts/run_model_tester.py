"""Run the frozen local benchmark suite through EvalScope and save aggregate evidence."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from evalscope import TaskConfig, run_task
from evalscope.benchmarks.local_model_tester.local_model_tester_adapter import SUBSETS
from evalscope.benchmarks.local_model_tester.scoring import SCORING_VERSION, execute_code


def main() -> None:
    """Evaluate a named immutable run; resume only when its identity matches."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exp', type=Path, default=Path('exp/2026-09-15'))
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--api-url', default='http://127.0.0.1:8092/v1')
    parser.add_argument('--model', default='gemma4-26b-a4b')
    parser.add_argument('--subsets', nargs='+', choices=SUBSETS, default=SUBSETS)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--rescore-from', help='Copy completed subset caches to a new run and recompute scores only')
    args = parser.parse_args()
    if args.limit < 1 or Path(args.run_name).name != args.run_name:
        parser.error('Use a positive limit and a plain run name')
    if args.rescore_from and (
        args.resume or args.rescore_from == args.run_name or Path(args.rescore_from).name != args.rescore_from
    ):
        parser.error('Rescoring requires a different plain source run name and cannot use --resume')
    source_run = json.loads((args.exp / f'{args.rescore_from}.json').read_text()) if args.rescore_from else None
    manifest_path = args.exp / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for subset in args.subsets:
        data = args.exp / 'data' / f'{subset}.jsonl'
        if hashlib.sha256(data.read_bytes()).hexdigest() != manifest['subsets'][subset]['sha256']:
            raise ValueError(f'Dataset hash mismatch: {subset}')
    if 'humaneval' in args.subsets and not execute_code('assert 1 + 1 == 2'):
        raise RuntimeError('HumanEval sandbox preflight failed')
    key = os.getenv('EVAL_API_KEY', 'EMPTY')
    if source_run:
        model_info = source_run['model_info']
    else:
        response = requests.get(
            args.api_url.rstrip('/') + '/models', headers={'Authorization': f'Bearer {key}'}, timeout=20
        )
        response.raise_for_status()
        model_info = response.json()
    if args.model not in {model['id'] for model in model_info['data']}:
        raise ValueError(f'Requested model {args.model} is not served by the endpoint')
    run_dir = args.exp / 'runs' / args.run_name
    state_path = args.exp / f'{args.run_name}.json'
    identity = {
        'model': args.model,
        'api_url': args.api_url,
        'subsets': args.subsets,
        'limit': args.limit,
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'temperature': 0,
        'seed': 42,
        'max_tokens': 4096,
        'reasoning': 'off',
        'scoring_version': SCORING_VERSION,
    }
    source_reports = {}
    if source_run:
        for field in ('model', 'api_url', 'limit', 'manifest_sha256', 'temperature', 'seed', 'max_tokens', 'reasoning'):
            if source_run['identity'][field] != identity[field]:
                raise ValueError(f'Rescoring cannot change generation identity: {field}')
        source_reports = {item['subset']: item['reports'][0] for item in source_run['completed_subsets']}
        for subset in args.subsets:
            if subset not in source_reports:
                raise ValueError(f'Source subset is not completed: {subset}')
        if run_dir.exists():
            raise FileExistsError('Rescoring requires a fresh destination directory')
    source_hashes = {
        str(path.relative_to(Path.cwd())): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [Path(__file__).resolve(), *Path('evalscope/benchmarks/local_model_tester').resolve().glob('*.py')]
    }
    previous = None
    if state_path.exists():
        if not args.resume:
            raise FileExistsError(f'{state_path} exists; use a new run name or --resume')
        previous = json.loads(state_path.read_text())
        if previous['identity'] != identity:
            raise ValueError('Cannot resume with a different experiment identity')
        if previous.get('source_sha256') != source_hashes:
            raise ValueError('Source code changed; create a new run instead of reusing cached scores')
    elif args.resume:
        raise FileNotFoundError('No previous run identity to resume')
    record = {
        'identity': identity,
        'rescore_from': args.rescore_from,
        'generation_identity': source_run['identity'] if source_run else identity,
        'status': 'running',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'model_info': model_info,
        'source_sha256': source_hashes,
        'previous_attempt': {key: previous.get(key) for key in ('started_at', 'updated_at', 'status', 'error')}
        if previous
        else None,
        'completed_subsets': [],
    }
    state_path.write_text(json.dumps(record, indent=2) + '\n')
    try:
        for subset in args.subsets:
            work = run_dir / subset
            cache_hashes = {}
            if source_run:
                origin = args.exp / 'runs' / args.rescore_from / subset
                shutil.copytree(origin, work)
                cache_hashes = {
                    str(path.relative_to(work)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (work / 'predictions').rglob('*.jsonl')
                }
                if not cache_hashes:
                    raise FileNotFoundError(f'No source prediction cache for {subset}')
            config = TaskConfig(
                model=args.model,
                api_url=args.api_url,
                api_key=key,
                eval_type='openai_api',
                datasets=['local_model_tester'],
                dataset_args={
                    'local_model_tester': {
                        'local_path': str((args.exp / 'data').resolve()),
                        'subset_list': [subset],
                        'shuffle': False,
                        'extra_params': {'review_only': bool(source_run)},
                    }
                },
                limit=args.limit,
                eval_batch_size=1,
                seed=42,
                work_dir=str(work),
                no_timestamp=True,
                use_cache=str(work) if source_run or (args.resume and work.exists()) else None,
                rerun_review=bool(source_run),
                ignore_errors=False,
                generation_config={
                    'temperature': 0,
                    'seed': 42,
                    'max_tokens': 4096,
                    'timeout': 600,
                    'extra_body': {'chat_template_kwargs': {'enable_thinking': False}},
                },
            )
            run_task(config)
            if source_run:
                after = {
                    str(path.relative_to(work)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (work / 'predictions').rglob('*.jsonl')
                }
                if after != cache_hashes:
                    raise RuntimeError('Prediction cache changed during review-only scoring')
            reports = [json.loads(path.read_text()) for path in work.glob('reports/**/*.json')]
            if any(
                report.get('execution_summary', {}).get('incomplete')
                or report.get('execution_summary', {}).get('errored', 0)
                for report in reports
            ):
                raise RuntimeError(f'Incomplete or errored evaluation: {subset}')
            if not reports:
                raise RuntimeError(f'Missing EvalScope report: {subset}')
            expected = min(args.limit, manifest['subsets'][subset]['count'])
            if len(reports) != 1 or reports[0].get('num') != expected:
                raise RuntimeError(f'Review coverage mismatch: {subset}, expected {expected}')
            item = {'subset': subset, 'reports': reports}
            if source_run:
                item['generation_perf_metrics'] = source_reports[subset].get('perf_metrics')
                item['generation_execution_summary'] = source_reports[subset].get('execution_summary')
                item['unchanged_prediction_cache_sha256'] = cache_hashes
            record['completed_subsets'].append(item)
            state_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    except BaseException as error:
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        raise
    else:
        record['status'] = 'completed'
    finally:
        record['updated_at'] = datetime.now(timezone.utc).isoformat()
        state_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
