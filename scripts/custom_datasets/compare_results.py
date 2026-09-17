"""Compare separately audited native runs on the identical PokemonCards cohort."""

import argparse
import json
import random
import statistics
from pathlib import Path

from convert_all import sha256


def paired_summary(local: dict[int, float], remote: dict[int, float], tolerance: float = 0.05) -> dict:
    """Return paired accuracy change and a seeded percentile bootstrap interval."""
    if not local or local.keys() != remote.keys():
        raise ValueError('Comparison requires nonempty identical sample ID sets')
    differences = [remote[key] - local[key] for key in sorted(local)]
    rng = random.Random(42)
    samples = sorted(statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(10000))
    interval = [samples[249], samples[9749]]
    return {
        'n': len(local),
        'local_accuracy': statistics.mean(local.values()),
        'remote_accuracy': statistics.mean(remote.values()),
        'remote_minus_local': statistics.mean(differences),
        'paired_bootstrap_95_interval': interval,
        'bootstrap_seed': 42,
        'bootstrap_resamples': 10000,
        'correctness_agreement': statistics.mean(local[key] == remote[key] for key in local),
        'local_only_correct': sum(local[key] == 1 and remote[key] == 0 for key in local),
        'remote_only_correct': sum(local[key] == 0 and remote[key] == 1 for key in local),
        'tolerance': tolerance,
        'within_tolerance': interval[0] >= -tolerance and interval[1] <= tolerance,
        'interpretation': 'Paired bootstrap describes this sample set, not universal model equivalence.',
    }


def compare(exp: Path, local_name: str, remote_name: str, task: str) -> dict:
    """Require identical input, scoring and native framework identities before pairing."""
    runs = [json.loads((exp / f'{name}.json').read_text()) for name in (local_name, remote_name)]
    audits = [json.loads((exp / f'{name}-task-analysis.json').read_text()) for name in (local_name, remote_name)]
    for name, run, audit in zip((local_name, remote_name), runs, audits):
        if run['status'] != 'completed' or audit['status'] != 'audited':
            raise ValueError('Both runs must be completed and audited')
        if audit['run_sha256'] != sha256(exp / f'{name}.json'):
            raise ValueError('Run changed since its audit')
        if run['identity']['manifest_sha256'] != sha256(exp / 'manifest.json'):
            raise ValueError('Manifest changed since inference')
        for path, expected in audit['subsets'][task]['review_sha256'].items():
            if sha256(exp / path) != expected:
                raise ValueError('Native review changed since its audit')
    for field in ('manifest_sha256', 'temperature', 'seed', 'max_tokens', 'runner_sha256', 'framework_tree'):
        if runs[0]['identity'][field] != runs[1]['identity'][field]:
            raise ValueError(f'Incompatible generation identity: {field}')
    for field in ('task_metric_sha256', 'analyzer_sha256', 'task_metric_version'):
        if audits[0][field] != audits[1][field]:
            raise ValueError(f'Incompatible independent metric: {field}')
    items = [audit['subsets'][task] for audit in audits]
    if items[0]['benchmark'] != items[1]['benchmark']:
        raise ValueError('Native dataset interfaces differ')
    scores = [{int(k): value for k, value in item['scores_by_source_index'].items()} for item in items]
    result = paired_summary(*scores)
    result.update(
        {
            'subset': task,
            'local_run': local_name,
            'remote_run': remote_name,
            'metric_origin': items[0]['task_metric_origin'],
            'local_perf_metrics': items[0]['perf_metrics'],
            'remote_perf_metrics': items[1]['perf_metrics'],
            'manifest_sha256': runs[0]['identity']['manifest_sha256'],
            'comparison_sha256': sha256(Path(__file__)),
            'deployment_caveat': 'Local llama.cpp GGUF Q4 and remote vLLM FP8 differ; not a hardware-only comparison.',
        }
    )
    return result


def main() -> None:
    """Write a paired comparison without altering either original evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exp', type=Path, required=True)
    parser.add_argument('--local', required=True)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--subset', default='pokemon')
    args = parser.parse_args()
    result = compare(args.exp, args.local, args.remote, args.subset)
    output = args.exp / f'comparison-{args.local}-{args.remote}.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if 'perf_metrics' not in key}, indent=2))


if __name__ == '__main__':
    main()
