"""Evaluate converted data exclusively through public TaskConfig/run_task interfaces."""

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests
from convert_all import sha256

from evalscope import TaskConfig, run_task


def build_config(
    exp: Path, task: str, entry: dict, run_name: str, api_url: str, model: str, limit: int, resume: bool = False
) -> TaskConfig:
    """Configure an existing built-in dataset; no custom adapter or scoring hooks."""
    benchmark = entry['benchmark']
    settings = {
        'local_path': str((exp / 'data' / benchmark).resolve()),
        'subset_list': [task],
        'shuffle': False,
        'few_shot_num': 0,
    }
    if benchmark == 'general_mcq':
        settings['extra_params'] = {'multiple_correct': entry['multiple_correct'], 'use_cot': False}
    work = exp / 'runs' / run_name / task
    return TaskConfig(
        model=model,
        api_url=api_url,
        api_key=os.getenv('EVAL_API_KEY', 'EMPTY'),
        eval_type='openai_api',
        datasets=[benchmark],
        dataset_args={benchmark: settings},
        limit=limit,
        eval_batch_size=1,
        seed=42,
        work_dir=str(work),
        no_timestamp=True,
        use_cache=str(work) if resume and work.exists() else None,
        ignore_errors=False,
        generation_config={
            'temperature': 0,
            'seed': 42,
            'max_tokens': 4096,
            'timeout': 600,
            'extra_body': {'chat_template_kwargs': {'enable_thinking': False}},
        },
    )


def main() -> None:
    """Run fresh inference, preserve native reports, and record exact configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exp', type=Path, required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--api-url', default='http://127.0.0.1:8092/v1')
    parser.add_argument('--model', default='gemma4-26b-a4b')
    parser.add_argument('--subsets', nargs='+')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--pokemon-limit', type=int, default=300)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if min(args.limit, args.pokemon_limit) < 1 or Path(args.run_name).name != args.run_name:
        parser.error('Use positive limits and a plain run name')
    subprocess.run(
        ['git', 'diff', '--exit-code', 'origin/main', '--', 'evalscope'], check=True, stdout=subprocess.DEVNULL
    )
    manifest = json.loads((args.exp / 'manifest.json').read_text())
    subsets = args.subsets or list(manifest['subsets'])
    for task in subsets:
        entry = manifest['subsets'][task]
        for file, expected in [(entry['file'], entry['sha256']), (entry['sidecar'], entry['sidecar_sha256'])]:
            if sha256(args.exp / 'data' / file) != expected:
                raise ValueError(f'Frozen input changed: {file}')
    state = args.exp / f'{args.run_name}.json'
    identity = {
        'api_url': args.api_url,
        'model': args.model,
        'subsets': subsets,
        'limit': args.limit,
        'pokemon_limit': args.pokemon_limit,
        'temperature': 0,
        'seed': 42,
        'max_tokens': 4096,
        'manifest_sha256': sha256(args.exp / 'manifest.json'),
        'runner_sha256': sha256(Path(__file__)),
        'framework_tree': subprocess.check_output(['git', 'rev-parse', 'origin/main:evalscope'], text=True).strip(),
    }
    if state.exists():
        record = json.loads(state.read_text())
        if not args.resume or record['identity'] != identity:
            raise ValueError('Existing run requires --resume and identical configuration/source')
    else:
        if args.resume or (args.exp / 'runs' / args.run_name).exists():
            raise ValueError('Use a new run name; no unverified cache reuse')
        record = {
            'identity': identity,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_subsets': [],
            'configs': {},
            'status': 'running',
        }
    response = requests.get(
        args.api_url.rstrip('/') + '/models',
        headers={'Authorization': f'Bearer {os.getenv("EVAL_API_KEY", "EMPTY")}'},
        timeout=30,
    )
    response.raise_for_status()
    record['model_info'] = response.json()
    if args.model not in {m['id'] for m in record['model_info']['data']}:
        raise ValueError('Requested model is not served by the endpoint')

    def save() -> None:
        record['updated_at'] = datetime.now(timezone.utc).isoformat()
        state.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')

    record['status'] = 'running'
    save()
    try:
        completed = {item['subset'] for item in record['completed_subsets']}
        for task in subsets:
            if task in completed:
                continue
            entry = manifest['subsets'][task]
            limit = args.pokemon_limit if task == 'pokemon' else args.limit
            config = build_config(args.exp, task, entry, args.run_name, args.api_url, args.model, limit, args.resume)
            record['current_subset'] = task
            public_config = config.to_dict()
            public_config['api_key'] = 'FROM_ENV_OR_EMPTY'
            record['configs'][task] = public_config
            save()
            run_task(config)
            work = args.exp / 'runs' / args.run_name / task
            reports = [json.loads(p.read_text()) for p in work.glob('reports/**/*.json')]
            expected = min(limit, entry['count'])
            if len(reports) != 1 or reports[0].get('num') != expected:
                raise RuntimeError(f'Native report coverage mismatch: {task}')
            execution = reports[0].get('execution_summary', {})
            if execution.get('incomplete') or execution.get('errored', 0) or execution.get('succeeded') != expected:
                raise RuntimeError(f'Native evaluation failed: {task}: {execution}')
            reviews = [json.loads(line) for p in work.glob('reviews/**/*.jsonl') for line in p.read_text().splitlines()]
            if len(reviews) != expected or any(
                r['sample_score']['score']['status'] != 'success'
                or r['sample_score']['score'].get('metadata', {}).get('metric_errors')
                for r in reviews
            ):
                raise RuntimeError(f'Unusable native scores: {task}')
            record['completed_subsets'].append({'subset': task, 'benchmark': entry['benchmark'], 'reports': reports})
            save()
        record['status'] = 'completed'
        record.pop('error', None)
    except BaseException as error:
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
