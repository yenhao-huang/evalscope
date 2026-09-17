"""Compare two completed runs with identical samples, prompts and decoding settings."""

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path


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


def load_scores(run_dir: Path, subset: str) -> dict[int, float]:
    """Read committed EvalScope review records, rejecting excluded or duplicate samples."""
    scores = {}
    for path in (run_dir / subset / 'reviews').rglob('*.jsonl'):
        for line in path.open():
            if not line.strip():
                continue
            record = json.loads(line)['sample_score']
            score = record['score']
            if score['status'] != 'success':
                raise ValueError(f'Unusable score in {path}')
            values = score['value']
            value = values.get('acc', values.get('accuracy'))
            index = record['sample_metadata']['source_index']
            if value not in (0, 1) or index in scores:
                raise ValueError(f'Invalid or duplicate score for source index {index}')
            scores[index] = value
    return scores


def validate_pair(local: dict, remote: dict, manifest_bytes: bytes, subset: str) -> set[int]:
    """Require the on-disk manifest and scoring code to match both recorded runs."""
    for record in (local, remote):
        if record['status'] != 'completed' or subset not in record['identity']['subsets']:
            raise ValueError('Both runs must be completed and contain the requested subset')
        if record['identity']['manifest_sha256'] != hashlib.sha256(manifest_bytes).hexdigest():
            raise ValueError('Current manifest does not match the evaluated manifest')
    fields = ['limit', 'temperature', 'seed', 'max_tokens', 'reasoning', 'scoring_version']
    for field in fields:
        if local['identity'][field] != remote['identity'][field]:
            raise ValueError(f'Incompatible run identity: {field}')
    for source in ('local_model_tester_adapter.py', 'scoring.py'):
        hashes = []
        for record in (local, remote):
            matching = [value for path, value in record.get('source_sha256', {}).items() if Path(path).name == source]
            if len(matching) != 1:
                raise ValueError(f'Missing or ambiguous source fingerprint: {source}')
            hashes.append(matching[0])
        if hashes[0] != hashes[1]:
            raise ValueError(f'Scoring implementation differs: {source}')
    manifest = json.loads(manifest_bytes)
    expected = min(local['identity']['limit'], manifest['subsets'][subset]['count'])
    return set(range(expected))


def performance_summary(record: dict, subset: str) -> dict:
    """Expose measured end-to-end latency and coverage without inventing missing values."""
    reports = [
        report for item in record.get('completed_subsets', []) if item['subset'] == subset for report in item['reports']
    ]
    if len(reports) != 1:
        raise ValueError(f'Expected one completed report for {subset}')
    report = reports[0]
    item = next(item for item in record['completed_subsets'] if item['subset'] == subset)
    perf = item.get('generation_perf_metrics', report.get('perf_metrics')) or {}
    measured = (perf.get('summary') or {}).get('latency') or {}
    latency = {}
    for label, key in [('mean', 'mean'), ('median', '50%'), ('p90', '90%'), ('p99', '99%')]:
        value = measured.get(key)
        latency[label] = value if isinstance(value, (float, int)) and math.isfinite(value) and value >= 0 else None
    return {
        'latency_seconds': latency,
        'measurement_coverage': perf.get('coverage'),
        'execution': item.get('generation_execution_summary', report.get('execution_summary')),
        'note': 'End-to-end request latency includes image processing and network overhead, not pure decode speed.',
    }


def main() -> None:
    """Validate run identities before generating the paired comparison artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exp', type=Path, default=Path('exp/2026-09-15'))
    parser.add_argument('--local', required=True)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--subset', default='pokemon')
    parser.add_argument('--tolerance', type=float, default=0.05)
    args = parser.parse_args()
    if not 0 <= args.tolerance <= 1:
        parser.error('tolerance must be between 0 and 1')
    local = json.loads((args.exp / f'{args.local}.json').read_text())
    remote = json.loads((args.exp / f'{args.remote}.json').read_text())
    manifest_bytes = (args.exp / 'manifest.json').read_bytes()
    expected_ids = validate_pair(local, remote, manifest_bytes, args.subset)
    left = load_scores(args.exp / 'runs' / args.local, args.subset)
    right = load_scores(args.exp / 'runs' / args.remote, args.subset)
    if left.keys() != expected_ids or right.keys() != expected_ids:
        raise ValueError('Review source indices do not cover the expected original sample order')
    local_perf = performance_summary(local, args.subset)
    remote_perf = performance_summary(remote, args.subset)
    local_mean = local_perf['latency_seconds']['mean']
    remote_mean = remote_perf['latency_seconds']['mean']
    result = {
        'local': args.local,
        'remote': args.remote,
        'subset': args.subset,
        'local_model_info': local['model_info'],
        'remote_model_info': remote['model_info'],
        'performance': {
            'local': local_perf,
            'remote': remote_perf,
            'mean_latency_remote_over_local': remote_mean / local_mean
            if local_mean and remote_mean is not None
            else None,
        },
        **paired_summary(left, right, args.tolerance),
    }
    destination = args.exp / f'comparison-{args.local}-{args.remote}.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
