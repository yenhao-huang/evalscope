"""Audit native output files and report independent task metrics separately."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

from convert_all import sha256
from task_metrics import SCORING_VERSION, execute_code, score_response


def records(path: Path) -> list[dict]:
    """Read one JSONL file without interpreting Unicode line separators as new rows."""
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate_input(review: dict, native: dict, sidecar: dict, benchmark: str) -> None:
    """Validate targets, source order, prompts, and actual image bytes before scoring."""
    expected_target = ''.join(native['answer']) if isinstance(native['answer'], list) else native['answer']
    if review['target'] != expected_target:
        raise ValueError('Native target differs from converted data')
    messages = [m for m in review['messages'] if m['role'] != 'assistant']
    if benchmark == 'general_mcq':
        if str(review['sample_score']['sample_metadata']['id']) != str(native['id']):
            raise ValueError('MCQ source identity differs')
        prompt = '\n'.join(m['content'] for m in messages)
        if native['question'] not in prompt or any(str(native[k]) not in prompt for k in 'ABCDEFGHIJ' if k in native):
            raise ValueError('MCQ source question/options differ')
        return
    if len(messages) != len(native['messages']):
        raise ValueError('Message count differs')
    for actual, expected in zip(messages, native['messages']):
        if actual['role'] != expected['role']:
            raise ValueError('Message role differs')
        if isinstance(expected['content'], str):
            if actual['content'] != expected['content']:
                raise ValueError('Text prompt differs')
            continue
        if len(actual['content']) != len(expected['content']):
            raise ValueError('Multimodal content count differs')
        for got, wanted in zip(actual['content'], expected['content']):
            if wanted['type'] == 'text':
                if got.get('text') != wanted['text']:
                    raise ValueError('Vision prompt differs')
            else:
                image = got.get('image', '')
                if image != wanted['image_url']['url']:
                    raise ValueError('Image input differs')
                if (
                    hashlib.sha256(base64.b64decode(image.split(',', 1)[1])).hexdigest()
                    != sidecar['metadata']['image_sha256']
                ):
                    raise ValueError('Image hash differs')


def analyze(exp: Path, run_name: str) -> dict:
    """Validate complete native reports and calculate supplementary task accuracy."""
    run_path = exp / f'{run_name}.json'
    run = json.loads(run_path.read_text())
    if run['status'] != 'completed':
        raise ValueError('Only a completed run can be summarized')
    if sha256(exp / 'manifest.json') != run['identity']['manifest_sha256']:
        raise ValueError('Manifest changed after evaluation')
    manifest = json.loads((exp / 'manifest.json').read_text())
    if 'humaneval' in run['identity']['subsets'] and not execute_code('assert 2 + 2 == 4'):
        raise RuntimeError('Code metric sandbox preflight failed')
    summary = {
        'run_name': run_name,
        'run_sha256': sha256(run_path),
        'status': 'audited',
        'task_metric_version': SCORING_VERSION,
        'task_metric_sha256': sha256(Path(__file__).with_name('task_metrics.py')),
        'analyzer_sha256': sha256(Path(__file__)),
        'note': 'MCQ accuracy is native. Other task accuracies are independent post-processing, not EvalScope metrics.',
        'subsets': {},
    }
    for item in run['completed_subsets']:
        task = item['subset']
        entry = manifest['subsets'][task]
        path = exp / 'data' / entry['file']
        sidecar_path = exp / 'data' / entry['sidecar']
        if sha256(path) != entry['sha256'] or sha256(sidecar_path) != entry['sidecar_sha256']:
            raise ValueError('Converted data or sidecar changed')
        native = records(path)
        sidecars = records(sidecar_path)
        expected = min(entry['count'], run['identity']['pokemon_limit' if task == 'pokemon' else 'limit'])
        review_paths = sorted((exp / 'runs' / run_name / task / 'reviews').rglob('*.jsonl'))
        scores = {}
        native_values = {}
        for review_path in review_paths:
            for review in records(review_path):
                index = review['index']
                if not isinstance(index, int) or index in scores or not 0 <= index < expected:
                    raise ValueError('Invalid/duplicate/out-of-cohort sample index')
                sidecar = sidecars[index]
                if sidecar['index'] != index or sidecar['metadata']['source_index'] != index:
                    raise ValueError('Source order changed')
                validate_input(review, native[index], sidecar, entry['benchmark'])
                score = review['sample_score']['score']
                if score['status'] != 'success' or score.get('metadata', {}).get('metric_errors'):
                    raise ValueError('Native scoring error')
                for metric, native_value in score['value'].items():
                    native_values.setdefault(metric, []).append(float(native_value))
                if entry['benchmark'] == 'general_mcq':
                    value = score['value']['accuracy']
                else:
                    value = score_response(score['prediction'], sidecar['target'], sidecar['metadata'])['acc']
                if value not in (0, 1):
                    raise ValueError('Expected binary task metric')
                scores[index] = value
        if set(scores) != set(range(expected)):
            raise ValueError('Incomplete sample coverage')
        report = item['reports'][0]
        if report['num'] != expected or report['execution_summary']['succeeded'] != expected:
            raise ValueError('Native report count mismatch')
        summary['subsets'][task] = {
            'benchmark': entry['benchmark'],
            'n': expected,
            'correct': int(sum(scores.values())),
            'task_accuracy': sum(scores.values()) / expected,
            'task_metric_origin': 'native_general_mcq'
            if entry['benchmark'] == 'general_mcq'
            else 'independent_postprocessing',
            'scores_by_source_index': {str(k): scores[k] for k in sorted(scores)},
            'native_metrics_mean': {key: sum(values) / len(values) for key, values in native_values.items()},
            'native_report_metrics': report.get('metrics'),
            'execution_summary': report['execution_summary'],
            'perf_metrics': report.get('perf_metrics'),
            'review_sha256': {str(p.relative_to(exp)): sha256(p) for p in review_paths},
            'audit': 'all source indices, native targets, prompts/options and image hashes verified',
        }
    return summary


def main() -> None:
    """Write a separate task report without changing any native output files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exp', type=Path, required=True)
    parser.add_argument('--run-name', required=True)
    args = parser.parse_args()
    result = analyze(args.exp, args.run_name)
    output = args.exp / f'{args.run_name}-task-analysis.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for task, item in result['subsets'].items():
        print(task, item['correct'], '/', item['n'], item['task_metric_origin'])


if __name__ == '__main__':
    main()
