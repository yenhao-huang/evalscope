"""Reject comparisons with changed manifests or mismatched sample cohorts."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/custom_datasets'))
from compare_results import compare, paired_summary
from convert_all import sha256


def test_paired_cohort_required() -> None:
    with pytest.raises(ValueError):
        paired_summary({0: 1}, {1: 1})
    result = paired_summary({0: 1, 1: 0}, {0: 1, 1: 0})
    assert result['paired_bootstrap_95_interval'] == [0, 0]
    assert result['within_tolerance']


def test_comparison_rejects_changed_evidence(tmp_path: Path) -> None:
    manifest = tmp_path / 'manifest.json'
    manifest.write_text('{}')
    identity = dict.fromkeys(('temperature', 'seed', 'max_tokens', 'runner_sha256', 'framework_tree'), 'same')
    identity['manifest_sha256'] = sha256(manifest)
    for name in ('local', 'remote'):
        run = tmp_path / f'{name}.json'
        run.write_text(json.dumps({'status': 'completed', 'identity': identity}))
        review = tmp_path / f'{name}-review.jsonl'
        review.write_text('{}\n')
        audit = {'status': 'audited', 'run_sha256': sha256(run), 'task_metric_sha256': 'same',
                 'analyzer_sha256': 'same', 'task_metric_version': 'same', 'subsets': {'pokemon': {
                     'benchmark': 'general_vqa', 'scores_by_source_index': {'0': 1, '1': 0},
                     'review_sha256': {review.name: sha256(review)}, 'task_metric_origin': 'independent_postprocessing',
                     'perf_metrics': {}}}}
        (tmp_path / f'{name}-task-analysis.json').write_text(json.dumps(audit))
    assert compare(tmp_path, 'local', 'remote', 'pokemon')['n'] == 2
    (tmp_path / 'remote-review.jsonl').write_text('changed')
    with pytest.raises(ValueError, match='review changed'):
        compare(tmp_path, 'local', 'remote', 'pokemon')
    manifest.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='Manifest changed'):
        compare(tmp_path, 'local', 'remote', 'pokemon')
